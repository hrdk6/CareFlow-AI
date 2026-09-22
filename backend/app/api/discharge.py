"""Discharge co-pilot: draft, resume and sign a discharge summary (see app.services.discharge)."""
from fastapi import APIRouter, Depends

from app.api.ai import TooManyQuestions
from app.api.deps import DB
from app.auth.dependencies import require
from app.auth.rbac import Perm
from app.core.config import get_settings
from app.core.ratelimit import ai_query_limiter
from app.models import User
from app.schemas.discharge import DischargeDraftOut, DischargeSignIn, DischargeSignOut
from app.services.discharge import DischargeCopilot

router = APIRouter(tags=["discharge"])
# Discharging is a clinical act: the same permissions as admitting/discharging and writing the record.
Discharging = Depends(require(Perm.ADMISSIONS_WRITE, Perm.CLINICAL_WRITE, Perm.PATIENTS_READ_CLINICAL))


@router.post("/admissions/{admission_id}/discharge-draft", response_model=DischargeDraftOut, status_code=201)
def create_draft(admission_id: int, db: DB, user: User = Discharging) -> DischargeDraftOut:
    """Gather the record, apply the discharge policy, score readmission risk and draft the prose. Writes nothing
    to the medical record."""
    s = get_settings()
    if s.demo_protected:  # a draft costs a language-model call, like a question to the assistant
        limiter, key = ai_query_limiter.get(), f"user:{user.id}"
        if limiter.blocked(key):
            raise TooManyQuestions("You have used the AI features a lot in a short time. Please try again in a few "
                                   "minutes.")
        limiter.hit(key)
    return DischargeCopilot(db, user).draft(admission_id)


@router.get("/admissions/{admission_id}/discharge-draft", response_model=DischargeDraftOut)
def latest_draft(admission_id: int, db: DB, user: User = Discharging) -> DischargeDraftOut:
    """The newest unsigned draft for the admission, so a review can be resumed."""
    return DischargeCopilot(db, user).latest(admission_id)


@router.post("/admissions/{admission_id}/discharge-summary", response_model=DischargeSignOut, status_code=201)
def sign_summary(admission_id: int, body: DischargeSignIn, db: DB, user: User = Discharging) -> DischargeSignOut:
    """Sign the reviewed text into the medical record (and optionally close the admission)."""
    return DischargeCopilot(db, user).sign(admission_id, body)
