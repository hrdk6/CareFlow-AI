from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.auth.access import AccessPolicy
from app.models import Admission, AuditLog, Medication, Patient


@pytest.fixture
def writable_patient(db, users):
    """A Rao-visible, nurse-assigned patient other than the demo patient (keeps P1024's history stable)."""
    from app.models import CareAssignment

    nurse_patients = select(CareAssignment.patient_id).where(CareAssignment.user_id == users["nurse"].id)
    rao = AccessPolicy(db, users["doctor"]).accessible_patient_ids()
    return db.scalar(select(Patient).where(Patient.id.in_(nurse_patients), Patient.id.in_(rao),
                                           Patient.mrn != "P1024").order_by(Patient.id).limit(1))


def _med(db, name):
    return db.scalar(select(Medication.id).where(Medication.name == name))


def test_doctor_and_nurse_can_write_records_for_their_patients(client, auth, writable_patient, restricted_patient):
    body = {"patient_id": writable_patient.id, "visit_date": str(date.today()), "record_type": "progress_note",
            "chief_complaint": "Ward review", "notes": "Stable overnight."}
    r = client.post("/records", json=body, headers=auth("doctor"))
    assert r.status_code == 201 and r.json()["doctor_name"] == "Dr. Ananya Rao"
    assert client.post("/records", json=body, headers=auth("nurse")).status_code == 201
    assert client.post("/records", json={**body, "patient_id": restricted_patient.id},
                       headers=auth("nurse")).status_code == 404
    assert client.post("/records", json=body, headers=auth("reception")).status_code == 403


def test_prescription_lifecycle_and_safety_checks(client, auth, db, writable_patient, demo_patient):
    liraglutide = _med(db, "liraglutide")
    body = {"patient_id": writable_patient.id, "medication_id": liraglutide, "dosage": "0.6 mg",
            "frequency": "once daily", "start_date": str(date.today()), "duration_days": 30}
    created = client.post("/prescriptions", json=body, headers=auth("doctor"))
    assert created.status_code == 201, created.text
    rx = created.json()
    assert rx["end_date"] is not None and rx["duration_days"] == 30
    assert client.post("/prescriptions", json=body, headers=auth("doctor")).status_code == 409  # duplicate active
    assert client.post("/prescriptions", json=body, headers=auth("nurse")).status_code == 403
    stopped = client.post(f"/prescriptions/{rx['id']}/discontinue", json={"reason": "Nausea"}, headers=auth("doctor"))
    assert stopped.json()["status"] == "discontinued"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "prescription.discontinue",
                                            AuditLog.resource_id == str(rx["id"]))) is not None
    # Documented penicillin allergy blocks a beta-lactam order for the demo patient.
    allergy = client.post("/prescriptions", headers=auth("doctor"), json={
        "patient_id": demo_patient.id, "medication_id": _med(db, "ceftriaxone"), "dosage": "1 g",
        "frequency": "once daily", "start_date": str(date.today())})
    assert allergy.status_code == 409 and "allergy" in allergy.json()["error"]["message"].lower()


def test_lab_results_are_flagged_from_reference_ranges(client, auth, writable_patient):
    now = datetime.now(UTC).isoformat()
    critical = client.post("/labs", headers=auth("nurse"), json={
        "patient_id": writable_patient.id, "test_code": "glu", "value": 452, "collected_at": now})
    assert critical.status_code == 201 and critical.json()["flag"] == "critical"
    normal = client.post("/labs", headers=auth("nurse"), json={
        "patient_id": writable_patient.id, "test_code": "K", "value": 4.2, "collected_at": now})
    assert normal.json()["flag"] == "normal" and normal.json()["unit"] == "mmol/L"
    assert client.post("/labs", headers=auth("nurse"), json={
        "patient_id": writable_patient.id, "test_code": "ZZZ", "value": 1, "collected_at": now}).status_code == 422


def test_admit_and_discharge(client, auth, db, users):
    policy = AccessPolicy(db, users["doctor"])
    candidate = db.scalar(select(Patient).where(Patient.id.in_(policy.accessible_patient_ids()),
                                                Patient.status == "active", Patient.mrn != "P1024",
                                                ~Patient.id.in_(select(Admission.patient_id).where(
                                                    Admission.status == "admitted"))).limit(1))
    gm = next(d["id"] for d in client.get("/departments", headers=auth("doctor")).json() if d["code"] == "GM")
    body = {"patient_id": candidate.id, "department_id": gm, "attending_doctor_id": users["doctor"].doctor_id,
            "admission_type": "emergency", "admission_source": "emergency_room", "reason": "Chest infection"}
    adm = client.post("/admissions", json=body, headers=auth("doctor"))
    assert adm.status_code == 201 and adm.json()["status"] == "admitted"
    assert client.post("/admissions", json=body, headers=auth("doctor")).status_code == 409
    out = client.post(f"/admissions/{adm.json()['id']}/discharge", json={"discharge_disposition": "home"},
                      headers=auth("doctor"))
    assert out.status_code == 200 and out.json()["discharged_at"] is not None


def test_cross_patient_lists_are_scoped(client, auth, restricted_patient):
    for path in ("/records?limit=200", "/prescriptions?limit=200", "/labs?limit=500"):
        items = client.get(path, headers=auth("doctor")).json()["items"]
        assert items and all(i["patient_id"] != restricted_patient.id for i in items)
    high_alert = client.get("/prescriptions?high_alert=true&limit=200", headers=auth("doctor")).json()["items"]
    assert high_alert and all(i["is_high_alert"] for i in high_alert)
