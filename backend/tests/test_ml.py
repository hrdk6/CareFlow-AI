"""Feature contract, registry/versioning, inference, explanations and similarity."""
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.core.errors import ServiceUnavailableError, ValidationFailedError
from app.ml.explain import grouped_contributions
from app.ml.feature_contract import LOS_FEATURES, READMISSION_FEATURES, validate_features
from app.ml.features import readmission_features, reference_admission
from app.ml.registry import ModelRegistry, get_registry
from app.ml.service import predict_from_features
from app.models import Admission, MLPrediction, ModelVersion, Patient

BASE = {"age_years": 70, "time_in_hospital": 5, "num_lab_procedures": 40, "num_medications": 15,
        "number_outpatient": 0, "number_emergency": 0, "number_inpatient": 0, "number_diagnoses": 8,
        "medication_changed": 1, "on_diabetes_medication": 1, "gender": "F", "admission_type": "emergency",
        "admission_source": "emergency_room", "discharge_disposition": "home", "admitting_specialty": "general_medicine",
        "primary_diagnosis_category": "circulatory", "a1c_result": "none", "max_glucose": "none",
        "insulin_regimen": "steady"}


# ------------------------------------------------------------------ feature contract / preprocessing
def test_contract_accepts_valid_and_imputes_missing():
    raw = {**BASE}
    raw.pop("num_lab_procedures")
    raw.pop("a1c_result")
    clean, missing = validate_features(READMISSION_FEATURES, raw)
    assert clean["num_lab_procedures"] is None and clean["a1c_result"] == "none"
    assert set(missing) == {"num_lab_procedures", "a1c_result"}


@pytest.mark.parametrize("patch,msg", [({"gender": "Z"}, "not in"), ({"age_years": 150}, "outside plausible"),
                                       ({"number_inpatient": "three"}, "numeric"), ({"shoe_size": 42}, "Unexpected")])
def test_contract_rejects_invalid_inputs(patch, msg):
    with pytest.raises(ValidationFailedError, match=msg):
        validate_features(READMISSION_FEATURES, {**BASE, **patch})


def test_required_categorical_without_unknown_bucket():
    raw = {**BASE}
    raw.pop("gender")
    with pytest.raises(ValidationFailedError, match="missing"):
        validate_features(READMISSION_FEATURES, raw)


# ------------------------------------------------------------------ registry / versioning
def test_registry_loads_versioned_artifacts_with_model_cards():
    reg = get_registry()
    assert set(reg.active_versions()) == {"readmission_30d", "length_of_stay"}
    model = reg.get("readmission_30d")
    assert {"pipeline", "calibrator"} <= set(model.payload)
    meta = model.metadata
    assert meta["version"] == model.version and len(meta["dataset"]["sha256"]) == 64
    assert meta["split"]["method"] == "grouped by patient"
    assert 0.5 < meta["metrics"]["test"]["roc_auc"] < 1 and "confusion_matrix" in meta["metrics"]["test"]


def test_model_versions_are_mirrored_in_database(db):
    rows = db.scalars(select(ModelVersion).where(ModelVersion.is_active)).all()
    assert {r.model_name for r in rows} == {"readmission_30d", "length_of_stay"}
    assert all(r.dataset_version and r.metrics and r.feature_config for r in rows)


def test_missing_model_raises_service_unavailable(tmp_path):
    reg = ModelRegistry(tmp_path)
    with pytest.raises(ServiceUnavailableError):
        reg.get("readmission_30d")
    (tmp_path / "registry.json").write_text('{"readmission_30d": "9.9.9"}')
    with pytest.raises(ServiceUnavailableError, match="missing"):
        reg.get("readmission_30d")


# ------------------------------------------------------------------ inference
def test_inference_is_sane_and_monotone_in_prior_admissions():
    low = predict_from_features("readmission_30d", BASE)["value"]
    high = predict_from_features("readmission_30d", {**BASE, "number_inpatient": 6, "number_emergency": 4})["value"]
    assert 0 <= low < high <= 1
    los = predict_from_features("length_of_stay", {k: BASE[k] for k in LOS_FEATURES.all})["value"]
    assert 1 <= los <= 14


