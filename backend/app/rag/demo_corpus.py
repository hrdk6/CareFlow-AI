"""Load the synthetic demo knowledge base (rag/corpus) through the normal ingestion pipeline.

Static documents come from rag/corpus/dist (built by scripts/build_demo_corpus.py). Patient-specific
documents are rendered from templates with facts from the demo database, so they stay consistent
with the structured records.
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.core.config import REPO_DIR
from app.models import Admission, Department, Doctor, Document, LabReport, Patient, User
from app.rag.ingestion import create_document, process_document, slugify

CORPUS = REPO_DIR / "rag" / "corpus"


def _manifest() -> dict:
    return json.loads((CORPUS / "manifest.json").read_text())


def _dept_id(db: Session, code: str | None) -> int | None:
    return db.scalar(select(Department.id).where(Department.code == code)) if code else None


def _resolve_patient(db: Session, spec: str) -> Patient | None:
    if spec.startswith("auto:"):
        rao = db.scalar(select(User).where(User.email == "dr.rao@careflow.demo"))
        card = _dept_id(db, "CARD")
        if rao is None or card is None:
            return None
        visible = AccessPolicy(db, rao).accessible_patient_ids()
        return db.scalar(select(Patient).where(Patient.primary_department_id == card, Patient.id.not_in(visible))
                         .order_by(Patient.id).limit(1))
    return db.scalar(select(Patient).where(Patient.mrn == spec))


def _template_fields(db: Session, patient: Patient) -> dict:
    fields = {"name": patient.full_name, "mrn": patient.mrn, "dob": patient.date_of_birth.isoformat()}
    adm = db.scalar(select(Admission).where(Admission.patient_id == patient.id, Admission.status == "discharged")
                    .order_by(Admission.discharged_at.desc()).limit(1))
    if adm is not None:
        attending = db.scalar(select(Doctor.full_name).where(Doctor.id == adm.attending_doctor_id))
        labs = db.execute(select(LabReport.test_code, LabReport.value).where(LabReport.admission_id == adm.id)).all()
        glucose = [v for c, v in labs if c == "GLU"]
        a1c = [v for c, v in labs if c == "HBA1C"]
        egfr = db.scalar(select(LabReport.value).where(LabReport.patient_id == patient.id, LabReport.test_code == "EGFR")
                         .order_by(LabReport.collected_at.desc()).limit(1))
        fields.update(admitted=adm.admitted_at.date().isoformat(), discharged=adm.discharged_at.date().isoformat(),
                      los=adm.length_of_stay_days, reason=adm.reason, attending=attending or "the attending team",
                      max_glucose=f"{max(glucose):g}" if glucose else "not recorded",
                      a1c=f"{max(a1c):g}" if a1c else "not measured", egfr=f"{egfr:g}" if egfr else "unknown")
    return fields


class _SafeDict(dict):
    def __missing__(self, key):
        return "not recorded"


def ingest_demo_corpus(db: Session, uploaded_by: int | None = None) -> dict:
    """Ingest every manifest document that is not already indexed. Idempotent."""
    manifest = _manifest()
    results = {"indexed": [], "skipped": [], "failed": [], "missing_files": []}
    admin = uploaded_by or db.scalar(select(User.id).where(User.email == "admin@careflow.demo"))

    def exists(key: str) -> bool:
        return db.scalar(select(Document.id).where(Document.doc_key == slugify(key), Document.is_current.is_(True),
                                                   Document.status == "indexed")) is not None

    jobs: list[int] = []
    for entry in manifest["documents"]:
        path = CORPUS / "dist" / f"{Path(entry['source']).stem}.{entry['format']}"
        if exists(entry["doc_key"]):
            results["skipped"].append(entry["title"])
            continue
        if not path.exists():
            results["missing_files"].append(str(path.relative_to(REPO_DIR)))
            continue
        doc = create_document(db, data=path.read_bytes(), filename=path.name, title=entry["title"],
                              doc_type=entry["doc_type"], access_scope=entry["access_scope"],
                              department_id=_dept_id(db, entry["department"]), patient_id=None,
                              uploaded_by=admin, doc_key=entry["doc_key"])
        jobs.append(doc.id)
    for entry in manifest["patient_documents"]:
        patient = _resolve_patient(db, entry["patient"])
        if patient is None:
            results["failed"].append(f"{entry['title']} (patient not found)")
            continue
        key = entry["doc_key"].format(mrn=patient.mrn.lower())
        title = entry["title"].format(mrn=patient.mrn)
        if exists(key):
            results["skipped"].append(title)
            continue
        text = (CORPUS / "templates" / entry["template"]).read_text(encoding="utf-8")
        body = text.format_map(_SafeDict(_template_fields(db, patient)))
        doc = create_document(db, data=body.encode("utf-8"), filename=f"{key}.txt", title=title,
                              doc_type=entry["doc_type"], access_scope=entry["access_scope"],
                              department_id=_dept_id(db, entry["department"]), patient_id=patient.id,
                              uploaded_by=admin, doc_key=key)
        jobs.append(doc.id)
    db.commit()
    for doc_id in jobs:
        status = process_document(doc_id)
        title = db.scalar(select(Document.title).where(Document.id == doc_id))
        results["indexed" if status == "indexed" else "failed"].append(title)
    return results
