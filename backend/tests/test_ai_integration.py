"""End-to-end AI workflows: SQL, RAG, ML, and their combinations, with extractive and scripted-LLM providers."""
from sqlalchemy import select

from app.llm.orchestrator import AIOrchestrator
from app.llm.prompts import INSUFFICIENT
from app.models import AIQueryTrace
from app.schemas.ai import AIQueryIn
from tests.fakes import FAILURE, TIMEOUT, ScriptedLLM, malformed_call, text, tool_call


def ask(client, auth, query, patient_id=None, role="doctor"):
    r = client.post("/ai/query", json={"query": query, "patient_id": patient_id}, headers=auth(role))
    assert r.status_code == 200, r.text
    return r.json()


def test_sql_route(client, auth):
    r = ask(client, auth, "What is patient P1024's age?")
    assert r["route"] == ["SQL"] and "67" in r["answer"] and r["record_refs"]


def test_rag_route_with_real_citations(client, auth):
    r = ask(client, auth, "What does our diabetes guideline say about monitoring?")
    assert r["route"] == ["RAG"] and r["citations"] and not r["insufficient_context"]
    context_ids = set(r["retrieval"]["context_source_ids"])
    for c in r["citations"]:
        assert c["chunk_id"] in context_ids  # every citation was actually retrieved
        source = client.get(f"/ai/sources/{c['chunk_id']}", headers=auth("doctor")).json()
        assert source["text"].startswith(c["excerpt"][:80])
    assert any("Diabetes" in c["document_title"] for c in r["citations"])


def test_ml_route(client, auth, demo_patient):
    r = ask(client, auth, "What is this patient's readmission risk?", demo_patient.id)
    assert r["route"] == ["SQL", "ML"] and r["predictions"][0]["model_version"] == "1.0.0"


def test_sql_rag_route(client, auth, demo_patient):
    r = ask(client, auth, "Compare this patient's treatment with our diabetes guideline.", demo_patient.id)
    assert {"SQL", "RAG"} <= set(r["route"]) and r["citations"] and r["record_refs"]
    assert any("metformin" in (c["excerpt"].lower()) for c in r["citations"])


def test_sql_ml_route(client, auth, demo_patient):
    r = ask(client, auth, "Why is this patient's readmission risk high?", demo_patient.id)
    assert {"SQL", "ML"} <= set(r["route"])
    assert "contributed" in r["answer"] and "not causes" in r["answer"]


def test_sql_rag_ml_route(client, auth, demo_patient):
    r = ask(client, auth, "Why is this patient's readmission risk high, and what does the discharge policy say "
                          "for high-risk patients?", demo_patient.id)
    assert {"SQL", "RAG", "ML"} <= set(r["route"])
    assert r["predictions"] and r["citations"]


def test_similarity_route(client, auth, demo_patient):
    r = ask(client, auth, "Find similar historical patients and summarize relevant patterns.", demo_patient.id)
    assert r["route"][0] == "SIMILARITY" and r["similarity"]["results"]
    assert "Historical patterns" in r["answer"]


def test_patient_summary_and_timeline_changes(client, auth, demo_patient):
    r = ask(client, auth, "Summarize this patient's medical history.", demo_patient.id)
    assert "Sunita Deshpande" in r["answer"] and "HbA1c" in r["answer"] and len(r["record_refs"]) > 5
    changes = ask(client, auth, "What were the major treatment changes?", demo_patient.id)
    assert "metformin" in changes["answer"].lower() and "insulin glargine" in changes["answer"].lower()


def test_insufficient_context(client, auth):
    r = ask(client, auth, "What is the capital of Peru?")
    assert r["insufficient_context"] and INSUFFICIENT in r["answer"] and not r["citations"]


def test_unknown_or_unauthorized_patient(client, auth, restricted_patient):
    for mrn in ("P9999", restricted_patient.mrn):
        r = ask(client, auth, f"Summarize patient {mrn}")
        assert "not found or is not accessible" in r["answer"] and not r["record_refs"]


def test_receptionist_cannot_extract_clinical_data_via_ai(client, auth, demo_patient):
    r = ask(client, auth, "Summarize this patient's history", demo_patient.id, role="reception")
    denied = [t for t in r["tool_calls"] if t["status"] == "denied"]
    assert denied and "insulin" not in r["answer"].lower() and "diabetes" not in r["answer"].lower()


def test_decision_requests_get_safety_warning(client, auth, demo_patient):
    r = ask(client, auth, "What dose should I give this patient for her insulin?", demo_patient.id)
    assert any("does not make clinical decisions" in w for w in r["warnings"])


# ------------------------------------------------------------------ LLM synthesis / tool-calling paths
def test_llm_synthesis_receives_structured_context_and_citations_are_validated(db, users, demo_patient):
    llm = ScriptedLLM(text("HbA1c has risen [R1]. Guideline: measure every 3 months [S1]. Invented [S42]."))
    r = AIOrchestrator(db, users["doctor"], provider=llm).run(
        AIQueryIn(query="Compare this patient's treatment with our diabetes guideline.", patient_id=demo_patient.id))
    prompt = llm.requests[0]["messages"][0].content
    assert "<database_facts>" in prompt and "<retrieved_documents" in prompt and "<user_query>" in prompt
    assert llm.requests[0]["tools"] is None  # deterministic route: the model gets no tools
    assert "[S42]" not in r.answer and any("did not match" in w for w in r.warnings)
    assert r.provider == "scripted" and r.stage_ms["llm"] >= 0
    trace = db.scalar(select(AIQueryTrace).order_by(AIQueryTrace.id.desc()).limit(1))
    assert trace.prompt_tokens == 100 and trace.route == "SQL + RAG + LLM" and trace.retrieved_chunk_ids


