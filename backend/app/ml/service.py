"""Prediction service: the ONLY place that turns patient data into model outputs.

API routes, the AI assistant tools and the UI all call these functions, so validation, versioning,
explanation, persistence and latency metrics are applied uniformly.
"""
import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailableError, ValidationFailedError
from app.ml.explain import grouped_contributions
from app.ml.feature_contract import FEATURE_LABELS, LOS_FEATURES, READMISSION_FEATURES, FeatureSet, validate_features
from app.ml.features import FeatureBuild, los_features, readmission_features, reference_admission
from app.ml.registry import LoadedModel, get_registry, model_version_row
from app.models import MLPrediction, Patient
from app.observability.metrics import COMPONENT_ERRORS, ML_INFERENCE_LATENCY
from app.schemas.ml import FactorOut, PredictionOut, ReferenceAdmission

logger = logging.getLogger("careflow.ml")

READMISSION_MODEL = "readmission_30d"
LOS_MODEL = "length_of_stay"
DISCLAIMER = ("Decision-support estimate from a statistical model trained on public de-identified data. "
              "It is not a diagnosis and must not replace clinical judgement.")


def _frame(fs: FeatureSet, clean: dict) -> pd.DataFrame:
    row = {k: (np.nan if clean[k] is None else clean[k]) for k in fs.all}
    return pd.DataFrame([row], columns=list(fs.all))


