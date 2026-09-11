# Readmission model report - v1.0.0

*Generated from `artifacts/readmission_30d/1.0.0/metadata.json` at training time (2026-09-11T10:43:43+00:00).*

- **Selected model:** `random_forest:none` (selection: validation PR-AUC)
- **Dataset:** UCI Diabetes 130-US hospitals 1999-2008 (CC BY 4.0), rows used 99,340 (excluded: {'invalid_gender': 3, 'expired_or_hospice': 2423})
- **Split:** grouped by patient - train 69,465 / val 14,767 / test 15,108
- **Test prevalence:** 0.120

## Test-set metrics (held out, evaluated once)

| ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | Threshold |
|---|---|---|---|---|---|---|
| 0.685 | 0.242 | 0.237 | 0.427 | 0.305 | 0.0995 | 0.149 |

Confusion matrix at the threshold:

| | Predicted no | Predicted yes |
|---|---|---|
| **Actual no** | 10,807 | 2,493 |
| **Actual yes** | 1,035 | 773 |

Baseline (predict prevalence) validation PR-AUC: 0.110, ROC-AUC: 0.500

## Candidate comparison (validation / test)

| Candidate | Val ROC-AUC | Val PR-AUC | Test ROC-AUC | Test PR-AUC | Test F1 | Fit (s) |
|---|---|---|---|---|---|---|
| logistic_regression:none | 0.669 | 0.217 | 0.672 | 0.234 | 0.287 | 0.3 |
| logistic_regression:class_weight | 0.671 | 0.217 | 0.674 | 0.233 | 0.289 | 0.4 |
| random_forest:none | 0.679 | 0.231 | 0.686 | 0.253 | 0.305 | 2.0 |
| random_forest:class_weight | 0.679 | 0.228 | 0.682 | 0.243 | 0.297 | 2.4 |
| xgboost:none | 0.676 | 0.228 | 0.683 | 0.253 | 0.299 | 1.6 |
| xgboost:class_weight | 0.674 | 0.227 | 0.681 | 0.249 | 0.300 | 1.4 |

## Calibration

Isotonic calibration fitted on validation. Test Brier: 0.1000 (raw) -> 0.0995 (calibrated).

## Leakage ablation

| Split | Test ROC-AUC | Test PR-AUC |
|---|---|---|
| Grouped by patient (deployed) | 0.685 | 0.242 |
| Naive row split | 0.668 | 0.233 |

Row-level splitting lets encounters from the same patient appear in train and test.

## Global feature importance (mean |SHAP|, probability)

| Feature | Mean abs. attribution |
|---|---|
| Inpatient admissions in the prior year | 0.0233 |
| Discharge destination | 0.0176 |
| Insulin regimen | 0.0049 |
| Number of recorded diagnoses | 0.0045 |
| Emergency visits in the prior year | 0.0042 |
| Number of medications during the stay | 0.0042 |
| Length of the index stay | 0.0040 |
| Primary diagnosis group | 0.0038 |
| HbA1c result | 0.0026 |
| Age | 0.0025 |
| Number of lab tests during the stay | 0.0025 |
| Admitting specialty | 0.0023 |

## Limitations

- Trained on 1999-2008 US encounters of diabetic inpatients; performance on other populations is unknown.
- Moderate discrimination (see ROC-AUC/PR-AUC); many readmissions are not predictable from these features.
- Attributions describe the model's behaviour, not causes of readmission.
