"""Chest radiograph triage: what the model says about a film, and where on the film it was looking.

The model is a set of linear heads on frozen ResNet-50 features (trained by ml/training/train_cxr_triage.py).
Only the findings that met the publication bar on the held-out test set are reported at all - the model card
lists the rest with the numbers that kept them out.

This is a reading-order aid and a second look. It does not diagnose, it never writes to the record, and the
radiologist's report is written by the radiologist; see app/services/imaging.py for the sign-off path.
"""
import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.core.errors import ServiceUnavailableError
from app.imaging.backbone import get_backbone, prepare
from app.ml.registry import LoadedModel, get_registry
from app.observability.metrics import COMPONENT_ERRORS, ML_INFERENCE_LATENCY

logger = logging.getLogger("careflow.imaging")

MODEL_NAME = "chest_xray_triage"
ANY_FINDING = "any_finding"
DISCLAIMER = ("Triage support from a statistical model, for reading order and a second look. It is not a "
              "diagnosis, it is not a report, and a film it does not flag has not been cleared.")
# Where a film sits in the reading queue, from the two measured cut-offs in the model card: below the
# rule-out cut-off, between the two, and above the attention cut-off.
PRIORITY_BANDS = ("routine", "elevated", "priority")

LABELS = {
    ANY_FINDING: "Any finding", "Effusion": "Pleural effusion", "Pneumothorax": "Pneumothorax",
    "Consolidation": "Consolidation", "Edema": "Pulmonary oedema", "Emphysema": "Emphysema",
    "Cardiomegaly": "Cardiomegaly", "Atelectasis": "Atelectasis", "Infiltration": "Infiltration",
    "Mass": "Mass", "Nodule": "Nodule", "Pneumonia": "Pneumonia", "Fibrosis": "Fibrosis",
    "Pleural_Thickening": "Pleural thickening", "Hernia": "Hernia",
}


@dataclass
class FindingScore:
    finding: str
    label: str
    probability: float
    threshold: float            # rule-out cut-off
    flagged: bool               # at or above the rule-out cut-off
    priority: bool              # at or above the attention cut-off
    roc_auc: float
    roc_auc_ci: list[float]
    sensitivity: float          # measured on the test films AT THIS cut-off, so a reader can weigh the flag
    specificity: float
    prevalence: float
    attention: list[list[float]] = field(default_factory=list)  # class activation map, row-major


@dataclass
class TriageResult:
    priority: str
    priority_score: float          # probability of any finding
    findings: list[FindingScore]
    model_name: str
    model_version: str
    trained_at: str
    backbone: str
    operating_point: str
    limitations: list[str]
    inference_ms: int

    @property
    def flagged(self) -> list[FindingScore]:
        return [f for f in self.findings if f.flagged and f.finding != ANY_FINDING]


def _calibrate(head: dict, raw: np.ndarray) -> float:
    calibrator = head["calibrator"]
    if head["calibration"] == "isotonic":
        return float(np.clip(calibrator.predict(raw), 1e-6, 1 - 1e-6)[0])
    return float(calibrator.predict_proba(raw.reshape(-1, 1))[0, 1])


def _activation(model, scale: np.ndarray, spatial: np.ndarray) -> list[list[float]]:
    """Exact class activation map: the head is linear on globally averaged features, so each location's
    contribution to the score is w . f(x, y) with the very weights the probability uses."""
    weights = model.coef_[0] / scale
    cam = np.tensordot(weights, spatial, axes=([0], [0]))     # (h, w)
    low, high = float(cam.min()), float(cam.max())
    if high - low < 1e-9:
        return [[0.0] * cam.shape[1] for _ in range(cam.shape[0])]
    return np.round((cam - low) / (high - low), 4).tolist()


def _band(score: "FindingScore") -> str:
    return PRIORITY_BANDS[2] if score.priority else PRIORITY_BANDS[1] if score.flagged else PRIORITY_BANDS[0]


def available() -> bool:
    """Whether this deployment can score films at all (the artifact may not be trained here)."""
    try:
        get_registry().get(MODEL_NAME)
        return True
    except ServiceUnavailableError:
        return False


def score(pixels: np.ndarray) -> TriageResult:
    """Score one radiograph. Raises ServiceUnavailableError if the model or backbone is not installed."""
    model: LoadedModel = get_registry().get(MODEL_NAME)
    payload, meta = model.payload, model.metadata
    t0 = time.perf_counter()
    try:
        pooled, spatial = get_backbone().embed(prepare(pixels)[None])
        scaled = payload["scaler"].transform(pooled)
        results: list[FindingScore] = []
        for finding in payload["published"]:
            head = payload["heads"][finding]
            probability = _calibrate(head, head["model"].predict_proba(scaled)[:, 1])
            measured = meta["metrics"]["test"][finding]
            rule_out = next(o for o in measured["operating_points"] if o["name"] == "rule_out")
            results.append(FindingScore(
                finding=finding, label=LABELS.get(finding, finding), probability=round(probability, 4),
                threshold=round(head["threshold"], 4), flagged=probability >= head["threshold"],
                priority=probability >= head["threshold_high"],
                roc_auc=measured["roc_auc"], roc_auc_ci=measured["roc_auc_ci"],
                sensitivity=rule_out["sensitivity"], specificity=rule_out["specificity"],
                prevalence=measured["prevalence"],
                attention=_activation(head["model"], payload["scaler"].scale_, spatial[0])))
    except ServiceUnavailableError:
        raise
    except Exception as exc:
        COMPONENT_ERRORS.labels("ml_inference").inc()
        logger.exception("chest radiograph triage failed")
        raise ServiceUnavailableError("The imaging model could not score this study") from exc
    finally:
        ML_INFERENCE_LATENCY.labels(MODEL_NAME).observe(time.perf_counter() - t0)

    overall = next(f for f in results if f.finding == ANY_FINDING)
    # Worst finding first, but keep "any finding" at the top: it is the number the queue is ordered by.
    results.sort(key=lambda f: (f.finding != ANY_FINDING, -f.probability))
    return TriageResult(
        priority=_band(overall), priority_score=overall.probability,
        findings=results, model_name=model.name, model_version=model.version, trained_at=model.trained_at,
        backbone=meta["features"]["backbone"], operating_point=meta["operating_point"]["rule"],
        limitations=meta["limitations"], inference_ms=int((time.perf_counter() - t0) * 1000))
