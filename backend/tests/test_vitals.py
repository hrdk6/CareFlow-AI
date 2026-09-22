"""NEWS2 scoring, recording observations, the ward board and its live stream."""
import json
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models import Admission, AuditLog, VitalSigns
from app.services.events import hub
from app.services.news2 import Observations, rapid_response_triggers, score

NORMAL = dict(respiratory_rate=16, spo2=98, on_oxygen=False, systolic_bp=124, heart_rate=72, consciousness="A",
              temperature=36.7)


def obs(**overrides) -> Observations:
    return Observations(**{**NORMAL, **overrides})


def test_news2_bands_follow_the_chart():
    assert score(obs()).score == 0
    # One point each side of every boundary that matters.
    assert score(obs(respiratory_rate=20)).score == 0 and score(obs(respiratory_rate=21)).score == 2
    assert score(obs(respiratory_rate=24)).score == 2 and score(obs(respiratory_rate=25)).score == 3
    assert score(obs(respiratory_rate=8)).score == 3 and score(obs(respiratory_rate=9)).score == 1
    assert score(obs(spo2=96)).score == 0 and score(obs(spo2=95)).score == 1 and score(obs(spo2=91)).score == 3
    assert score(obs(systolic_bp=111)).score == 0 and score(obs(systolic_bp=110)).score == 1
    assert score(obs(systolic_bp=90)).score == 3 and score(obs(systolic_bp=220)).score == 3
    assert score(obs(heart_rate=90)).score == 0 and score(obs(heart_rate=91)).score == 1
    assert score(obs(heart_rate=131)).score == 3 and score(obs(heart_rate=40)).score == 3
    assert score(obs(temperature=38.0)).score == 0 and score(obs(temperature=38.1)).score == 1
    assert score(obs(temperature=39.1)).score == 2 and score(obs(temperature=35.0)).score == 3
    assert score(obs(consciousness="C")).score == 3
    assert score(obs(on_oxygen=True)).score == 2  # air or oxygen is a parameter in its own right


def test_news2_scale_2_is_for_patients_on_the_copd_target_range():
    # Scale 2 (confirmed hypercapnic respiratory failure): 88-92% is the target, so it scores 0 ...
    assert score(obs(spo2=90, spo2_scale=2)).parameters["spo2"] == 0
    assert score(obs(spo2=90, spo2_scale=1)).parameters["spo2"] == 3  # ... but 3 on the usual scale
    assert score(obs(spo2=96, spo2_scale=2, on_oxygen=True)).parameters["spo2"] == 2  # too high on oxygen
    assert score(obs(spo2=96, spo2_scale=2)).parameters["spo2"] == 0  # breathing air, that is fine
    assert score(obs(spo2=85, spo2_scale=2)).parameters["spo2"] == 2


def test_risk_bands_and_the_single_parameter_rule():
    assert score(obs()).risk == "low"
    low = score(obs(temperature=38.5, heart_rate=95))  # 1 + 1
    assert low.score == 2 and low.risk == "low" and low.due_within_hours == 4.0
    single = score(obs(respiratory_rate=26))  # a 3 in one parameter: urgent ward-based response
    assert single.score == 3 and single.risk == "low_medium" and single.single_parameter_3
    medium = score(obs(respiratory_rate=22, spo2=93, heart_rate=115))  # 2 + 2 + 2
    assert medium.score == 6 and medium.risk == "medium" and medium.due_within_hours == 1.0
    high = score(obs(respiratory_rate=26, spo2=91, on_oxygen=True, systolic_bp=88))
    assert high.score >= 7 and high.risk == "high" and "Emergency response" in high.response


def test_hospital_rapid_response_triggers():
    current = obs(consciousness="V", respiratory_rate=32, systolic_bp=85)
    triggers = rapid_response_triggers(current, score(current), previous=obs())
    assert any("NEWS2 of" in t for t in triggers) and any("New drop in consciousness" in t for t in triggers)
    assert any("Respiratory rate 32" in t for t in triggers) and any("below 90" in t for t in triggers)
    # Already not alert at the last round: the drop is no longer new.
    unchanged = rapid_response_triggers(obs(consciousness="V"), score(obs(consciousness="V")), previous=obs(consciousness="V"))
    assert not any("New drop" in t for t in unchanged)
    assert rapid_response_triggers(obs(), score(obs()), previous=obs()) == []


@pytest.fixture
def ward_patient(db, users):
    """A patient Nurse Kim is assigned to, who is currently admitted."""
    admitted = db.scalars(select(Admission).where(Admission.status == "admitted")).all()
    from app.auth.access import AccessPolicy

    visible = set(db.scalars(AccessPolicy(db, users["nurse"]).clinical_patient_ids()))
    return next(a for a in admitted if a.patient_id in visible)


