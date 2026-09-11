"""Render human-readable evaluation reports (Markdown) from a model's metadata.json.

Numbers are copied verbatim from the training run's metadata; nothing is hand-edited.
"""
import json
from pathlib import Path

REPORTS = Path(__file__).resolve().parent / "reports"


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def write_readmission_report(metadata_path: Path) -> Path:
    m = _load(metadata_path)
    t = m["metrics"]["test"]
    cm = t["confusion_matrix"]
    lines = [
        f"# Readmission model report - v{m['version']}",
        "",
        f"*Generated from `{metadata_path.as_posix().split('ml/')[-1]}` at training time ({m['trained_at']}).*",
        "",
        f"- **Selected model:** `{m['algorithm']}` (selection: {m['selection_metric']})",
        f"- **Dataset:** {m['dataset']['name']} ({m['dataset']['license']}), rows used {m['dataset']['rows_used']:,}"
        f" (excluded: {m['dataset']['rows_excluded']})",
        f"- **Split:** {m['split']['method']} - train {m['split']['train']:,} / val {m['split']['validation']:,}"
        f" / test {m['split']['test']:,}",
        f"- **Test prevalence:** {t['prevalence']:.3f}",
        "",
        "## Test-set metrics (held out, evaluated once)",
        "",
        "| ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | Threshold |",
        "|---|---|---|---|---|---|---|",
        f"| {t['roc_auc']:.3f} | {t['pr_auc']:.3f} | {t['precision']:.3f} | {t['recall']:.3f} | {t['f1']:.3f}"
        f" | {t['brier']:.4f} | {t['threshold']:.3f} |",
        "",
        "Confusion matrix at the threshold:",
        "",
        "| | Predicted no | Predicted yes |",
        "|---|---|---|",
        f"| **Actual no** | {cm['tn']:,} | {cm['fp']:,} |",
        f"| **Actual yes** | {cm['fn']:,} | {cm['tp']:,} |",
        "",
        f"Baseline (predict prevalence) validation PR-AUC: {m['metrics']['baseline_validation']['pr_auc']:.3f}"
        f", ROC-AUC: {m['metrics']['baseline_validation']['roc_auc']:.3f}",
        "",
        "## Candidate comparison (validation / test)",
        "",
        "| Candidate | Val ROC-AUC | Val PR-AUC | Test ROC-AUC | Test PR-AUC | Test F1 | Fit (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in m["candidates"]:
        v, te = c["validation"], c["test"]
        lines.append(f"| {c['candidate']} | {v['roc_auc']:.3f} | {v['pr_auc']:.3f} | {te['roc_auc']:.3f}"
                     f" | {te['pr_auc']:.3f} | {te['f1']:.3f} | {c['fit_seconds']} |")
    cal = m["calibration"]
    ab = m["leakage_ablation"]
    lines += [
        "",
        "## Calibration",
        "",
        f"Isotonic calibration fitted on validation. Test Brier: {cal['test_brier_uncalibrated']:.4f} (raw)"
        f" -> {cal['test_brier_calibrated']:.4f} (calibrated).",
        "",
        "## Leakage ablation",
        "",
        "| Split | Test ROC-AUC | Test PR-AUC |",
        "|---|---|---|",
        f"| Grouped by patient (deployed) | {ab['grouped_split_test']['roc_auc']:.3f}"
        f" | {ab['grouped_split_test']['pr_auc']:.3f} |",
        f"| Naive row split | {ab['row_split_test']['roc_auc']:.3f} | {ab['row_split_test']['pr_auc']:.3f} |",
        "",
        ab["note"],
        "",
        "## Global feature importance (mean |SHAP|, " + m["explanation_space"] + ")",
        "",
        "| Feature | Mean abs. attribution |",
        "|---|---|",
    ]
    for f, v in list(m["global_importance"].items())[:12]:
        lines.append(f"| {m['features']['labels'].get(f, f)} | {v:.4f} |")
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in m["limitations"]]
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"readmission_30d_v{m['version']}.md"
    out.write_text("\n".join(lines) + "\n")
    return out


def write_los_report(metadata_path: Path) -> Path:
    m = _load(metadata_path)
    t, b = m["metrics"]["test"], m["metrics"]["baseline_test"]
    ab = m["leakage_ablation"]
    pi = m["prediction_interval"]
    lines = [
        f"# Length-of-stay model report - v{m['version']}",
        "",
        f"*Generated from training metadata ({m['trained_at']}).*",
        "",
        f"- **Selected model:** `{m['algorithm']}` (selection: {m['selection_metric']})",
        f"- **Features (admission-time only):** {', '.join(m['features']['numeric'] + m['features']['categorical'])}",
        "",
        "## Test-set metrics",
        "",
        "| Model | MAE (days) | RMSE (days) | R2 |",
        "|---|---|---|---|",
        f"| Selected ({m['algorithm']}) | {t['mae']:.3f} | {t['rmse']:.3f} | {t['r2']:.3f} |",
        f"| Baseline (median) | {b['mae']:.3f} | {b['rmse']:.3f} | {b['r2']:.3f} |",
        "",
        "## Candidates (validation)",
        "",
        "| Candidate | MAE | RMSE | R2 | Fit (s) |",
        "|---|---|---|---|---|",
    ]
    for c in m["candidates"]:
        v = c["validation"]
        lines.append(f"| {c['candidate']} | {v['mae']:.3f} | {v['rmse']:.3f} | {v['r2']:.3f} | {c['fit_seconds']} |")
    lt, ll = ab["admission_time_features_test"], ab["with_stay_time_features_test"]
    lines += [
        "",
        "## Prediction interval",
        "",
        f"80% empirical interval from validation residuals: prediction {pi['lower_residual']:+.2f} /"
        f" {pi['upper_residual']:+.2f} days; observed test coverage {pi['test_coverage']:.1%}.",
        "",
        "## Leakage ablation",
        "",
        "| Feature set | Test MAE | Test R2 |",
        "|---|---|---|",
        f"| Admission-time (deployed) | {lt['mae']:.3f} | {lt['r2']:.3f} |",
        f"| + stay-time features ({', '.join(ab['extra_features'])}) | {ll['mae']:.3f} | {ll['r2']:.3f} |",
        "",
        ab["note"],
        "",
        "## Global feature importance",
        "",
        "| Feature | Mean abs. attribution (days) |",
        "|---|---|",
    ]
    for f, v in m["global_importance"].items():
        lines.append(f"| {m['features']['labels'].get(f, f)} | {v:.4f} |")
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in m["limitations"]]
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"length_of_stay_v{m['version']}.md"
    out.write_text("\n".join(lines) + "\n")
    return out
