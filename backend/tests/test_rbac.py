"""Role-based and row-level authorization."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth.access import AccessPolicy
from app.auth.rbac import ROLE_PERMISSIONS, Perm, RoleName
from app.models import AuditLog, CareAssignment, Document


def test_permission_matrix_is_least_privilege():
    admin = ROLE_PERMISSIONS[RoleName.ADMIN]
    assert {Perm.USERS_MANAGE, Perm.AUDIT_READ, Perm.SYSTEM_OBSERVE, Perm.DOCUMENTS_MANAGE} <= admin
    # Administration is not clinical practice: oversight is read-only on the record.
    assert Perm.PATIENTS_READ_CLINICAL in admin
    assert not ({Perm.CLINICAL_WRITE, Perm.PRESCRIPTIONS_WRITE, Perm.ADMISSIONS_WRITE} & admin)
    assert Perm.PATIENTS_READ_CLINICAL not in ROLE_PERMISSIONS[RoleName.RECEPTIONIST]
    assert Perm.ML_READ not in ROLE_PERMISSIONS[RoleName.NURSE]
    assert Perm.PRESCRIPTIONS_WRITE not in ROLE_PERMISSIONS[RoleName.NURSE]
    assert Perm.USERS_MANAGE not in ROLE_PERMISSIONS[RoleName.DOCTOR]


def test_stored_grants_are_reconciled_with_the_policy_in_code(db):
    """Grants live in the database but the policy is code: a stale database must be corrected at startup."""
    from app.auth.provisioning import sync_role_permissions
    from app.models import Permission, Role

    admin = db.scalar(select(Role).where(Role.name == "ADMIN"))
    stray = db.scalar(select(Permission).where(Permission.code == Perm.CLINICAL_WRITE.value))
    admin.permissions.append(stray)  # as if seeded under the older policy
    db.flush()
    assert Perm.CLINICAL_WRITE.value in {p.code for p in admin.permissions}

    changes = sync_role_permissions(db)
    assert f"ADMIN:{Perm.CLINICAL_WRITE.value}" in changes["revoked"]
    assert Perm.CLINICAL_WRITE.value not in {p.code for p in admin.permissions}
    assert sync_role_permissions(db) == {"granted": [], "revoked": []}  # idempotent
    db.rollback()


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


# ------------------------------------------------------------------ role invariants
def test_administrators_cannot_author_clinical_data(client, auth, demo_patient):
    """Oversight roles read the record; they do not write in it."""
    record = {"patient_id": demo_patient.id, "record_type": "consultation", "visit_date": "2026-01-05",
              "chief_complaint": "Review", "assessment": "Stable", "plan": "Continue"}
    assert client.post("/records", json=record, headers=auth("admin")).status_code == 403
    assert client.post("/labs", json={"patient_id": demo_patient.id, "test_code": "HBA1C", "value": 7.0,
                                      "collected_at": "2026-01-05T09:00:00Z"}, headers=auth("admin")).status_code == 403
    assert client.post("/admissions", json={"patient_id": demo_patient.id, "department_id": 1,
                                            "attending_doctor_id": 1, "admission_type": "elective",
                                            "reason": "x"}, headers=auth("admin")).status_code == 403
    assert client.get(f"/patients/{demo_patient.id}", headers=auth("admin")).status_code == 200


def test_only_clinical_staff_may_change_allergies(client, auth, demo_patient):
    """Registration roles capture contact details; allergies drive the prescribing safety check."""
    allergy = {"allergies": [{"substance": "Latex", "reaction": "rash", "severity": "mild"}]}
    denied = client.patch(f"/patients/{demo_patient.id}", json=allergy, headers=auth("reception"))
    assert denied.status_code == 403 and "allergies" in denied.json()["error"]["message"]
    assert client.patch(f"/patients/{demo_patient.id}", json={"phone": "+91 98765 43210"},
                        headers=auth("reception")).status_code == 200
    assert client.patch(f"/patients/{demo_patient.id}", json=allergy, headers=auth("doctor")).status_code == 200
    wrong_way = client.patch(f"/patients/{demo_patient.id}", json={"phone": "+91 90000 00000"}, headers=auth("doctor"))
    assert wrong_way.status_code == 403 and "registration details" in wrong_way.json()["error"]["message"]


def test_cancelled_appointment_does_not_leave_the_doctor_with_access(client, auth, db, restricted_patient):
    """Booking grants a care relationship; cancelling it must take that access away again."""
    rao = next(d["id"] for d in client.get("/doctors?q=Rao", headers=auth("reception")).json())
    day = datetime.now(UTC).date() + timedelta(days=(7 - datetime.now(UTC).date().weekday()) + 21)
    slots = client.get(f"/doctors/{rao}/availability?day={day}", headers=auth("reception")).json()
    booked = client.post("/appointments", json={"patient_id": restricted_patient.id, "doctor_id": rao,
                                                "scheduled_start": slots[0]["start"], "duration_minutes": 30,
                                                "reason": "Referral"}, headers=auth("reception"))
    assert booked.status_code == 201, booked.text
    db.expire_all()
    assert client.get(f"/patients/{restricted_patient.id}", headers=auth("doctor")).status_code == 200
    client.post(f"/appointments/{booked.json()['id']}/cancel", json={"reason": "Patient request"},
                headers=auth("reception"))
    db.expire_all()
    assert client.get(f"/patients/{restricted_patient.id}", headers=auth("doctor")).status_code == 404


def test_role_change_keeps_the_doctor_profile_invariant(client, auth, db, users):
    """A DOCTOR account must act as a clinician; a demoted one must stop authoring as that clinician."""
    nurse_id = users["nurse"].id
    free_doctor = client.post("/doctors", json={"full_name": "Dr. Nina Kapoor", "specialty": "Cardiology",
                                                "department_id": 2}, headers=auth("admin")).json()
    no_profile = client.patch(f"/admin/users/{nurse_id}", json={"role": "DOCTOR"}, headers=auth("admin"))
    assert no_profile.status_code == 422 and "doctor profile" in no_profile.json()["error"]["message"]
    taken = client.patch(f"/admin/users/{nurse_id}", json={"role": "DOCTOR", "doctor_id": users["doctor"].doctor_id},
                         headers=auth("admin"))
    assert taken.status_code == 409
    promoted = client.patch(f"/admin/users/{nurse_id}", json={"role": "DOCTOR", "doctor_id": free_doctor["id"]},
                            headers=auth("admin"))
    assert promoted.status_code == 200 and promoted.json()["doctor_id"] == free_doctor["id"]
    assert promoted.json()["department_id"] == 2  # derived from the profile, not entered separately
    demoted = client.patch(f"/admin/users/{nurse_id}", json={"role": "NURSE"}, headers=auth("admin"))
    assert demoted.status_code == 200 and demoted.json()["doctor_id"] is None  # link cleared, not left stale
    assert demoted.json()["department_id"] is None


def test_care_team_membership_is_limited_to_clinical_roles(client, auth, users, demo_patient):
    def assign(role_key: str, care_role: str):
        return client.post("/admin/care-assignments", headers=auth("admin"),
                           json={"patient_id": demo_patient.id, "user_id": users[role_key].id, "care_role": care_role})

    denied = assign("reception", "nurse")
    assert denied.status_code == 422 and "clinical staff" in denied.json()["error"]["message"]
    assert assign("nurse", "attending").status_code == 422  # a nurse is not an attending clinician
    assert assign("nurse", "nurse").status_code == 201
    assert assign("doctor", "attending").status_code == 201

    listed = client.get(f"/admin/care-assignments?patient_id={demo_patient.id}", headers=auth("admin"))
    assert listed.status_code == 200
    team = {row["user_id"]: row for row in listed.json()}
    assert team[users["nurse"].id]["care_role"] == "nurse" and team[users["nurse"].id]["id"]
    assert client.get(f"/admin/care-assignments?patient_id={demo_patient.id}",
                      headers=auth("doctor")).status_code == 403
    revoked = client.delete(f"/admin/care-assignments/{team[users['nurse'].id]['id']}", headers=auth("admin"))
    assert revoked.status_code == 204
    remaining = {row["user_id"] for row in client.get(f"/admin/care-assignments?patient_id={demo_patient.id}",
                                                      headers=auth("admin")).json()}
    assert users["nurse"].id not in remaining


def test_a_doctors_department_follows_the_profile(client, auth, db):
    """The department decides which patients a doctor sees, so it has exactly one source: the profile."""
    profile = client.post("/doctors", json={"full_name": "Dr. Ishan Verma", "specialty": "Dermatology",
                                            "department_id": 6}, headers=auth("admin")).json()
    account = client.post("/admin/users", headers=auth("admin"),
                          json={"email": "ishan@careflow.demo", "full_name": "Ishan Verma",
                                "password": "CareFlow-Demo-2026", "role": "DOCTOR", "doctor_id": profile["id"]})
    assert account.status_code == 201 and account.json()["department_id"] == 6

    transferred = client.patch(f"/doctors/{profile['id']}", json={"department_id": 3}, headers=auth("admin"))
    assert transferred.status_code == 200 and transferred.json()["department"] == "Neurology"
    db.expire_all()
    moved = next(u for u in client.get("/admin/users", headers=auth("admin")).json()
                 if u["id"] == account.json()["id"])
    assert moved["department_id"] == 3  # access moved with the clinician