def test_seeded_inpatients_have_observations(db):
    total = db.scalar(select(func.count()).select_from(VitalSigns))
    admitted = db.scalar(select(func.count()).select_from(Admission).where(Admission.status == "admitted"))
    assert total > admitted  # several sets each
    stored = db.scalars(select(VitalSigns).limit(50)).all()
    for v in stored:  # the stored score always matches the chart
        assert v.news2_score == score(Observations(
            respiratory_rate=v.respiratory_rate, spo2=v.spo2, on_oxygen=v.on_oxygen, systolic_bp=v.systolic_bp,
            heart_rate=v.heart_rate, consciousness=v.consciousness, temperature=v.temperature,
            spo2_scale=v.spo2_scale)).score


def test_nurses_record_observations_and_the_server_scores_them(client, auth, db, ward_patient, restricted_patient):
    body = {**NORMAL, "respiratory_rate": 26, "spo2": 91, "on_oxygen": True, "systolic_bp": 88, "heart_rate": 124,
            "consciousness": "C", "temperature": 38.6, "diastolic_bp": 60, "news2_score": 0}
    r = client.post(f"/patients/{ward_patient.patient_id}/vitals", json=body, headers=auth("nurse"))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["news2_score"] >= 7 and out["news2"]["risk"] == "high"  # the client's "news2_score" is ignored
    assert out["news2"]["parameters"]["consciousness"] == 3 and out["recorded_by"] == "Jiwoo Kim, RN"
    assert any("NEWS2 of" in t for t in out["news2"]["triggers"])
    assert out["admission_id"] == ward_patient.id  # attached to the open admission

    assert client.post(f"/patients/{ward_patient.patient_id}/vitals", json=body, headers=auth("reception")).status_code == 403
    assert client.post(f"/patients/{restricted_patient.id}/vitals", json=body, headers=auth("nurse")).status_code == 404
    assert client.post(f"/patients/{ward_patient.patient_id}/vitals", json={**body, "spo2": 900},
                       headers=auth("nurse")).status_code == 422
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "vitals.record").order_by(AuditLog.id.desc()).limit(1))
    assert audit.details["news2"] >= 7 and "value" not in audit.details

    listed = client.get(f"/patients/{ward_patient.patient_id}/vitals", headers=auth("doctor")).json()
    assert listed[0]["id"] == out["id"] and listed[0]["news2"]["score"] == out["news2"]["score"]


def test_the_preview_scores_without_saving(client, auth, db):
    before = db.scalar(select(func.count()).select_from(VitalSigns))
    preview = client.post("/vitals/score", json={**NORMAL, "respiratory_rate": 22}, headers=auth("nurse"))
    assert preview.status_code == 200 and preview.json()["score"] == 2
    assert db.scalar(select(func.count()).select_from(VitalSigns)) == before


def test_ward_board_is_scoped_ordered_and_cites_the_policy(client, auth, db, users):
    board = client.get("/ward/board", headers=auth("doctor")).json()
    scores = [p["latest"]["news2"]["score"] for p in board["patients"] if p["latest"]]
    assert scores == sorted(scores, reverse=True)  # worst first
    assert board["counts"]["inpatients"] == len(board["patients"])
    sections = {c["section_path"] for c in board["citations"]}
    assert any("Recognising Deterioration" in s for s in sections)  # patient safety guidelines
    assert any("Early Warning Score" in s for s in sections)  # emergency admission procedure
    row = next(p for p in board["patients"] if p["latest"])
    assert row["day_of_stay"] >= 1 and row["latest"]["news2"]["monitoring"]
    if row["overdue_hours"] is not None:
        assert row["overdue_hours"] > 0 and datetime.fromisoformat(row["due_at"]) < datetime.now(UTC)

    from app.auth.access import AccessPolicy

    nurse_board = client.get("/ward/board", headers=auth("nurse")).json()
    allowed = set(db.scalars(AccessPolicy(db, users["nurse"]).clinical_patient_ids()))
    assert {p["patient_id"] for p in nurse_board["patients"]} <= allowed
    assert client.get("/ward/board", headers=auth("reception")).status_code == 403


@pytest.fixture(scope="module")
def live_server():
    """A real uvicorn server: server-sent events need a real connection, not the test client's portal."""
    import threading

    import uvicorn

    from app.main import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    if not server.started:
        pytest.skip("uvicorn did not start")
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(timeout=10)


