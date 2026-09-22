"""FHIR R4 read-only endpoints (application/fhir+json). Errors are returned as OperationOutcome (see main.py)."""
from collections import Counter

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import false, or_, select

from app.api.deps import DB, policy_for
from app.audit.service import audit
from app.auth.dependencies import require
from app.auth.rbac import Perm
from app.interop.fhir import FHIR_JSON, MRN_SYSTEM, FhirExporter, capability_statement
from app.models import Patient, User

router = APIRouter(prefix="/fhir", tags=["fhir"])


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/fhir"


def _fhir(body: dict) -> JSONResponse:
    return JSONResponse(body, media_type=FHIR_JSON)


@router.get("/metadata")
def metadata(request: Request) -> JSONResponse:
    """CapabilityStatement: what this server supports. Public, like any FHIR server's metadata; no patient data."""
    return _fhir(capability_statement(_base(request)))


@router.get("/Patient")
def search_patients(request: Request, db: DB, user: User = Depends(require(Perm.PATIENTS_READ_DEMOGRAPHICS)),
                    identifier: str | None = Query(None, max_length=128), name: str | None = Query(None, max_length=64),
                    count: int = Query(20, alias="_count", ge=1, le=100)) -> JSONResponse:
    """Search by MRN (identifier=system|value or value) or name, among the patients the caller may see."""
    stmt = select(Patient).where(policy_for(db, user).patient_predicate())
    if identifier:
        system, _, value = identifier.rpartition("|")
        if system and system != MRN_SYSTEM:
            stmt = stmt.where(false())  # an identifier system we do not issue matches nothing
        stmt = stmt.where(Patient.mrn == value.strip().upper())
    if name:
        like = f"%{name.strip()}%"
        stmt = stmt.where(or_(Patient.first_name.ilike(like), Patient.last_name.ilike(like)))
    rows = db.scalars(stmt.order_by(Patient.mrn).limit(count)).all()
    audit("fhir.search", user=user, details={"count": len(rows)})
    exporter = FhirExporter(db, _base(request))
    return _fhir(exporter.searchset([exporter.patient(p) for p in rows], list(exporter.extra.values()), str(request.url)))


@router.get("/Patient/{mrn}")
def read_patient(mrn: str, request: Request, db: DB,
                 user: User = Depends(require(Perm.PATIENTS_READ_DEMOGRAPHICS))) -> JSONResponse:
    p = policy_for(db, user).get_patient_by_mrn(mrn, clinical=False)
    audit("fhir.patient.read", user=user, resource_type="patient", resource_id=p.id, patient_id=p.id)
    return _fhir(FhirExporter(db, _base(request)).patient(p))


@router.get("/Patient/{mrn}/$everything")
def patient_everything(mrn: str, request: Request, db: DB,
                       user: User = Depends(require(Perm.PATIENTS_READ_CLINICAL))) -> JSONResponse:
    """The patient's whole record as one searchset Bundle, under the caller's access policy."""
    p = policy_for(db, user).get_patient_by_mrn(mrn, clinical=True)
    bundle = FhirExporter(db, _base(request)).everything(p, str(request.url))
    counts = Counter(e["resource"]["resourceType"] for e in bundle["entry"])
    audit("fhir.export", user=user, resource_type="patient", resource_id=p.id, patient_id=p.id,
          details={"resources": dict(sorted(counts.items()))})
    return _fhir(bundle)
