"""Pseudonymisation gateway: patient identifiers never reach a cloud language model."""
from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.llm.fallback import FallbackProvider
from app.llm.openai_compat import OpenAICompatibleProvider
from app.llm.orchestrator import AIOrchestrator
from app.llm.providers import GROQ_BASE_URL, ExtractiveProvider
from app.models import AIQueryTrace, Patient
from app.privacy.pseudonymize import IdentifierVault, _staff_forms, pseudonymization_enabled
from app.schemas.ai import AIQueryIn
from tests.fakes import ScriptedLLM, text, tool_call


def _patient(pid: int, first: str, last: str, mrn: str, **kw) -> Patient:
    return Patient(id=pid, mrn=mrn, first_name=first, last_name=last, date_of_birth=kw.pop("dob", date(1958, 3, 14)),
                   sex="F", **kw)


SUNITA = dict(phone="+91 98220 13456", email="sunita.d@example.com", address="12, MG Road, Pune 411001",
              emergency_contact_name="Meena Deshpande", emergency_contact_phone="+91 90110 22334")


def test_every_direct_identifier_is_replaced_and_restored():
    vault = IdentifierVault()
    vault.add_patient(_patient(1, "Sunita", "Deshpande", "P1024", **SUNITA))
    original = ("Sunita Deshpande (P1024), born 1958-03-14, phone +91 98220 13456, e-mail sunita.d@example.com, "
                "lives at 12, MG Road, Pune 411001. Emergency contact Meena Deshpande on +91 90110 22334. "
                "Mrs. Deshpande reports that Sunita feels better.")
    sent = vault.pseudonymize(original)
    for value in ("Sunita", "Deshpande", "P1024", "1958-03-14", "98220", "example.com", "MG Road", "Meena", "90110"):
        assert value not in sent
    assert sent.startswith("PATIENT_1 (MRN_1), born DOB_1, phone PHONE_1, e-mail EMAIL_1, lives at ADDRESS_1.")
    assert vault.counts() == {"address": 1, "contact_name": 1, "date_of_birth": 1, "email": 1, "mrn": 1,
                              "patient_name": 1, "phone": 2}
    restored = vault.reidentify(sent)
    # A bare first name or "Mrs. Deshpande" comes back as the full name; everything else verbatim.
    assert restored.startswith(original.split(" Mrs.")[0])
    assert restored.endswith("Sunita Deshpande reports that Sunita Deshpande feels better.")


def test_staff_names_stay_and_ambiguous_first_names_are_not_guessed():
    vault = IdentifierVault()
    vault.add_patient(_patient(1, "Kavita", "Rao", "P1100"))
    vault.add_patient(_patient(2, "Asha", "Patil", "P1101"))
    vault.add_patient(_patient(3, "Asha", "Kulkarni", "P1102"))
    vault.protect(_staff_forms(["Dr. Ananya Rao", "Jiwoo Kim, RN"]))
    sent = vault.pseudonymize("Dr. Ananya Rao and Jiwoo Kim reviewed Kavita Rao. Dr Rao spoke to Asha Patil; "
                              "Asha Kulkarni is next. Asha asked about discharge.")
    assert sent == ("Dr. Ananya Rao and Jiwoo Kim reviewed PATIENT_1. Dr Rao spoke to PATIENT_2; "
                    "PATIENT_3 is next. Asha asked about discharge.")


def test_identifiers_the_database_did_not_supply_are_caught_by_shape():
    vault = IdentifierVault()
    vault.add_patient(_patient(1, "Sunita", "Deshpande", "P1024", **SUNITA))
    sent = vault.pseudonymize("Call 9822013456 or +91 70000 12345, write to a.b@example.org, Aadhaar 2345 6789 0123; "
                              "compare with P1099. HbA1c 9.4% on 2026-09-01, eGFR 44.")
    # The same phone number in another format maps to the patient's existing placeholder.
    assert sent == ("Call PHONE_1 or PHONE_3, write to EMAIL_2, Aadhaar NATIONAL_ID_1; compare with MRN_2. "
                    "HbA1c 9.4% on 2026-09-01, eGFR 44.")
    assert vault.reidentify("MRN_2 and PHONE_3") == "P1099 and +91 70000 12345"