def test_explanations_are_additive():
    model = get_registry().get("readmission_30d")
    clean, _ = validate_features(READMISSION_FEATURES, BASE)
    X = pd.DataFrame([clean], columns=list(READMISSION_FEATURES.all))
    frame, base, space = grouped_contributions(model.payload["pipeline"], X, model.payload.get("background"))
    raw = model.payload["pipeline"].predict_proba(X)[0, 1]
    total = frame.iloc[0].sum() + base[0]
    if space == "log_odds":
        total = 1 / (1 + np.exp(-total))
    assert abs(total - raw) < 1e-3
    assert set(frame.columns) == set(READMISSION_FEATURES.all)  # one-hot columns summed back per feature


def test_db_feature_engineering_for_demo_patient(db, demo_patient):
    adm = reference_admission(db, demo_patient.id)
    fb = readmission_features(db, demo_patient, adm)
    f = fb.features
    assert f["number_inpatient"] == 3 and f["number_emergency"] == 2
    assert f["discharge_disposition"] == "home_health" and f["insulin_regimen"] == "up"
    assert f["a1c_result"] == "high_8" and f["max_glucose"] == "high_300"
    assert fb.in_training_population


def test_risk_endpoint_returns_versioned_explained_prediction(client, auth, demo_patient, db):
    r = client.get(f"/patients/{demo_patient.id}/risk", headers=auth("doctor"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["model_version"] == "1.0.0" and body["predicted_at"]
    assert 0 < body["value"] < 1 and body["label"] in ("low", "moderate", "high")
    assert body["factors"] and all("contribution" in f and f["direction"] in ("up", "down") for f in body["factors"])
    assert "not a diagnosis" in body["disclaimer"] and body["limitations"]
    again = client.get(f"/patients/{demo_patient.id}/risk", headers=auth("doctor")).json()
    assert again["prediction_id"] == body["prediction_id"]  # identical input -> reused, not duplicated
    assert db.get(MLPrediction, body["prediction_id"]).model_version.version == "1.0.0"


def test_los_endpoint_includes_interval_and_actual(client, auth, demo_patient):
    body = client.get(f"/patients/{demo_patient.id}/length-of-stay", headers=auth("doctor")).json()
    lo, hi = body["interval"]
    assert lo <= body["value"] <= hi and body["reference"]["actual_length_of_stay_days"] == pytest.approx(6.9, 0.2)


def test_prediction_not_applicable_without_admission(client, auth, db):
    pid = db.scalar(select(Patient.id).where(~Patient.id.in_(select(Admission.patient_id))).limit(1))
    body = client.get(f"/patients/{pid}/risk", headers=auth("admin")).json()
    assert body["status"] == "not_applicable" and body["value"] is None


# ------------------------------------------------------------------ similarity
def test_similarity_is_authorized_ranked_and_excludes_self(client, auth, demo_patient, restricted_patient):
    body = client.get(f"/patients/{demo_patient.id}/similar?k=8", headers=auth("doctor")).json()
    ids = [r["patient_id"] for r in body["results"]]
    sims = [r["similarity"] for r in body["results"]]
    assert ids and demo_patient.id not in ids and restricted_patient.id not in ids
    assert sims == sorted(sims, reverse=True)
    assert body["metric"].startswith("cosine") and "do not share" in body["disclaimer"]
    assert "diabetes" in body["results"][0]["shared_diagnosis_categories"]
    assert body["cohort_patterns"]["cohort_size"] == len(ids)


def test_similarity_representation_dimension():
    from app.ml.similarity import FEATURE_NAMES, vectorize

    profile = {"age": 67, "sex": "F", "admissions_2y": 3, "ed_visits_2y": 1, "mean_los_days": 5,
               "active_medications": 5, "chronic_conditions": 4, "last_hba1c": None, "last_egfr": 44,
               "diagnosis_categories": {"diabetes"}, "medication_groups": {"insulin"}}
    vec = vectorize(profile)
    assert len(vec) == len(FEATURE_NAMES) == 32
    assert vec[FEATURE_NAMES.index("num:last_hba1c")] == 0.0  # missing -> reference mean
