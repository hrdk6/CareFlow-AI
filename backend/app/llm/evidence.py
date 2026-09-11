"""Evidence store: every fact the answer may use, each with a stable citation id.

[R#] = a database record (medical record, lab, prescription, admission, diagnosis, patient, appointment)
[S#] = a retrieved document chunk
Ids are assigned only when evidence actually enters the context, so a citation can never point to
something the model did not receive.
"""
from dataclasses import dataclass, field
from typing import Any

from app.rag.retrieval import RetrievedChunk
from app.schemas.ai import Citation, RecordRef
from app.schemas.ml import PredictionOut, SimilarityOut


@dataclass
class EvidenceBlock:
    kind: str  # database | documents | prediction | similarity | tool_status
    title: str
    text: str


@dataclass
class EvidenceStore:
    records: dict[str, RecordRef] = field(default_factory=dict)
    _record_keys: dict[tuple[str, int], str] = field(default_factory=dict)
    sources: dict[str, RetrievedChunk] = field(default_factory=dict)
    _source_keys: dict[int, str] = field(default_factory=dict)
    blocks: list[EvidenceBlock] = field(default_factory=list)
    predictions: list[PredictionOut] = field(default_factory=list)
    similarity: SimilarityOut | None = None
    data: dict[str, Any] = field(default_factory=dict)
    patient_ids: set[int] = field(default_factory=set)
    retrieval: dict = field(default_factory=dict)
    withheld_sources: list[dict] = field(default_factory=list)
    model_versions: list[str] = field(default_factory=list)

    def ref_record(self, source_type: str, source_id: int, label: str, date: str | None = None) -> str:
        key = (source_type, source_id)
        if key not in self._record_keys:
            rid = f"R{len(self.records) + 1}"
            self._record_keys[key] = rid
            self.records[rid] = RecordRef(id=rid, source_type=source_type, source_id=source_id, label=label[:160],
                                          date=date)
        return self._record_keys[key]

    def ref_chunk(self, chunk: RetrievedChunk) -> str:
        if chunk.chunk_id not in self._source_keys:
            sid = f"S{len(self.sources) + 1}"
            self._source_keys[chunk.chunk_id] = sid
            self.sources[sid] = chunk
        return self._source_keys[chunk.chunk_id]

    def add_block(self, kind: str, title: str, text: str) -> None:
        self.blocks.append(EvidenceBlock(kind, title, text))

    @property
    def valid_ids(self) -> set[str]:
        return set(self.records) | set(self.sources)

    def has_substantive_evidence(self) -> bool:
        """True when anything besides access-denied/not-found notices was gathered (records OR documents)."""
        return bool(self.sources) or any(b.kind != "tool_status" for b in self.blocks)

    def citation(self, sid: str) -> Citation:
        c = self.sources[sid]
        return Citation(id=sid, chunk_id=c.chunk_id, document_id=c.document_id, document_title=c.document_title,
                        version=c.doc_version, page_start=c.page_start, page_end=c.page_end,
                        section_path=c.section_path, excerpt=c.text[:700], retrieval=c.retrieval_info())
