"""Discharge co-pilot: deterministic reconciliation and policy checks, checked prose, clinician sign-off."""
import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth.access import AccessPolicy
from app.core.errors import ConflictError
from app.llm.base import LLMResult
from app.models import Admission, AIDraft, Document, LabReport, MedicalRecord, Medication, Patient, Prescription
from app.schemas.discharge import DischargeSignIn
from app.services.discharge import _SENTENCE_END, DischargeCopilot, _numbers_unsupported


class FactAwareLLM:
    """Writes the prose from the facts it is sent, citing the [R#] ids those facts carry."""

    name, model, supports_tools = "scripted", "scripted-test-model", True

    def __init__(self, write):
        self.write = write
        self.prompts: list[str] = []

    def chat(self, system, messages, tools=None, max_tokens=None) -> LLMResult:
        prompt = messages[-1].content
        self.prompts.append(prompt)

        def rid(fragment: str) -> str:
            return re.search(rf"^\[(R\d+)\][^\n]*{re.escape(fragment)}", prompt, re.M).group(1)

        return LLMResult(text=self.write(rid), tool_calls=[], model=self.model)


def _latest_admission(db, patient: Patient) -> Admission:
    return db.scalar(select(Admission).where(Admission.patient_id == patient.id)
                     .order_by(Admission.admitted_at.desc()).limit(1))


def test_draft_reconciles_medications_and_applies_the_discharge_policy(client, auth, db, demo_patient):
    adm = _latest_admission(db, demo_patient)
    r = client.post(f"/admissions/{adm.id}/discharge-draft", headers=auth("doctor"))
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["generated_by"] == "template" and d["status"] == "draft"  # no language model in the test settings
    assert all(s["citations"] and not s["issues"] for sec in d["sections"] for s in sec["sentences"])

    meds = {m["medication"]: m for m in d["medications"]}
    glargine = meds["insulin glargine"]
    assert glargine["status"] == "changed" and glargine["high_alert"]
    assert (glargine["before"], glargine["after"]) == ("10 units once nightly", "16 units once nightly")
    assert glargine["reason"].startswith("Dose increased")
    assert meds["metformin"]["status"] == "held_resumed"  # held during a hyperglycaemia admission
    assert meds["insulin lispro"]["status"] == "inpatient_only"

    criteria = {c["key"]: c for c in d["risk"]["criteria"]}
    assert d["risk"]["high_risk"]
    assert criteria["prior_admissions"]["status"] == "met" and criteria["recent_ed_visit"]["status"] == "met"
    assert criteria["insulin_anticoagulant_change"]["status"] == "met"
    assert criteria["model_flag"]["status"] in ("met", "not_met")  # scored this admission
    checklist = {c["key"]: c for c in d["checklist"]}
    assert checklist["phone_call"]["status"] == "to_confirm"  # high risk -> transitional care applies
    assert checklist["high_alert_review"]["status"] == "to_confirm"

    # Every check links to the policy section it implements.
    sections = {c["id"]: c["section_path"] for c in d["citations"]}
    assert {"3. Readmission Risk Screening", "4. Transitional Care for High-Risk Patients"} <= set(sections.values())
    assert any(ref in sections and sections[ref].startswith("3.") for ref in criteria["prior_admissions"]["refs"])
    assert "[S" in d["follow_up_plan"] and "Nurse telephone call" in d["follow_up_plan"]

    resumed = client.get(f"/admissions/{adm.id}/discharge-draft", headers=auth("doctor")).json()
    assert resumed["draft_id"] == d["draft_id"] and resumed["medications"] == d["medications"]


def test_only_clinicians_who_can_discharge_this_patient_may_draft(client, auth, db, demo_patient, restricted_patient):
    adm = _latest_admission(db, demo_patient)
    for role in ("nurse", "reception", "admin"):
        assert client.post(f"/admissions/{adm.id}/discharge-draft", headers=auth(role)).status_code == 403
    assert client.post(f"/admissions/{adm.id}/discharge-draft", headers=auth("cardio")).status_code == 404
    other = _latest_admission(db, restricted_patient)
    if other is not None:
        assert client.post(f"/admissions/{other.id}/discharge-draft", headers=auth("doctor")).status_code == 404


