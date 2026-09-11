"""Train and select the 30-day readmission classifier.

    uv run --project backend python -m ml.training.train_readmission [--version 1.0.0] [--force]

Pipeline: load -> clean -> contract features -> patient-grouped split (70/15/15)
-> baseline + candidates (LR / RF / XGBoost x {no weighting, class weighting})
-> select on VALIDATION PR-AUC -> isotonic calibration on validation -> F1-optimal threshold
-> single evaluation on the untouched TEST split -> leakage ablation -> artifact + model card.
"""
import argparse
import time

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.ml.explain import global_importance
from app.ml.feature_contract import FEATURE_LABELS, READMISSION_FEATURES
from ml.evaluation.report import write_readmission_report
from ml.preprocessing.uci_diabetes import grouped_split, load_and_prepare
from ml.training.common import (
    SEED,
    best_f1_threshold,
    build_pipeline,
    classification_metrics,
    save_artifact,
)

MODEL_NAME = "readmission_30d"


def candidates(pos_weight: float):
    xgb_params = dict(n_estimators=500, learning_rate=0.03, max_depth=4, subsample=0.8, colsample_bytree=0.8,
                      min_child_weight=5, reg_lambda=1.0, tree_method="hist", n_jobs=-1, random_state=SEED)
    rf_params = dict(n_estimators=300, min_samples_leaf=25, max_features="sqrt", n_jobs=-1, random_state=SEED)
    return [
        ("logistic_regression", "none", LogisticRegression(max_iter=3000)),
        ("logistic_regression", "class_weight", LogisticRegression(max_iter=3000, class_weight="balanced")),
        ("random_forest", "none", RandomForestClassifier(**rf_params)),
        ("random_forest", "class_weight", RandomForestClassifier(**rf_params, class_weight="balanced_subsample")),
        ("xgboost", "none", XGBClassifier(**xgb_params)),
        ("xgboost", "class_weight", XGBClassifier(**xgb_params, scale_pos_weight=pos_weight)),
    ]


