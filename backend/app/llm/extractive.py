"""Extractive answer composer - the no-LLM mode.

Builds answers ONLY from structured evidence and verbatim document sentences, every line carrying a
citation. Document answers select sentences with the cross-encoder (query, sentence) scores, falling
back to lexical overlap if the reranker is unavailable. It cannot reason, compare or paraphrase;
answers say so where an LLM would add synthesis.
"""
import re

from app.llm.evidence import EvidenceStore
from app.llm.prompts import INSUFFICIENT
from app.rag.bm25 import tokenize
from app.rag.reranking import RerankerError, get_reranker
from app.routing.router import Intent, RoutePlan

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
FOOTER = "_Extractive mode: assembled from retrieved records and passages without a language model._"


def _best_sentences(query: str, ev: EvidenceStore, max_sentences: int = 6,
                    per_chunk: int = 2) -> list[tuple[str, str]]:
    """Pick the sentences that best answer the query.

    Sentences are scored WITH their section path ("4. Monitoring > 4.1 HbA1c monitoring: Measure HbA1c
    every 3 months...") because a bare sentence often lacks the words that make it relevant. The chunk's
    own rerank score is blended in, and at most `per_chunk` sentences are taken per passage for coverage.
    """
    candidates: list[tuple[str, str, int, str, float]] = []
    for rank, (sid, chunk) in enumerate(ev.data.get("chunks", [])):
        for sentence in _SENT.split(chunk.text):
            s = sentence.strip()
            if 6 <= len(s.split()) <= 90 and not s.upper().startswith("SYNTHETIC DEMONSTRATION"):
                context = f"{chunk.document_title}. {chunk.section_path}: {s}"
                candidates.append((sid, s, rank, context, chunk.rerank_score or 0.0))
    if not candidates:
        return []
    try:
        reranker = get_reranker()
        raw = reranker.score(query, [c[3] for c in candidates])
        scores = [r + 0.5 * c[4] for r, c in zip(raw, candidates, strict=True)]
        threshold = -3.0 if reranker.name != "none" else float("-inf")
    except RerankerError:
        q = set(tokenize(query))
        scores = [len(q & set(tokenize(c[3]))) / (1 + len(q)) for c in candidates]
        threshold = 0.2
    ranked = sorted(zip(candidates, scores, strict=True), key=lambda x: -x[1])
    chosen, taken = [], {}
    for cand, score in ranked:
        if score < threshold or len(chosen) >= max_sentences:
            break
        if taken.get(cand[0], 0) >= per_chunk:
            continue
        taken[cand[0]] = taken.get(cand[0], 0) + 1
        chosen.append(cand)
    chosen.sort(key=lambda c: (c[2], candidates.index(c)))  # keep retrieval/document order for readability
    return [(sid, s) for sid, s, *_ in chosen]


def _patient_header(ev: EvidenceStore) -> list[str]:
    p = ev.data.get("patient")
    if not p:
        return []
    sex = {"F": "female", "M": "male"}.get(p["sex"], "patient")
    return [f"**{p['name']} ({p['mrn']})**, {p['age']}-year-old {sex}, status {p['status']} [{p['ref']}]."]


def _trend(ev: EvidenceStore, code: str, label: str) -> str | None:
    series = ev.data.get("labs", {}).get(code)
    if not series:
        return None
    latest, oldest = series[0], series[-1]
    if len(series) == 1:
        return f"{label} {latest['value']:g} {latest['unit']} on {latest['date']} [{latest['ref']}]"
    return (f"{label} {oldest['value']:g} → {latest['value']:g} {latest['unit']} ({oldest['date']} to "
            f"{latest['date']}) [{oldest['ref']}][{latest['ref']}]")


def _summary(ev: EvidenceStore) -> list[str]:
    out = _patient_header(ev)
    p = ev.data.get("patient", {})
    if p.get("problems"):
        out.append("**Active problems:** " + "; ".join(f"{x['text']} (since {x['since'][:4]}) [{x['ref']}]"
                                                      for x in p["problems"]))
    if p.get("medications"):
        out.append("**Current medications:** " + "; ".join(f"{m['text']} [{m['ref']}]" for m in p["medications"]))
    timeline = ev.data.get("timeline", [])
    admissions = [e for e in timeline if e["category"] == "admission"]
    if admissions:
        out.append("**Admissions in the period:**")
        out += [f"- {e['date']}: {e['title']} [{e['ref']}]" for e in admissions[:6]]
    trends = [t for t in (_trend(ev, "HBA1C", "HbA1c"), _trend(ev, "EGFR", "eGFR")) if t]
    if trends:
        out.append("**Key results:** " + "; ".join(trends) + ".")
    changes = [e for e in timeline if e["category"] in ("medication_change", "medication_start", "medication_stop")]
    if changes:
        out.append("**Recent treatment changes:**")
        out += [f"- {e['date']}: {e['title']}" + (f" ({e['detail']})" if e["detail"] else "") + f" [{e['ref']}]"
                for e in changes[:5]]
    upcoming = [e for e in timeline if e["category"] == "appointment"]
    if upcoming:
        out.append(f"**Next appointment:** {upcoming[-1]['date']} - {upcoming[-1]['title']} [{upcoming[-1]['ref']}]")
    return out


