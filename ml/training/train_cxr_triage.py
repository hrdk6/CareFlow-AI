"""Train and select the chest radiograph triage heads.

    uv run --project backend python -m ml.training.train_cxr_triage [--version 1.0.0] [--force]

Pipeline: frozen ResNet-50 features (ml.preprocessing.nih_cxr) -> patient-grouped split (70/10/20)
-> one linear head per finding, regularisation chosen on VALIDATION ROC-AUC -> probability calibration on
validation -> two operating points (90% and 60% sensitivity) -> one evaluation on the untouched TEST split
-> a metadata-only baseline and a publication bar -> artifact + model card.

Why a linear head on frozen features rather than a fine-tuned CNN: the backbone never changes, so the
whole model is 2048 numbers per finding, it trains in minutes on a laptop, the class activation map is
exact rather than approximated, and the thing that would improve it most (fine-tuning) is stated in the
model card instead of being quietly skipped. Expect roughly 0.05 less AUROC than a fine-tuned DenseNet-121
of the CheXNet family, which is the honest price of that choice.

PUBLICATION BAR. A head is shown in the product only if, on the held-out test set, its ROC-AUC is at
least 0.70, the lower end of its 95% bootstrap interval is at least 0.65, and it has at least 30 positive
films. Every head is reported in the model card either way, including the ones that did not make it.
"""
import argparse
import json
import time
from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from app.imaging.backbone import DESCRIPTION, FEATURE_DIM, INPUT_SIZE, REPO
from ml.evaluation.report import write_cxr_triage_report
from ml.preprocessing.nih_cxr import FINDINGS, Dataset, build, grouped_split
from ml.training.common import SEED, calibration_bins, classification_metrics, save_artifact

MODEL_NAME = "chest_xray_triage"
ANY_FINDING = "any_finding"
C_GRID = (0.0003, 0.001, 0.003, 0.01)
# Two measured operating points rather than one. A triage tool is first a rule-out ("nothing here needs to
# jump the queue"), so the low cut-off is set for sensitivity; the higher one is what moves a film up the
# reading order, and both are reported with the specificity they actually achieved.
RULE_OUT_SENSITIVITY, ATTENTION_SENSITIVITY = 0.90, 0.60
MIN_AUC, MIN_AUC_LOWER, MIN_POSITIVES = 0.70, 0.65, 30
BOOTSTRAPS = 500
AGE_BANDS = ((0, 39, "under 40"), (40, 59, "40-59"), (60, 74, "60-74"), (75, 200, "75 and over"))

LIMITATIONS = [
    "Decision support for reading order and for a second look. It is not a diagnosis, it does not replace "
    "a radiologist's report, and no finding it reports may be acted on before a clinician has read the film.",
    "Trained on NIH ChestX-ray14, whose labels were mined from radiology reports with NLP and are about 90% "
    "accurate. The model can be no better than the labels it learned from, and its metrics are measured "
    "against those same noisy labels.",
    "One institution, one country, frontal films of adults only. Accuracy on films from other equipment, "
    "other populations or children is unknown and is likely to be worse.",
    "The backbone is an ImageNet model that has never been fine-tuned on radiographs. A fine-tuned "
    "DenseNet-121 of the CheXNet family reaches roughly 0.05 more ROC-AUC on the same findings.",
    "Portable AP films come from sicker patients, so a model can score them higher for reasons that are "
    "about the camera and not the chest. The model card reports accuracy separately for AP and PA views.",
    "Findings below the publication bar are not shown at all, so the absence of a finding in this tool "
    "means nothing about whether it is present on the film.",
]


@dataclass
class Head:
    finding: str
    model: LogisticRegression
    calibrator: object
    threshold: float        # rule-out cut-off: below it, the film is not moved up the queue
    threshold_high: float   # attention cut-off: above it, the film moves up
    C: float
    calibration: str
    published: bool


