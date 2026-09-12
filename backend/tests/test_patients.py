from sqlalchemy import select

from app.models import AuditLog


def test_synthetic_indian_mobile_numbers():
    import re

    from app.seed.generator import in_mobile

    for a, b in [(200, 1000), (999, 9999), (345, 6789)]:
        number = in_mobile(a, b)
        assert re.fullmatch(r"\+91 [6-9]\d{4} \d{5}", number), number
    assert in_mobile(345, 6789) == in_mobile(345, 6789)  # deterministic: no extra random draws


def test_seeded_patients_use_indian_phone_format(db):
    import re

    from app.models import Patient

    phones = db.scalars(select(Patient.phone).limit(50)).all()
    assert phones and all(re.fullmatch(r"\+91 [6-9]\d{4} \d{5}", p) for p in phones)


def test_search_by_mrn_and_name(client, auth):
    r = client.get("/patients?q=P1024", headers=auth("doctor"))
    assert r.status_code == 200 and r.json()["items"][0]["full_name"] == "Sunita Deshpande"
    r = client.get("/patients?q=sunita%20deshpande", headers=auth("doctor"))
    assert any(p["mrn"] == "P1024" for p in r.json()["items"])


def test_pagination(client, auth):
    first = client.get("/patients?limit=5&offset=0", headers=auth("admin")).json()
    second = client.get("/patients?limit=5&offset=5", headers=auth("admin")).json()
    assert len(first["items"]) == 5 and first["total"] >= 60
    assert not {p["id"] for p in first["items"]} & {p["id"] for p in second["items"]}


def test_clinical_view_for_doctor(client, auth, demo_patient):
    body = client.get(f"/patients/{demo_patient.id}", headers=auth("doctor")).json()
    assert any(d["icd10_code"] == "E11.9" for d in body["active_diagnoses"])
    assert any(m["medication"] == "insulin glargine" for m in body["current_medications"])
    assert any(m["name"] == "Dr. Ananya Rao" for m in body["care_team"])
    assert {"substance": "Penicillin", "reaction": "Rash", "severity": "moderate"} in body["allergies"]


def test_receptionist_registers_patient_with_new_mrn(client, auth, db):
    r = client.post("/patients", headers=auth("reception"), json={
        "first_name": "Test", "last_name": "Registration", "date_of_birth": "1985-04-02", "sex": "M",
        "phone": "+91 98765 43210", "allergies": [{"substance": "Latex", "reaction": "Rash", "severity": "mild"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mrn"].startswith("P") and body["is_synthetic"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "patient.create",
                                            AuditLog.patient_id == body["id"])) is not None


def test_doctor_cannot_register_patients(client, auth):
    r = client.post("/patients", headers=auth("doctor"),
                    json={"first_name": "A", "last_name": "B", "date_of_birth": "1985-04-02", "sex": "F"})
    assert r.status_code == 403


def test_validation_errors_do_not_echo_input(client, auth):
    r = client.post("/patients", headers=auth("reception"), json={
        "first_name": "", "last_name": "SecretSurname", "date_of_birth": "2999-01-01", "sex": "Q",
        "email": "not-an-email"})
    assert r.status_code == 422
    body = r.json()
    fields = {i["field"] for i in body["error"]["details"]["issues"]}
    assert {"first_name", "date_of_birth", "sex", "email"} <= fields
    assert "SecretSurname" not in r.text and "2999" not in r.text


def test_update_patient_contact_details(client, auth, demo_patient):
    r = client.patch(f"/patients/{demo_patient.id}", headers=auth("reception"),
                     json={"emergency_contact_phone": "+91 98765 43211"})
    assert r.status_code == 200 and r.json()["emergency_contact_phone"] == "+91 98765 43211"


def test_timeline_is_chronological_and_linked(client, auth, demo_patient):
    events = client.get(f"/patients/{demo_patient.id}/timeline?months=36", headers=auth("doctor")).json()["events"]
    times = [e["at"] for e in events]
    assert times == sorted(times, reverse=True)
    categories = {e["category"] for e in events}
    assert {"admission", "discharge", "medication_change", "diagnosis", "lab_abnormal"} <= categories
    change = next(e for e in events if e["category"] == "medication_change" and "metformin" in e["title"])
    assert change["source_type"] == "prescription" and change["source_id"] > 0
    assert "eGFR" in (change["detail"] or "") or "HbA1c" in (change["detail"] or "")


def test_patient_subresources(client, auth, demo_patient):
    pid = demo_patient.id
    assert len(client.get(f"/patients/{pid}/admissions", headers=auth("doctor")).json()) == 4
    labs = client.get(f"/patients/{pid}/labs?test_code=HBA1C", headers=auth("doctor")).json()
    assert labs and all(lab["test_code"] == "HBA1C" for lab in labs)
    rx = client.get(f"/patients/{pid}/prescriptions", headers=auth("doctor")).json()
    assert any(p["status"] == "discontinued" for p in rx)
    docs = client.get(f"/patients/{pid}/documents", headers=auth("doctor")).json()
    assert any(d["doc_type"] == "report" for d in docs)
