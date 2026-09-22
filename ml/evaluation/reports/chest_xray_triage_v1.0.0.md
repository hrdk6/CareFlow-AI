# Chest radiograph triage report - v1.0.0

*Generated from `artifacts/chest_xray_triage/1.0.0/metadata.json` at training time (2026-09-22T08:39:47+00:00).*

- **Model:** `resnet50_frozen+logistic_regression` - ResNet-50 (ImageNet-1k), frozen; 224x224 grayscale replicated to 3 channels
- **Backbone:** `Qdrant/resnet50-onnx`, frozen (never fine-tuned on radiographs)
- **Dataset:** NIH ChestX-ray14 - Wang et al., CVPR 2017 (NIH Clinical Center)
- **Labels:** NLP-mined from radiology reports (~90% accurate by the authors' estimate)
- **Films:** 37,339 from 16,170 patients, split by patient - train 26,122 / val 3,668 / test 7,549
- **Operating point:** two cut-offs per finding, set on validation at 90% sensitivity (rule-out) and 60% sensitivity (attention)

## Test-set metrics (held out, evaluated once)

`meta only` is a logistic regression on age, sex and view position with no image at all: a finding
whose image model barely beats it is being predicted from who was photographed, not from the chest.

| Finding | Positives | ROC-AUC | 95% CI | PR-AUC | Sens | Spec | Brier | Meta only | Shown |
|---|---|---|---|---|---|---|---|---|---|
| Edema | 145 | 0.800 | 0.766-0.834 | 0.080 | 0.83 | 0.59 | 0.018 | 0.747 | yes |
| Emphysema | 162 | 0.792 | 0.755-0.827 | 0.100 | 0.90 | 0.39 | 0.020 | 0.550 | yes |
| Effusion | 823 | 0.779 | 0.763-0.794 | 0.287 | 0.87 | 0.51 | 0.088 | 0.607 | yes |
| Pneumothorax | 338 | 0.763 | 0.737-0.786 | 0.148 | 0.93 | 0.34 | 0.042 | 0.565 | yes |
| Cardiomegaly | 182 | 0.726 | 0.685-0.761 | 0.094 | 0.95 | 0.18 | 0.023 | 0.562 | yes |
| Consolidation | 300 | 0.712 | 0.685-0.737 | 0.076 | 0.95 | 0.21 | 0.037 | 0.645 | yes |
| any finding | 3,477 | 0.708 | 0.697-0.719 | 0.644 | 0.91 | 0.28 | 0.216 | 0.590 | yes |
| Atelectasis | 774 | 0.708 | 0.691-0.724 | 0.196 | 0.92 | 0.33 | 0.087 | 0.611 | yes |
| Fibrosis | 146 | 0.678 | 0.634-0.721 | 0.062 | 0.92 | 0.21 | 0.019 | 0.641 | no |
| Pleural Thickening | 235 | 0.675 | 0.639-0.709 | 0.067 | 0.89 | 0.26 | 0.030 | 0.584 | no |
| Infiltration | 1,397 | 0.644 | 0.627-0.660 | 0.283 | 0.94 | 0.14 | 0.145 | 0.589 | no |
| Mass | 403 | 0.634 | 0.606-0.661 | 0.102 | 0.81 | 0.31 | 0.050 | 0.568 | no |
| Pneumonia | 114 | 0.625 | 0.574-0.678 | 0.026 | 0.96 | 0.13 | 0.015 | 0.592 | no |
| Nodule | 422 | 0.587 | 0.561-0.613 | 0.083 | 0.89 | 0.15 | 0.052 | 0.561 | no |

**Publication bar.** A finding is shown in the product only with ROC-AUC >= 0.7, a 95% interval starting at or above 0.65 (500 bootstrap resamples of the test films) and at least 30 positive test films. Shown: any_finding, Atelectasis, Cardiomegaly, Effusion, Pneumothorax, Consolidation, Edema, Emphysema.
Not modelled at all (too few positives in this slice): Hernia.

## Accuracy by subgroup (published findings)

| Finding | Group | n | Positives | ROC-AUC |
|---|---|---|---|---|
| any finding | sex F | 3,187 | 1,432 | 0.698 |
| any finding | sex M | 4,362 | 2,045 | 0.715 |
| any finding | view PA | 4,430 | 1,824 | 0.692 |
| any finding | view AP | 3,119 | 1,653 | 0.702 |
| any finding | age under 40 | 2,439 | 1,000 | 0.728 |
| any finding | age 40-59 | 3,227 | 1,474 | 0.701 |
| any finding | age 60-74 | 1,665 | 880 | 0.671 |
| any finding | age 75 and over | 218 | 123 | 0.685 |
| Atelectasis | sex F | 3,187 | 275 | 0.702 |
| Atelectasis | sex M | 4,362 | 499 | 0.708 |
| Atelectasis | view PA | 4,430 | 376 | 0.734 |
| Atelectasis | view AP | 3,119 | 398 | 0.660 |
| Atelectasis | age under 40 | 2,439 | 167 | 0.706 |
| Atelectasis | age 40-59 | 3,227 | 360 | 0.702 |
| Atelectasis | age 60-74 | 1,665 | 214 | 0.679 |
| Atelectasis | age 75 and over | 218 | 33 | 0.729 |
| Cardiomegaly | sex F | 3,187 | 96 | 0.721 |
| Cardiomegaly | sex M | 4,362 | 86 | 0.724 |
| Cardiomegaly | view PA | 4,430 | 97 | 0.769 |
| Cardiomegaly | view AP | 3,119 | 85 | 0.661 |
| Cardiomegaly | age under 40 | 2,439 | 79 | 0.729 |
| Cardiomegaly | age 40-59 | 3,227 | 63 | 0.757 |
| Cardiomegaly | age 60-74 | 1,665 | 35 | 0.691 |
| Cardiomegaly | age 75 and over | 218 | 5 | 0.573 |
| Effusion | sex F | 3,187 | 352 | 0.763 |
| Effusion | sex M | 4,362 | 471 | 0.790 |
| Effusion | view PA | 4,430 | 391 | 0.802 |
| Effusion | view AP | 3,119 | 432 | 0.734 |
| Effusion | age under 40 | 2,439 | 197 | 0.760 |
| Effusion | age 40-59 | 3,227 | 342 | 0.788 |
| Effusion | age 60-74 | 1,665 | 245 | 0.781 |
| Effusion | age 75 and over | 218 | 39 | 0.648 |
| Pneumothorax | sex F | 3,187 | 180 | 0.747 |
| Pneumothorax | sex M | 4,362 | 158 | 0.769 |
| Pneumothorax | view PA | 4,430 | 210 | 0.779 |
| Pneumothorax | view AP | 3,119 | 128 | 0.736 |
| Pneumothorax | age under 40 | 2,439 | 120 | 0.797 |
| Pneumothorax | age 40-59 | 3,227 | 128 | 0.740 |
| Pneumothorax | age 60-74 | 1,665 | 83 | 0.750 |
| Pneumothorax | age 75 and over | 218 | 7 | 0.792 |
| Consolidation | sex F | 3,187 | 106 | 0.725 |
| Consolidation | sex M | 4,362 | 194 | 0.703 |
| Consolidation | view PA | 4,430 | 93 | 0.699 |
| Consolidation | view AP | 3,119 | 207 | 0.625 |
| Consolidation | age under 40 | 2,439 | 92 | 0.739 |
| Consolidation | age 40-59 | 3,227 | 131 | 0.718 |
| Consolidation | age 60-74 | 1,665 | 69 | 0.662 |
| Consolidation | age 75 and over | 218 | 8 | 0.723 |
| Edema | sex F | 3,187 | 68 | 0.803 |
| Edema | sex M | 4,362 | 77 | 0.799 |
| Edema | view PA | 4,430 | 19 | 0.618 |
| Edema | view AP | 3,119 | 126 | 0.700 |
| Edema | age under 40 | 2,439 | 47 | 0.852 |
| Edema | age 40-59 | 3,227 | 59 | 0.792 |
| Edema | age 60-74 | 1,665 | 38 | 0.746 |
| Edema | age 75 and over | 218 | 1 | 0.710 |
| Emphysema | sex F | 3,187 | 58 | 0.754 |
| Emphysema | sex M | 4,362 | 104 | 0.815 |
| Emphysema | view PA | 4,430 | 95 | 0.793 |
| Emphysema | view AP | 3,119 | 67 | 0.791 |
| Emphysema | age under 40 | 2,439 | 55 | 0.826 |
| Emphysema | age 40-59 | 3,227 | 47 | 0.819 |
| Emphysema | age 60-74 | 1,665 | 53 | 0.740 |
| Emphysema | age 75 and over | 218 | 7 | 0.603 |

## Calibration (published findings)

Predicted probability against observed rate, in deciles of predicted risk.

**any finding** (isotonic)

| Predicted | Observed | n |
|---|---|---|
| 0.141 | 0.182 | 702 |
| 0.238 | 0.243 | 765 |
| 0.304 | 0.324 | 1,517 |
| 0.413 | 0.428 | 643 |
| 0.453 | 0.473 | 562 |
| 0.549 | 0.547 | 1,027 |
| 0.601 | 0.595 | 624 |
| 0.700 | 0.658 | 937 |
| 0.775 | 0.751 | 772 |

**Atelectasis** (isotonic)

| Predicted | Observed | n |
|---|---|---|
| 0.019 | 0.016 | 626 |
| 0.039 | 0.025 | 611 |
| 0.044 | 0.034 | 981 |
| 0.060 | 0.051 | 513 |
| 0.082 | 0.089 | 426 |
| 0.102 | 0.105 | 1,884 |
| 0.145 | 0.125 | 783 |
| 0.160 | 0.179 | 861 |
| 0.260 | 0.235 | 864 |

**Cardiomegaly** (platt)

| Predicted | Observed | n |
|---|---|---|
| 0.011 | 0.007 | 755 |
| 0.013 | 0.009 | 755 |
| 0.013 | 0.008 | 755 |
| 0.015 | 0.013 | 755 |
| 0.017 | 0.011 | 754 |
| 0.019 | 0.022 | 755 |
| 0.022 | 0.016 | 755 |
| 0.026 | 0.033 | 755 |
| 0.034 | 0.040 | 755 |
| 0.052 | 0.082 | 755 |

**Effusion** (isotonic)

| Predicted | Observed | n |
|---|---|---|
| 0.005 | 0.009 | 742 |
| 0.013 | 0.032 | 285 |
| 0.013 | 0.024 | 987 |
| 0.027 | 0.037 | 626 |
| 0.046 | 0.050 | 886 |
| 0.068 | 0.064 | 990 |
| 0.099 | 0.134 | 373 |
| 0.162 | 0.143 | 1,134 |
| 0.237 | 0.227 | 687 |
| 0.414 | 0.340 | 839 |

**Pneumothorax** (isotonic)

| Predicted | Observed | n |
|---|---|---|
| 0.002 | 0.006 | 180 |
| 0.007 | 0.007 | 863 |
| 0.015 | 0.014 | 1,210 |
| 0.016 | 0.005 | 200 |
| 0.025 | 0.024 | 1,042 |
| 0.045 | 0.030 | 1,000 |
| 0.052 | 0.031 | 159 |
| 0.055 | 0.046 | 1,356 |
| 0.092 | 0.079 | 772 |
| 0.233 | 0.168 | 767 |

**Consolidation** (isotonic)

| Predicted | Observed | n |
|---|---|---|
| 0.007 | 0.004 | 482 |
| 0.015 | 0.013 | 999 |
| 0.023 | 0.013 | 78 |
| 0.023 | 0.014 | 1,402 |
| 0.026 | 0.028 | 746 |
| 0.035 | 0.029 | 613 |
| 0.050 | 0.046 | 1,409 |
| 0.081 | 0.088 | 1,820 |

**Edema** (platt)

| Predicted | Observed | n |
|---|---|---|
| 0.007 | 0.001 | 755 |
| 0.007 | 0.001 | 755 |
| 0.008 | 0.008 | 755 |
| 0.009 | 0.005 | 755 |
| 0.010 | 0.007 | 754 |
| 0.011 | 0.011 | 755 |
| 0.015 | 0.012 | 755 |
| 0.021 | 0.026 | 755 |
| 0.037 | 0.041 | 755 |
| 0.082 | 0.080 | 755 |

**Emphysema** (platt)

| Predicted | Observed | n |
|---|---|---|
| 0.010 | 0.003 | 755 |
| 0.011 | 0.001 | 755 |
| 0.012 | 0.007 | 755 |
| 0.013 | 0.012 | 755 |
| 0.015 | 0.011 | 754 |
| 0.017 | 0.005 | 755 |
| 0.021 | 0.012 | 755 |
| 0.028 | 0.026 | 755 |
| 0.044 | 0.049 | 755 |
| 0.091 | 0.089 | 755 |

## Limitations

- Decision support for reading order and for a second look. It is not a diagnosis, it does not replace a radiologist's report, and no finding it reports may be acted on before a clinician has read the film.
- Trained on NIH ChestX-ray14, whose labels were mined from radiology reports with NLP and are about 90% accurate. The model can be no better than the labels it learned from, and its metrics are measured against those same noisy labels.
- One institution, one country, frontal films of adults only. Accuracy on films from other equipment, other populations or children is unknown and is likely to be worse.
- The backbone is an ImageNet model that has never been fine-tuned on radiographs. A fine-tuned DenseNet-121 of the CheXNet family reaches roughly 0.05 more ROC-AUC on the same findings.
- Portable AP films come from sicker patients, so a model can score them higher for reasons that are about the camera and not the chest. The model card reports accuracy separately for AP and PA views.
- Findings below the publication bar are not shown at all, so the absence of a finding in this tool means nothing about whether it is present on the film.
