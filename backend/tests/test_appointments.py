from datetime import UTC, date, datetime, timedelta

import pytest


@pytest.fixture
def rao_id(client, auth):
    return next(d["id"] for d in client.get("/doctors?q=Rao", headers=auth("reception")).json())


@pytest.fixture
def okoro_id(client, auth):
    return next(d["id"] for d in client.get("/doctors?q=Okoro", headers=auth("reception")).json())


def _future_monday() -> date:
    today = datetime.now(UTC).date()
    return today + timedelta(days=(7 - today.weekday()) + 14)


def test_availability_and_booking_lifecycle(client, auth, rao_id, okoro_id, demo_patient):
    day = _future_monday()
    slots = client.get(f"/doctors/{rao_id}/availability?day={day}", headers=auth("reception")).json()
    assert len(slots) >= 3
    start = slots[0]["start"]
    body = {"patient_id": demo_patient.id, "doctor_id": rao_id, "scheduled_start": start, "duration_minutes": 30,
            "reason": "Diabetes review", "appointment_type": "follow_up"}
    created = client.post("/appointments", json=body, headers=auth("reception"))
    assert created.status_code == 201, created.text
    appt = created.json()
    assert appt["status"] == "scheduled" and appt["doctor_name"] == "Dr. Ananya Rao"

    # The slot is gone from availability and cannot be double-booked.
    remaining = client.get(f"/doctors/{rao_id}/availability?day={day}", headers=auth("reception")).json()
    assert start not in {s["start"] for s in remaining}
    other = client.get("/patients?q=P1025", headers=auth("reception")).json()["items"][0]["id"]
    clash = client.post("/appointments", json={**body, "patient_id": other}, headers=auth("reception"))
    assert clash.status_code == 409 and "already has an appointment" in clash.json()["error"]["message"]
    # The same patient cannot be in two places at once.
    patient_clash = client.post("/appointments", json={**body, "doctor_id": okoro_id}, headers=auth("reception"))
    assert patient_clash.status_code == 409

    moved = client.patch(f"/appointments/{appt['id']}", json={"scheduled_start": slots[2]["start"]},
                         headers=auth("reception"))
    assert moved.status_code == 200 and moved.json()["scheduled_start"] == slots[2]["start"]
    cancelled = client.post(f"/appointments/{appt['id']}/cancel", json={"reason": "Patient request"},
                            headers=auth("reception"))
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(f"/appointments/{appt['id']}/cancel", json={"reason": "again"},
                       headers=auth("reception")).status_code == 422
    assert client.patch(f"/appointments/{appt['id']}", json={"status": "completed"},
                        headers=auth("reception")).status_code == 422


def test_booking_outside_availability_or_in_past_is_rejected(client, auth, rao_id, demo_patient):
    night = datetime.combine(_future_monday(), datetime.min.time(), tzinfo=UTC).replace(hour=3)
    body = {"patient_id": demo_patient.id, "doctor_id": rao_id, "scheduled_start": night.isoformat(),
            "reason": "Night visit"}
    r = client.post("/appointments", json=body, headers=auth("reception"))
    assert r.status_code == 422 and "not available" in r.json()["error"]["message"]
    past = (datetime.now(UTC) - timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    assert client.post("/appointments", json={**body, "scheduled_start": past.isoformat()},
                       headers=auth("reception")).status_code == 422


def test_appointment_validation(client, auth, rao_id, demo_patient):
    r = client.post("/appointments", headers=auth("reception"), json={
        "patient_id": demo_patient.id, "doctor_id": rao_id, "scheduled_start": "2030-01-07T10:00:00Z",
        "duration_minutes": 500, "reason": "x"})
    assert r.status_code == 422


def test_nurse_cannot_create_appointments(client, auth, rao_id, demo_patient):
    r = client.post("/appointments", headers=auth("nurse"), json={
        "patient_id": demo_patient.id, "doctor_id": rao_id, "scheduled_start": "2030-01-07T10:00:00Z",
        "reason": "Review"})
    assert r.status_code == 403


def test_appointment_list_filters(client, auth, rao_id):
    day0 = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    r = client.get(f"/appointments?doctor_id={rao_id}&date_from={day0.isoformat().replace('+', '%2B')}&limit=100",
                   headers=auth("doctor"))
    assert r.status_code == 200
    assert all(a["doctor_id"] == rao_id for a in r.json()["items"])


# ------------------------------------------------------------------ doctor administration
@pytest.fixture
def neurology_id(client, auth) -> int:
    depts = client.get("/departments", headers=auth("reception")).json()
    return next(d["id"] for d in depts if d["name"] == "Neurology")


def register_doctor(client, auth, neurology_id, role="admin", **overrides):
    body = {"full_name": "Dr. Meera Joshi", "specialty": "Neurology", "department_id": neurology_id} | overrides
    return client.post("/doctors", json=body, headers=auth(role))


def test_admin_can_register_a_doctor_who_is_then_bookable(client, auth, neurology_id):
    r = register_doctor(client, auth, neurology_id)
    assert r.status_code == 201, r.text
    doctor = r.json()
    assert doctor["staff_code"].startswith(f"D{neurology_id}") and doctor["department"] == "Neurology"
    assert doctor["email"].startswith("joshi.") and doctor["is_active"] is True
    assert doctor["availability"]["mon"] == [["09:00", "13:00"], ["14:00", "17:00"]]
    listed = client.get("/doctors?q=Joshi", headers=auth("reception")).json()
    assert [d["id"] for d in listed] == [doctor["id"]]
    assert client.get(f"/doctors/{doctor['id']}/availability?day={_future_monday()}",
                      headers=auth("reception")).json()


@pytest.mark.parametrize("role", ["doctor", "nurse", "reception"])
def test_registering_a_doctor_is_admin_only(client, auth, neurology_id, role):
    assert register_doctor(client, auth, neurology_id, role=role).status_code == 403


@pytest.mark.parametrize(("overrides", "status"), [
    ({"department_id": 9999}, 422),                            # unknown department
    ({"full_name": "X"}, 422),                                 # too short
    ({"availability": {"mon": [["09:00", "08:00"]]}}, 422),    # window ends before it starts
    ({"availability": {"funday": [["09:00", "17:00"]]}}, 422),  # not a weekday
])
def test_doctor_registration_validates_input(client, auth, neurology_id, overrides, status):
    assert register_doctor(client, auth, neurology_id, **overrides).status_code == status


def test_user_account_links_to_a_free_doctor_profile_only(client, auth, neurology_id):
    doctor = register_doctor(client, auth, neurology_id, full_name="Dr. Ravi Kulkarni").json()
    account = {"email": "ravi@careflow.demo", "full_name": "Ravi Kulkarni", "password": "CareFlow-Demo-2026",
               "role": "DOCTOR", "doctor_id": doctor["id"], "department_id": neurology_id}
    assert client.post("/admin/users", json=account, headers=auth("admin")).status_code == 201
    duplicate = account | {"email": "ravi2@careflow.demo"}
    assert client.post("/admin/users", json=duplicate, headers=auth("admin")).status_code == 409
    unknown = account | {"email": "ghost@careflow.demo", "doctor_id": 99999}
    assert client.post("/admin/users", json=unknown, headers=auth("admin")).status_code == 422
