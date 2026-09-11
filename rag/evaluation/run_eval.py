"""RAG evaluation: vector-only vs BM25 vs hybrid vs hybrid + cross-encoder reranking.

    uv run --project backend python -m rag.evaluation.run_eval [--k 6]

Runs against the configured database (the indexed demo corpus, real embeddings) as the admin user.
The answer generator is held constant across modes (the extractive composer: cross-encoder sentence
selection with citations), so differences in answer metrics come from retrieval alone.

Metrics
  recall@1/3/5    an expected (document, section) is among the top-k chunks
  mrr             reciprocal rank of the first expected chunk
  context_prec    share of the k context chunks that come from an expected document
  answer_correct  the answer contains the benchmark's key facts (string criteria)
  faithfulness    share of answer statements whose content words appear in the passage they cite
  citation_prec   share of citations that point to an expected document
  citation_hit    at least one citation points to an expected source
  abstention      unanswerable questions answered with "insufficient information"
"""
import argparse
import json
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.auth.access import AccessPolicy
from app.db.session import get_session_factory
from app.llm.evidence import EvidenceStore
from app.llm.extractive import _documents
from app.llm.prompts import INSUFFICIENT
from app.models import Document, User
from app.rag.bm25 import tokenize
from app.rag.retrieval import HybridRetriever

HERE = Path(__file__).resolve().parent
MODES = ["vector", "keyword", "hybrid", "hybrid_rerank"]


def load_benchmark() -> list[dict]:
    return [json.loads(line) for line in (HERE / "benchmark.jsonl").read_text().splitlines() if line.strip()]


def is_expected(chunk, doc_keys: dict[int, str], expected: list[dict]) -> bool:
    key = doc_keys.get(chunk.document_id)
    for e in expected:
        leaf = chunk.section_path.split(" > ")[-1] if chunk.section_path else ""
        if key == e["doc_key"] and (leaf.startswith(e["section"]) or f"> {e['section']}" in chunk.section_path):
            return True
    return False


def criteria_met(answer: str, criteria: dict) -> bool:
    if criteria.get("abstain"):
        return INSUFFICIENT in answer
    low = answer.lower()
    if "all" in criteria:
        return all(c.lower() in low for c in criteria["all"])
    return any(c.lower() in low for c in criteria.get("any", []))


def faithfulness(answer: str, ev: EvidenceStore) -> float | None:
    statements = [s for s in answer.split("\n") if re.search(r"\[S\d+\]", s)]
    if not statements:
        return None
    supported = 0
    for s in statements:
        cited = re.findall(r"\[(S\d+)\]", s)
        words = set(tokenize(re.sub(r"\[S\d+\]", "", s)))
        context = set().union(*(tokenize(ev.sources[c].text) for c in cited if c in ev.sources))
        if words and len(words & context) / len(words) >= 0.8:
            supported += 1
    return supported / len(statements)


def evaluate(k: int) -> dict:
    Session = get_session_factory()
    bench = load_benchmark()
    with Session() as db:
        admin = db.scalar(select(User).where(User.email == "admin@careflow.demo"))
        policy = AccessPolicy(db, admin)
        doc_keys = dict(db.execute(select(Document.id, Document.doc_key)).all())
        retriever = HybridRetriever(db, policy)
        rows = {m: [] for m in MODES}
        for item in bench:
            for mode in MODES:
                t0 = time.perf_counter()
                res = retriever.retrieve(item["question"], mode=mode, top_k=k)
                ms = (time.perf_counter() - t0) * 1000
                ev = EvidenceStore()
                kept = [(ev.ref_chunk(c), c) for c in res.chunks if not c.flags.get("injection_suspected")]
                ev.data["chunks"] = kept
                lines, _ = _documents(item["question"], ev)
                answer = "\n".join(lines)
                cited = re.findall(r"\[(S\d+)\]", answer)
                cited_chunks = [ev.sources[c] for c in dict.fromkeys(cited) if c in ev.sources]
                hits = [i for i, c in enumerate(res.chunks) if is_expected(c, doc_keys, item["expected"])]
                expected_docs = {e["doc_key"] for e in item["expected"]}
                row = {"id": item["id"], "category": item["category"], "latency_ms": round(ms, 1),
                       "answer_correct": criteria_met(answer, item["criteria"])}
                if item["expected"]:
                    row.update({
                        "recall@1": any(i < 1 for i in hits), "recall@3": any(i < 3 for i in hits),
                        "recall@5": any(i < 5 for i in hits), "mrr": 1 / (hits[0] + 1) if hits else 0.0,
                        "context_prec": (sum(doc_keys[c.document_id] in expected_docs for c in res.chunks)
                                         / len(res.chunks)) if res.chunks else 0.0,
                        "faithfulness": faithfulness(answer, ev),
                        "citation_prec": (sum(doc_keys[c.document_id] in expected_docs for c in cited_chunks)
                                          / len(cited_chunks)) if cited_chunks else None,
                        "citation_hit": any(is_expected(c, doc_keys, item["expected"]) for c in cited_chunks),
                    })
                rows[mode].append(row)
        return summarise(rows, k, len(bench))


