"""Authorized patient-similarity response shared by the REST API and the AI tools."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.ml.similarity import REPRESENTATION_VERSION, cohort_patterns, find_similar
from app.models import Patient
from app.schemas.ml import SimilarityOut, SimilarPatientOut

DISCLAIMER = ("Similarity is computed from structured features (age, diagnosis groups, medication groups, "
              "utilisation, recent HbA1c/eGFR). Similar patients do not share a diagnosis, treatment response or "
              "outcome; historical patterns are descriptive only.")


def similar_patients(db: Session, policy: AccessPolicy, patient: Patient, k: int = 5) -> SimilarityOut:
    allowed = policy.clinical_patient_ids()  # authorization happens inside the vector query
    query_profile, neighbours = find_similar(db, patient.id, allowed, k=k)
    patients = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_([n["patient_id"] for n in neighbours])))}
    results = []
    for n in neighbours:
        p, prof = patients[n["patient_id"]], n["profile"]
        results.append(SimilarPatientOut(
            patient_id=p.id, mrn=p.mrn, full_name=p.full_name, age=prof["age"], sex=prof["sex"],
            similarity=n["similarity"], shared_diagnosis_categories=n["shared_diagnosis_categories"],
            shared_medication_groups=n["shared_medication_groups"], diagnoses=prof.get("diagnoses", [])[:6],
            admissions_2y=prof.get("admissions_2y", 0), mean_los_days=prof.get("mean_los_days"),
            last_hba1c=prof.get("last_hba1c"), last_egfr=prof.get("last_egfr")))
    scope = {"ADMIN": "all patients", "DOCTOR": "patients in your department or care", "NURSE": "your assigned patients"}
    return SimilarityOut(
        patient_id=patient.id, representation_version=REPRESENTATION_VERSION, metric="cosine similarity (pgvector)",
        query_profile=query_profile, results=results, cohort_patterns=cohort_patterns(db, [r.patient_id for r in results]),
        candidate_scope=f"Searched only {scope.get(policy.role.value, 'accessible patients')}.", disclaimer=DISCLAIMER)
