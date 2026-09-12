"""AI orchestrator: route -> authorized tools -> evidence -> LLM synthesis -> grounding checks -> trace.

Two execution modes:
  deterministic  (router confident)  the router's fixed plan runs the tools; the LLM only writes the answer
                                     over the evidence (no tool access at all).
  llm            (router unsure)     the LLM chooses among the tools the user is permitted to use, in a
                                     bounded loop; every call is still authorized server-side.
If no LLM is configured, or it fails, the extractive composer answers from the same evidence.
"""
import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.access import AccessPolicy
from app.core.config import get_settings
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import request_id_var
from app.llm import extractive
from app.llm.base import ChatMessage, LLMError, LLMResult
from app.llm.evidence import EvidenceStore
from app.llm.grounding import redact_unauthorized_mrns, validate_citations
from app.llm.prompts import AGENT_ADDENDUM, INSUFFICIENT, SYSTEM_PROMPT, render_evidence, synthesis_prompt
from app.llm.providers import get_llm_provider
from app.llm.tools import TOOLS, ToolContext, execute_tool, tools_for
from app.ml.service import DISCLAIMER as ML_DISCLAIMER
from app.models import AIQueryTrace, User
from app.observability.metrics import AI_QUERIES, LLM_TOKENS, StageTimer
from app.routing.router import Intent, RoutePlan, route
from app.schemas.ai import AIQueryIn, AIResponse, ToolCallOut

logger = logging.getLogger("careflow.ai")

DISCLAIMER = ("CareFlow AI provides information retrieval, summaries and model-based decision support on synthetic "
              "demo data. It does not diagnose or make treatment decisions; clinical judgement remains with the "
              "treating clinician.")

_LAB_WORDS = ("lab", "hba1c", "a1c", "egfr", "glucose", "creatinine", "potassium", "ldl", "bnp", "inr", "result")
_MED_WORDS = ("medic", "meds", "prescri", "drug", "dose", "insulin", "metformin")


