"""Train and select the length-of-stay regressor (predicted at admission time).

    uv run --project backend python -m ml.training.train_los [--version 1.0.0] [--force]

Only admission-time features are used. A leakage ablation trains the same model with features that
are only known after the stay (lab/medication counts, discharge-coded diagnoses) to show how much
they would inflate offline metrics - that variant is reported but never deployed.
"""
import argparse
import time

import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor

from app.ml.feature_contract import FEATURE_LABELS, LOS_FEATURES, LOS_LEAKY_EXTRA
from ml.evaluation.report import write_los_report
from ml.preprocessing.uci_diabetes import grouped_split, load_and_prepare
from ml.training.common import SEED, build_pipeline, regression_metrics, save_artifact

MODEL_NAME = "length_of_stay"


def candidates():
    return [
        ("ridge", Ridge(alpha=1.0)),
        ("random_forest", RandomForestRegressor(n_estimators=300, min_samples_leaf=20, max_features=0.5,
                                                n_jobs=-1, random_state=SEED)),
        ("xgboost", XGBRegressor(n_estimators=600, learning_rate=0.03, max_depth=5, subsample=0.8,
                                 colsample_bytree=0.8, min_child_weight=10, tree_method="hist",
                                 n_jobs=-1, random_state=SEED)),
    ]


def main(version: str, force: bool) -> None:
    data = load_and_prepare()
    fs = LOS_FEATURES
    X = data.features
    y = data.length_of_stay.to_numpy()
    tr, va, te = grouped_split(data.groups, seed=SEED)
    num, cat = list(fs.numeric), list(fs.categorical)

    baseline = build_pipeline(num, cat, DummyRegressor(strategy="median")).fit(X.iloc[tr], y[tr])
    baseline_val = regression_metrics(y[va], baseline.predict(X.iloc[va]))
    baseline_test = regression_metrics(y[te], baseline.predict(X.iloc[te]))

    results, fitted = [], {}
    for algo, est in candidates():
        pipe = build_pipeline(num, cat, est)
        t0 = time.perf_counter()
        pipe.fit(X.iloc[tr], y[tr])
        fit_s = time.perf_counter() - t0
        val = regression_metrics(y[va], pipe.predict(X.iloc[va]))
        test = regression_metrics(y[te], pipe.predict(X.iloc[te]))
        fitted[algo] = pipe
        results.append({"candidate": algo, "fit_seconds": round(fit_s, 1), "validation": val, "test": test})
        print(f"{algo:14s} val MAE={val['mae']:.3f} RMSE={val['rmse']:.3f} R2={val['r2']:.3f} ({fit_s:.1f}s)")

    best = min(results, key=lambda r: r["validation"]["mae"])
    pipe = fitted[best["candidate"]]
    print(f"selected: {best['candidate']}")

    # Empirical prediction interval from validation residuals (10th-90th percentile).
    residuals = y[va] - pipe.predict(X.iloc[va])
    interval = {"lower_residual": round(float(np.quantile(residuals, 0.10)), 3),
                "upper_residual": round(float(np.quantile(residuals, 0.90)), 3),
                "coverage_target": 0.8}
    pred_test = pipe.predict(X.iloc[te])
    res_test = y[te] - pred_test
    interval["test_coverage"] = round(float(np.mean(
        (res_test >= interval["lower_residual"]) & (res_test <= interval["upper_residual"]))), 4)

    background = None
    if best["candidate"] == "ridge":
        background = pipe.named_steps["preprocess"].transform(X.iloc[tr[:500]])
    from app.ml.explain import global_importance

    sample_idx = np.random.default_rng(SEED).choice(te, size=min(3000, len(te)), replace=False)
    importance = global_importance(pipe, X.iloc[sample_idx], background)

    # Leakage ablation - same algorithm, plus stay-time features.
    leaky_num = num + list(LOS_LEAKY_EXTRA)
    leaky_est = dict(candidates())[best["candidate"]]
    leaky = build_pipeline(leaky_num, cat, leaky_est).fit(X.iloc[tr], y[tr])
    ablation = {
        "admission_time_features_test": regression_metrics(y[te], pred_test),
        "with_stay_time_features_test": regression_metrics(y[te], leaky.predict(X.iloc[te])),
        "extra_features": list(LOS_LEAKY_EXTRA),
        "note": "Stay-time features are unavailable at admission; using them would be target leakage.",
    }

    metadata = {
        "task": "regression",
        "algorithm": best["candidate"],
        "target": "length of stay in days (UCI 'time_in_hospital', range 1-14)",
        "dataset": {"name": "UCI Diabetes 130-US hospitals 1999-2008", "license": "CC BY 4.0",
                    "doi": "10.24432/C5230J", "sha256": data.dataset_sha256, "rows_raw": data.rows_raw,
                    "rows_used": int(len(X)), "rows_excluded": data.rows_excluded},
        "features": {"set": fs.name, "numeric": num, "categorical": cat,
                     "labels": {f: FEATURE_LABELS[f] for f in fs.all}},
        "split": {"method": "grouped by patient", "train": int(len(tr)), "validation": int(len(va)),
                  "test": int(len(te)), "seed": SEED},
        "selection_metric": "validation MAE",
        "prediction_interval": interval,
        "metrics": {"test": regression_metrics(y[te], pred_test), "baseline_test": baseline_test,
                    "baseline_validation": baseline_val},
        "candidates": results,
        "global_importance": importance,
        "leakage_ablation": ablation,
        "intended_use": "Rough operational estimate of inpatient stay length at admission (bed planning). "
                        "Not a clinical judgement.",
        "limitations": [
            "Training data only contains stays of 1-14 days; longer stays cannot be predicted.",
            "Admission-time information explains only a small share of LOS variance (see R2).",
            "Trained on diabetic inpatients 1999-2008 (US); other populations are out of distribution.",
        ],
    }
    payload = {"pipeline": pipe, "background": background, "feature_set": fs.name}
    target = save_artifact(MODEL_NAME, version, payload, metadata, force=force)
    write_los_report(target / "metadata.json")
    print(f"saved {target}")
    print(metadata["metrics"]["test"], "baseline", baseline_test)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    main(a.version, a.force)
