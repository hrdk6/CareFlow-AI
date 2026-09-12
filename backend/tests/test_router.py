"""Query routing: each category from the specification."""
import pytest

from app.routing.router import Intent, route


@pytest.mark.parametrize("query,ctx,intents,caps", [
    ("What is patient P1024's age?", False, [Intent.PATIENT_FACT], ["SQL"]),
    ("What appointments does Dr. Rao have?", False, [Intent.APPOINTMENTS], ["SQL"]),
    ("What does our diabetes guideline say?", False, [Intent.DOCUMENT_QA], ["RAG", "LLM"]),
    ("What is this patient's readmission risk?", True, [Intent.READMISSION], ["SQL", "ML"]),
    ("Summarize this patient's history.", True, [Intent.PATIENT_SUMMARY], ["SQL", "LLM"]),
    ("Why is this patient's readmission risk high?", True, [Intent.EXPLAIN_PREDICTION], ["SQL", "ML", "LLM"]),
    ("Compare the patient's treatment with our diabetes guideline.", True, [Intent.GUIDELINE_COMPARISON],
     ["SQL", "RAG", "LLM"]),
    ("Find similar patients.", True, [Intent.SIMILAR_PATIENTS], ["SIMILARITY", "SQL", "LLM"]),
    ("Find similar patients and summarize their relevant history.", True, [Intent.SIMILAR_PATIENTS],
     ["SIMILARITY", "SQL", "LLM"]),
    ("What were the major treatment changes?", True, [Intent.TREATMENT_CHANGES], ["SQL", "LLM"]),
    ("How long will this patient stay in hospital?", True, [Intent.LENGTH_OF_STAY], ["SQL", "ML"]),
    ("Which medications are high-alert?", False, [Intent.DOCUMENT_QA], ["RAG", "LLM"]),
    ("What can you do?", False, [Intent.GENERAL], ["LLM"]),
])
def test_routes(query, ctx, intents, caps):
    plan = route(query, has_patient_context=ctx)
    assert plan.intents == intents
    assert plan.capabilities == caps
    assert plan.confidence == "high"


@pytest.mark.parametrize("query", ["whats up with the patient", "What's going on with her?", "How is this patient doing?",
                                   "Any update on the patient?"])
def test_conversational_patient_questions_route_to_summary(query):
    plan = route(query, has_patient_context=True)
    assert plan.intents == [Intent.PATIENT_SUMMARY] and plan.confidence == "high"


def test_unrecognised_question_about_patient_defaults_to_summary():
    plan = route("Anything notable to tell the bed manager?", has_patient_context=True)
    assert plan.intents == [Intent.PATIENT_SUMMARY] and plan.confidence == "low"


def test_combined_sql_ml_rag_route():
    plan = route("Why is this patient's readmission risk high, and what does the discharge policy say for "
                 "high-risk patients?", has_patient_context=True)
    assert set(plan.capabilities) >= {"SQL", "ML", "RAG", "LLM"}


def test_entities_extracted():
    plan = route("Show appointments for Dr. Rao and patient p1024")
    assert plan.doctor_name == "Rao" and plan.mrn == "P1024"


def test_unrecognised_question_is_low_confidence():
    plan = route("Tell me something interesting about the weather")
    assert plan.confidence == "low" and plan.intents == [Intent.DOCUMENT_QA]


def test_clinical_decision_requests_are_flagged():
    assert route("What dose should I give this patient?", has_patient_context=True).decision_request
    assert not route("What does the guideline say about dosing?").decision_request
