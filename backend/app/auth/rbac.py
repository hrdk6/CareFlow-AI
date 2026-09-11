"""Role and permission definitions - the single source of truth for RBAC.

Permissions are coarse capabilities ("may read clinical data"). WHICH patients a user may see is a
separate, row-level decision made by app.auth.access.AccessPolicy.
"""
from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    NURSE = "NURSE"
    RECEPTIONIST = "RECEPTIONIST"


class Perm(StrEnum):
    PATIENTS_READ_DEMOGRAPHICS = "patients:read_demographics"
    PATIENTS_READ_CLINICAL = "patients:read_clinical"
    PATIENTS_WRITE = "patients:write"
    APPOINTMENTS_READ = "appointments:read"
    APPOINTMENTS_WRITE = "appointments:write"
    CLINICAL_WRITE = "clinical:write"  # medical records, diagnoses, lab results
    PRESCRIPTIONS_WRITE = "prescriptions:write"
    ADMISSIONS_WRITE = "admissions:write"
    DOCTORS_READ = "doctors:read"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_MANAGE = "documents:manage"
    AI_QUERY = "ai:query"
    ML_READ = "ml:read"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    SYSTEM_OBSERVE = "system:observe"


PERMISSION_DESCRIPTIONS: dict[Perm, str] = {
    Perm.PATIENTS_READ_DEMOGRAPHICS: "View patient registration details",
    Perm.PATIENTS_READ_CLINICAL: "View clinical data for accessible patients",
    Perm.PATIENTS_WRITE: "Register and update patients",
    Perm.APPOINTMENTS_READ: "View appointments",
    Perm.APPOINTMENTS_WRITE: "Create, reschedule and cancel appointments",
    Perm.CLINICAL_WRITE: "Write medical records and lab results",
    Perm.PRESCRIPTIONS_WRITE: "Prescribe and discontinue medications",
    Perm.ADMISSIONS_WRITE: "Admit and discharge patients",
    Perm.DOCTORS_READ: "View the doctor directory",
    Perm.DOCUMENTS_READ: "Read knowledge-base documents allowed for the role",
    Perm.DOCUMENTS_MANAGE: "Upload, re-index and delete documents",
    Perm.AI_QUERY: "Use the AI assistant",
    Perm.ML_READ: "View ML predictions and patient similarity",
    Perm.USERS_MANAGE: "Manage users and roles",
    Perm.AUDIT_READ: "Read the audit log",
    Perm.SYSTEM_OBSERVE: "View system metrics and AI traces",
}

ROLE_PERMISSIONS: dict[RoleName, set[Perm]] = {
    RoleName.ADMIN: set(Perm),
    RoleName.DOCTOR: {
        Perm.PATIENTS_READ_DEMOGRAPHICS, Perm.PATIENTS_READ_CLINICAL, Perm.APPOINTMENTS_READ,
        Perm.APPOINTMENTS_WRITE, Perm.CLINICAL_WRITE, Perm.PRESCRIPTIONS_WRITE, Perm.ADMISSIONS_WRITE,
        Perm.DOCTORS_READ, Perm.DOCUMENTS_READ, Perm.AI_QUERY, Perm.ML_READ,
    },
    RoleName.NURSE: {
        Perm.PATIENTS_READ_DEMOGRAPHICS, Perm.PATIENTS_READ_CLINICAL, Perm.APPOINTMENTS_READ,
        Perm.CLINICAL_WRITE, Perm.DOCTORS_READ, Perm.DOCUMENTS_READ, Perm.AI_QUERY,
    },
    RoleName.RECEPTIONIST: {
        Perm.PATIENTS_READ_DEMOGRAPHICS, Perm.PATIENTS_WRITE, Perm.APPOINTMENTS_READ,
        Perm.APPOINTMENTS_WRITE, Perm.DOCTORS_READ, Perm.DOCUMENTS_READ, Perm.AI_QUERY,
    },
}

ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.ADMIN: "Full management permissions",
    RoleName.DOCTOR: "Clinical access to patients under their care or in their department",
    RoleName.NURSE: "Clinical access to explicitly assigned patients",
    RoleName.RECEPTIONIST: "Registration, scheduling and non-clinical information",
}

# Knowledge-base access scopes each role may read.
DOCUMENT_SCOPES: dict[RoleName, set[str]] = {
    RoleName.ADMIN: {"all_staff", "clinical", "admin"},
    RoleName.DOCTOR: {"all_staff", "clinical"},
    RoleName.NURSE: {"all_staff", "clinical"},
    RoleName.RECEPTIONIST: {"all_staff"},
}
