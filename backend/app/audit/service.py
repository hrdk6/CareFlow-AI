"""Audit logging for sensitive operations.

Writes use their own short-lived session and commit immediately, so a denied or failed request
(whose main transaction is rolled back) still leaves an audit trail. Details must never contain
clinical free text, query text or document content - identifiers and counts only.
"""
import logging
from typing import Any

from app.core.logging import client_ip_var, request_id_var
from app.db.session import get_session_factory
from app.models.audit import AuditLog

logger = logging.getLogger("careflow.audit")

_FORBIDDEN_DETAIL_KEYS = {"query", "text", "content", "notes", "answer", "password"}


def audit(
    action: str,
    *,
    user: Any = None,
    outcome: str = "success",
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    patient_id: int | None = None,
    details: dict | None = None,
) -> None:
    details = {k: v for k, v in (details or {}).items() if k not in _FORBIDDEN_DETAIL_KEYS}
    entry = AuditLog(
        user_id=getattr(user, "id", None),
        user_role=getattr(getattr(user, "role", None), "name", None),
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        patient_id=patient_id,
        outcome=outcome,
        ip_address=client_ip_var.get(),
        request_id=request_id_var.get(),
        details=details,
    )
    try:
        with get_session_factory()() as session:
            session.add(entry)
            session.commit()
    except Exception:  # audit failure must be visible but must not leak details to the client
        logger.exception("audit write failed", extra={"fields": {"action": action}})
