"""Administration: users, roles, care assignments, audit log, AI traces, metrics, model cards, dashboard."""
import json
from datetime import UTC, datetime, timedelta

import numpy as np
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, policy_for
from app.audit.service import audit
from app.auth.dependencies import require
from app.auth.rbac import PERMISSION_DESCRIPTIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS, Perm, RoleName
from app.core.config import REPO_DIR
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import hash_password
from app.ml.registry import get_registry
from app.models import (
    Admission,
    AIQueryTrace,
    Appointment,
    AuditLog,
    CareAssignment,
    Document,
    ModelVersion,
    Patient,
    Role,
    User,
)
from app.schemas.admin import (
    AITraceOut,
    AuditLogOut,
    CareAssignmentIn,
    RoleOut,
    UserAdminOut,
    UserCreate,
    UserUpdate,
)
from app.schemas.common import Page
from app.schemas.ml import ModelCardOut

router = APIRouter(tags=["admin"])
UsersManage = Depends(require(Perm.USERS_MANAGE))


def user_admin_out(u: User) -> UserAdminOut:
    return UserAdminOut(id=u.id, email=u.email, full_name=u.full_name, role=u.role.name, is_active=u.is_active,
                        doctor_id=u.doctor_id, department_id=u.department_id, last_login_at=u.last_login_at)


@router.get("/admin/users", response_model=list[UserAdminOut])
def list_users(db: DB, user: User = UsersManage) -> list[UserAdminOut]:
    return [user_admin_out(u) for u in db.scalars(select(User).order_by(User.id))]


@router.post("/admin/users", response_model=UserAdminOut, status_code=201)
def create_user(body: UserCreate, db: DB, user: User = UsersManage) -> UserAdminOut:
    if db.scalar(select(User.id).where(func.lower(User.email) == body.email.lower())):
        raise ConflictError("A user with this email already exists")
    role = db.scalar(select(Role).where(Role.name == body.role))
    if body.role == "DOCTOR" and body.doctor_id is None:
        raise ValidationFailedError("Doctor accounts must be linked to a doctor profile")
    new = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password),
               role=role, doctor_id=body.doctor_id, department_id=body.department_id)
    db.add(new)
    db.flush()
    audit("user.create", user=user, resource_type="user", resource_id=new.id, details={"role": body.role})
    return user_admin_out(new)


@router.patch("/admin/users/{user_id}", response_model=UserAdminOut)
def update_user(user_id: int, body: UserUpdate, db: DB, user: User = UsersManage) -> UserAdminOut:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found")
    if target.id == user.id and (body.is_active is False or (body.role and body.role != "ADMIN")):
        raise ValidationFailedError("You cannot demote or deactivate your own account")
    if body.role and body.role != target.role.name:
        old = target.role.name
        target.role = db.scalar(select(Role).where(Role.name == body.role))
        audit("permission.role_change", user=user, resource_type="user", resource_id=target.id,
              details={"from": old, "to": body.role})
    if body.is_active is not None and body.is_active != target.is_active:
        target.is_active = body.is_active
        audit("user.activation_change", user=user, resource_type="user", resource_id=target.id,
              details={"is_active": body.is_active})
    if body.department_id is not None:
        target.department_id = body.department_id
    db.flush()
    return user_admin_out(target)


@router.get("/admin/roles", response_model=list[RoleOut])
def list_roles(user: User = UsersManage) -> list[RoleOut]:
    return [RoleOut(name=r.value, description=ROLE_DESCRIPTIONS[r], permissions=sorted(p.value for p in perms))
            for r, perms in ROLE_PERMISSIONS.items()]


@router.get("/admin/permissions")
def list_permissions(user: User = UsersManage) -> list[dict]:
    return [{"code": p.value, "description": d} for p, d in PERMISSION_DESCRIPTIONS.items()]


@router.post("/admin/care-assignments", status_code=201)
def assign_care(body: CareAssignmentIn, db: DB, user: User = UsersManage) -> dict:
    if db.get(Patient, body.patient_id) is None or db.get(User, body.user_id) is None:
        raise NotFoundError("Patient or user not found")
    existing = db.scalar(select(CareAssignment).where(CareAssignment.patient_id == body.patient_id,
                                                      CareAssignment.user_id == body.user_id))
    if existing:
        existing.active, existing.care_role = True, body.care_role
    else:
        existing = CareAssignment(**body.model_dump())
        db.add(existing)
    db.flush()
    audit("permission.care_assignment", user=user, resource_type="care_assignment", resource_id=existing.id,
          patient_id=body.patient_id, details={"assignee": body.user_id, "care_role": body.care_role})
    return {"id": existing.id, "active": True}


