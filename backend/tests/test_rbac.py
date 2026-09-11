"""Role-based and row-level authorization."""
import pytest
from sqlalchemy import select

from app.auth.access import AccessPolicy
from app.auth.rbac import ROLE_PERMISSIONS, Perm, RoleName
from app.models import AuditLog, CareAssignment, Document


def test_permission_matrix_is_least_privilege():
    assert ROLE_PERMISSIONS[RoleName.ADMIN] == set(Perm)
    assert Perm.PATIENTS_READ_CLINICAL not in ROLE_PERMISSIONS[RoleName.RECEPTIONIST]
    assert Perm.ML_READ not in ROLE_PERMISSIONS[RoleName.NURSE]
    assert Perm.PRESCRIPTIONS_WRITE not in ROLE_PERMISSIONS[RoleName.NURSE]
    assert Perm.USERS_MANAGE not in ROLE_PERMISSIONS[RoleName.DOCTOR]


def test_doctor_cannot_open_patient_outside_care_relationship(client, auth, restricted_patient, db):
    r = client.get(f"/patients/{restricted_patient.id}", headers=auth("doctor"))
    assert r.status_code == 404  # same response as a non-existent id: no enumeration
    for sub in ("records", "timeline", "risk", "similar", "labs"):
        assert client.get(f"/patients/{restricted_patient.id}/{sub}", headers=auth("doctor")).status_code == 404
    denied = db.scalar(select(AuditLog).where(AuditLog.action == "patient.access_denied",
                                              AuditLog.patient_id == restricted_patient.id))
    assert denied is not None and denied.outcome == "denied"


def test_patient_list_is_scoped(client, auth, restricted_patient):
    ids = {p["id"] for p in client.get("/patients?limit=200", headers=auth("doctor")).json()["items"]}
    assert restricted_patient.id not in ids
    admin_total = client.get("/patients?limit=1", headers=auth("admin")).json()["total"]
    doctor_total = client.get("/patients?limit=1", headers=auth("doctor")).json()["total"]
    assert admin_total > doctor_total > 0


def test_nurse_only_sees_assigned_patients(client, auth, db, users):
    assigned = set(db.scalars(select(CareAssignment.patient_id).where(CareAssignment.user_id == users["nurse"].id)))
    listed = {p["id"] for p in client.get("/patients?limit=200", headers=auth("nurse")).json()["items"]}
    assert listed == assigned and len(assigned) > 0
    other = client.get("/patients?limit=200", headers=auth("admin")).json()["items"]
    unassigned = next(p["id"] for p in other if p["id"] not in assigned)
    assert client.get(f"/patients/{unassigned}", headers=auth("nurse")).status_code == 404


def test_nurse_has_no_ml_access(client, auth, demo_patient):
    assert client.get(f"/patients/{demo_patient.id}/risk", headers=auth("nurse")).status_code == 403


def test_receptionist_sees_demographics_but_not_clinical_data(client, auth, demo_patient):
    r = client.get(f"/patients/{demo_patient.id}", headers=auth("reception"))
    assert r.status_code == 200
    body = r.json()
    assert body["mrn"] == "P1024" and "allergies" not in body and "active_diagnoses" not in body
    for sub in ("records", "timeline", "prescriptions", "labs", "risk", "length-of-stay", "similar"):
        assert client.get(f"/patients/{demo_patient.id}/{sub}", headers=auth("reception")).status_code == 403


def test_admin_endpoints_require_admin(client, auth):
    for role in ("doctor", "nurse", "reception"):
        assert client.get("/admin/users", headers=auth(role)).status_code == 403
        assert client.get("/admin/audit-logs", headers=auth(role)).status_code == 403
    assert client.get("/admin/users", headers=auth("admin")).status_code == 200


@pytest.mark.parametrize("role,expected_scopes", [("reception", {"all_staff"}), ("nurse", {"all_staff", "clinical"}),
                                                  ("admin", {"all_staff", "clinical", "admin"})])
def test_document_scope_filtering(client, auth, role, expected_scopes):
    docs = client.get("/documents?limit=200", headers=auth(role)).json()["items"]
    assert docs and {d["access_scope"] for d in docs} <= expected_scopes


def test_patient_specific_document_follows_patient_access(db, users):
    letter = db.scalar(select(Document).where(Document.doc_key.like("cardiology-letter-%")))
    rao, mensah = AccessPolicy(db, users["doctor"]), AccessPolicy(db, users["cardio"])
    visible_rao = db.scalar(select(Document.id).where(Document.id == letter.id, rao.document_predicate()))
    visible_mensah = db.scalar(select(Document.id).where(Document.id == letter.id, mensah.document_predicate()))
    assert visible_rao is None and visible_mensah == letter.id


def test_role_change_is_audited(client, auth, db, users):
    target = users["nurse"].id
    assert client.patch(f"/admin/users/{target}", json={"role": "RECEPTIONIST"}, headers=auth("admin")).status_code == 200
    assert client.patch(f"/admin/users/{target}", json={"role": "NURSE"}, headers=auth("admin")).status_code == 200
    changes = db.scalars(select(AuditLog).where(AuditLog.action == "permission.role_change",
                                                AuditLog.resource_id == str(target))).all()
    assert len(changes) >= 2


def test_audit_log_contains_no_query_text(client, auth, demo_patient, db):
    secret_phrase = "zebra-unicorn-canary"
    client.post("/ai/query", json={"query": f"Summarize {secret_phrase} history", "patient_id": demo_patient.id},
                headers=auth("doctor"))
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "ai.query")).all()
    assert rows and all(secret_phrase not in str(r.details) for r in rows)