def _display(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("_", " ") if value is not None else "missing"


def _factors(model: LoadedModel, X: pd.DataFrame, clean: dict, top: int = 6) -> tuple[list[FactorOut], str]:
    frame, _, space = grouped_contributions(model.payload["pipeline"], X, model.payload.get("background"))
    row = frame.iloc[0].sort_values(key=lambda s: -s.abs())
    factors = []
    for feature, value in row.head(top).items():
        if abs(value) < 1e-6:
            continue
        direction = "increased" if value > 0 else "decreased"
        factors.append(FactorOut(
            feature=feature, label=FEATURE_LABELS.get(feature, feature), value=_display(clean.get(feature)),
            contribution=round(float(value), 4), direction="up" if value > 0 else "down",
            text=f"{FEATURE_LABELS.get(feature, feature)} ({_display(clean.get(feature))}) {direction} "
                 f"the model's prediction"))
    return factors, space


def _persist(db: Session, model: LoadedModel, patient: Patient, fb: FeatureBuild, kind: str, value: float,
             label: str | None, clean: dict, explanation: dict, user_id: int | None) -> MLPrediction:
    """Store the prediction; reuse an identical one from the last 24h to avoid duplicates."""
    version_row = model_version_row(db, model.name, model.version)
    digest = hashlib.sha256(json.dumps(clean, sort_keys=True, default=str).encode()).hexdigest()[:16]
    since = datetime.now(UTC) - timedelta(hours=24)
    for existing in db.scalars(select(MLPrediction).where(
            MLPrediction.patient_id == patient.id, MLPrediction.model_version_id == version_row.id,
            MLPrediction.admission_id == fb.admission.id, MLPrediction.created_at >= since)):
        if existing.explanation.get("features_digest") == digest:
            return existing
    row = MLPrediction(model_version_id=version_row.id, patient_id=patient.id, admission_id=fb.admission.id,
                       requested_by_user_id=user_id, prediction_type=kind, value=value, label=label,
                       features=clean, explanation={**explanation, "features_digest": digest})
    db.add(row)
    db.flush()
    return row


def _reference(fb: FeatureBuild) -> ReferenceAdmission:
    a = fb.admission
    return ReferenceAdmission(admission_id=a.id, admitted_at=a.admitted_at, discharged_at=a.discharged_at,
                              status=a.status, reason=a.reason,
                              actual_length_of_stay_days=a.length_of_stay_days)


def _prepare(db: Session, patient: Patient, fs: FeatureSet, builder) -> tuple[FeatureBuild, dict, list[str]] | None:
    adm = reference_admission(db, patient.id)
    if adm is None:
        return None
    fb = builder(db, patient, adm)
    clean, missing = validate_features(fs, fb.features)
    return fb, clean, missing


def not_applicable(kind: str) -> PredictionOut:
    return PredictionOut(prediction_type=kind, status="not_applicable",
                         reason="This prediction is defined relative to an inpatient admission and the patient "
                                "has none on record.", disclaimer=DISCLAIMER)


def predict_readmission(db: Session, patient: Patient, user_id: int | None = None) -> PredictionOut:
    prepared = _prepare(db, patient, READMISSION_FEATURES, readmission_features)
    if prepared is None:
        return not_applicable("readmission_30d")
    fb, clean, missing = prepared
    model = get_registry().get(READMISSION_MODEL)
    X = _frame(READMISSION_FEATURES, clean)
    t0 = time.perf_counter()
    try:
        raw = float(model.payload["pipeline"].predict_proba(X)[0, 1])
        prob = float(model.payload["calibrator"].predict([raw])[0])
        factors, space = _factors(model, X, clean)
    except Exception as exc:
        COMPONENT_ERRORS.labels("ml_inference").inc()
        logger.exception("readmission inference failed")
        raise ServiceUnavailableError("Readmission model inference failed") from exc
    finally:
        ML_INFERENCE_LATENCY.labels(READMISSION_MODEL).observe(time.perf_counter() - t0)
    bands = model.metadata["risk_bands"]
    band = "high" if prob >= bands["high"] else "moderate" if prob >= bands["moderate"] else "low"
    threshold = model.metadata["threshold"]["value"]
    test = model.metadata["metrics"]["test"]
    row = _persist(db, model, patient, fb, "readmission_30d", prob, band, clean,
                   {"factors": [f.model_dump() for f in factors], "space": space, "raw_score": raw}, user_id)
    return PredictionOut(
        prediction_type="readmission_30d", status="ok", prediction_id=row.id, value=round(prob, 4),
        label=band, unit="probability", threshold=threshold, flagged=prob >= threshold,
        model_name=model.name, model_version=model.version, model_algorithm=model.metadata["algorithm"],
        trained_at=model.trained_at, predicted_at=row.created_at, reference=_reference(fb),
        features=clean, missing_features=missing, factors=factors, explanation_space=space,
        in_training_population=fb.in_training_population, notes=fb.notes,
        context={"base_rate": bands["moderate"], "high_risk_cutoff": bands["high"],
                 "test_roc_auc": test["roc_auc"], "test_pr_auc": test["pr_auc"]},
        limitations=model.metadata["limitations"], disclaimer=DISCLAIMER)


def predict_length_of_stay(db: Session, patient: Patient, user_id: int | None = None) -> PredictionOut:
    prepared = _prepare(db, patient, LOS_FEATURES, los_features)
    if prepared is None:
        return not_applicable("length_of_stay")
    fb, clean, missing = prepared
    model = get_registry().get(LOS_MODEL)
    X = _frame(LOS_FEATURES, clean)
    t0 = time.perf_counter()
    try:
        days = float(model.payload["pipeline"].predict(X)[0])
        factors, space = _factors(model, X, clean)
    except Exception as exc:
        COMPONENT_ERRORS.labels("ml_inference").inc()
        logger.exception("LOS inference failed")
        raise ServiceUnavailableError("Length-of-stay model inference failed") from exc
    finally:
        ML_INFERENCE_LATENCY.labels(LOS_MODEL).observe(time.perf_counter() - t0)
    pi = model.metadata["prediction_interval"]
    low, high = max(1.0, days + pi["lower_residual"]), min(14.0, days + pi["upper_residual"])
    test = model.metadata["metrics"]["test"]
    row = _persist(db, model, patient, fb, "length_of_stay", days, None, clean,
                   {"factors": [f.model_dump() for f in factors], "space": space}, user_id)
    return PredictionOut(
        prediction_type="length_of_stay", status="ok", prediction_id=row.id, value=round(days, 2), unit="days",
        interval=[round(low, 1), round(high, 1)], model_name=model.name, model_version=model.version,
        model_algorithm=model.metadata["algorithm"], trained_at=model.trained_at, predicted_at=row.created_at,
        reference=_reference(fb), features=clean, missing_features=missing, factors=factors,
        explanation_space=space, in_training_population=fb.in_training_population, notes=fb.notes,
        context={"test_mae_days": test["mae"], "test_r2": test["r2"],
                 "interval_coverage_target": pi["coverage_target"]},
        limitations=model.metadata["limitations"], disclaimer=DISCLAIMER)


def predict_from_features(model_name: str, raw: dict) -> dict:
    """Score an explicit feature payload (used by tests and the model playground)."""
    fs = READMISSION_FEATURES if model_name == READMISSION_MODEL else LOS_FEATURES
    if model_name not in (READMISSION_MODEL, LOS_MODEL):
        raise ValidationFailedError(f"Unknown model '{model_name}'")
    clean, missing = validate_features(fs, raw)
    model = get_registry().get(model_name)
    X = _frame(fs, clean)
    if model_name == READMISSION_MODEL:
        raw_p = float(model.payload["pipeline"].predict_proba(X)[0, 1])
        value = float(model.payload["calibrator"].predict([raw_p])[0])
    else:
        value = float(model.payload["pipeline"].predict(X)[0])
    return {"value": value, "missing_features": missing, "model_version": model.version}
