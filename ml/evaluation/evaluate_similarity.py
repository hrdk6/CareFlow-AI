"""Patient-similarity validation (no ground-truth "similar" labels exist, so we test proxies).

    uv run --project backend python -m ml.evaluation.evaluate_similarity [--k 5]

Validation strategy
  1. Clinical coherence: do neighbours share the query patient's primary department and diagnosis
     groups more often than random patients do? (agreement@k vs a random-pair baseline)
  2. Outcome concordance (a signal NOT used in the representation): is a neighbour cohort's 30-day
     readmission rate higher for patients who were themselves readmitted?
  3. Ablations: block weighting vs unweighted features; cosine vs euclidean distance.
Runs on the synthetic demo hospital, so results characterise the method on synthetic data only.
"""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sqlalchemy import select

from app.db.session import get_session_factory
from app.ml import similarity as sim
from app.models import Admission, Patient

REPORTS = Path(__file__).resolve().parent / "reports"


def readmitted_flags(db) -> dict[int, bool]:
    stays: dict[int, list] = {}
    for pid, a, d in db.execute(select(Admission.patient_id, Admission.admitted_at, Admission.discharged_at)
                                .order_by(Admission.admitted_at)):
        stays.setdefault(pid, []).append((a, d))
    flags = {}
    for pid, s in stays.items():
        flags[pid] = any(d is not None and i + 1 < len(s) and (s[i + 1][0] - d).days <= 30
                         for i, (_, d) in enumerate(s))
    return flags


def neighbours(X: np.ndarray, k: int, metric: str) -> np.ndarray:
    if metric == "cosine":
        norm = X / np.clip(np.linalg.norm(X, axis=1, keepdims=True), 1e-12, None)
        dist = 1 - norm @ norm.T
    else:
        dist = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=2)
    np.fill_diagonal(dist, np.inf)
    return np.argsort(dist, axis=1)[:, :k]


def score(ids, idx, depts, dx_sets, readm) -> dict:
    n, k = idx.shape
    dept_agree = np.mean([[depts[ids[j]] == depts[ids[i]] for j in idx[i]] for i in range(n)])
    jacc = np.mean([[len(dx_sets[ids[i]] & dx_sets[ids[j]]) / max(1, len(dx_sets[ids[i]] | dx_sets[ids[j]]))
                     for j in idx[i]] for i in range(n)])
    cohort_rate = np.array([np.mean([readm.get(ids[j], False) for j in idx[i]]) for i in range(n)])
    own = np.array([readm.get(ids[i], False) for i in range(n)])
    return {"department_agreement": round(float(dept_agree), 4), "diagnosis_jaccard": round(float(jacc), 4),
            "neighbour_readmission_rate_if_readmitted": round(float(cohort_rate[own].mean()), 4) if own.any() else None,
            "neighbour_readmission_rate_if_not": round(float(cohort_rate[~own].mean()), 4)}


def main(k: int) -> dict:
    rng = np.random.default_rng(0)
    with get_session_factory()() as db:
        profiles = sim.patient_profiles(db)
        ids = sorted(profiles)
        depts = dict(db.execute(select(Patient.id, Patient.primary_department_id)).all())
        readm = readmitted_flags(db)
    dx_sets = {pid: set(profiles[pid]["diagnosis_categories"]) for pid in ids}
    X = np.array([sim.vectorize(profiles[p]) for p in ids])
    saved = dict(sim.WEIGHTS)
    sim.WEIGHTS.update({key: 1.0 for key in sim.WEIGHTS})
    X_unweighted = np.array([sim.vectorize(profiles[p]) for p in ids])
    sim.WEIGHTS.update(saved)

    random_idx = np.array([rng.choice([j for j in range(len(ids)) if j != i], size=k, replace=False)
                           for i in range(len(ids))])
    result = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "patients": len(ids), "k": k,
        "representation_version": sim.REPRESENTATION_VERSION, "dimensions": len(sim.FEATURE_NAMES),
        "overall_readmission_rate": round(float(np.mean([readm.get(p, False) for p in ids])), 4),
        "variants": {
            "weighted_cosine (deployed)": score(ids, neighbours(X, k, "cosine"), depts, dx_sets, readm),
            "unweighted_cosine": score(ids, neighbours(X_unweighted, k, "cosine"), depts, dx_sets, readm),
            "weighted_euclidean": score(ids, neighbours(X, k, "euclidean"), depts, dx_sets, readm),
            "random_baseline": score(ids, random_idx, depts, dx_sets, readm),
        },
        "note": "Synthetic demo data; proxies for similarity quality, not clinical validation.",
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "similarity_latest.json").write_text(json.dumps(result, indent=2))
    lines = [f"# Patient similarity evaluation ({result['generated_at']})", "",
             f"{result['patients']} synthetic patients, k = {k}, representation {result['representation_version']} "
             f"({result['dimensions']} dims). Overall 30-day readmission rate: {result['overall_readmission_rate']:.3f}.",
             "", "| Variant | Dept agreement@k | Diagnosis Jaccard | Neighbour readmit rate (patient readmitted) "
                 "| Neighbour readmit rate (not readmitted) |", "|---|---|---|---|---|"]
    for name, v in result["variants"].items():
        lines.append(f"| {name} | {v['department_agreement']:.3f} | {v['diagnosis_jaccard']:.3f} | "
                     f"{v['neighbour_readmission_rate_if_readmitted']} | {v['neighbour_readmission_rate_if_not']} |")
    lines += ["", result["note"]]
    (REPORTS / "similarity_latest.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    main(ap.parse_args().k)
