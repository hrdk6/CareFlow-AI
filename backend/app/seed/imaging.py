"""Attach the demo radiographs to the synthetic hospital.

The films are real DICOM objects built by `ml/data/build_demo_studies.py` from HELD-OUT test films of the
public NIH ChestX-ray14 release; their headers carry invented identities so that ingestion has something to
strip. Each film goes to a patient of the same sex and the closest age, so the viewer never shows a 40-year
mismatch between the header and the record.

The reference labels in the manifest are NOT used here. The seed knows nothing about what is on a film -
the indication comes from why the patient is in hospital, and the score comes from the model, exactly as it
would for a film that arrived this morning.
"""
import json
import logging
import random
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_DIR
from app.models import Admission, ImagingStudy, Patient
from app.services import imaging as service

logger = logging.getLogger("careflow.seed")

DEMO_DIR = REPO_DIR / "ml" / "data" / "demo_studies"
MIN_AGE = 16  # the model is fitted on adults; a paediatric film would be outside its stated population

OUTPATIENT_INDICATIONS = [
    "Cough for three weeks, non-smoker", "Pre-operative assessment", "Breathlessness on exertion",
    "Chest pain, atypical", "Occupational health screening", "Weight loss and night sweats",
]
INPATIENT_INDICATIONS = {
    "pneumonia": "Fever and productive cough; query consolidation",
    "heart failure": "Worsening breathlessness and leg swelling",
    "copd": "Breathless, wheeze, query infection",
    "asthma": "Acute wheeze, poor response to nebulisers",
    "hyperglycemia": "Unwell with hyperglycaemia; query infection",
    "urinary tract": "Sepsis screen",
    "stroke": "Admission film, query aspiration",
    "fracture": "Pre-operative film",
    "atrial fibrillation": "Palpitations and breathlessness",
}


def _indication(patient: Patient, admission: Admission | None, rng: random.Random) -> str:
    if admission is not None:
        reason = (admission.reason or "").lower()
        for key, text in INPATIENT_INDICATIONS.items():
            if key in reason:
                return text
        return f"Admitted with {admission.reason}; baseline film"
    return rng.choice(OUTPATIENT_INDICATIONS)


def _age(patient: Patient, on) -> int:
    dob = patient.date_of_birth
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def seed_imaging(db: Session, *, seed: int = 7) -> int:
    """Ingest the demo studies once. Returns how many were added (0 if they are already there)."""
    manifest_path = DEMO_DIR / "manifest.json"
    if not manifest_path.exists():
        logger.info("no demo studies at %s - skipping radiology seed", DEMO_DIR)
        return 0
    if db.scalar(select(func.count()).select_from(ImagingStudy)):
        return 0

    from datetime import UTC, datetime

    today = datetime.now(UTC).date()
    manifest = json.loads(manifest_path.read_text())
    rng = random.Random(seed)
    patients = db.scalars(select(Patient).order_by(Patient.id)).all()
    admissions = {a.patient_id: a for a in db.scalars(select(Admission).where(Admission.status == "admitted"))}
    pool = [p for p in patients if _age(p, today) >= MIN_AGE]
    used: set[int] = set()
    added = 0

    for entry in manifest["studies"]:
        candidates = [p for p in pool if p.sex == entry["sex"] and p.id not in used]
        if not candidates:
            candidates = [p for p in pool if p.id not in used]
        if not candidates:
            break
        patient = min(candidates, key=lambda p: abs(_age(p, today) - entry["age"]))
        used.add(patient.id)
        admission = admissions.get(patient.id)
        try:
            service.ingest(db, None, patient, (DEMO_DIR / entry["file"]).read_bytes(),
                           indication=_indication(patient, admission, rng),
                           description=f"Chest {entry['view']}", source="seed",
                           admission_id=admission.id if admission else None)
            added += 1
        except Exception:  # a corrupt demo file must not stop the rest of the seed
            logger.exception("could not seed study %s", entry["file"])
    db.flush()
    _remove_orphan_files(db)
    return added


def _remove_orphan_files(db: Session) -> None:
    """Files left behind by an earlier --reset. Only ever removes files under the imaging store."""
    root = service.storage_root()
    if not root.exists():
        return
    known = {Path(p).name for p in db.scalars(select(ImagingStudy.storage_path))}
    for path in root.glob("*.dcm"):
        if path.name not in known:
            path.unlink(missing_ok=True)