class AIOrchestrator:
    def __init__(self, db: Session, user: User, provider=None):
        self.db = db
        self.user = user
        self.policy = AccessPolicy(db, user)
        self.provider = provider or get_llm_provider()
        self.settings = get_settings()

    # ------------------------------------------------------------------ plan execution
    def _run_plan(self, plan: RoutePlan, ctx: ToolContext, query: str, calls: list[ToolCallOut]) -> None:
        def call(name: str, **args) -> None:
            execute_tool(ctx, name, {k: v for k, v in args.items() if v is not None}, calls)

        q = query.lower()
        done: set[str] = set()

        def once(name: str, **args) -> None:
            if name not in done:
                done.add(name)
                call(name, **args)

        for intent in plan.intents:
            if intent == Intent.PATIENT_SUMMARY:
                once("get_patient")
                once("get_patient_timeline", months=24)
                once("get_lab_reports")
                once("get_patient_records", limit=4)
            elif intent == Intent.TREATMENT_CHANGES:
                once("get_patient")
                once("get_patient_timeline", months=36)
                once("get_prescriptions", status="all")
            elif intent == Intent.PATIENT_FACT:
                once("get_patient")
                if any(w in q for w in _LAB_WORDS):
                    once("get_lab_reports")
                if any(w in q for w in _MED_WORDS):
                    once("get_prescriptions", status="active")
            elif intent == Intent.APPOINTMENTS:
                period = "today" if "today" in q else "past" if any(w in q for w in ("past", "previous", "last")) \
                    else "upcoming"
                once("get_appointments", doctor=plan.doctor_name, period=period,
                     patient=plan.mrn if plan.mrn else None)
            elif intent == Intent.DOCUMENT_QA:
                once("search_documents", query=query)
            elif intent == Intent.READMISSION:
                once("get_patient")
                once("predict_readmission")
            elif intent == Intent.LENGTH_OF_STAY:
                once("get_patient")
                once("predict_length_of_stay")
            elif intent == Intent.EXPLAIN_PREDICTION:
                once("get_patient")
                if "length of stay" in q or "los" in q.split():
                    once("predict_length_of_stay")
                else:
                    once("predict_readmission")
                once("get_patient_timeline", months=12)
                once("get_lab_reports")
            elif intent == Intent.GUIDELINE_COMPARISON:
                once("get_patient")
                once("get_lab_reports")
                # A focused retrieval query built from the patient's record works better than the user's
                # "compare ..." phrasing, and only guidance documents (not other reports) are searched.
                pdata = ctx.evidence.data.get("patient", {})
                meds = sorted({m["text"].split()[0] for m in pdata.get("medications", [])})
                problems = [p["text"] for p in pdata.get("problems", [])]
                if any("diabetes" in p.lower() for p in problems):
                    topic = "type 2 diabetes"
                else:
                    topic = problems[0] if problems else ""
                focus = (f"{topic} guideline recommendations for {', '.join(meds)}: dosing, renal limits, "
                         "glycemic targets and monitoring")
                once("search_documents", query=focus.strip(), doc_type="guideline")
            elif intent == Intent.SIMILAR_PATIENTS:
                once("find_similar_patients", k=5)

    # ------------------------------------------------------------------ LLM paths
    def _synthesize(self, plan: RoutePlan, ctx: ToolContext, query: str, patient_label: str | None) -> LLMResult:
        prompt = synthesis_prompt(query, ctx.evidence, patient_label=patient_label,
                                  decision_request=plan.decision_request,
                                  budget_chars=self.settings.llm_context_budget_chars)
        with ctx.timer.stage("llm"):
            return self.provider.chat(SYSTEM_PROMPT, [ChatMessage(role="user", content=prompt)])

    def _agent(self, ctx: ToolContext, query: str, patient_label: str | None,
               calls: list[ToolCallOut]) -> LLMResult:
        specs = [t.spec() for t in tools_for(self.user)]
        intro = f"Patient in context: {patient_label}.\n" if patient_label else ""
        messages = [ChatMessage(role="user", content=f"{intro}<user_query>\n{query}\n</user_query>")]
        usage = [0, 0]
        result: LLMResult | None = None
        fallback_reason: str | None = None
        for _ in range(self.settings.llm_max_tool_rounds):
            with ctx.timer.stage("llm"):
                result = self.provider.chat(SYSTEM_PROMPT + AGENT_ADDENDUM, messages, tools=specs)
            fallback_reason = result.fallback_reason or fallback_reason
            usage[0] += result.prompt_tokens or 0
            usage[1] += result.completion_tokens or 0
            if not result.tool_calls:
                break
            messages.append(ChatMessage(role="assistant", content=result.text, tool_calls=result.tool_calls,
                                        provider_raw=result.raw_content))
            for tc in result.tool_calls:
                if tc.malformed:
                    out_text, is_error = "Tool arguments were not valid JSON; please retry with a JSON object.", True
                    calls.append(ToolCallOut(name=tc.name, arguments={}, status="error", summary="malformed arguments"))
                else:
                    res = execute_tool(ctx, tc.name, tc.arguments, calls)
                    out_text, is_error = res.text, res.status != "ok"
                    cap = self.settings.llm_context_budget_chars // 3  # keep several tool results within budget
                    if len(out_text) > cap:
                        out_text = out_text[:cap] + "\n(... output truncated to fit the context window)"
                messages.append(ChatMessage(role="tool", content=f"<tool_output>\n{out_text}\n</tool_output>",
                                            tool_call_id=tc.id, tool_name=tc.name, is_error=is_error))
        else:
            # Tool budget exhausted: answer with what was gathered, without further tool access.
            with ctx.timer.stage("llm"):
                result = self.provider.chat(SYSTEM_PROMPT, [ChatMessage(role="user", content=synthesis_prompt(
                    query, ctx.evidence, patient_label=patient_label, decision_request=False,
                    budget_chars=self.settings.llm_context_budget_chars))])
            usage[0] += result.prompt_tokens or 0
            usage[1] += result.completion_tokens or 0
        result.prompt_tokens, result.completion_tokens = usage[0] or None, usage[1] or None
        result.fallback_reason = result.fallback_reason or fallback_reason
        return result

    # ------------------------------------------------------------------ entry point
    def run(self, req: AIQueryIn) -> AIResponse:
        timer = StageTimer()
        ev = EvidenceStore()
        calls: list[ToolCallOut] = []
        warnings: list[str] = []
        limitations: list[str] = []
        status, error_code = "ok", None
        patient_id, patient_label = None, None

        with timer.stage("routing"):
            plan = route(req.query, has_patient_context=req.patient_id is not None)
        try:
            if req.patient_id is not None:
                p = self.policy.get_patient(req.patient_id, clinical=False)
                patient_id, patient_label = p.id, f"{p.full_name} ({p.mrn})"
            if plan.mrn:
                p = self.policy.get_patient_by_mrn(plan.mrn, clinical=False)
                patient_id, patient_label = p.id, f"{p.full_name} ({p.mrn})"
        except (NotFoundError, PermissionDeniedError):
            return self._finish(req, plan, ev, calls, timer, "The requested patient was not found or is not "
                                "accessible to you.", "deterministic", None, warnings, limitations,
                                "denied", "patient_not_accessible", patient_id=None, insufficient=False)

        if plan.needs_patient and patient_id is None and plan.confidence == "high":
            return self._finish(req, plan, ev, calls, timer, "Which patient do you mean? Open a patient profile or "
                                "mention an MRN such as P1024.", "deterministic", None, warnings, limitations, "ok",
                                None, patient_id=None, insufficient=False)

        ctx = ToolContext(self.db, self.user, self.policy, patient_id, ev, timer)
        method = "deterministic"
        llm_result: LLMResult | None = None
        insufficient = False
        use_agent = (plan.confidence == "low" and self.provider.supports_tools
                     and self.settings.llm_tool_calling == "auto")
        try:
            if use_agent:
                method = "llm"
                llm_result = self._agent(ctx, req.query, patient_label, calls)
            else:
                with timer.stage("tools"):
                    self._run_plan(plan, ctx, req.query, calls)
                if self.provider.name == "extractive":
                    answer, insufficient, lim = extractive.compose(plan, req.query, ev)
                    limitations += lim
                elif not ev.has_substantive_evidence():
                    statuses = [b.text for b in ev.blocks if b.kind == "tool_status"]
                    answer = "\n\n".join(statuses) if statuses else INSUFFICIENT
                    insufficient = not statuses
                elif Intent.DOCUMENT_QA in plan.intents and not ev.sources and len(plan.intents) == 1:
                    answer, insufficient = INSUFFICIENT, True  # nothing retrieved: do not let the LLM improvise
                else:
                    llm_result = self._synthesize(plan, ctx, req.query, patient_label)
        except LLMError as exc:
            warnings.append(f"The language model is unavailable ({exc.message}); showing an extractive answer instead.")
            status, error_code = "degraded", exc.code
            if not ev.blocks:
                with timer.stage("tools"):
                    self._run_plan(plan, ctx, req.query, calls)
            llm_result = None
            answer, insufficient, lim = extractive.compose(plan, req.query, ev)
            limitations += lim
        if llm_result is not None:
            answer = llm_result.text or INSUFFICIENT
            if llm_result.stop_reason == "refusal":
                warnings.append("The language model declined this request.")
            if llm_result.fallback_reason:
                # Silent to the user by design: the backup is an equivalent model. Operators see it in the
                # trace (provider column), the logs and careflow_component_errors_total{component="llm_primary"}.
                logger.info("answer generated by backup LLM", extra={"fields": {
                    "provider": llm_result.provider, "reason": llm_result.fallback_reason}})
            answered_by = llm_result.provider or self.provider.name
            if llm_result.prompt_tokens:
                LLM_TOKENS.labels(answered_by, "prompt").inc(llm_result.prompt_tokens)
            if llm_result.completion_tokens:
                LLM_TOKENS.labels(answered_by, "completion").inc(llm_result.completion_tokens)
        return self._finish(req, plan, ev, calls, timer, answer, method, llm_result, warnings, limitations, status,
                            error_code, patient_id=patient_id, insufficient=insufficient)

    def _finish(self, req, plan, ev, calls, timer, answer, method, llm_result, warnings, limitations, status,
                error_code, *, patient_id, insufficient) -> AIResponse:
        with timer.stage("grounding"):
            answer, used, removed = validate_citations(answer, ev.valid_ids)
            answer, redacted = redact_unauthorized_mrns(answer, self.db, self.policy)
        if removed:
            warnings.append(f"Removed {removed} citation(s) that did not match any retrieved source.")
        if redacted:
            warnings.append("Identifiers of patients outside your access were redacted from the answer.")
        if ev.withheld_sources:
            titles = sorted({w["document_title"] for w in ev.withheld_sources})
            warnings.append(f"{len(ev.withheld_sources)} retrieved passage(s) were withheld because they contain "
                            f"instruction-like text (possible prompt injection): {', '.join(titles)}.")
        if plan.decision_request:
            warnings.append("This assistant does not make clinical decisions; the information above supports, "
                            "but does not replace, the treating clinician's judgement.")
        if INSUFFICIENT in answer:
            insufficient = True
        if ev.predictions:
            limitations.append(ML_DISCLAIMER)
        if method == "llm":
            caps = []
            for c in calls:
                cap = TOOLS[c.name].capability if c.name in TOOLS else None
                if cap and cap not in caps:
                    caps.append(cap)
            capabilities = caps + ["LLM"]
            intents = ["llm_tool_selection"]
        else:
            capabilities = plan.capabilities if self.provider.name != "extractive" else \
                [c for c in plan.capabilities if c != "LLM"] or ["SQL"]
            intents = [i.value for i in plan.intents]
        citations = [ev.citation(i) for i in used if i.startswith("S")]
        record_refs = [ev.records[i] for i in used if i.startswith("R")]
        # Report who actually wrote the answer: the backup after a fallback, "extractive" when no model did.
        model = llm_result.model if llm_result else None
        provider = (llm_result.provider or self.provider.name) if llm_result else "extractive"
        AI_QUERIES.labels(" + ".join(capabilities), status).inc()
        self._trace(req, capabilities, method, status, error_code, timer, ev, calls, used, llm_result, model, provider)
        audit("ai.query", user=self.user, outcome="denied" if status == "denied" else "success",
              resource_type="patient" if patient_id else None, resource_id=patient_id, patient_id=patient_id,
              details={"route": capabilities, "tools": [c.name for c in calls],
                       "patients_touched": sorted(ev.patient_ids)[:20],
                       "sources": [ev.sources[i].chunk_id for i in used if i.startswith("S")]})
        return AIResponse(
            answer=answer, route=capabilities, routing_method=method, intents=intents, patient_id=patient_id,
            citations=citations, record_refs=record_refs, predictions=ev.predictions, similarity=ev.similarity,
            tool_calls=calls, warnings=warnings, limitations=limitations, insufficient_context=insufficient,
            provider=provider, model=model, stage_ms={**timer.stages, "total": timer.total_ms},
            retrieval={**ev.retrieval, "context_source_ids": [c.chunk_id for c in ev.sources.values()],
                       "withheld": ev.withheld_sources},
            request_id=request_id_var.get(), created_at=datetime.now(UTC), disclaimer=DISCLAIMER)

    def _trace(self, req, capabilities, method, status, error_code, timer, ev, calls, used, llm_result, model,
               provider) -> None:
        try:
            self.db.add(AIQueryTrace(
                user_id=self.user.id, request_id=request_id_var.get(),
                query_hash=hashlib.sha256(req.query.encode()).hexdigest(), query_length=len(req.query),
                route=" + ".join(capabilities), routing_method=method, provider=provider,
                llm_model=model, status=status, error_code=error_code, total_ms=timer.total_ms,
                stage_ms=timer.stages, retrieved_chunk_ids=[c.chunk_id for c in ev.sources.values()],
                cited_source_ids=[ev.sources[i].chunk_id for i in used if i.startswith("S")],
                tool_calls=[{"name": c.name, "status": c.status, "ms": c.ms} for c in calls],
                model_versions=ev.model_versions,
                prompt_tokens=llm_result.prompt_tokens if llm_result else None,
                completion_tokens=llm_result.completion_tokens if llm_result else None))
            self.db.flush()
        except Exception:
            logger.exception("failed to persist AI trace")


__all__ = ["AIOrchestrator", "render_evidence"]