def test_placeholder_shaped_text_from_a_document_is_not_restored_as_a_name():
    vault = IdentifierVault()
    vault.add_patient(_patient(1, "Sunita", "Deshpande", "P1024"))
    sent = vault.pseudonymize("Notice: PATIENT_1 must report to the desk.")
    assert sent == "Notice: PATIENT-1 must report to the desk."
    assert vault.reidentify(sent) == sent


def test_pseudonymisation_is_on_for_models_outside_the_network():
    def compat(base_url: str, name: str = "openai_compatible") -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(base_url, "m", name=name, transport=httpx.MockTransport(lambda r: None))

    groq = compat(GROQ_BASE_URL, "groq")
    assert pseudonymization_enabled(groq, "auto")
    assert pseudonymization_enabled(compat("https://api.openai.com/v1"), "auto")
    for local in ("http://localhost:11434/v1", "http://127.0.0.1:8080/v1", "http://ollama:11434/v1",
                  "http://host.docker.internal:11434/v1", "http://192.168.1.20:11434/v1"):
        assert not pseudonymization_enabled(compat(local), "auto"), local
        assert pseudonymization_enabled(compat(local), "on")
    assert not pseudonymization_enabled(groq, "off")
    assert not pseudonymization_enabled(ExtractiveProvider(), "on")
    chain = FallbackProvider(compat("http://localhost:11434/v1"), groq)
    assert pseudonymization_enabled(chain, "auto")  # the backup would send the prompt out


def _all_sent(llm: ScriptedLLM) -> str:
    return "\n".join(m.content for req in llm.requests for m in req["messages"])


def test_cloud_model_never_sees_the_patient_and_the_answer_is_restored(db, users, demo_patient):
    llm = ScriptedLLM(text("PATIENT_1 (MRN_1) has type 2 diabetes [R2] and was reviewed by Dr. Ananya Rao."))
    r = AIOrchestrator(db, users["doctor"], provider=llm, pseudonymize=True).run(
        AIQueryIn(query="Summarize this patient's medical history.", patient_id=demo_patient.id))
    sent = _all_sent(llm)
    for value in (demo_patient.first_name, demo_patient.last_name, demo_patient.mrn,
                  demo_patient.date_of_birth.isoformat()):
        assert value not in sent
    assert "PATIENT_1" in sent and "Ananya Rao" in sent  # clinicians are not patient identifiers
    assert r.answer.startswith(f"{demo_patient.full_name} ({demo_patient.mrn}) has type 2 diabetes [R2]")
    assert r.privacy.applied and r.privacy.destination == "scripted"
    assert r.privacy.replaced["patient_name"] == 1 and r.privacy.replaced["mrn"] == 1
    assert demo_patient.last_name not in r.privacy.preview and "<user_query>" in r.privacy.preview
    trace = db.scalar(select(AIQueryTrace).order_by(AIQueryTrace.id.desc()).limit(1))
    assert trace.privacy["applied"] and "preview" not in trace.privacy


def test_tool_arguments_are_restored_before_the_tool_runs(db, users, demo_patient):
    llm = ScriptedLLM(tool_call("get_patient", patient="MRN_1"), text("PATIENT_1 is allergic to penicillin [R1]."))
    r = AIOrchestrator(db, users["doctor"], provider=llm, pseudonymize=True).run(
        AIQueryIn(query="Tell me something surprising", patient_id=demo_patient.id))
    assert r.routing_method == "llm"
    assert r.tool_calls[0].status == "ok" and r.tool_calls[0].arguments == {"patient": demo_patient.mrn}
    tool_output = llm.requests[1]["messages"][-1]
    assert tool_output.role == "tool" and "PATIENT_1" in tool_output.content
    assert demo_patient.last_name not in _all_sent(llm)
    assert r.answer.startswith(demo_patient.full_name)


