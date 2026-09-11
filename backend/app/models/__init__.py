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
from app.models.identity import Permission, Role, User, role_permissions
from app.models.ml import MLPrediction, ModelVersion, PatientEmbedding

__all__ = [
    "AIQueryTrace", "AuditLog", "Admission", "Appointment", "CareAssignment", "Department", "Diagnosis",
    "Doctor", "LabReport", "MedicalRecord", "Medication", "Patient", "Prescription", "Document",
    "DocumentChunk", "Permission", "Role", "User", "role_permissions", "MLPrediction", "ModelVersion",
    "PatientEmbedding",
]