def main(version: str, force: bool) -> None:
    data = load_and_prepare()
    fs = READMISSION_FEATURES
    X = data.features[list(fs.all)]
    y = data.readmitted_30d.to_numpy()
    tr, va, te = grouped_split(data.groups, seed=SEED)
    assert not set(data.groups.iloc[tr]) & set(data.groups.iloc[te]), "patient leakage between splits"
    pos_weight = float((y[tr] == 0).sum() / (y[tr] == 1).sum())
    print(f"rows={len(X)} train={len(tr)} val={len(va)} test={len(te)} prevalence={y.mean():.4f}")

    # Baseline: predicts the training prevalence for everyone.
    base = build_pipeline(list(fs.numeric), list(fs.categorical), DummyClassifier(strategy="prior"))
    base.fit(X.iloc[tr], y[tr])
    baseline_val = classification_metrics(y[va], base.predict_proba(X.iloc[va])[:, 1], 0.5)

    results, fitted = [], {}
    for algo, imbalance, est in candidates(pos_weight):
        pipe = build_pipeline(list(fs.numeric), list(fs.categorical), est)
        t0 = time.perf_counter()
        pipe.fit(X.iloc[tr], y[tr])
        fit_s = time.perf_counter() - t0
        p_val = pipe.predict_proba(X.iloc[va])[:, 1]
        thr = best_f1_threshold(y[va], p_val)
        val = classification_metrics(y[va], p_val, thr)
        test = classification_metrics(y[te], pipe.predict_proba(X.iloc[te])[:, 1], thr)
        key = f"{algo}:{imbalance}"
        fitted[key] = pipe
        results.append({"candidate": key, "algorithm": algo, "imbalance": imbalance,
                        "fit_seconds": round(fit_s, 1), "validation": val, "test": test})
        print(f"{key:36s} val PR-AUC={val['pr_auc']:.4f} ROC-AUC={val['roc_auc']:.4f} ({fit_s:.1f}s)")

    # Model selection uses validation only; ties broken toward the simpler model (list order).
    best = max(results, key=lambda r: r["validation"]["pr_auc"])
    pipe = fitted[best["candidate"]]
    print(f"selected: {best['candidate']}")

    # Probability calibration (isotonic, fitted on validation) so that "0.25" means ~25% observed rate.
    raw_val = pipe.predict_proba(X.iloc[va])[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw_val, y[va])
    cal_val = calibrator.predict(raw_val)
    threshold = best_f1_threshold(y[va], cal_val)
    raw_test = pipe.predict_proba(X.iloc[te])[:, 1]
    cal_test = calibrator.predict(raw_test)
    test_metrics = classification_metrics(y[te], cal_test, threshold, curves=True)
    test_uncalibrated_brier = classification_metrics(y[te], raw_test, 0.5)["brier"]

    base_rate = float(y[tr].mean())
    bands = {"moderate": round(base_rate, 4), "high": round(2 * base_rate, 4)}

    background = None
    if best["algorithm"] == "logistic_regression":
        rng = np.random.default_rng(SEED)
        sample = X.iloc[rng.choice(tr, size=500, replace=False)]
        background = pipe.named_steps["preprocess"].transform(sample)
    sample_idx = np.random.default_rng(SEED).choice(te, size=min(3000, len(te)), replace=False)
    importance = global_importance(pipe, X.iloc[sample_idx], background)

    # Leakage ablation: the same model with a naive row-level split (patients can straddle splits).
    Xtr_r, Xte_r, ytr_r, yte_r = train_test_split(X, y, test_size=0.15, random_state=SEED, stratify=y)
    naive = build_pipeline(list(fs.numeric), list(fs.categorical), candidates(pos_weight)[
        [f"{a}:{i}" for a, i, _ in candidates(pos_weight)].index(best["candidate"])][2])
    naive.fit(Xtr_r, ytr_r)
    p_naive = naive.predict_proba(Xte_r)[:, 1]
    ablation = {
        "grouped_split_test": {k: test_metrics[k] for k in ("roc_auc", "pr_auc")},
        "row_split_test": {k: v for k, v in classification_metrics(yte_r, p_naive, 0.5).items()
                           if k in ("roc_auc", "pr_auc")},
        "note": "Row-level splitting lets encounters from the same patient appear in train and test.",
    }

    metadata = {
        "task": "classification",
        "algorithm": best["candidate"],
        "target": "readmitted within 30 days of discharge (UCI 'readmitted' == '<30')",
        "dataset": {"name": "UCI Diabetes 130-US hospitals 1999-2008", "license": "CC BY 4.0",
                    "doi": "10.24432/C5230J", "sha256": data.dataset_sha256, "rows_raw": data.rows_raw,
                    "rows_used": int(len(X)), "rows_excluded": data.rows_excluded},
        "features": {"set": fs.name, "numeric": list(fs.numeric), "categorical": list(fs.categorical),
                     "labels": {f: FEATURE_LABELS[f] for f in fs.all}},
        "split": {"method": "grouped by patient", "train": int(len(tr)), "validation": int(len(va)),
                  "test": int(len(te)), "seed": SEED},
        "selection_metric": "validation PR-AUC",
        "threshold": {"value": round(threshold, 4), "method": "F1-optimal on calibrated validation scores"},
        "risk_bands": {**bands, "definition": "moderate >= training base rate, high >= 2x base rate"},
        "calibration": {"method": "isotonic (validation)", "test_brier_uncalibrated": test_uncalibrated_brier,
                        "test_brier_calibrated": test_metrics["brier"]},
        "metrics": {"test": test_metrics, "baseline_validation": baseline_val},
        "candidates": results,
        "global_importance": importance,
        "leakage_ablation": ablation,
        "explanation_space": "log_odds" if best["algorithm"] != "random_forest" else "probability",
        "intended_use": "Decision support for discharge planning in adult inpatients with diabetes. "
                        "Not a diagnosis. Not validated for clinical use.",
        "limitations": [
            "Trained on 1999-2008 US encounters of diabetic inpatients; performance on other populations is unknown.",
            "Moderate discrimination (see ROC-AUC/PR-AUC); many readmissions are not predictable from these features.",
            "Attributions describe the model's behaviour, not causes of readmission.",
        ],
    }
    payload = {"pipeline": pipe, "calibrator": calibrator, "background": background, "feature_set": fs.name}
    target = save_artifact(MODEL_NAME, version, payload, metadata, force=force)
    write_readmission_report(target / "metadata.json")
    print(f"saved {target}")
    print({k: test_metrics[k] for k in ("roc_auc", "pr_auc", "precision", "recall", "f1", "brier")})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    main(a.version, a.force)