def test_model_prose_is_checked_sentence_by_sentence(db, users, demo_patient):
    llm = FactAwareLLM(lambda rid: (
        f"## Presenting problem\nPATIENT_1 was admitted with hyperglycemia [{rid('Reason:')}]. "
        f"She reported symptoms for 5 days.\n"
        f"## Hospital course\n**Glucose** was 999 mg/dL on arrival [{rid('Glucose:')}]. "
        f"Seen by Dr. Ananya Rao on the ward [{rid('Reason:')}]. Insulin was adjusted [R999]."))
    adm = _latest_admission(db, demo_patient)
    d = DischargeCopilot(db, users["doctor"], provider=llm, pseudonymize=True).draft(adm.id)
    assert d.generated_by == "scripted/scripted-test-model"
    presenting, course = d.sections
    assert presenting.sentences[0].text.startswith(demo_patient.full_name) and not presenting.sentences[0].issues
    assert presenting.sentences[1].issues == ["no_source"]
    assert course.sentences[0].issues == ["number_not_in_source:999"]
    assert course.sentences[1].issues == []  # "Dr." does not end a sentence
    assert course.sentences[2].issues == ["no_source"] and "[R999]" not in course.sentences[2].text
    assert any("could not be traced" in w for w in d.warnings)
    assert demo_patient.last_name not in llm.prompts[0] and d.privacy.applied  # the cloud model saw placeholders


@pytest.fixture
def open_admission(db, users):
    """A fresh pneumonia admission for a Dr. Rao patient other than P1024, rolled back after the test."""
    visible = AccessPolicy(db, users["doctor"]).accessible_patient_ids()
    patient = db.scalar(select(Patient).where(Patient.id.in_(visible), Patient.status == "active",
                                              Patient.mrn != "P1024").order_by(Patient.id).limit(1))
    now = datetime.now(UTC)
    adm = Admission(patient_id=patient.id, department_id=users["doctor"].department_id,
                    attending_doctor_id=users["doctor"].doctor_id, admitted_at=now - timedelta(days=3),
                    admission_type="emergency", admission_source="emergency_room",
                    reason="Community-acquired pneumonia", status="admitted", ward="GM-2")
    db.add(adm)
    db.flush()
    patient.status = "admitted"
    for day, value in ((3, 140.0), (1, 38.0)):
        db.add(LabReport(patient_id=patient.id, admission_id=adm.id, test_code="CRP", test_name="C-reactive protein",
                         value=value, unit="mg/L", reference_high=5.0, flag="high",
                         collected_at=now - timedelta(days=day), reported_at=now - timedelta(days=day)))
    ceftriaxone = db.scalar(select(Medication).where(Medication.name == "ceftriaxone"))
    db.add(Prescription(patient_id=patient.id, medication_id=ceftriaxone.id, doctor_id=users["doctor"].doctor_id,
                        admission_id=adm.id, dosage="1 g", frequency="once daily", route="iv",
                        start_date=adm.admitted_at.date(), status="active", instructions="Inpatient order"))
    db.add(MedicalRecord(patient_id=patient.id, doctor_id=users["doctor"].doctor_id, admission_id=adm.id,
                         visit_date=adm.admitted_at.date(), record_type="emergency",
                         chief_complaint="Community-acquired pneumonia",
                         symptoms="Fever, productive cough and shortness of breath."))
    db.flush()
    return adm


def _prose(rid):
    return (f"## Presenting problem\nAdmitted with fever and productive cough [{rid('emergency by')}].\n"
            f"## Hospital course\nTreated with intravenous ceftriaxone [{rid('ceftriaxone')}]. "
            f"CRP fell from 140 to 38 mg/L [{rid('C-reactive protein')}]. She walked 300 metres on day 2.")


