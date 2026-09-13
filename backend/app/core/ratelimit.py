"""Small in-memory sliding-window limiter (per process) used for login brute-force protection.

A multi-instance deployment should move this to a shared store (e.g. Redis); documented in docs/security.md.
"""
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._events[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_events

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=15 * 60)


class _AIQueryLimiter:
    """Per-user AI question budget, sized from settings on first use."""

    def __init__(self) -> None:
        self._limiter: SlidingWindowLimiter | None = None

    def get(self) -> SlidingWindowLimiter:
        if self._limiter is None:
            from app.core.config import get_settings

            s = get_settings()
            self._limiter = SlidingWindowLimiter(s.ai_queries_per_window, s.ai_query_window_seconds)
        return self._limiter


ai_query_limiter = _AIQueryLimiter()
