"""Shared training utilities: preprocessing pipelines, metrics and artifact persistence."""
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.feature_contract import CATEGORY_VALUES

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
SEED = 42


def build_pipeline(numeric: list[str], categorical: list[str], estimator) -> Pipeline:
    numeric_pipe = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical_pipe = OneHotEncoder(
        categories=[list(CATEGORY_VALUES[c]) for c in categorical],
        handle_unknown="ignore",
        sparse_output=False,
    )
    pre = ColumnTransformer(
        [("num", numeric_pipe, numeric), ("cat", categorical_pipe, categorical)], remainder="drop"
    )
    return Pipeline([("preprocess", pre), ("model", estimator)])


# ---------------------------------------------------------------- classification metrics
def best_f1_threshold(y_true, proba) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-12, None)
    return float(thresholds[int(np.nanargmax(f1[:-1]))])


def _downsample(xs, ys, n=60):
    idx = np.unique(np.linspace(0, len(xs) - 1, min(n, len(xs))).astype(int))
    return [[round(float(xs[i]), 4), round(float(ys[i]), 4)] for i in idx]


def classification_metrics(y_true, proba, threshold: float, curves: bool = False) -> dict:
    y_true = np.asarray(y_true)
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    out = {
        "n": int(len(y_true)),
        "prevalence": round(float(y_true.mean()), 4),
        "threshold": round(float(threshold), 4),
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_true, proba)), 4),
        "brier": round(float(brier_score_loss(y_true, proba)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    if curves:
        fpr, tpr, _ = roc_curve(y_true, proba)
        prec, rec, _ = precision_recall_curve(y_true, proba)
        out["roc_curve"] = _downsample(fpr, tpr)
        out["pr_curve"] = _downsample(rec[::-1], prec[::-1])
        out["calibration"] = calibration_bins(y_true, proba)
    return out


def calibration_bins(y_true, proba, bins: int = 10) -> list[dict]:
    edges = np.quantile(proba, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    idx = np.digitize(proba, edges[1:-1])
    rows = []
    for b in range(bins):
        m = idx == b
        if m.sum():
            rows.append({"mean_predicted": round(float(proba[m].mean()), 4),
                         "observed_rate": round(float(np.asarray(y_true)[m].mean()), 4), "n": int(m.sum())})
    return rows


# ---------------------------------------------------------------- regression metrics
def regression_metrics(y_true, pred) -> dict:
    return {
        "n": int(len(y_true)),
        "mae": round(float(mean_absolute_error(y_true, pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, pred))), 4),
        "r2": round(float(r2_score(y_true, pred)), 4),
    }


# ---------------------------------------------------------------- persistence
def environment_info() -> dict:
    return {"python": platform.python_version(), "sklearn": sklearn.__version__,
            "xgboost": xgboost.__version__, "numpy": np.__version__}


def save_artifact(model_name: str, version: str, payload: dict, metadata: dict, force: bool = False) -> Path:
    target = ARTIFACT_DIR / model_name / version
    if target.exists() and not force:
        raise FileExistsError(f"{target} exists; pass --force or choose a new --version")
    target.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, target / "model.joblib", compress=3)
    metadata = {**metadata, "model_name": model_name, "version": version,
                "trained_at": datetime.now(UTC).isoformat(timespec="seconds"), "environment": environment_info()}
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2))
    registry_path = ARTIFACT_DIR / "registry.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    registry[model_name] = version
    registry_path.write_text(json.dumps(registry, indent=2))
    return target
