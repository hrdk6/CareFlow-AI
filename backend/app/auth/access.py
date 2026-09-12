"""Row-level access policy.

Every query that returns patient-linked data composes these predicates INTO the SQL, so
unauthorized rows never leave the database - and therefore can never reach the RAG context,
the ML services or the LLM. The LLM is never asked to decide access.

Policy:
  ADMIN         all patients
  RECEPTIONIST  all patients, demographics only (no clinical permission)
  DOCTOR        care-team assignment OR patient's primary department is the doctor's department
                OR patient was admitted to that department OR had an appointment with the doctor
  NURSE         explicit active care-team assignment only
"""
from sqlalchemy import and_, false, literal, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement, Select

from app.audit.service import audit
from app.auth.rbac import DOCUMENT_SCOPES, Perm, RoleName
from app.core.errors import NotFoundError, PermissionDeniedError
from app.models import Admission, Appointment, CareAssignment, Document, Patient, User

NOT_ACCESSIBLE = "Patient not found or not accessible"


class AccessPolicy:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.role = RoleName(user.role.name)

    # ------------------------------------------------------------------ capabilities
    def has(self, perm: Perm) -> bool:
        return perm.value in self.user.permission_codes

    @property
    def can_read_clinical(self) -> bool:
        return self.has(Perm.PATIENTS_READ_CLINICAL)

    # ------------------------------------------------------------------ patients
    def patient_predicate(self) -> ColumnElement[bool]:
        if self.role in (RoleName.ADMIN, RoleName.RECEPTIONIST):
            return true()
        assigned = select(CareAssignment.patient_id).where(
            CareAssignment.user_id == self.user.id, CareAssignment.active.is_(True)
        )
        if self.role == RoleName.NURSE:
            return Patient.id.in_(assigned)
        if self.role == RoleName.DOCTOR:
            conditions = [Patient.id.in_(assigned)]
            if self.user.department_id is not None:
                conditions.append(Patient.primary_department_id == self.user.department_id)
                conditions.append(Patient.id.in_(
                    select(Admission.patient_id).where(Admission.department_id == self.user.department_id)))
            if self.user.doctor_id is not None:
                # A cancelled or missed appointment is not a care relationship, and must not leave the
                # doctor with permanent access to that patient's record.
                conditions.append(Patient.id.in_(
                    select(Appointment.patient_id).where(Appointment.doctor_id == self.user.doctor_id,
                                                         Appointment.status.notin_(("cancelled", "no_show")))))
            return or_(*conditions)
        return false()

    def accessible_patient_ids(self) -> Select:
        return select(Patient.id).where(self.patient_predicate())

    def clinical_patient_ids(self) -> Select:
        """Patients whose CLINICAL data this user may read (empty for non-clinical roles)."""
        if not self.can_read_clinical:
            return select(Patient.id).where(false())
        return self.accessible_patient_ids()

    def get_patient(self, patient_id: int, *, clinical: bool) -> Patient:
        if clinical and not self.can_read_clinical:
            audit("patient.access_denied", user=self.user, outcome="denied", patient_id=patient_id,
                  details={"reason": "no clinical permission"})
            raise PermissionDeniedError("Your role cannot view clinical information")
        patient = self.db.scalar(select(Patient).where(Patient.id == patient_id, self.patient_predicate()))
        if patient is None:
            if self.db.get(Patient, patient_id) is not None:
                audit("patient.access_denied", user=self.user, outcome="denied", patient_id=patient_id,
                      details={"reason": "outside care relationship"})
            # Same response for "missing" and "forbidden": identifiers cannot be enumerated.
            raise NotFoundError(NOT_ACCESSIBLE)
        return patient

    def get_patient_by_mrn(self, mrn: str, *, clinical: bool) -> Patient:
        pid = self.db.scalar(select(Patient.id).where(Patient.mrn == mrn.upper()))
        if pid is None:
            raise NotFoundError(NOT_ACCESSIBLE)
        return self.get_patient(pid, clinical=clinical)

    # ------------------------------------------------------------------ documents
    def document_predicate(self) -> ColumnElement[bool]:
        scopes = DOCUMENT_SCOPES[self.role]
        patient_ok = or_(
            Document.patient_id.is_(None),
            and_(literal(self.can_read_clinical), Document.patient_id.in_(self.clinical_patient_ids())),
        )
        return and_(Document.access_scope.in_(scopes), patient_ok)
