"""Turn the downloaded NIH ChestX-ray14 shards into frozen backbone features.

    uv run --project backend python -m ml.preprocessing.nih_cxr

Every film is passed through the same ONNX ResNet-50 the API serves (app.imaging.backbone), so the numbers
the heads are fitted on are the numbers the running system produces. The result is cached as one .npz next
to the shards; extraction is the slow part (~25 ms a film) and training re-runs read the cache.

Dataset: Wang et al., CVPR 2017 (NIH Clinical Center). The labels were mined from radiology reports with
NLP and are ~90% accurate by the authors' own estimate, which caps how good any model fitted on them can
look and is the first limitation in the model card.
"""
import hashlib
import io
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.imaging.backbone import FEATURE_DIM, get_backbone, prepare

# CAREFLOW_CXR_DIR points the pipeline at an existing download (a big corpus does not belong in a synced
# folder, and re-downloading 5 GB to try a different head would be silly).
RAW = Path(os.environ.get("CAREFLOW_CXR_DIR") or Path(__file__).resolve().parents[1] / "data" / "raw" / "cxr")
CACHE = RAW / "features_v1.npz"

# The 14 findings of ChestX-ray14, in the dataset's own order. "No Finding" is the absence of all of them.
FINDINGS = ["Atelectasis", "Cardiomegaly", "Effusion", "Infiltration", "Mass", "Nodule", "Pneumonia",
            "Pneumothorax", "Consolidation", "Edema", "Emphysema", "Fibrosis", "Pleural_Thickening", "Hernia"]
MAX_PLAUSIBLE_AGE = 100  # the release contains a handful of typos (ages of 148, 411 ...)
BATCH = 16


@dataclass
class Dataset:
    features: np.ndarray      # (n, 2048) float32
    labels: np.ndarray        # (n, 14) uint8
    patient_id: np.ndarray    # (n,) int   - the split is grouped on this
    age: np.ndarray           # (n,) int
    sex: np.ndarray           # (n,) '<U1' M/F
    view: np.ndarray          # (n,) '<U2' PA/AP
    image: np.ndarray         # (n,) original file name, e.g. 00000013_005.png
    source: dict              # provenance for the model card

    def __len__(self) -> int:
        return len(self.patient_id)

    @property
    def any_finding(self) -> np.ndarray:
        return (self.labels.sum(axis=1) > 0).astype(np.uint8)


def shard_paths() -> list[Path]:
    return sorted(RAW.rglob("*.parquet"))


def _digest(paths: list[Path]) -> str:
    """Identify the slice by shard names and sizes; hashing 5 GB of pixels would gain nothing."""
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode())
        h.update(str(p.stat().st_size).encode())
    return h.hexdigest()


def _read_shard(path: Path) -> dict:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    images = table.column("image").to_pylist()
    return {
        "bytes": [im["bytes"] for im in images],
        "name": [Path(im.get("path") or "").name for im in images],
        "labels": table.column("label").to_pylist(),
        "patient_id": table.column("Patient ID").to_pylist(),
        "age": table.column("Patient Age").to_pylist(),
        "sex": table.column("Patient Gender").to_pylist(),
        "view": table.column("View Position").to_pylist(),
    }


def _features(blobs: list[bytes]) -> np.ndarray:
    from PIL import Image

    backbone = get_backbone()
    out = np.empty((len(blobs), FEATURE_DIM), dtype=np.float32)
    with ThreadPoolExecutor(8) as pool:
        for start in range(0, len(blobs), BATCH):
            chunk = blobs[start:start + BATCH]
            tensors = list(pool.map(lambda b: prepare(np.asarray(Image.open(io.BytesIO(b)).convert("L"))), chunk))
            pooled, _ = backbone.embed(np.stack(tensors))
            out[start:start + len(chunk)] = pooled
    return out


def build(force: bool = False) -> Dataset:
    """Extract (or load) features for every downloaded shard."""
    paths = shard_paths()
    if not paths:
        raise FileNotFoundError(f"No shards in {RAW}. Run: python -m ml.data.download_cxr")
    digest = _digest(paths)
    if CACHE.exists() and not force:
        cached = np.load(CACHE, allow_pickle=False)
        if str(cached["digest"]) == digest:
            return Dataset(cached["features"], cached["labels"], cached["patient_id"], cached["age"],
                           cached["sex"], cached["view"], cached["image"],
                           {"name": "NIH ChestX-ray14", "shards": len(paths), "sha256": digest,
                            "rows": int(len(cached["patient_id"]))})

    feats, labels, pid, age, sex, view, image = [], [], [], [], [], [], []
    dropped = 0
    for path in paths:
        t0 = time.perf_counter()
        shard = _read_shard(path)
        keep = [i for i, a in enumerate(shard["age"]) if 0 < a <= MAX_PLAUSIBLE_AGE]
        dropped += len(shard["age"]) - len(keep)
        feats.append(_features([shard["bytes"][i] for i in keep]))
        labels.extend([[1 if f in shard["labels"][i] else 0 for f in FINDINGS] for i in keep])
        for column, target in (("patient_id", pid), ("age", age), ("sex", sex), ("view", view), ("name", image)):
            target.extend(shard[column][i] for i in keep)
        print(f"  {path.name}: {len(keep)} films in {time.perf_counter() - t0:.0f}s", flush=True)

    data = Dataset(
        features=np.concatenate(feats), labels=np.array(labels, dtype=np.uint8),
        patient_id=np.array(pid, dtype=np.int32), age=np.array(age, dtype=np.int16),
        sex=np.array(sex, dtype="<U1"), view=np.array(view, dtype="<U2"), image=np.array(image, dtype="<U32"),
        source={"name": "NIH ChestX-ray14", "shards": len(paths), "sha256": digest, "rows": len(pid),
                "dropped_implausible_age": dropped})
    np.savez_compressed(CACHE, digest=digest, features=data.features, labels=data.labels,
                        patient_id=data.patient_id, age=data.age, sex=data.sex, view=data.view, image=data.image)
    print(f"Cached {len(data)} films -> {CACHE}")
    return data


def grouped_split(patient_id: np.ndarray, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split 70/10/20 by PATIENT. Two films of the same chest are not independent samples, and the
    dataset ships several studies per patient, so splitting by film would leak."""
    patients = np.unique(patient_id)
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(patients)
    n_train, n_val = int(0.7 * len(shuffled)), int(0.1 * len(shuffled))
    groups = {"train": set(shuffled[:n_train].tolist()),
              "val": set(shuffled[n_train:n_train + n_val].tolist()),
              "test": set(shuffled[n_train + n_val:].tolist())}
    return tuple(np.array([p in groups[name] for p in patient_id]) for name in ("train", "val", "test"))


if __name__ == "__main__":
    build()
