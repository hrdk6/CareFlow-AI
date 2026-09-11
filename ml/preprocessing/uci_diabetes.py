"""Clean the UCI "Diabetes 130-US hospitals (1999-2008)" dataset into the CareFlow feature contract.

Dataset: Strack et al., 2014. UCI Machine Learning Repository, https://doi.org/10.24432/C5230J
License: CC BY 4.0. Fully de-identified encounter-level data; no identifiable patients.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

RAW_CSV = Path(__file__).resolve().parents[1] / "data" / "raw" / "diabetic_data.csv"

# Discharge codes where readmission is impossible/meaningless (death, hospice). Keeping them would
# teach the model a trivially-negative label and inflate metrics.
EXCLUDED_DISPOSITIONS = {11, 13, 14, 19, 20, 21}

ADMISSION_TYPE = {1: "emergency", 2: "urgent", 3: "elective", 7: "emergency"}
ADMISSION_SOURCE = {
    7: "emergency_room", 1: "physician_referral", 3: "physician_referral", 2: "clinic",
    4: "transfer", 5: "transfer", 6: "transfer", 10: "transfer", 22: "transfer", 25: "transfer",
}
DISCHARGE = {
    1: "home", 6: "home_health", 8: "home_health", 3: "skilled_nursing", 4: "skilled_nursing",
    24: "skilled_nursing", 15: "skilled_nursing", 22: "rehab", 2: "transfer", 5: "transfer", 23: "transfer",
    27: "transfer", 28: "transfer", 29: "transfer", 30: "transfer", 7: "ama",
}
A1C = {"None": "none", "Norm": "normal", ">7": "high_7", ">8": "high_8"}
GLUCOSE = {"None": "none", "Norm": "normal", ">200": "high_200", ">300": "high_300"}
INSULIN = {"No": "none", "Steady": "steady", "Up": "up", "Down": "down"}


def specialty_group(s: object) -> str:
    if not isinstance(s, str) or not s:
        return "unknown"
    if s in ("InternalMedicine", "Family/GeneralPractice", "Hospitalist", "Endocrinology"):
        return "general_medicine"
    if s.startswith("Cardiology"):
        return "cardiology"
    if s.startswith("Neurology"):
        return "neurology"
    if s.startswith("Orthopedics"):
        return "orthopedics"
    if s.startswith("Pediatrics"):
        return "pediatrics"
    if s == "Dermatology":
        return "dermatology"
    if s in ("Emergency/Trauma",):
        return "emergency"
    if s.startswith("Surgery") or s.startswith("Surgeon"):
        return "surgery"
    if s == "Nephrology":
        return "nephrology"
    return "other"


def icd9_group(code: object) -> str:
    """Standard ICD-9 chapter grouping used in the dataset's original paper."""
    if not isinstance(code, str) or not code:
        return "other"
    if code.startswith(("V", "E")):
        return "other"
    try:
        v = float(code)
    except ValueError:
        return "other"
    if 250 <= v < 251:
        return "diabetes"
    if 390 <= v <= 459 or int(v) == 785:
        return "circulatory"
    if 460 <= v <= 519 or int(v) == 786:
        return "respiratory"
    if 520 <= v <= 579 or int(v) == 787:
        return "digestive"
    if 800 <= v <= 999:
        return "injury"
    if 710 <= v <= 739:
        return "musculoskeletal"
    if 580 <= v <= 629 or int(v) == 788:
        return "genitourinary"
    if 140 <= v <= 239:
        return "neoplasms"
    return "other"


@dataclass
class PreparedData:
    features: pd.DataFrame
    readmitted_30d: pd.Series
    length_of_stay: pd.Series
    groups: pd.Series  # patient identifier (pseudonymous) for grouped splitting
    dataset_sha256: str
    rows_raw: int
    rows_excluded: dict[str, int]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_and_prepare(path: Path = RAW_CSV) -> PreparedData:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run: python -m ml.data.download")
    # keep_default_na=False: the literal string "None" is a real category (test not performed).
    df = pd.read_csv(path, keep_default_na=False, na_values=["?"], low_memory=False)
    rows_raw = len(df)
    excluded: dict[str, int] = {}

    mask_gender = df["gender"].isin(["Female", "Male"])
    excluded["invalid_gender"] = int((~mask_gender).sum())
    df = df[mask_gender]

    mask_disp = ~df["discharge_disposition_id"].isin(EXCLUDED_DISPOSITIONS)
    excluded["expired_or_hospice"] = int((~mask_disp).sum())
    df = df[mask_disp].copy()

    age_mid = df["age"].str.extract(r"\[(\d+)-(\d+)\)").astype(float).mean(axis=1)

    feats = pd.DataFrame(index=df.index)
    feats["age_years"] = age_mid
    feats["time_in_hospital"] = df["time_in_hospital"].astype(float)
    feats["num_lab_procedures"] = df["num_lab_procedures"].astype(float)
    feats["num_medications"] = df["num_medications"].astype(float)
    feats["number_outpatient"] = df["number_outpatient"].astype(float)
    feats["number_emergency"] = df["number_emergency"].astype(float)
    feats["number_inpatient"] = df["number_inpatient"].astype(float)
    feats["number_diagnoses"] = df["number_diagnoses"].clip(upper=16).astype(float)
    feats["medication_changed"] = (df["change"] == "Ch").astype(float)
    feats["on_diabetes_medication"] = (df["diabetesMed"] == "Yes").astype(float)
    feats["num_procedures"] = df["num_procedures"].astype(float)  # ablation only

    feats["gender"] = df["gender"].map({"Female": "F", "Male": "M"})
    feats["admission_type"] = df["admission_type_id"].map(ADMISSION_TYPE).fillna("unknown")
    feats["admission_source"] = df["admission_source_id"].map(ADMISSION_SOURCE).fillna("unknown")
    feats["discharge_disposition"] = df["discharge_disposition_id"].map(DISCHARGE).fillna("unknown")
    feats["admitting_specialty"] = df["medical_specialty"].map(specialty_group)
    feats["primary_diagnosis_category"] = df["diag_1"].map(icd9_group)
    feats["a1c_result"] = df["A1Cresult"].map(A1C).fillna("none")
    feats["max_glucose"] = df["max_glu_serum"].map(GLUCOSE).fillna("none")
    feats["insulin_regimen"] = df["insulin"].map(INSULIN).fillna("none")

    return PreparedData(
        features=feats.reset_index(drop=True),
        readmitted_30d=(df["readmitted"] == "<30").astype(int).reset_index(drop=True),
        length_of_stay=df["time_in_hospital"].astype(float).reset_index(drop=True),
        groups=df["patient_nbr"].reset_index(drop=True),
        dataset_sha256=file_sha256(path),
        rows_raw=rows_raw,
        rows_excluded=excluded,
    )


def grouped_split(groups: pd.Series, seed: int = 42, val: float = 0.15, test: float = 0.15):
    """Split indices so that every encounter of a patient lands in exactly one partition."""
    rng = np.random.default_rng(seed)
    unique = groups.unique()
    rng.shuffle(unique)
    n = len(unique)
    n_test, n_val = int(n * test), int(n * val)
    test_ids = set(unique[:n_test])
    val_ids = set(unique[n_test:n_test + n_val])
    part = groups.map(lambda g: "test" if g in test_ids else ("val" if g in val_ids else "train"))
    return (np.flatnonzero(part == "train"), np.flatnonzero(part == "val"), np.flatnonzero(part == "test"))