def _treatment_changes(ev: EvidenceStore) -> list[str]:
    out = _patient_header(ev)
    events = [e for e in ev.data.get("timeline", [])
              if e["category"] in ("medication_change", "medication_start", "medication_stop")]
    if not events:
        return out + ["No outpatient medication changes were recorded in the period."]
    out.append("**Medication starts, changes and stops (newest first):**")
    out += [f"- {e['date']}: {e['title']}" + (f" - {e['detail']}" if e["detail"] else "") + f" [{e['ref']}]"
            for e in events[:12]]
    return out


def _fact(query: str, ev: EvidenceStore) -> list[str]:
    out = _patient_header(ev)
    p = ev.data.get("patient", {})
    q = query.lower()
    if not p.get("clinical", True):
        return out + ["Clinical information is not available to your role."]
    if "allerg" in q:
        blk = next((b.text for b in ev.blocks if b.title.startswith("Patient")), "")
        m = re.search(r"Allergies: (.*?)\.", blk)
        out.append(f"**Allergies:** {m.group(1) if m else 'none recorded'} [{p['ref']}]")
    if re.search(r"medic|meds|prescri|drug", q) and p.get("medications"):
        out.append("**Current medications:** " + "; ".join(f"{m['text']} [{m['ref']}]" for m in p["medications"]))
    if re.search(r"diagnos|condition|problem", q) and p.get("problems"):
        out.append("**Active problems:** " + "; ".join(f"{x['text']} [{x['ref']}]" for x in p["problems"]))
    for code, name in (("HBA1C", "HbA1c"), ("EGFR", "eGFR"), ("GLU", "Glucose"), ("K", "Potassium"),
                       ("LDL", "LDL"), ("CREAT", "Creatinine"), ("BNP", "BNP"), ("INR", "INR")):
        if re.search(rf"\b{name.lower()}\b|\b{code.lower()}\b", q) or (code == "HBA1C" and "a1c" in q):
            t = _trend(ev, code, name)
            if t:
                out.append(f"**{name}:** {t}")
    if re.search(r"admi|discharg|hospital", q) and p.get("last_admission"):
        la = p["last_admission"]
        out.append(f"**Most recent admission:** {la['text']} [{la['ref']}]")
    if len(out) <= 1 and p.get("problems"):
        out.append("**Active problems:** " + "; ".join(f"{x['text']} [{x['ref']}]" for x in p["problems"]))
    return out


def _prediction(ev: EvidenceStore, key: str, explain: bool) -> list[str]:
    item = ev.data.get(key)
    if not item:
        return []
    pred, ref = item["prediction"], item["ref"]
    if pred.status != "ok":
        return [f"{'Readmission' if key == 'readmission' else 'Length-of-stay'} prediction: {pred.reason}"]
    cite = f" [{ref}]" if ref else ""
    if key == "readmission":
        ratio = pred.value / pred.context["base_rate"]
        out = [f"**Model estimate:** {pred.value:.1%} probability of readmission within 30 days of the admission "
               f"for *{pred.reference.reason}*{cite} - {ratio:.1f}× the average rate in the training data "
               f"({pred.context['base_rate']:.1%}); risk band **{pred.label}**, "
               f"{'above' if pred.flagged else 'below'} the model's alert threshold of {pred.threshold:.1%}. "
               f"(`{pred.model_name}` v{pred.model_version}, {pred.model_algorithm})"]
    else:
        actual = pred.reference.actual_length_of_stay_days
        out = [f"**Model estimate:** {pred.value:.1f} days (80% interval {pred.interval[0]}-{pred.interval[1]} days) "
               f"for the admission{cite}" + (f"; the actual stay was {actual} days" if actual is not None else "")
               + f". (`{pred.model_name}` v{pred.model_version}, test MAE {pred.context['test_mae_days']} days)"]
    if explain or key == "readmission":
        out.append("**Factors that contributed most to the model's prediction:**")
        out += [f"- {f.label} = {f.value} contributed toward a {'higher' if f.direction == 'up' else 'lower'} "
                f"predicted {'risk' if key == 'readmission' else 'stay'} ({f.contribution:+.3f})" for f in pred.factors[:5]]
        out.append("These attributions describe how the model reached its estimate; they are not causes of "
                   "readmission.")
    out += [f"_Note: {n}_" for n in pred.notes]
    return out


def _appointments(ev: EvidenceStore) -> list[str]:
    appts = ev.data.get("appointments", [])
    if not appts:
        return ["No matching appointments were found."]
    return ["**Appointments:**"] + [f"- {a['when']} UTC - {a['patient']} ({a['mrn']}) with {a['doctor']}: {a['reason']} "
                                    f"({a['status']}) [{a['ref']}]" for a in appts[:15]]