def _mean(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.mean(vals), 4) if vals else None


def summarise(rows: dict, k: int, n: int) -> dict:
    summary = {}
    for mode, rs in rows.items():
        ans = [r for r in rs if r["category"] != "unanswerable"]
        una = [r for r in rs if r["category"] == "unanswerable"]
        summary[mode] = {
            "recall@1": _mean(r["recall@1"] for r in ans), "recall@3": _mean(r["recall@3"] for r in ans),
            "recall@5": _mean(r["recall@5"] for r in ans), "mrr": _mean(r["mrr"] for r in ans),
            "context_precision": _mean(r["context_prec"] for r in ans),
            "answer_correctness": _mean(r["answer_correct"] for r in ans),
            "faithfulness": _mean(r["faithfulness"] for r in ans),
            "citation_precision": _mean(r["citation_prec"] for r in ans),
            "citation_hit_rate": _mean(r["citation_hit"] for r in ans),
            "abstention_accuracy": _mean(r["answer_correct"] for r in una),
            "latency_ms_p50": round(statistics.median(r["latency_ms"] for r in rs), 1),
            "by_category": {cat: {"n": len(g), "recall@5": _mean(r["recall@5"] for r in g),
                                  "answer_correctness": _mean(r["answer_correct"] for r in g)}
                            for cat in sorted({r["category"] for r in ans})
                            for g in [[r for r in ans if r["category"] == cat]]},
        }
    return {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "k": k, "questions": n,
            "answerable": sum(1 for r in rows[MODES[0]] if r["category"] != "unanswerable"),
            "modes": summary, "per_question": rows}


def write_report(result: dict) -> Path:
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "latest.json").write_text(json.dumps(result, indent=2))
    cols = [("recall@1", "R@1"), ("recall@3", "R@3"), ("recall@5", "R@5"), ("mrr", "MRR"),
            ("context_precision", "Ctx prec"), ("answer_correctness", "Answer"), ("faithfulness", "Faithful"),
            ("citation_precision", "Cite prec"), ("citation_hit_rate", "Cite hit"),
            ("abstention_accuracy", "Abstain"), ("latency_ms_p50", "p50 ms")]
    lines = [f"# RAG evaluation ({result['generated_at']})", "",
             f"{result['questions']} questions ({result['answerable']} answerable, "
             f"{result['questions'] - result['answerable']} unanswerable); top-k = {result['k']}. "
             "Same extractive answer generator for every mode.", "",
             "| Mode | " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for mode, m in result["modes"].items():
        lines.append(f"| {mode} | " + " | ".join("-" if m[c] is None else f"{m[c]:.3f}" if c != "latency_ms_p50"
                                                  else f"{m[c]:.0f}" for c, _ in cols) + " |")
    lines += ["", "## Recall@5 by question category", "", "| Category | " + " | ".join(result["modes"]) + " |",
              "|" + "---|" * (len(result["modes"]) + 1)]
    cats = next(iter(result["modes"].values()))["by_category"]
    for cat in cats:
        lines.append(f"| {cat} (n={cats[cat]['n']}) | " + " | ".join(
            f"{result['modes'][m]['by_category'][cat]['recall@5']:.2f}" for m in result["modes"]) + " |")
    path = out / "latest.md"
    path.write_text("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=6)
    res = evaluate(ap.parse_args().k)
    print(write_report(res).read_text())
