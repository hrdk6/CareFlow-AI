# Length-of-stay model report - v1.0.0

*Generated from training metadata (2026-09-11T10:43:52+00:00).*

- **Selected model:** `xgboost` (selection: validation MAE)
- **Features (admission-time only):** age_years, number_outpatient, number_emergency, number_inpatient, gender, admission_type, admission_source, admitting_specialty, primary_diagnosis_category

## Test-set metrics

| Model | MAE (days) | RMSE (days) | R2 |
|---|---|---|---|
| Selected (xgboost) | 2.246 | 2.883 | 0.078 |
| Baseline (median) | 2.279 | 3.031 | -0.019 |

## Candidates (validation)

| Candidate | MAE | RMSE | R2 | Fit (s) |
|---|---|---|---|---|
| ridge | 2.273 | 2.906 | 0.045 | 0.1 |
| random_forest | 2.235 | 2.864 | 0.072 | 1.9 |
| xgboost | 2.228 | 2.855 | 0.078 | 1.4 |

## Prediction interval

80% empirical interval from validation residuals: prediction -2.97 / +4.15 days; observed test coverage 79.9%.

## Leakage ablation

| Feature set | Test MAE | Test R2 |
|---|---|---|
| Admission-time (deployed) | 2.246 | 0.078 |
| + stay-time features (num_lab_procedures, num_medications, number_diagnoses, num_procedures) | 1.733 | 0.413 |

Stay-time features are unavailable at admission; using them would be target leakage.

## Global feature importance

| Feature | Mean abs. attribution (days) |
|---|---|
| Age | 0.2498 |
| Primary diagnosis group | 0.2311 |
| Inpatient admissions in the prior year | 0.2211 |
| Admission source | 0.1476 |
| Admitting specialty | 0.1293 |
| Admission type | 0.0782 |
| Outpatient visits in the prior year | 0.0619 |
| Sex | 0.0600 |
| Emergency visits in the prior year | 0.0282 |

## Limitations

- Training data only contains stays of 1-14 days; longer stays cannot be predicted.
- Admission-time information explains only a small share of LOS variance (see R2).
- Trained on diabetic inpatients 1999-2008 (US); other populations are out of distribution.
