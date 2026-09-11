"""Document upload -> ingestion -> indexing -> versioning -> authorization -> deletion."""
from sqlalchemy import select

from app.models import Document, DocumentChunk

POLICY_V1 = b"""# SEPSIS SCREENING POLICY

## 1. Scope

All adult inpatients are screened for sepsis on admission using the qSOFA-X tool.

## 2. Escalation

A qSOFA-X score of 2 or more requires review by a doctor within 30 minutes.
"""
POLICY_V2 = POLICY_V1.replace(b"30 minutes", b"15 minutes")


def _upload(client, auth, content=POLICY_V1, name="sepsis.txt", **form):
    data = {"title": "Sepsis Screening Policy", "doc_type": "policy", "access_scope": "clinical",
            "doc_key": "test-sepsis-policy", **form}
    return client.post("/documents", headers=auth("admin"), data=data, files={"file": (name, content, "text/plain")})


def test_upload_is_parsed_chunked_embedded_and_indexed(client, auth):
    r = _upload(client, auth)
    assert r.status_code == 202, r.text
    doc_id = r.json()["id"]
    detail = client.get(f"/documents/{doc_id}", headers=auth("admin")).json()
    assert detail["status"] == "indexed" and detail["chunk_count"] >= 2
    assert {c["section_path"].split(" > ")[-1] for c in detail["chunks"]} >= {"1. Scope", "2. Escalation"}
    answer = client.post("/ai/query", json={"query": "What does the qSOFA-X escalation policy require?"},
                         headers=auth("doctor")).json()
    assert any(c["document_title"] == "Sepsis Screening Policy" for c in answer["citations"])


def test_duplicate_upload_is_rejected(client, auth):
    assert _upload(client, auth).status_code == 409


def test_new_version_replaces_old_in_retrieval(client, auth, db):
    r = _upload(client, auth, content=POLICY_V2)
    assert r.status_code == 202 and r.json()["version"] == 2
    versions = db.scalars(select(Document).where(Document.doc_key == "test-sepsis-policy")
                          .order_by(Document.version)).all()
    assert [v.is_current for v in versions] == [False, True]
    answer = client.post("/ai/query", json={"query": "qSOFA-X escalation review within how many minutes?"},
                         headers=auth("doctor")).json()
    sepsis = [c for c in answer["citations"] if c["document_title"] == "Sepsis Screening Policy"]
    assert sepsis and all(c["version"] == 2 for c in sepsis)
    cited = " ".join(c["excerpt"] for c in sepsis)
    assert "doctor within 15 minutes" in cited and "doctor within 30 minutes" not in cited


def test_invalid_uploads(client, auth):
    assert _upload(client, auth, name="malware.exe", doc_key="bad-1").status_code == 422
    assert _upload(client, auth, content=b"", doc_key="bad-2").status_code == 422
    assert _upload(client, auth, content=b"not a pdf", name="fake.pdf", doc_key="bad-3").status_code == 422
    r = client.post("/documents", headers=auth("admin"), data={"title": "X doc", "doc_type": "nonsense",
                                                                "access_scope": "clinical"},
                    files={"file": ("x.txt", b"hello world", "text/plain")})
    assert r.status_code == 422


def test_parsing_failure_marks_document_failed(client, auth):
    r = _upload(client, auth, content=b"%PDF-1.4 this is not really a pdf", name="broken.pdf", doc_key="broken-pdf")
    assert r.status_code == 202
    detail = client.get(f"/documents/{r.json()['id']}", headers=auth("admin")).json()
    assert detail["status"] == "failed" and detail["error_message"]


def test_only_admins_manage_documents(client, auth):
    r = client.post("/documents", headers=auth("doctor"), data={"title": "Doc", "doc_type": "policy",
                                                                 "access_scope": "clinical"},
                    files={"file": ("d.txt", b"content here", "text/plain")})
    assert r.status_code == 403


def test_role_scoped_document_and_source_access(client, auth, db):
    clinical = db.scalar(select(Document).where(Document.access_scope == "clinical", Document.status == "indexed",
                                                Document.patient_id.is_(None)).limit(1))
    chunk = db.scalar(select(DocumentChunk.id).where(DocumentChunk.document_id == clinical.id).limit(1))
    assert client.get(f"/documents/{clinical.id}", headers=auth("reception")).status_code == 404
    assert client.get(f"/ai/sources/{chunk}", headers=auth("reception")).status_code == 404
    src = client.get(f"/ai/sources/{chunk}", headers=auth("nurse"))
    assert src.status_code == 200 and src.json()["document_title"] == clinical.title
    download = client.get(f"/documents/{clinical.id}/file", headers=auth("doctor"))
    assert download.status_code == 200 and len(download.content) == clinical.file_size


def test_delete_promotes_previous_version(client, auth, db):
    current = db.scalar(select(Document).where(Document.doc_key == "test-sepsis-policy", Document.is_current))
    assert client.delete(f"/documents/{current.id}", headers=auth("admin")).status_code == 204
    assert client.get(f"/documents/{current.id}", headers=auth("admin")).status_code == 404
    db.expire_all()
    remaining = db.scalar(select(Document).where(Document.doc_key == "test-sepsis-policy"))
    assert remaining.version == 1 and remaining.is_current
