"""Parsing, chunking, embeddings, BM25, fusion, hybrid retrieval, filtering and reranking."""
import io

import pytest
from sqlalchemy import select

from app.auth.access import AccessPolicy
from app.models import Document
from app.rag.bm25 import BM25Index, tokenize
from app.rag.chunking import chunk_document, detect_blocks
from app.rag.embeddings import EmbeddingError, HashingEmbeddingService
from app.rag.parsing import ParsedDocument, ParsedPage, ParsingError, clean_text, parse_file, strip_running_lines
from app.rag.reranking import RerankerError
from app.rag.retrieval import HybridRetriever, RetrievalFilters, rrf_fuse
from tests.conftest import DOCX_SUPPORTED, FASTEMBED_SUPPORTED

GUIDE = """# SAMPLE GUIDELINE

## 1. Scope

This guideline covers adults. It applies to all wards.

## 2. Monitoring

### 2.1 HbA1c

Measure HbA1c every 3 months when not at target. Stable patients every 6 months.

### 2.2 Kidney

Check eGFR yearly. """ + " ".join([f"Additional kidney detail sentence number {i}." for i in range(60)])


# ------------------------------------------------------------------ parsing
def test_clean_text_normalises_whitespace_and_hyphenation():
    assert clean_text("treat-\nment  of\r\n\n\n\nfoo\x07") == "treatment of\n\nfoo"


def test_running_headers_and_footers_are_removed():
    bodies = ["Insulin dosing overview.", "Renal limits for metformin.", "Monitoring intervals.", "Discharge steps."]
    pages = [ParsedPage(i + 1, f"{b}\nCONFIDENTIAL DEMO - page {i + 1}") for i, b in enumerate(bodies)]
    cleaned = strip_running_lines(pages)
    assert all("CONFIDENTIAL" not in p.text for p in cleaned)
    assert [p.text for p in cleaned] == bodies


def test_parse_txt_pdf_docx(tmp_path):
    from fpdf import FPDF

    txt = tmp_path / "a.txt"
    txt.write_text("Hello world policy.\fSecond page.", encoding="utf-8")
    assert parse_file(txt).page_count == 2

    pdf = FPDF()
    for i in range(2):
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, f"Page {i + 1} content about metformin dosing.")
    pdf_path = tmp_path / "a.pdf"
    pdf.output(str(pdf_path))
    parsed = parse_file(pdf_path)
    assert parsed.page_count == 2 and "metformin" in parsed.pages[1].text

    if not DOCX_SUPPORTED:
        pytest.skip("python-docx cannot load on this host (blocked lxml extension)")
    import docx

    d = docx.Document()
    d.add_heading("Protocol", level=1)
    d.add_paragraph("Daily weights are required.")
    docx_path = tmp_path / "a.docx"
    d.save(str(docx_path))
    assert "## Protocol" in parse_file(docx_path).pages[0].text


def test_parse_rejects_unsupported_and_empty(tmp_path):
    bad = tmp_path / "x.exe"
    bad.write_bytes(b"MZ")
    with pytest.raises(ParsingError):
        parse_file(bad)
    empty = tmp_path / "e.txt"
    empty.write_text("   ")
    with pytest.raises(ParsingError):
        parse_file(empty)


# ------------------------------------------------------------------ chunking
def test_structure_detection_and_section_paths():
    blocks = detect_blocks(ParsedDocument([ParsedPage(1, GUIDE)]))
    headings = [(b.level, b.text) for b in blocks if b.kind == "heading"]
    assert (3, "2.1 HbA1c") in headings and (2, "2. Monitoring") in headings


def test_chunks_respect_sections_size_and_overlap():
    chunks = chunk_document(ParsedDocument([ParsedPage(1, GUIDE)]), "structure", max_words=60, overlap_words=15)
    hba1c = [c for c in chunks if c.section_path.endswith("2.1 HbA1c")]
    assert len(hba1c) == 1 and "Kidney" not in hba1c[0].text  # no section crossing
    kidney = [c for c in chunks if c.section_path.endswith("2.2 Kidney")]
    assert len(kidney) > 1 and all(c.word_count <= 60 + 15 for c in kidney)
    first_tail = kidney[0].text.split(". ")[-1]
    assert first_tail.rstrip(".") in kidney[1].text  # overlap carries the trailing sentence forward
    assert chunks[0].section_path == "SAMPLE GUIDELINE > 1. Scope"


def test_fixed_strategy_windows():
    chunks = chunk_document(ParsedDocument([ParsedPage(1, GUIDE)]), "fixed", max_words=50, overlap_words=10)
    assert len(chunks) > 3 and all(c.section_path == "" for c in chunks)


# ------------------------------------------------------------------ embeddings / keyword search
def test_hashing_embeddings_are_normalised_and_deterministic():
    e = HashingEmbeddingService(384)
    a, b = e.embed_query("metformin renal dose"), e.embed_query("metformin renal dose")
    assert a == b and len(a) == 384 and abs(sum(x * x for x in a) - 1) < 1e-6


def test_tokenizer_preserves_clinical_identifiers():
    toks = tokenize("Follow MED-POL-004 for HbA1c >8% in P1024 (E11.9); patients")
    assert {"med-pol-004", "hba1c", "p1024", "e11.9", "patient"} <= set(toks)
    assert "pol" in toks and "the" not in tokenize("the policy")


def test_bm25_prefers_rare_exact_terms_and_respects_allowed_set():
    idx = BM25Index().build([(1, "insulin glargine titration schedule"), (2, "insulin safety general policy"),
                             (3, "MED-POL-004 high alert medication policy insulin")])
    assert idx.search("MED-POL-004")[0][0] == 3
    assert [d for d, _ in idx.search("insulin", allowed={1, 2})] and 3 not in dict(idx.search("insulin", allowed={1, 2}))


