"""Feature contract shared by offline training (UCI data) and online inference (hospital DB).

Both sides must produce exactly these columns with exactly these vocabularies; the serialized
sklearn pipeline embeds the preprocessing, so the contract is the only coupling point.
"""
from dataclasses import dataclass

from app.core.errors import ValidationFailedError

UNKNOWN = "unknown"

CATEGORY_VALUES: dict[str, tuple[str, ...]] = {
    "gender": ("F", "M"),
    "admission_type": ("emergency", "urgent", "elective", UNKNOWN),
    "admission_source": ("emergency_room", "physician_referral", "clinic", "transfer", UNKNOWN),
    "discharge_disposition": ("home", "home_health", "skilled_nursing", "rehab", "transfer", "ama", UNKNOWN),
    "admitting_specialty": (
        "general_medicine", "cardiology", "neurology", "orthopedics", "pediatrics", "dermatology",
        "emergency", "surgery", "nephrology", "other", UNKNOWN,
    ),
    "primary_diagnosis_category": (
        "circulatory", "respiratory", "digestive", "diabetes", "injury", "musculoskeletal",
        "genitourinary", "neoplasms", "other",
    ),
    "a1c_result": ("none", "normal", "high_7", "high_8"),
    "max_glucose": ("none", "normal", "high_200", "high_300"),
    "insulin_regimen": ("none", "steady", "up", "down"),
}

# Plausible ranges (inclusive). Values outside are rejected rather than silently clipped.
NUMERIC_RANGES: dict[str, tuple[float, float]] = {
    "age_years": (0, 110),
    "time_in_hospital": (0, 60),
    "num_lab_procedures": (0, 200),
    "num_medications": (0, 100),
    "number_outpatient": (0, 60),
    "number_emergency": (0, 60),
    "number_inpatient": (0, 30),
    "number_diagnoses": (0, 20),
    "medication_changed": (0, 1),
    "on_diabetes_medication": (0, 1),
}

FEATURE_LABELS: dict[str, str] = {
    "age_years": "Age",
    "time_in_hospital": "Length of the index stay",
    "num_lab_procedures": "Number of lab tests during the stay",
    "num_medications": "Number of medications during the stay",
    "number_outpatient": "Outpatient visits in the prior year",
    "number_emergency": "Emergency visits in the prior year",
    "number_inpatient": "Inpatient admissions in the prior year",
    "number_diagnoses": "Number of recorded diagnoses",
    "medication_changed": "Diabetes medication changed",
    "on_diabetes_medication": "On diabetes medication",
    "gender": "Sex",
    "admission_type": "Admission type",
    "admission_source": "Admission source",
    "discharge_disposition": "Discharge destination",
    "admitting_specialty": "Admitting specialty",
    "primary_diagnosis_category": "Primary diagnosis group",
    "a1c_result": "HbA1c result",
    "max_glucose": "Maximum glucose result",
    "insulin_regimen": "Insulin regimen",
}


@dataclass(frozen=True)
class FeatureSet:
    name: str
    numeric: tuple[str, ...]
    categorical: tuple[str, ...]

    @property
    def all(self) -> tuple[str, ...]:
        return self.numeric + self.categorical


# Readmission is scored at (or near) discharge, so stay-level information is legitimately available.
READMISSION_FEATURES = FeatureSet(
    name="readmission_v1",
    numeric=(
        "age_years", "time_in_hospital", "num_lab_procedures", "num_medications", "number_outpatient",
        "number_emergency", "number_inpatient", "number_diagnoses", "medication_changed",
        "on_diabetes_medication",
    ),
    categorical=(
        "gender", "admission_type", "admission_source", "discharge_disposition", "admitting_specialty",
        "primary_diagnosis_category", "a1c_result", "max_glucose", "insulin_regimen",
    ),
)

# Length of stay is predicted AT ADMISSION: anything measured during the stay (labs, medication
# counts, discharge-coded diagnoses, disposition) would be target leakage and is excluded.
LOS_FEATURES = FeatureSet(
    name="los_admission_v1",
    numeric=("age_years", "number_outpatient", "number_emergency", "number_inpatient"),
    categorical=("gender", "admission_type", "admission_source", "admitting_specialty",
                 "primary_diagnosis_category"),
)

# Used only in the documented leakage ablation - never deployed.
LOS_LEAKY_EXTRA = ("num_lab_procedures", "num_medications", "number_diagnoses", "num_procedures")


def validate_features(feature_set: FeatureSet, raw: dict) -> tuple[dict, list[str]]:
    """Validate an inference payload against the contract.

    Returns (clean_features, missing_features). Missing numeric values stay None (the pipeline
    imputes with the training median); missing categoricals become "unknown" when allowed.
    """
    unexpected = set(raw) - set(feature_set.all)
    if unexpected:
        raise ValidationFailedError(f"Unexpected features: {sorted(unexpected)}")
    clean: dict = {}
    missing: list[str] = []
    for name in feature_set.numeric:
        value = raw.get(name)
        if value is None:
            missing.append(name)
            clean[name] = None
            continue
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, (int, float)):
            raise ValidationFailedError(f"Feature '{name}' must be numeric")
        lo, hi = NUMERIC_RANGES[name]
        if not lo <= value <= hi:
            raise ValidationFailedError(f"Feature '{name}'={value} outside plausible range [{lo}, {hi}]")
        clean[name] = float(value)
    for name in feature_set.categorical:
        value = raw.get(name)
        allowed = CATEGORY_VALUES[name]
        if value is None:
            missing.append(name)
            if UNKNOWN in allowed:
                clean[name] = UNKNOWN
            elif name == "a1c_result" or name == "max_glucose" or name == "insulin_regimen":
                clean[name] = "none"
            else:
                raise ValidationFailedError(f"Required feature '{name}' is missing")
            continue
        if value not in allowed:
            raise ValidationFailedError(f"Feature '{name}'='{value}' not in {list(allowed)}")
        clean[name] = value
    return clean, missing