def _bootstrap_auc(y: np.ndarray, p: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """Percentile interval over resampled films. Wide intervals on rare findings are the point."""
    scores = []
    index = np.arange(len(y))
    for _ in range(BOOTSTRAPS):
        pick = rng.choice(index, size=len(index), replace=True)
        if 0 < y[pick].sum() < len(pick):
            scores.append(roc_auc_score(y[pick], p[pick]))
    if not scores:
        return float("nan"), float("nan")
    return float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


def _threshold_at_sensitivity(y: np.ndarray, p: np.ndarray, target: float) -> float:
    """The highest cut-off that still catches `target` of the positive films."""
    positives = np.sort(p[y == 1])
    if len(positives) == 0:
        return 0.5
    return float(positives[max(0, int((1 - target) * len(positives)) - 1)]) if len(positives) > 1 else 0.0


def _targets(data: Dataset, finding: str) -> np.ndarray:
    if finding == ANY_FINDING:
        return data.any_finding
    return data.labels[:, FINDINGS.index(finding)]


def _fit_head(finding: str, Xtr, ytr, Xva, yva, rng) -> tuple[Head, list[dict]]:
    """Choose regularisation on validation ROC-AUC, then calibrate the winner on the same split."""
    candidates = []
    best = None
    for C in C_GRID:
        t0 = time.perf_counter()
        model = LogisticRegression(C=C, max_iter=1000, tol=1e-3, class_weight="balanced")
        model.fit(Xtr, ytr)
        val = model.predict_proba(Xva)[:, 1]
        auc = float(roc_auc_score(yva, val)) if 0 < yva.sum() < len(yva) else float("nan")
        candidates.append({"C": C, "val_roc_auc": round(auc, 4), "fit_seconds": round(time.perf_counter() - t0, 1)})
        if best is None or (auc == auc and auc > best[0]):
            best = (auc, C, model, val)
    _, C, model, val = best

    # Balanced class weights make the raw scores meaningless as probabilities; calibration puts them back on
    # a scale a reader can act on. Isotonic needs positives to be worth its flexibility.
    if yva.sum() >= 100:
        calibrator, kind = IsotonicRegression(out_of_bounds="clip").fit(val, yva), "isotonic"
    else:
        calibrator, kind = LogisticRegression(max_iter=1000).fit(val.reshape(-1, 1), yva), "platt"
    calibrated = _apply(calibrator, val)
    return Head(finding, model, calibrator,
                _threshold_at_sensitivity(yva, calibrated, RULE_OUT_SENSITIVITY),
                _threshold_at_sensitivity(yva, calibrated, ATTENTION_SENSITIVITY),
                C, kind, published=False), candidates


def _apply(calibrator, raw: np.ndarray) -> np.ndarray:
    if isinstance(calibrator, IsotonicRegression):
        return np.clip(calibrator.predict(raw), 1e-6, 1 - 1e-6)
    return calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]


def _operating_points(y: np.ndarray, p: np.ndarray, head: "Head") -> list[dict]:
    """What each cut-off actually costs and buys, measured on the test films."""
    rows = []
    for name, target, threshold in (("rule_out", RULE_OUT_SENSITIVITY, head.threshold),
                                    ("attention", ATTENTION_SENSITIVITY, head.threshold_high)):
        flagged = p >= threshold
        positives, negatives = y == 1, y == 0
        rows.append({
            "name": name, "target_sensitivity": target, "threshold": round(float(threshold), 4),
            "sensitivity": round(float(flagged[positives].mean()), 4) if positives.any() else None,
            "specificity": round(float((~flagged)[negatives].mean()), 4) if negatives.any() else None,
            "share_flagged": round(float(flagged.mean()), 4),
        })
    return rows


def _subgroups(data: Dataset, mask: np.ndarray, y: np.ndarray, p: np.ndarray) -> list[dict]:
    """Accuracy for the groups a reader would ask about: sex, view and age."""
    rows = []
    groups = [("sex", label, data.sex[mask] == label) for label in ("F", "M")]
    groups += [("view", label, data.view[mask] == label) for label in ("PA", "AP")]
    ages = data.age[mask]
    groups += [("age", label, (ages >= lo) & (ages <= hi)) for lo, hi, label in AGE_BANDS]
    for kind, label, pick in groups:
        if pick.sum() < 50 or not 0 < y[pick].sum() < pick.sum():
            continue
        rows.append({"group": kind, "value": label, "n": int(pick.sum()), "positives": int(y[pick].sum()),
                     "roc_auc": round(float(roc_auc_score(y[pick], p[pick])), 4)})
    return rows