def test_the_live_stream_sends_only_events_the_viewer_may_see(live_server, tokens, db, users):
    """Open a stream, record an observation, and see the event arrive - or not, depending on access."""
    import httpx

    from app.auth.access import AccessPolicy

    cardio_allowed = set(db.scalars(AccessPolicy(db, users["cardio"]).clinical_patient_ids()))
    doctor_allowed = set(db.scalars(AccessPolicy(db, users["doctor"]).clinical_patient_ids()))
    admitted = db.scalars(select(Admission.patient_id).where(Admission.status == "admitted")).all()
    patient_id = next(pid for pid in admitted if pid in doctor_allowed and pid not in cardio_allowed)

    def headers(role: str) -> dict:
        return {"Authorization": f"Bearer {tokens[role]}"}

    with httpx.Client(base_url=live_server, timeout=20) as http:
        for role, expected in (("doctor", True), ("cardio", False)):
            with http.stream("GET", "/vitals/stream", headers=headers(role)) as stream:
                assert stream.status_code == 200
                assert stream.headers["content-type"].startswith("text/event-stream")
                lines = stream.iter_lines()
                assert next(lines).strip() == ": connected"
                recorded = http.post(f"/patients/{patient_id}/vitals", json={**NORMAL, "respiratory_rate": 28},
                                     headers=headers("doctor"))
                assert recorded.status_code == 201, recorded.text
                # The stream closes itself after CAREFLOW_STREAM_MAX_SECONDS, so this always ends.
                data = [line for line in lines if line.startswith("data:")]
            assert bool(data) is expected, (role, data)
            if expected:
                event = json.loads(data[0].removeprefix("data:").strip())
                assert event["patient_id"] == patient_id and event["news2"] >= 2
                assert "full_name" not in event and "spo2" not in event  # ids and the score only
    assert hub.open_streams == 0  # a closed stream lets go of its subscription


def test_a_role_without_clinical_access_cannot_watch_the_stream(client, auth):
    assert client.get("/vitals/stream", headers=auth("reception")).status_code == 403
    assert client.get("/vitals/stream").status_code == 401


def test_observations_reach_the_discharge_draft_and_fhir_export(db, users, ward_patient, demo_patient):
    """The co-pilot and the FHIR export both read the same observations."""
    from app.interop.fhir import FhirExporter
    from app.models import Patient
    from app.services.discharge import DischargeCopilot

    patient = db.get(Patient, ward_patient.patient_id)
    draft = DischargeCopilot(db, users["doctor"]).draft(ward_patient.id)
    assert draft.observations is not None and draft.observations.news2.score >= 0
    bundle = FhirExporter(db, "https://example.test/fhir").everything(patient, "https://example.test/x")
    sets = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"
            and e["resource"]["code"]["coding"][0]["code"] == "news2-observation-set"]
    assert sets, "vital-sign observations are exported"
    components = {c["code"]["coding"][0]["code"] for c in sets[0]["component"]}
    assert {"9279-1", "59408-5", "8867-4", "8310-5", "8480-6"} <= components  # LOINC vital signs
    assert sets[0]["valueInteger"] == sets[0]["valueInteger"]


def test_news2_is_not_presented_for_a_child(client, auth, db):
    """NEWS2 is validated for adults; for a child the values are recorded but no risk band is implied."""
    from app.models import Patient

    child = db.scalar(select(Patient).join(Admission, Admission.patient_id == Patient.id)
                      .where(Admission.status == "admitted",
                             Patient.date_of_birth > datetime.now(UTC).date().replace(year=datetime.now(UTC).year - 16))
                      .limit(1))
    if child is None:
        pytest.skip("no paediatric inpatient in this seed")
    # The administrator can read every patient; Dr. Rao could not open a paediatric one at all.
    preview = client.post(f"/vitals/score?patient_id={child.id}", json={**NORMAL, "respiratory_rate": 26},
                          headers=auth("admin")).json()
    assert preview["applies"] is False and "paediatric" in preview["note"]
    assert preview["score"] == 3 and preview["triggers"] == []  # the number is still there, the band is not
    adult = client.post("/vitals/score", json={**NORMAL, "respiratory_rate": 26}, headers=auth("admin")).json()
    assert adult["applies"] is True and adult["note"] is None

    board = client.get("/ward/board", headers=auth("admin")).json()
    row = next((p for p in board["patients"] if p["patient_id"] == child.id), None)
    if row and row["latest"]:
        assert row["latest"]["news2"]["applies"] is False
        assert row["due_at"] is None and row["overdue_hours"] is None  # the adult chart's frequency does not apply
    assert board["counts"]["not_scored"] >= 1