def test_llm_synthesis_for_pure_document_question_with_patient_context(db, users, demo_patient):
    """Regression: document-only evidence must reach the LLM (it previously short-circuited to 'insufficient')."""
    llm = ScriptedLLM(text("Measure HbA1c every 3 months when not at target [S1]."))
    r = AIOrchestrator(db, users["doctor"], provider=llm).run(
        AIQueryIn(query="What does our diabetes guideline say about monitoring?", patient_id=demo_patient.id))
    assert llm.requests, "the LLM was never called"
    assert "<retrieved_documents" in llm.requests[0]["messages"][0].content
    assert not r.insufficient_context and r.citations and r.citations[0].id == "S1"


def test_prompt_is_trimmed_to_the_context_budget(db, users, demo_patient):
    llm = ScriptedLLM(text("Summary [R1]."))
    orch = AIOrchestrator(db, users["doctor"], provider=llm)
    orch.settings = orch.settings.model_copy(update={"llm_context_budget_chars": 3000})
    orch.run(AIQueryIn(query="Summarize this patient's medical history.", patient_id=demo_patient.id))
    prompt = llm.requests[0]["messages"][0].content
    assert len(prompt) < 4500 and "omitted to fit the context window" in prompt and "<user_query>" in prompt


def test_llm_tool_calling_for_unrouted_questions(db, users, demo_patient):
    llm = ScriptedLLM(tool_call("get_patient", patient="P1024"), tool_call("predict_length_of_stay"),
                      text("She is 67 [R1]; the model estimates a stay of about five days."))
    r = AIOrchestrator(db, users["doctor"], provider=llm).run(
        AIQueryIn(query="Anything notable to tell the bed manager?", patient_id=demo_patient.id))
    assert r.routing_method == "llm" and [t.name for t in r.tool_calls] == ["get_patient", "predict_length_of_stay"]
    assert {"SQL", "ML", "LLM"} == set(r.route)
    offered = {t.name for t in llm.requests[0]["tools"]}
    assert "predict_readmission" in offered
    tool_msgs = [m for m in llm.requests[1]["messages"] if m.role == "tool"]
    assert tool_msgs and "<tool_output>" in tool_msgs[0].content


def test_tool_calling_off_uses_single_synthesis_call(db, users, demo_patient):
    """For slow local models: unrecognised questions use the router's plan and ONE LLM call without tools."""
    llm = ScriptedLLM(text("Summary [R1]."))
    orch = AIOrchestrator(db, users["doctor"], provider=llm)
    orch.settings = orch.settings.model_copy(update={"llm_tool_calling": "off"})
    r = orch.run(AIQueryIn(query="Anything notable to tell the bed manager?", patient_id=demo_patient.id))
    assert r.routing_method == "deterministic" and len(llm.requests) == 1 and llm.requests[0]["tools"] is None
    assert "get_patient_timeline" in [t.name for t in r.tool_calls]


def test_tools_offered_depend_on_role(db, users):
    llm = ScriptedLLM(text("ok"))
    AIOrchestrator(db, users["reception"], provider=llm).run(AIQueryIn(query="Tell me something interesting"))
    offered = {t.name for t in llm.requests[0]["tools"]}
    assert "get_patient_records" not in offered and "predict_readmission" not in offered
    assert {"get_patient", "get_appointments", "search_documents"} <= offered


def test_malformed_tool_output_is_handled(db, users):
    llm = ScriptedLLM(malformed_call("get_patient"), text("I could not retrieve that."))
    r = AIOrchestrator(db, users["doctor"], provider=llm).run(AIQueryIn(query="Tell me something interesting"))
    assert r.tool_calls[0].status == "error" and r.answer


def test_llm_failure_and_timeout_fall_back_to_extractive(db, users, demo_patient):
    for failure in (FAILURE, TIMEOUT):
        r = AIOrchestrator(db, users["doctor"], provider=ScriptedLLM(failure)).run(
            AIQueryIn(query="Summarize this patient's medical history.", patient_id=demo_patient.id))
        assert any("unavailable" in w for w in r.warnings) and "Sunita Deshpande" in r.answer


def test_backup_llm_answers_silently_when_primary_fails(db, users, demo_patient):
    from app.llm.fallback import FallbackProvider

    primary, backup = ScriptedLLM(FAILURE), ScriptedLLM(text("Backup summary [R1]."))
    primary.name, backup.name = "groq", "gemini"
    r = AIOrchestrator(db, users["doctor"], provider=FallbackProvider(primary, backup)).run(
        AIQueryIn(query="Summarize this patient's medical history.", patient_id=demo_patient.id))
    assert r.answer.startswith("Backup summary") and r.provider == "gemini"
    assert not any("unavailable" in w or "backup" in w for w in r.warnings)  # no error shown to the user
    trace = db.scalar(select(AIQueryTrace).order_by(AIQueryTrace.id.desc()).limit(1))
    assert trace.provider == "gemini"


def test_observability_endpoints(client, auth):
    ask(client, auth, "What does our discharge policy say about follow-up?")
    traces = client.get("/admin/ai-traces?limit=5", headers=auth("admin")).json()
    assert traces["total"] > 0 and traces["items"][0]["stage_ms"]
    summary = client.get("/admin/metrics/summary", headers=auth("admin")).json()
    assert summary["ai_queries"] > 0 and "total" in summary["latency_ms"]
    metrics = client.get("/metrics").text
    assert "careflow_http_request_seconds" in metrics and "careflow_ai_stage_seconds" in metrics