def _metadata_baseline(data: Dataset, train: np.ndarray, test: np.ndarray, finding: str) -> float:
    """What can be predicted from age, sex and view alone? A film model must beat the camera."""
    def frame(mask):
        return np.column_stack([data.age[mask], (data.sex[mask] == "M").astype(float),
                                (data.view[mask] == "AP").astype(float)])
    ytr, yte = _targets(data, finding)[train], _targets(data, finding)[test]
    if not 0 < yte.sum() < len(yte):
        return float("nan")
    model = LogisticRegression(max_iter=1000, class_weight="balanced").fit(frame(train), ytr)
    return float(roc_auc_score(yte, model.predict_proba(frame(test))[:, 1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = build()
    train, val, test = grouped_split(data.patient_id, seed=SEED)
    print(f"{len(data)} films, {len(np.unique(data.patient_id))} patients -> "
          f"train {train.sum()} / val {val.sum()} / test {test.sum()}")
    scaler = StandardScaler().fit(data.features[train])
    Xtr, Xva, Xte = (scaler.transform(data.features[m]) for m in (train, val, test))
    rng = np.random.default_rng(SEED)

    heads: dict[str, Head] = {}
    report: dict[str, dict] = {}
    for finding in [ANY_FINDING, *FINDINGS]:
        y = _targets(data, finding)
        ytr, yva, yte = y[train], y[val], y[test]
        if ytr.sum() < 20 or yva.sum() < 5 or yte.sum() < 10:
            report[finding] = {"skipped": "too few positive films to fit or evaluate",
                               "positives": {"train": int(ytr.sum()), "val": int(yva.sum()), "test": int(yte.sum())}}
            print(f"  {finding:20s} skipped (positives {ytr.sum()}/{yva.sum()}/{yte.sum()})", flush=True)
            continue
        t0 = time.perf_counter()
        head, candidates = _fit_head(finding, Xtr, ytr, Xva, yva, rng)
        probabilities = _apply(head.calibrator, head.model.predict_proba(Xte)[:, 1])
        metrics = classification_metrics(yte, probabilities, head.threshold)
        low, high = _bootstrap_auc(yte, probabilities, rng)
        head.published = bool(metrics["roc_auc"] >= MIN_AUC and low >= MIN_AUC_LOWER and yte.sum() >= MIN_POSITIVES)
        heads[finding] = head
        tn, fp, fn, tp = (metrics["confusion_matrix"][k] for k in ("tn", "fp", "fn", "tp"))
        report[finding] = {
            **metrics, "roc_auc_ci": [round(low, 4), round(high, 4)],
            "sensitivity": round(tp / max(1, tp + fn), 4), "specificity": round(tn / max(1, tn + fp), 4),
            "operating_points": _operating_points(yte, probabilities, head),
            "metadata_only_roc_auc": round(_metadata_baseline(data, train, test, finding), 4),
            "calibration": head.calibration, "calibration_bins": calibration_bins(yte, probabilities),
            "regularisation_C": head.C, "candidates": candidates, "published": head.published,
            "subgroups": _subgroups(data, test, yte, probabilities),
        }
        print(f"  {finding:20s} AUC {metrics['roc_auc']:.3f} [{low:.3f}-{high:.3f}]  "
              f"sens {report[finding]['sensitivity']:.2f} spec {report[finding]['specificity']:.2f}  "
              f"meta-only {report[finding]['metadata_only_roc_auc']:.3f}  "
              f"{'PUBLISHED' if head.published else 'held back'}  ({time.perf_counter() - t0:.0f}s)", flush=True)

    published = [f for f, h in heads.items() if h.published]
    payload = {
        "scaler": scaler,
        "heads": {f: {"model": h.model, "calibrator": h.calibrator, "calibration": h.calibration,
                      "threshold": h.threshold, "threshold_high": h.threshold_high}
                  for f, h in heads.items()},
        "published": published,
    }
    metadata = {
        "task": "classification",
        "algorithm": "resnet50_frozen+logistic_regression",
        "target": "thoracic findings on a frontal chest radiograph (NIH ChestX-ray14 label set)",
        "dataset": {"name": data.source["name"], "citation": "Wang et al., CVPR 2017 (NIH Clinical Center)",
                    "labels": "NLP-mined from radiology reports (~90% accurate by the authors' estimate)",
                    "sha256": data.source["sha256"], "shards": data.source["shards"],
                    "rows_used": len(data), "patients": int(len(np.unique(data.patient_id))),
                    "split": {"train": int(train.sum()), "val": int(val.sum()), "test": int(test.sum()),
                              "grouped_by": "patient"}},
        "features": {"set": "cxr_backbone_v1", "backbone": REPO, "description": DESCRIPTION,
                     "input_size": INPUT_SIZE, "dimension": FEATURE_DIM, "fine_tuned": False},
        "publication_bar": {"roc_auc": MIN_AUC, "roc_auc_ci_lower": MIN_AUC_LOWER,
                            "test_positives": MIN_POSITIVES, "bootstraps": BOOTSTRAPS},
        "operating_point": {
            "rule": f"two cut-offs per finding, set on validation at {RULE_OUT_SENSITIVITY:.0%} sensitivity "
                    f"(rule-out) and {ATTENTION_SENSITIVITY:.0%} sensitivity (attention)",
            "thresholds": {f: {"rule_out": round(h.threshold, 4), "attention": round(h.threshold_high, 4)}
                           for f, h in heads.items()}},
        "published_findings": published,
        "metrics": {"test": report},
        "intended_use": "Reading-order support and a second look on adult frontal chest radiographs. Not a "
                        "diagnosis, not a report, and not validated for clinical use.",
        "limitations": LIMITATIONS,
    }
    target = save_artifact(MODEL_NAME, args.version, payload, metadata, force=args.force)
    print(f"\nSaved {target}")
    print(json.dumps({"published": published}, indent=2))
    print(f"Report: {write_cxr_triage_report(target / 'metadata.json')}")


if __name__ == "__main__":
    main()
