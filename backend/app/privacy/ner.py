"""Finding the names a dictionary cannot know about.

The pseudonymisation vault knows every identifier the database holds. What it cannot know is a third
party written into free text - "patient's daughter Ravi Menon called", "discussed with Dr Sandhya Iyer at
Apollo" - because nobody ever issued that name to CareFlow. This module is the second pass: a named-entity
model reads the text the dictionary has already been through and masks the people it still finds.

The model is `Xenova/bert-base-NER`, an ONNX export of dslim/bert-base-NER (BERT-base fine-tuned on
CoNLL-2003). It is a general-purpose tagger, not a clinical de-identification model, and its recall on
clinical prose is good but not perfect - which is why it is a second pass over a deterministic first one
and not a replacement for it. What it costs and what it catches is measured in tests/test_privacy.py.
"""
import logging
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("careflow.privacy")

REPO = "Xenova/bert-base-NER"
# int8: a third of the size and about three times the speed of the float model, for a difference in
# tagging this pass does not depend on (a missed name is caught by the dictionary or by the next pass).
FILES = {"model": "onnx/model_quantized.onnx", "tokenizer": "tokenizer.json", "config": "config.json"}
MAX_TOKENS = 384          # comfortably inside the model's 512, with room for the [CLS]/[SEP] pair
CHUNK_CHARS = 1000        # ~250 tokens of clinical prose
PERSON_LABELS = ("B-PER", "I-PER")
CACHE_ENTRIES = 256
# Words a tagger trained on news mislabels as people often enough to be worth refusing outright.
NEVER = {"patient", "mrn", "dob", "nhs", "icu", "ct", "mri", "ecg", "covid", "x-ray"}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


def _chunks(text: str) -> list[tuple[int, str]]:
    """Split on whitespace near CHUNK_CHARS so no chunk can exceed the model's window."""
    out: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            space = text.rfind(" ", start + CHUNK_CHARS // 2, end)
            if space > start:
                end = space
        out.append((start, text[start:end]))
        start = end
    return out


class NameFinder:
    """Lazily loaded ONNX tagger. Loading costs ~1 s and ~120 MB, so it happens on first use."""

    def __init__(self) -> None:
        self._session = None
        self._tokenizer = None
        self._labels: dict[int, str] = {}
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[Span, ...]] = {}
        self.available = True

    # ------------------------------------------------------------------ loading
    def _download(self) -> dict[str, Path]:
        from huggingface_hub import hf_hub_download

        cache = get_settings().model_cache_dir
        cache.mkdir(parents=True, exist_ok=True)
        return {key: Path(hf_hub_download(repo_id=REPO, filename=name, cache_dir=str(cache)))
                for key, name in FILES.items()}

    def _load(self) -> bool:
        import json

        import onnxruntime as ort
        from tokenizers import Tokenizer

        try:
            paths = self._download()
            tokenizer = Tokenizer.from_file(str(paths["tokenizer"]))
            tokenizer.enable_truncation(MAX_TOKENS)
            options = ort.SessionOptions()
            threads = get_settings().model_threads
            if threads:
                options.intra_op_num_threads = threads
            self._session = ort.InferenceSession(str(paths["model"]), options,
                                                 providers=["CPUExecutionProvider"])
            self._tokenizer = tokenizer
            self._labels = {int(k): v for k, v in json.loads(paths["config"].read_text())["id2label"].items()}
            return True
        except Exception:
            # A host without the model still pseudonymises with the dictionary; it just says so.
            logger.warning("name finder unavailable; the dictionary pass runs alone", exc_info=True)
            self.available = False
            return False

    def _ready(self) -> bool:
        if self._session is None and self.available:
            with self._lock:
                if self._session is None and self.available:
                    self._load()
        return self._session is not None

    # ------------------------------------------------------------------ tagging
    def find(self, text: str) -> tuple[Span, ...]:
        """Every person name in `text`, as character spans, longest-match and non-overlapping."""
        if not text or not text.strip() or not self._ready():
            return ()
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        spans = self._tag(text)
        if len(self._cache) >= CACHE_ENTRIES:
            self._cache.clear()   # one request's evidence is repeated across rounds; nothing lives longer
        self._cache[text] = spans
        return spans

    def _tag(self, text: str) -> tuple[Span, ...]:
        pieces = _chunks(text)
        encodings = [self._tokenizer.encode(piece) for _, piece in pieces]
        width = max(len(e.ids) for e in encodings)
        ids = np.zeros((len(encodings), width), dtype=np.int64)
        mask = np.zeros_like(ids)
        for row, encoding in enumerate(encodings):
            ids[row, :len(encoding.ids)] = encoding.ids
            mask[row, :len(encoding.ids)] = encoding.attention_mask
        feed = {"input_ids": ids, "attention_mask": mask}
        if any(i.name == "token_type_ids" for i in self._session.get_inputs()):
            feed["token_type_ids"] = np.zeros_like(ids)
        logits = self._session.run(None, feed)[0]
        predictions = logits.argmax(axis=-1)

        spans: list[Span] = []
        for row, (offset, piece) in enumerate(pieces):
            encoding = encodings[row]
            current: list[tuple[int, int]] = []
            previous_end = -1
            for position, (token_start, token_end) in enumerate(encoding.offsets):
                if position >= width or token_end <= token_start:   # special tokens have empty offsets
                    continue
                label = self._labels.get(int(predictions[row, position]), "O")
                token = encoding.tokens[position]
                # The tagger works on word pieces and happily puts B-PER on every piece of a name, so a
                # new entity only starts at a piece that begins a word.
                starts_word = (not token.startswith("##")
                               and (token_start != previous_end or not token[:1].isalnum()))
                if label in PERSON_LABELS:
                    if label == "B-PER" and current and starts_word:
                        spans.append(self._span(piece, offset, current))
                        current = []
                    current.append((token_start, token_end))
                elif current and starts_word:
                    spans.append(self._span(piece, offset, current))
                    current = []
                elif current:
                    current.append((token_start, token_end))  # the rest of a word whose first piece was PER
                previous_end = token_end
            if current:
                spans.append(self._span(piece, offset, current))
        return tuple(s for s in spans if self._plausible(s))

    @staticmethod
    def _span(piece: str, offset: int, tokens: list[tuple[int, int]]) -> Span:
        """Grow the piece-level span out to whole words: half a surname is worse than none."""
        start, end = tokens[0][0], tokens[-1][1]
        while start > 0 and (piece[start - 1].isalnum() or piece[start - 1] in "'-"):
            start -= 1
        while end < len(piece) and (piece[end].isalnum() or piece[end] in "'-"):
            end += 1
        return Span(offset + start, offset + end, piece[start:end])

    @staticmethod
    def _plausible(span: Span) -> bool:
        text = span.text.strip()
        return (len(text) >= 3 and text.casefold() not in NEVER
                and bool(re.search(r"[A-Za-z]{3}", text)) and not text.isupper())


@lru_cache
def get_name_finder() -> NameFinder:
    return NameFinder()


def name_finder_enabled() -> bool:
    return get_settings().privacy_ner
