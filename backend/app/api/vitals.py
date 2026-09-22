"""Bedside observations, the NEWS2 preview, the ward board and its live event stream."""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import DB, policy_for
from app.audit.service import audit
from app.auth.access import AccessPolicy
from app.auth.dependencies import get_current_user, require
from app.auth.rbac import Perm
from app.core.config import get_settings
from app.core.errors import PermissionDeniedError, ServiceUnavailableError
from app.db.session import get_session_factory
from app.models import User
from app.schemas.vitals import News2Out, VitalSignsIn, VitalSignsOut, WardBoardOut
from app.services import vitals as service
from app.services.events import hub
from app.services.news2 import Observations

logger = logging.getLogger("careflow.vitals")
router = APIRouter(tags=["vitals"])
Clinical = Depends(require(Perm.PATIENTS_READ_CLINICAL))
KEEPALIVE_SECONDS = 15
ACCESS_REFRESH_SECONDS = 60


@router.post("/patients/{patient_id}/vitals", response_model=VitalSignsOut, status_code=201)
def record_vitals(patient_id: int, body: VitalSignsIn, db: DB,
                  user: User = Depends(require(Perm.CLINICAL_WRITE))) -> VitalSignsOut:
    """Record one set of observations. NEWS2 is computed here, never taken from the client."""
    patient = policy_for(db, user).get_patient(patient_id, clinical=True)
    return service.record(db, user, patient, body)


@router.get("/patients/{patient_id}/vitals", response_model=list[VitalSignsOut])
def list_vitals(patient_id: int, db: DB, user: User = Clinical, hours: int = Query(72, ge=1, le=24 * 30),
                limit: int = Query(200, ge=1, le=500)) -> list[VitalSignsOut]:
    patient = policy_for(db, user).get_patient(patient_id, clinical=True)
    audit("vitals.read", user=user, resource_type="patient", resource_id=patient.id, patient_id=patient.id)
    return service.history(db, patient, hours=hours, limit=limit)


@router.post("/vitals/score", response_model=News2Out)
def preview_score(body: VitalSignsIn, db: DB, user: User = Clinical, patient_id: int | None = None) -> News2Out:
    """Score a set of observations without saving it, so the form shows exactly what the server would store.

    With a patient, the answer also says whether the chart applies to them (it is not validated under 16).
    """
    patient = policy_for(db, user).get_patient(patient_id, clinical=True) if patient_id else None
    return service.news2_out(Observations(
        respiratory_rate=body.respiratory_rate, spo2=body.spo2, on_oxygen=body.on_oxygen,
        systolic_bp=body.systolic_bp, heart_rate=body.heart_rate, consciousness=body.consciousness,
        temperature=body.temperature, spo2_scale=body.spo2_scale),
        age=service.age_of(patient) if patient else None)


@router.get("/ward/board", response_model=WardBoardOut)
def ward_board(db: DB, user: User = Clinical) -> WardBoardOut:
    """Current inpatients the caller may see, worst NEWS2 first."""
    board = service.board(db, policy_for(db, user))
    audit("ward.board", user=user, details={"inpatients": board.counts["inpatients"]})
    return board


def _viewer(request: Request) -> tuple[int, set[int]]:
    """Authenticate the stream and snapshot which patients this viewer may see (its own short session)."""
    with get_session_factory()() as db:
        user = get_current_user(request, db)
        if Perm.PATIENTS_READ_CLINICAL.value not in user.permission_codes:
            raise PermissionDeniedError("Your role cannot watch the ward board")
        return user.id, set(db.scalars(AccessPolicy(db, user).clinical_patient_ids()))


@router.get("/vitals/stream", include_in_schema=False)
async def stream(request: Request) -> StreamingResponse:
    """Server-sent events: one line per new observation, filtered to the patients this viewer may see.

    The events carry ids and the score only; the board itself is refetched through the normal authorized
    endpoint. The access snapshot is refreshed periodically, so a care assignment removed during a long-lived
    stream stops its events.
    """
    user_id, allowed = await run_in_threadpool(_viewer, request)
    subscriber = hub.subscribe()
    if subscriber is None:
        raise ServiceUnavailableError("Too many live connections right now; the board will refresh on its own")

    # A stream ends by itself after a while and the browser reconnects, so a forgotten tab cannot hold a
    # connection open forever.
    deadline = time.monotonic() + get_settings().stream_max_seconds

    async def events():
        refreshed = time.monotonic()
        try:
            yield ": connected\n\n"
            while time.monotonic() < deadline and not await request.is_disconnected():
                try:
                    wait = min(KEEPALIVE_SECONDS, max(0.05, deadline - time.monotonic()))
                    event = await asyncio.wait_for(subscriber.queue.get(), timeout=wait)
                except TimeoutError:
                    yield ": keep-alive\n\n"  # keeps proxies from closing an idle stream
                else:
                    if event.get("patient_id") in allowed:
                        yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                if time.monotonic() - refreshed > ACCESS_REFRESH_SECONDS:
                    _, refreshed_allowed = await run_in_threadpool(_viewer, request)
                    allowed.clear()
                    allowed.update(refreshed_allowed)
                    refreshed = time.monotonic()
        except asyncio.CancelledError:  # the client went away
            raise
        finally:
            hub.unsubscribe(subscriber)
            logger.info("ward stream closed", extra={"fields": {"user_id": user_id, "open": hub.open_streams}})

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
