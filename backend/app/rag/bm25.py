"""Okapi BM25 keyword retrieval with a domain-aware tokenizer.

Why not Postgres full-text search? ts_rank is not BM25 (no IDF saturation / length normalisation)
and English stemming mangles identifiers. Clinical text is full of exact tokens that embeddings
blur - "HbA1c", "eGFR", "MED-POL-004", "P1024", drug names - so the tokenizer keeps them whole
(and additionally indexes their parts).

The index is held in memory per worker and rebuilt when the corpus signature (chunk count, max id,
last document update) changes. Authorization/metadata filtering is applied by passing the set of
chunk ids the caller may see; scores for other chunks are never computed or returned.
Scale note: fine for tens of thousands of chunks; beyond that use a search engine / pg_search.
"""
import math
import re
import threading
from collections import Counter, defaultdict
from collections.abc import Iterable

_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")
STOPWORDS = frozenset([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it", "its",
    "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with", "what", "which", "who",
    "whom", "how", "when", "where", "does", "do", "our", "we", "you", "your", "their", "they", "them",
    "should", "would", "can", "could", "about", "into", "than", "then", "there", "these", "those", "not", "no",
])


def _normalise(token: str) -> str:
    if len(token) > 4 and token.isalpha():
        if token.endswith("ies"):
            return token[:-3] + "y"
        if token.endswith("s") and not token.endswith("ss"):
            return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for tok in _TOKEN.findall(text.lower()):
        tok = tok.strip(".-/")
        if not tok or tok in STOPWORDS:
            continue
        out.append(_normalise(tok))
        if any(sep in tok for sep in ".-/"):
            # "med-pol-004" also matches "pol 004"; "e11.9" also matches "e11"
            out.extend(p for p in re.split(r"[.\-/]", tok) if p and p not in STOPWORDS and not p.isdigit())
    return out


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_len: dict[int, int] = {}
        self.postings: dict[str, dict[int, int]] = defaultdict(dict)
        self.avgdl = 0.0

    def build(self, docs: Iterable[tuple[int, str]]) -> "BM25Index":
        for doc_id, text in docs:
            tf = Counter(tokenize(text))
            self.doc_len[doc_id] = sum(tf.values())
            for term, count in tf.items():
                self.postings[term][doc_id] = count
        self.avgdl = (sum(self.doc_len.values()) / len(self.doc_len)) if self.doc_len else 0.0
        return self

    def idf(self, term: str) -> float:
        n, df = len(self.doc_len), len(self.postings.get(term, ()))
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, k: int = 30, allowed: set[int] | None = None) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = self.idf(term)
            for doc_id, tf in postings.items():
                if allowed is not None and doc_id not in allowed:
                    continue
                norm = tf + self.k1 * (1 - self.b + self.b * self.doc_len[doc_id] / (self.avgdl or 1))
                scores[doc_id] += idf * tf * (self.k1 + 1) / norm
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


class BM25Store:
    """Process-wide cache of the BM25 index, invalidated by a corpus signature."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._signature: tuple | None = None
        self._index: BM25Index | None = None

    def get(self, signature: tuple, loader) -> BM25Index:
        with self._lock:
            if self._index is None or signature != self._signature:
                self._index = BM25Index().build(loader())
                self._signature = signature
            return self._index

    def invalidate(self) -> None:
        with self._lock:
            self._index, self._signature = None, None


bm25_store = BM25Store()