def _documents(query: str, ev: EvidenceStore) -> tuple[list[str], bool]:
    picked = _best_sentences(query, ev)
    if not picked:
        return [INSUFFICIENT], True
    out = ["**From hospital documents:**"]
    out += [f"- {s} [{sid}]" for sid, s in picked]
    return out, False


def _similar(ev: EvidenceStore) -> list[str]:
    item = ev.data.get("similar")
    if not item or not item["out"].results:
        return ["No similar patients were found among the patients you can access."]
    sim, refs = item["out"], item["refs"]
    out = ["**Most similar patients** (structured-profile similarity; you are only shown patients you may access):"]
    for r, rid in zip(sim.results, refs, strict=True):
        out.append(f"- {r.full_name} ({r.mrn}), {r.age:.0f}y, similarity {r.similarity:.2f}; shared: "
                   f"{', '.join(r.shared_diagnosis_categories) or 'none'}; {r.admissions_2y} admission(s) in 2 years [{rid}]")
    cp = sim.cohort_patterns
    if cp:
        rate = f"{cp['readmission_rate']:.0%}" if cp["readmission_rate"] is not None else "n/a"
        out.append(f"**Historical patterns in this cohort:** {cp['discharges']} discharges, "
                   f"{cp['readmissions_within_30d']} followed by a 30-day readmission ({rate}); mean length of stay "
                   f"{cp['mean_length_of_stay_days']} days. Most common active medications: "
                   + ", ".join(m["medication"] for m in cp["common_active_medications"][:4]) + ".")
    out.append(f"_{sim.disclaimer}_")
    return out


def compose(plan: RoutePlan, query: str, ev: EvidenceStore) -> tuple[str, bool, list[str]]:
    """Return (markdown answer, insufficient_context, limitations)."""
    lines: list[str] = []
    insufficient = False
    limitations: list[str] = []
    statuses = [b for b in ev.blocks if b.kind == "tool_status"]
    if statuses and not ev.has_substantive_evidence():
        return "\n\n".join(b.text for b in statuses), False, []
    for intent in plan.intents:
        if intent == Intent.PATIENT_SUMMARY:
            lines += _summary(ev)
        elif intent == Intent.TREATMENT_CHANGES:
            lines += _treatment_changes(ev)
        elif intent == Intent.PATIENT_FACT:
            lines += _fact(query, ev)
        elif intent == Intent.APPOINTMENTS:
            lines += _appointments(ev)
        elif intent == Intent.DOCUMENT_QA:
            doc_lines, insufficient = _documents(query, ev)
            lines += doc_lines
        elif intent in (Intent.READMISSION, Intent.EXPLAIN_PREDICTION):
            if not lines:
                lines += _patient_header(ev)
            lines += _prediction(ev, "readmission", explain=intent == Intent.EXPLAIN_PREDICTION)
            if intent == Intent.EXPLAIN_PREDICTION:
                admissions = [e for e in ev.data.get("timeline", []) if e["category"] == "admission"]
                if ev.data.get("patient", {}).get("last_admission"):
                    la = ev.data["patient"]["last_admission"]
                    lines.append(f"**Relevant record:** most recent admission {la['text']} [{la['ref']}]")
                lines += [f"- {e['date']}: {e['title']} [{e['ref']}]" for e in admissions[:4]]
        elif intent == Intent.LENGTH_OF_STAY:
            lines += _prediction(ev, "los", explain=False)
        elif intent == Intent.GUIDELINE_COMPARISON:
            lines += _patient_header(ev)
            p = ev.data.get("patient", {})
            if p.get("medications"):
                lines.append("**Current treatment (patient record):** " + "; ".join(
                    f"{m['text']} [{m['ref']}]" for m in p["medications"]))
            trends = [t for t in (_trend(ev, "HBA1C", "HbA1c"), _trend(ev, "EGFR", "eGFR"),
                                  _trend(ev, "UACR", "UACR")) if t]
            if trends:
                lines.append("**Relevant results:** " + "; ".join(trends))
            meds = sorted({m["text"].split()[0] for m in p.get("medications", [])})
            doc_lines, insufficient = _documents(f"Recommendations for {', '.join(meds)}, glycemic targets and "
                                                 "kidney monitoring", ev)
            lines += doc_lines
            limitations.append("A point-by-point comparison requires an LLM provider; extractive mode shows the patient's "
                               "treatment next to the most relevant guideline passages for clinician review.")
        elif intent == Intent.SIMILAR_PATIENTS:
            lines += _similar(ev)
        elif intent == Intent.GENERAL:
            lines.append("I can summarise authorized patient records and timelines, answer questions from hospital "
                         "guidelines and policies with citations, show readmission and length-of-stay model estimates "
                         "with explanations, find similar patients, and list appointments. Open a patient profile or "
                         "mention an MRN such as P1024 for patient questions.")
    if statuses:
        lines += [f"_{b.text}_" for b in statuses]
    if not lines:
        lines, insufficient = [INSUFFICIENT], True
    return "\n\n".join(lines) + "\n\n" + FOOTER, insufficient, limitations
