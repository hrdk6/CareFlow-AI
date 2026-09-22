"""The frozen image backbone shared by training and serving.

One ONNX ResNet-50 (ImageNet weights, no medical fine-tuning) turns a chest film into 2048 numbers. The
triage heads in `ml/training/train_cxr_triage.py` are linear models on exactly these numbers, so the
preprocessing has to be identical on both sides - which is why it lives here and training imports it
rather than keeping its own copy.

The graph is loaded with one extra output: the activation just before the global average pool. Because the
head is linear on pooled features, the class activation map is then exact rather than an approximation -
CAM(x, y) = w . f(x, y), the same weights the probability uses (Zhou et al., CVPR 2016).
"""
import logging
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError

logger = logging.getLogger("careflow.imaging")

REPO = "Qdrant/resnet50-onnx"  # ONNX export of microsoft/resnet-50 (ImageNet-1k)
FILENAME = "model.onnx"
# The activation feeding GlobalAveragePool; exposing it costs nothing and makes the CAM exact.
SPATIAL_TENSOR = "/model/encoder/stages.3/layers.2/activation/Relu_output_0"
INPUT_SIZE = 224
FEATURE_DIM = 2048
# ImageNet normalisation, from the backbone's own preprocessor_config.json.
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
DESCRIPTION = "ResNet-50 (ImageNet-1k), frozen; 224x224 grayscale replicated to 3 channels"


def prepare(pixels: np.ndarray) -> np.ndarray:
    """One radiograph (2-D, any size, any dtype) -> the 3x224x224 float tensor the backbone expects.

    The image is squashed, not cropped: a chest film is framed deliberately and cropping it would throw
    away exactly the costophrenic angles and apices that findings hide in.
    """
    from PIL import Image

    a = np.asarray(pixels)
    if a.ndim == 3:  # a colour render of a grayscale film
        a = a.mean(axis=2)
    a = a.astype(np.float32)
    lo, hi = float(a.min()), float(a.max())
    a = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    small = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize(
        (INPUT_SIZE, INPUT_SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    return (np.repeat(small[None], 3, axis=0) - MEAN) / STD


def model_path() -> Path:
    """The backbone file, downloaded into the same cache the embedding models use (baked into the image)."""
    from huggingface_hub import hf_hub_download

    cache = get_settings().model_cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    return Path(hf_hub_download(repo_id=REPO, filename=FILENAME, cache_dir=str(cache)))


def prepared_path() -> Path:
    """The backbone with the pre-pool activation exposed as a second output, written once and reused.

    Editing the graph means holding two copies of it in memory; doing it once and keeping the result on
    disk costs 94 MB of disk and saves that every time a worker starts.
    """
    cached = get_settings().model_cache_dir / "careflow-resnet50-cam.onnx"
    if cached.exists():
        return cached
    import onnx

    graph = onnx.load(str(model_path()))
    if SPATIAL_TENSOR not in {o.name for o in graph.graph.output}:
        graph.graph.output.extend(
            [onnx.helper.make_tensor_value_info(SPATIAL_TENSOR, onnx.TensorProto.FLOAT, None)])
    onnx.save(graph, str(cached))
    return cached


class Backbone:
    """Lazily loaded ONNX session. Loading costs ~1 s and ~150 MB, so it happens on first use, not import."""

    def __init__(self) -> None:
        self._session = None
        self._lock = threading.Lock()

    @property
    def session(self):
        if self._session is None:
            with self._lock:
                if self._session is None:
                    self._session = self._load()
        return self._session

    def _load(self):
        try:
            import onnxruntime as ort

            options = ort.SessionOptions()
            threads = get_settings().model_threads
            if threads:
                options.intra_op_num_threads = threads
            return ort.InferenceSession(str(prepared_path()), options, providers=["CPUExecutionProvider"])
        except Exception as exc:
            logger.exception("image backbone unavailable")
            raise ServiceUnavailableError(
                "The imaging model is not available on this server (the backbone could not be loaded)") from exc

    def embed(self, batch: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(n, 3, 224, 224) -> pooled features (n, 2048) and the spatial map (n, 2048, 7, 7)."""
        pooled, spatial = self.session.run(["output", SPATIAL_TENSOR], {"input": batch.astype(np.float32)})
        return pooled, spatial


@lru_cache
def get_backbone() -> Backbone:
    return Backbone()
