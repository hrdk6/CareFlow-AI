"""In-process fan-out of ward events to open server-sent-event streams.

A recorded observation is written by a worker thread; the streams are async. Each subscriber owns a bounded
queue and its event loop, and the writer hands events over with `call_soon_threadsafe`. Events carry ids and
the score only - never a name or a value - and each stream drops the ones for patients its viewer may not see,
so the stream can never widen what someone is allowed to know.

One process only: with several instances behind a load balancer this becomes a shared bus (Redis pub/sub or
Postgres LISTEN/NOTIFY). Documented in docs/architecture.md.
"""
import asyncio
import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger("careflow.events")
MAX_SUBSCRIBERS = 64  # a small host should refuse a 65th stream rather than fall over
QUEUE_SIZE = 50


@dataclass(eq=False)
class Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE))


class EventHub:
    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()
        self._lock = threading.Lock()

    @property
    def open_streams(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def subscribe(self) -> Subscriber | None:
        """None when the process is already serving as many streams as it will."""
        subscriber = Subscriber(loop=asyncio.get_running_loop())
        with self._lock:
            if len(self._subscribers) >= MAX_SUBSCRIBERS:
                return None
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(_offer, subscriber.queue, event)
            except RuntimeError:  # the loop closed while we were handing the event over
                self.unsubscribe(subscriber)


def _offer(queue: asyncio.Queue, event: dict) -> None:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.warning("event stream is not keeping up; dropping an event")  # the client reloads anyway


hub = EventHub()