def test_signing_needs_confirmation_for_unsupported_sentences_and_records_provenance(db, users, open_admission):
    copilot = DischargeCopilot(db, users["doctor"], provider=FactAwareLLM(_prose))
    d = copilot.draft(open_admission.id)
    course = d.sections[1]
    assert [s.issues for s in course.sentences] == [[], [], ["no_source"]]
    body = DischargeSignIn(draft_id=d.draft_id, presenting_problem=d.sections[0].text, hospital_course=course.text,
                           follow_up_plan=d.follow_up_plan, discharge={"discharge_disposition": "home"})
    with pytest.raises(ConflictError) as blocked:
        copilot.sign(open_admission.id, body)
    assert blocked.value.details["unsupported"] == ["She walked 300 metres on day 2."]

    # The clinician rewrites the unsupported sentence in their own words: no confirmation needed any more.
    edited = course.text.replace("She walked 300 metres on day 2.", "Mobilising independently at discharge.")
    out = copilot.sign(open_admission.id, body.model_copy(update={"hospital_course": edited}))
    record = out.record
    assert record.record_type == "discharge_summary" and record.admission_id == open_admission.id
    prov = record.ai_provenance
    assert prov["signed_by"] == "Dr. Ananya Rao" and prov["generated_by"] == "scripted/scripted-test-model"
    assert 0 < prov["edited_pct"] < 40 and prov["unsupported_confirmed"] == 0
    cited = set(re.findall(r"\[([RS]\d+)\]", "\n".join([record.symptoms, record.notes, record.treatment_plan])))
    assert cited and cited <= set(prov["sources"])  # every marker kept in the record still resolves to its source
    assert "ceftriaxone" in record.notes and "Key investigations" in record.notes
    assert out.admission.status == "discharged" and out.admission.discharge_disposition == "home"
    assert db.get(AIDraft, d.draft_id).status == "signed"
    with pytest.raises(ConflictError):  # a signed draft cannot be signed twice
        copilot.sign(open_admission.id, body.model_copy(update={"confirm_unsupported": True}))


def test_confirmed_unsupported_sentences_are_counted_and_new_drafts_supersede_old(db, users, open_admission):
    copilot = DischargeCopilot(db, users["doctor"], provider=FactAwareLLM(_prose))
    first = copilot.draft(open_admission.id)
    second = copilot.draft(open_admission.id)
    assert db.get(AIDraft, first.draft_id).status == "superseded"
    body = DischargeSignIn(draft_id=second.draft_id, presenting_problem=second.sections[0].text,
                           hospital_course=second.sections[1].text, follow_up_plan=second.follow_up_plan,
                           confirm_unsupported=True)
    with pytest.raises(ConflictError):
        copilot.sign(open_admission.id, body.model_copy(update={"draft_id": first.draft_id}))
    out = copilot.sign(open_admission.id, body)
    assert out.record.ai_provenance["unsupported_confirmed"] == 1 and out.edited_pct == 0
    assert out.admission.status == "admitted"  # signing alone does not discharge


def test_a_changed_policy_document_is_reported(db, users, open_admission):
    doc = db.scalar(select(Document).where(Document.doc_key == "cf-pol-dc-07", Document.is_current.is_(True)))
    doc.version = 2
    db.flush()
    d = DischargeCopilot(db, users["doctor"]).draft(open_admission.id)
    assert any("now version 2" in w for w in d.warnings)


def test_number_and_sentence_checks():
    source = "Glucose: 431 mg/dL (critical) on 2026-09-05; latest 162 mg/dL (high) on 2026-09-10."
    assert _numbers_unsupported("Glucose was 431 mg/dL on 5 September 2026 [R3].", source) == []
    assert _numbers_unsupported("It fell to 162 by Sept 10, 2026 [R3].", source) == []
    assert _numbers_unsupported("Glucose was 431 on 7 September 2026 and 150 on day 3 [R3].", source) == [
        "7 September 2026", "150", "3"]
    parts = _SENTENCE_END.split("Seen by Dr. Rao and Mrs. Iyer, e.g. daily. Discharged home.")
    assert parts == ["Seen by Dr. Rao and Mrs. Iyer, e.g. daily.", "Discharged home."]
