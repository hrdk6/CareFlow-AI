"""Model registry: loads versioned artifacts and mirrors their model cards into `model_versions`.

Layout (produced by ml/training):  <model_dir>/<model_name>/<version>/{model.joblib, metadata.json}
                                    <model_dir>/registry.json  -> {"model_name": "active version"}
Callers ask for a model by NAME; which version is active is configuration, not code.
"""
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models import ModelVersion

logger = logging.getLogger("careflow.ml")


@dataclass
class LoadedModel:
    name: str
    version: str
    payload: dict
    metadata: dict

    @property
    def trained_at(self) -> str:
        return self.metadata.get("trained_at", "")


def limit_threads(payload: dict, threads: int | None) -> None:
    """Cap inference threads on the loaded estimator. Predictions are unchanged; only parallelism is.

    Artifacts are trained with n_jobs=-1 (every core). On a small container that still sees the host's cores, a
    single prediction would start one worker per host core, each with its own buffers.
    """
    if not threads or "pipeline" not in payload:  # the imaging heads are linear models, not a pipeline
        return
    estimator = payload["pipeline"].named_steps["model"]
    if hasattr(estimator, "n_jobs"):
        estimator.set_params(n_jobs=threads)


class ModelRegistry:
    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self._cache: dict[tuple[str, str], LoadedModel] = {}
        self._lock = threading.Lock()

    def active_versions(self) -> dict[str, str]:
        path = self.model_dir / "registry.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def metadata(self, name: str, version: str) -> dict:
        path = self.model_dir / name / version / "metadata.json"
        if not path.exists():
            raise ServiceUnavailableError(f"Model card for {name} v{version} not found")
        return json.loads(path.read_text())

    def get(self, name: str) -> LoadedModel:
        version = self.active_versions().get(name)
        if version is None:
            raise ServiceUnavailableError(
                f"No active '{name}' model. Train it with: python -m ml.training.train_all")
        key = (name, version)
        with self._lock:
            if key not in self._cache:
                artifact = self.model_dir / name / version / "model.joblib"
                if not artifact.exists():
                    raise ServiceUnavailableError(f"Model artifact missing for {name} v{version}")
                try:
                    payload = joblib.load(artifact)
                    limit_threads(payload, get_settings().model_threads)
                except Exception as exc:  # corrupted file or incompatible library versions
                    logger.exception("model load failed")
                    raise ServiceUnavailableError(f"Model {name} v{version} could not be loaded") from exc
                self._cache[key] = LoadedModel(name, version, payload, self.metadata(name, version))
            return self._cache[key]


@lru_cache
def get_registry() -> ModelRegistry:
    return ModelRegistry(get_settings().model_dir)


def sync_registry(db: Session, registry: ModelRegistry | None = None) -> list[ModelVersion]:
    """Upsert every model card found on disk into model_versions; mark the active versions."""
    registry = registry or get_registry()
    active = registry.active_versions()
    rows: list[ModelVersion] = []
    if not registry.model_dir.exists():
        return rows
    for meta_path in sorted(registry.model_dir.glob("*/*/metadata.json")):
        meta = json.loads(meta_path.read_text())
        name, version = meta["model_name"], meta["version"]
        row = db.scalar(select(ModelVersion).where(ModelVersion.model_name == name, ModelVersion.version == version))
        if row is None:
            row = ModelVersion(model_name=name, version=version)
            db.add(row)
        row.task = meta["task"]
        row.algorithm = meta["algorithm"]
        row.trained_at = datetime.fromisoformat(meta["trained_at"])
        row.dataset_name = meta["dataset"]["name"]
        row.dataset_version = meta["dataset"]["sha256"][:16]
        row.feature_config = meta["features"]
        row.metrics = meta["metrics"]
        row.artifact_path = str(meta_path.parent.relative_to(registry.model_dir))
        row.is_active = active.get(name) == version
        rows.append(row)
    db.flush()
    return rows


def model_version_row(db: Session, name: str, version: str) -> ModelVersion:
    row = db.scalar(select(ModelVersion).where(ModelVersion.model_name == name, ModelVersion.version == version))
    if row is None:
        sync_registry(db)
        row = db.scalar(select(ModelVersion).where(ModelVersion.model_name == name, ModelVersion.version == version))
    if row is None:
        raise ServiceUnavailableError(f"Model {name} v{version} is not registered")
    return row