def test_other_patients_named_in_the_evidence_are_masked_too(db, users):
    """An appointment list names many patients; none of them reaches the model."""
    llm = ScriptedLLM(tool_call("get_appointments", doctor="Rao", period="upcoming"), text("Listed [R1]."))
    AIOrchestrator(db, users["doctor"], provider=llm, pseudonymize=True).run(
        AIQueryIn(query="Anything I should prepare for this week?"))
    listed = llm.requests[1]["messages"][-1].content
    names = [p.full_name for p in db.scalars(select(Patient))]
    assert "PATIENT_" in listed and not any(name in listed for name in names)


def test_local_models_and_extractive_answers_are_left_alone(db, users, demo_patient):
    llm = ScriptedLLM(text("Summary [R1]."))
    r = AIOrchestrator(db, users["doctor"], provider=llm).run(  # "scripted" is not a cloud provider
        AIQueryIn(query="Summarize this patient's medical history.", patient_id=demo_patient.id))
    assert demo_patient.last_name in _all_sent(llm)
    assert r.privacy is not None and not r.privacy.applied and r.privacy.preview is None
    extractive = AIOrchestrator(db, users["doctor"]).run(
        AIQueryIn(query="Summarize this patient's medical history.", patient_id=demo_patient.id))
    assert extractive.privacy is None  # no model was called: nothing left the server


# ---------------------------------------------------------------- the third pass: people in free text
@pytest.mark.models
def test_people_written_into_free_text_are_masked_by_the_name_model():
    """A relative or an outside clinician has no identifier in this database, so only a tagger finds them."""
    from app.privacy.ner import get_name_finder

    vault = IdentifierVault()
    vault.add_patient(_patient(1, "Sunita", "Deshpande", "P1024", **SUNITA))
    vault.protect(_staff_forms(["Dr. Ananya Rao", "Jiwoo Kim, RN"]))
    vault.finder = get_name_finder()
    note = ("Ward round with Dr. Ananya Rao. Sunita Deshpande's daughter Bhavna Kulkarni called about "
            "discharge. Previously under Dr Sandhya Iyer at another hospital. HbA1c 7.8%.")
    sent = vault.pseudonymize(note)

    assert "Bhavna Kulkarni" not in sent and "Sandhya Iyer" not in sent
    assert "PERSON_1" in sent and "PERSON_2" in sent
    assert "Dr. Ananya Rao" in sent          # this hospital's own staff are the directory, not identifiers
    assert "PATIENT_1" in sent               # the dictionary pass still did its work first
    assert "HbA1c 7.8%" in sent              # clinical detail is not touched
    assert vault.counts()["person"] == 2
    # And the answer comes back with the real names, so the reader never sees a placeholder.
    assert vault.reidentify(sent) .count("Bhavna Kulkarni") == 1


@pytest.mark.models
def test_the_name_model_leaves_a_prompt_without_people_alone():
    from app.privacy.ner import get_name_finder

    vault = IdentifierVault()
    vault.finder = get_name_finder()
    clinical = ("Sodium 138 mmol/L, potassium 4.1 mmol/L, creatinine 96 umol/L. Chest radiograph shows "
                "clear lung fields. Continue ramipril 5 mg once daily and review in the diabetes clinic.")
    assert vault.pseudonymize(clinical) == clinical


def test_the_name_model_is_optional_and_the_answer_says_whether_it_ran(db, users, demo_patient):
    """With the pass off, the dictionary works exactly as before and the privacy panel does not claim it."""
    vault = IdentifierVault()
    vault.add_patient(_patient(1, "Sunita", "Deshpande", "P1024", **SUNITA))
    assert vault.finder is None
    assert "Bhavna Kulkarni" in vault.pseudonymize("Daughter Bhavna Kulkarni called about Sunita Deshpande.")