def test_rrf_rewards_agreement_between_retrievers():
    fused = rrf_fuse([[1, 2, 3], [3, 1, 4]], k=60)
    assert max(fused, key=fused.get) == 1 and fused[3] > fused[2] and 4 in fused


# ------------------------------------------------------------------ hybrid retrieval over the ingested corpus
def test_hybrid_retrieval_finds_exact_policy_code(db, users):
    r = HybridRetriever(db, AccessPolicy(db, users["doctor"])).retrieve("What is MED-POL-004?", mode="hybrid")
    assert r.chunks and r.chunks[0].document_title.startswith("Medication Safety")
    assert r.vector_candidates > 0 and r.keyword_candidates > 0


def test_keyword_matters_for_identifiers_vector_only_is_weaker(db, users):
    ret = HybridRetriever(db, AccessPolicy(db, users["doctor"]))
    hybrid = [c.document_title for c in ret.retrieve("NEWS2 of 7 or more", mode="hybrid", top_k=3).chunks]
    assert any("Emergency" in t or "Safety" in t for t in hybrid)


def test_metadata_filter_by_doc_type(db, users):
    r = HybridRetriever(db, AccessPolicy(db, users["admin"])).retrieve(
        "monitoring", RetrievalFilters(doc_types=["policy"]), mode="hybrid")
    assert r.chunks and all(c.doc_type == "policy" for c in r.chunks)


def test_retrieval_never_returns_unauthorized_chunks(db, users):
    ret = HybridRetriever(db, AccessPolicy(db, users["reception"]))
    chunks = ret.retrieve("metformin dose eGFR insulin", mode="hybrid", top_k=20).chunks
    allowed = set(db.scalars(select(Document.id).where(Document.access_scope == "all_staff")))
    assert all(c.document_id in allowed for c in chunks)
    doctor = HybridRetriever(db, AccessPolicy(db, users["doctor"]))
    assert not any("Cardiology Consultation" in c.document_title
                   for c in doctor.retrieve("left atrial appendage occlusion Watchman", mode="hybrid").chunks)
    cardio = HybridRetriever(db, AccessPolicy(db, users["cardio"]))
    assert any("Cardiology Consultation" in c.document_title
               for c in cardio.retrieve("left atrial appendage occlusion Watchman", mode="hybrid").chunks)


class ReverseReranker:
    name = "reverse-test"

    def score(self, query, passages):
        return [float(i) for i in range(len(passages))]  # last candidate scores highest


class BrokenReranker:
    name = "broken"

    def score(self, query, passages):
        raise RerankerError("down")


class BrokenEmbedder:
    name, dim = "broken", 384

    def embed_query(self, text):
        raise EmbeddingError("down")

    def embed_documents(self, texts):
        raise EmbeddingError("down")


def test_reranker_is_replaceable_and_reorders(db, users):
    policy = AccessPolicy(db, users["doctor"])
    fused = HybridRetriever(db, policy).retrieve("insulin", mode="hybrid", top_k=30).chunks
    reranked = HybridRetriever(db, policy, reranker=ReverseReranker()).retrieve("insulin", mode="hybrid_rerank",
                                                                                 top_k=30)
    assert reranked.reranked and reranked.chunks[0].chunk_id == fused[-1].chunk_id


def test_reranker_failure_degrades_to_fused_order(db, users):
    r = HybridRetriever(db, AccessPolicy(db, users["doctor"]), reranker=BrokenReranker()).retrieve("insulin")
    assert r.chunks and "reranker_unavailable" in r.degraded and not r.reranked


def test_embedding_failure_degrades_to_keyword_search(db, users):
    r = HybridRetriever(db, AccessPolicy(db, users["doctor"]), embedder=BrokenEmbedder()).retrieve("insulin glargine")
    assert r.chunks and "vector_search_unavailable" in r.degraded and r.keyword_candidates > 0


def test_near_duplicate_passages_are_deduplicated(db, users):
    r = HybridRetriever(db, AccessPolicy(db, users["admin"])).retrieve("discharge summary follow-up", mode="hybrid",
                                                                       top_k=30)
    hashes = [c.content_hash for c in r.chunks]
    assert len(hashes) == len(set(hashes))


@pytest.mark.skipif(not FASTEMBED_SUPPORTED, reason="fastembed cannot load on this host (blocked native extension)")
@pytest.mark.models
def test_real_models_hybrid_rerank_finds_renal_metformin_rule(db, users):
    from app.core.config import get_settings
    from app.rag.embeddings import FastEmbedService
    from app.rag.reranking import CrossEncoderReranker

    s = get_settings()
    reranker = CrossEncoderReranker(s.reranker_model, str(s.model_cache_dir))
    # the test corpus is embedded with hashing vectors, so use keyword candidates + the real cross-encoder
    r = HybridRetriever(db, AccessPolicy(db, users["doctor"]), reranker=reranker).retrieve(
        "maximum metformin dose when eGFR is between 30 and 44", mode="keyword")
    scores = reranker.score("maximum metformin dose when eGFR is between 30 and 44", [c.rerank_text for c in r.chunks])
    best = r.chunks[scores.index(max(scores))]
    assert "5.1 Metformin" in best.section_path
    assert len(FastEmbedService(s.embedding_model, 384, str(s.model_cache_dir)).embed_query("x")) == 384


def test_upload_parsing_bytes_roundtrip():
    assert io.BytesIO(b"abc").read() == b"abc"