@router.delete("/admin/care-assignments/{assignment_id}", status_code=204)
def revoke_care(assignment_id: int, db: DB, user: User = UsersManage) -> Response:
    ca = db.get(CareAssignment, assignment_id)
    if ca is None:
        raise NotFoundError("Assignment not found")
    ca.active = False
    audit("permission.care_revoked", user=user, resource_type="care_assignment", resource_id=ca.id,
          patient_id=ca.patient_id)
    return Response(status_code=204)


@router.get("/admin/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(db: DB, user: User = Depends(require(Perm.AUDIT_READ)), action: str | None = None,
               user_id: int | None = None, patient_id: int | None = None,
               outcome: str | None = Query(None, pattern="^(success|denied|error)$"),
               limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> Page[AuditLogOut]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if patient_id:
        stmt = stmt.where(AuditLog.patient_id == patient_id)
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset))
    return Page(items=[AuditLogOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/admin/ai-traces", response_model=Page[AITraceOut])
def ai_traces(db: DB, user: User = Depends(require(Perm.SYSTEM_OBSERVE)), limit: int = Query(50, ge=1, le=500),
              offset: int = Query(0, ge=0)) -> Page[AITraceOut]:
    total = db.scalar(select(func.count()).select_from(AIQueryTrace))
    rows = db.scalars(select(AIQueryTrace).order_by(AIQueryTrace.created_at.desc()).limit(limit).offset(offset))
    return Page(items=[AITraceOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


def _pct(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    arr = np.asarray(values)
    return {"n": len(values), "p50": round(float(np.percentile(arr, 50)), 1),
            "p95": round(float(np.percentile(arr, 95)), 1), "max": round(float(arr.max()), 1)}


@router.get("/admin/metrics/summary")
def metrics_summary(db: DB, user: User = Depends(require(Perm.SYSTEM_OBSERVE)),
                    hours: int = Query(168, ge=1, le=24 * 90)) -> dict:
    since = datetime.now(UTC) - timedelta(hours=hours)
    traces = db.scalars(select(AIQueryTrace).where(AIQueryTrace.created_at >= since)).all()
    stages: dict[str, list[float]] = {}
    routes: dict[str, int] = {}
    for t in traces:
        routes[t.route] = routes.get(t.route, 0) + 1
        for stage, ms in (t.stage_ms or {}).items():
            stages.setdefault(stage, []).append(ms)
    return {
        "window_hours": hours,
        "ai_queries": len(traces),
        "ai_errors_or_degraded": sum(1 for t in traces if t.status != "ok"),
        "latency_ms": {"total": _pct([t.total_ms for t in traces]), **{k: _pct(v) for k, v in stages.items()}},
        "routes": dict(sorted(routes.items(), key=lambda kv: -kv[1])),
        "routing_methods": {m: sum(1 for t in traces if t.routing_method == m) for m in ("deterministic", "llm")},
        "tokens": {"prompt": sum(t.prompt_tokens or 0 for t in traces),
                   "completion": sum(t.completion_tokens or 0 for t in traces)},
        "avg_retrieved_chunks": round(float(np.mean([len(t.retrieved_chunk_ids) for t in traces])), 2) if traces else 0,
        "documents": dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all()),
        "denied_events": db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.outcome == "denied", AuditLog.occurred_at >= since)),
    }


@router.get("/ml/models", response_model=list[ModelCardOut])
def model_cards(db: DB, user: User = Depends(require(Perm.ML_READ))) -> list[ModelCardOut]:
    registry = get_registry()
    active = registry.active_versions()
    cards = []
    for row in db.scalars(select(ModelVersion).order_by(ModelVersion.model_name, ModelVersion.version)):
        m = registry.metadata(row.model_name, row.version)
        extra = {k: m[k] for k in ("threshold", "risk_bands", "calibration", "prediction_interval", "split",
                                   "selection_metric", "explanation_space", "target") if k in m}
        cards.append(ModelCardOut(model_name=row.model_name, version=row.version, is_active=active.get(row.model_name) == row.version,
                                  task=m["task"], algorithm=m["algorithm"], trained_at=m["trained_at"], dataset=m["dataset"],
                                  features=m["features"], metrics=m["metrics"], candidates=m["candidates"],
                                  global_importance=m["global_importance"], leakage_ablation=m["leakage_ablation"],
                                  limitations=m["limitations"], intended_use=m["intended_use"], extra=extra))
    return cards


def _load_json(path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {"status": "not_run",
                                                              "message": "Run the evaluation script to produce results."}


@router.get("/ml/evaluation/rag")
def rag_evaluation(user: User = Depends(require(Perm.ML_READ))) -> dict:
    return _load_json(REPO_DIR / "rag" / "evaluation" / "results" / "latest.json")


@router.get("/ml/evaluation/similarity")
def similarity_evaluation(user: User = Depends(require(Perm.ML_READ))) -> dict:
    return _load_json(REPO_DIR / "ml" / "evaluation" / "reports" / "similarity_latest.json")


@router.get("/dashboard")
def dashboard(db: DB, user: CurrentUser) -> dict:
    """Role-aware landing page statistics (every figure is scoped by the access policy)."""
    policy = policy_for(db, user)
    visible = policy.accessible_patient_ids()
    now = datetime.now(UTC)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out: dict = {"role": user.role.name,
                 "patients_visible": db.scalar(select(func.count()).select_from(Patient).where(policy.patient_predicate()))}
    if Perm.APPOINTMENTS_READ.value in user.permission_codes:
        appts = db.scalars(select(Appointment).where(Appointment.patient_id.in_(visible),
                                                     Appointment.scheduled_start >= day0,
                                                     Appointment.scheduled_start < day0 + timedelta(days=1))
                           .order_by(Appointment.scheduled_start)).all()
        if user.doctor_id:
            appts = [a for a in appts if a.doctor_id == user.doctor_id] or appts
        out["appointments_today"] = [{"id": a.id, "time": a.scheduled_start, "patient": a.patient.full_name,
                                      "patient_id": a.patient_id, "mrn": a.patient.mrn, "doctor": a.doctor.full_name,
                                      "reason": a.reason, "status": a.status} for a in appts[:12]]
        out["appointments_today_count"] = len(appts)
    if policy.can_read_clinical:
        clinical = policy.clinical_patient_ids()
        out["inpatients"] = db.scalar(select(func.count()).select_from(Admission).where(
            Admission.status == "admitted", Admission.patient_id.in_(clinical)))
        out["discharges_7d"] = db.scalar(select(func.count()).select_from(Admission).where(
            Admission.discharged_at >= now - timedelta(days=7), Admission.patient_id.in_(clinical)))
        recent = db.execute(select(Patient, Admission).join(Admission, Admission.patient_id == Patient.id)
                            .where(Patient.id.in_(clinical), Admission.discharged_at >= now - timedelta(days=30))
                            .order_by(Admission.discharged_at.desc()).limit(8)).all()
        out["recent_discharges"] = [{"patient_id": p.id, "mrn": p.mrn, "name": p.full_name, "reason": a.reason,
                                     "discharged_at": a.discharged_at, "disposition": a.discharge_disposition}
                                    for p, a in recent]
        census = db.execute(select(Patient, Admission).join(Admission, Admission.patient_id == Patient.id)
                            .where(Patient.id.in_(clinical), Admission.status == "admitted")
                            .order_by(Admission.admitted_at.desc()).limit(10)).all()
        out["census"] = [{"patient_id": p.id, "mrn": p.mrn, "name": p.full_name, "reason": a.reason,
                          "admitted_at": a.admitted_at, "department": a.department.name, "ward": a.ward}
                         for p, a in census]
    if Perm.DOCUMENTS_READ.value in user.permission_codes:
        out["documents_indexed"] = db.scalar(select(func.count()).select_from(Document).where(
            Document.status == "indexed", Document.is_current.is_(True), policy.document_predicate()))
    if Perm.SYSTEM_OBSERVE.value in user.permission_codes:
        out["ai_queries_24h"] = db.scalar(select(func.count()).select_from(AIQueryTrace).where(
            AIQueryTrace.created_at >= now - timedelta(hours=24)))
        out["denied_events_24h"] = db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.outcome == "denied", AuditLog.occurred_at >= now - timedelta(hours=24)))
    out["role_label"] = {RoleName.ADMIN: "Administrator", RoleName.DOCTOR: "Doctor", RoleName.NURSE: "Nurse",
                         RoleName.RECEPTIONIST: "Reception"}[policy.role]
    return out
