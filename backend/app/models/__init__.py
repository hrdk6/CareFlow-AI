"""Import all models so SQLAlchemy metadata (and Alembic autogenerate) sees every table."""
from app.models.audit import AIQueryTrace, AuditLog
from app.models.clinical import (
    Admission,
    Appointment,
    CareAssignment,
    Department,
    Diagnosis,
    Doctor,
    LabReport,
    MedicalRecord,
    Medication,
    Patient,
    Prescription,
)
from app.models.documents import Document, DocumentChunk
from app.models.drafts import AIDraft
from app.models.identity import Permission, Role, User, role_permissions
from app.models.imaging import ImagingReport, ImagingStudy
from app.models.ml import MLPrediction, ModelVersion, PatientEmbedding
from app.models.vitals import VitalSigns

__all__ = [
    "AIDraft", "AIQueryTrace", "AuditLog", "Admission", "Appointment", "CareAssignment", "Department", "Diagnosis",
    "Doctor", "ImagingReport", "ImagingStudy", "LabReport", "MedicalRecord", "Medication", "Patient",
    "Prescription", "Document", "DocumentChunk", "Permission", "Role", "User", "role_permissions",
    "MLPrediction", "ModelVersion", "PatientEmbedding", "VitalSigns",
]
