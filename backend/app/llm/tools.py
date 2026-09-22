"""Controlled tools available to the AI layer.

Each tool is a thin adapter over the SAME services the REST API uses. The tool receives the
authenticated user's AccessPolicy - never a raw DB handle chosen by the model - so every call is
authorized server-side regardless of what the LLM asks for. Tools also register evidence (with
citation ids) and return compact text for the model.
"""
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.access import NOT_ACCESSIBLE, AccessPolicy
from app.auth.rbac import Perm
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError, PermissionDeniedError, ServiceUnavailableError
from app.llm.base import ToolSpec
from app.llm.evidence import EvidenceStore
from app.ml.service import predict_length_of_stay, predict_readmission
from app.models import (
    Admission,
    Appointment,
    CareAssignment,
    Diagnosis,
    Doctor,
    LabReport,
    MedicalRecord,
    Medication,
    Patient,
    Prescription,
    User,
)
from app.observability.metrics import StageTimer
from app.rag.retrieval import HybridRetriever, RetrievalFilters
from app.schemas.ai import ToolCallOut
from app.services.similarity import similar_patients
from app.services.timeline import build_timeline

logger = logging.getLogger("careflow.tools")


@dataclass
class ToolContext:
    db: Session
    user: User
    policy: AccessPolicy
    patient_id: int | None
    evidence: EvidenceStore
    timer: StageTimer


@dataclass
class ToolResult:
    status: str  # ok | denied | not_found | error
    text: str
    summary: str


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatientArgs(_Args):
    patient: str | None = Field(default=None, description="Patient MRN such as P1024. Omit to use the patient in context.")


class RecordsArgs(PatientArgs):
    limit: int = Field(default=6, ge=1, le=20, description="Maximum number of records, newest first")


class TimelineArgs(PatientArgs):
    months: int = Field(default=24, ge=1, le=120, description="How many months of history to include")


class PrescriptionArgs(PatientArgs):
    status: str = Field(default="active", pattern="^(active|all)$", description="'active' or 'all' (includes history)")


class LabArgs(PatientArgs):
    test_code: str | None = Field(default=None, description="Optional test code, e.g. HBA1C, EGFR, GLU, K, LDL")


class AppointmentArgs(_Args):
    patient: str | None = Field(default=None, description="Optional patient MRN")
    doctor: str | None = Field(default=None, description="Optional doctor surname, e.g. 'Rao'")
    period: str = Field(default="upcoming", pattern="^(today|upcoming|past|all)$")


class SearchArgs(_Args):
    query: str = Field(min_length=2, max_length=500, description="What to look for in hospital documents")
    doc_type: str | None = Field(default=None, pattern="^(guideline|policy|protocol|procedure|report|other)$")


class SourceArgs(_Args):
    source_id: str = Field(description="A source id previously returned by search_documents, e.g. S2")


class SimilarArgs(PatientArgs):
    k: int = Field(default=5, ge=1, le=10)


def _clean_schema(schema: dict) -> dict:
    """Pydantic JSON schema -> minimal schema accepted by every provider."""
    props = {}
    for name, prop in schema.get("properties", {}).items():
        prop = {k: v for k, v in prop.items() if k not in ("title", "default")}
        if "anyOf" in prop:
            non_null = [p for p in prop.pop("anyOf") if p.get("type") != "null"]
            prop.update(non_null[0] if non_null else {"type": "string"})
        props[name] = prop
    return {"type": "object", "properties": props, "required": schema.get("required", []),
            "additionalProperties": False}


def _patient(ctx: ToolContext, ref: str | None, *, clinical: bool) -> Patient:
    if ref is None or ref.strip().lower() in ("", "current", "this patient", "the patient"):
        if ctx.patient_id is None:
            raise NotFoundError("No patient specified. Mention an MRN (for example P1024) or open a patient profile.")
        patient = ctx.policy.get_patient(ctx.patient_id, clinical=clinical)
    else:
        ref = ref.strip().upper()
        if re.fullmatch(r"P\d{4}", ref):
            patient = ctx.policy.get_patient_by_mrn(ref, clinical=clinical)
        elif ref.isdigit():
            patient = ctx.policy.get_patient(int(ref), clinical=clinical)
        else:
            raise NotFoundError(NOT_ACCESSIBLE)
    ctx.evidence.patient_ids.add(patient.id)
    return patient


def _age(p: Patient) -> int:
    today = datetime.now(UTC).date()
    return today.year - p.date_of_birth.year - ((today.month, today.day) < (p.date_of_birth.month, p.date_of_birth.day))


# ====================================================================== tool implementations
def get_patient(ctx: ToolContext, a: PatientArgs) -> ToolResult:
    clinical = ctx.policy.can_read_clinical
    p = _patient(ctx, a.patient, clinical=False)
    ev, db = ctx.evidence, ctx.db
    rid = ev.ref_record("patient", p.id, f"{p.full_name} ({p.mrn})")
    lines = [f"[{rid}] {p.full_name}, MRN {p.mrn}, {_age(p)}-year-old {'female' if p.sex == 'F' else 'male' if p.sex == 'M' else 'patient'}, "
             f"born {p.date_of_birth}, status {p.status}, primary department "
             f"{p.primary_department.name if p.primary_department else 'none'}. Synthetic patient."]
    data: dict = {"id": p.id, "mrn": p.mrn, "name": p.full_name, "age": _age(p), "sex": p.sex, "status": p.status,
                  "ref": rid, "clinical": clinical}
    if not clinical:
        lines.append(f"Phone {p.phone or 'n/a'}; emergency contact {p.emergency_contact_name or 'n/a'}. "
                     "Clinical information is not available to this role.")
    else:
        allergies = ", ".join(f"{x['substance']} ({x['reaction']}, {x['severity']})" for x in p.allergies) or "none recorded"
        lines.append(f"Allergies: {allergies}.")
        dxs = db.scalars(select(Diagnosis).where(Diagnosis.patient_id == p.id, Diagnosis.is_chronic,
                                                 Diagnosis.status == "active").order_by(Diagnosis.diagnosed_on)).all()
        data["problems"] = []
        if dxs:
            lines.append("Active chronic problems:")
            for d in dxs:
                r = ev.ref_record("diagnosis", d.id, f"{d.description} ({d.icd10_code})", str(d.diagnosed_on))
                lines.append(f"- [{r}] {d.description} ({d.icd10_code}), since {d.diagnosed_on}")
                data["problems"].append({"ref": r, "text": d.description, "since": str(d.diagnosed_on)})
        meds = db.execute(select(Prescription, Medication).join(Medication).where(
            Prescription.patient_id == p.id, Prescription.status == "active", Prescription.admission_id.is_(None))
            .order_by(Prescription.start_date)).all()
        data["medications"] = []
        if meds:
            lines.append("Current medications:")
            for rx, m in meds:
                r = ev.ref_record("prescription", rx.id, f"{m.name} {rx.dosage} {rx.frequency}", str(rx.start_date))
                lines.append(f"- [{r}] {m.name} {rx.dosage} {rx.frequency} (since {rx.start_date})"
                             + (" [high-alert]" if m.is_high_alert else ""))
                data["medications"].append({"ref": r, "text": f"{m.name} {rx.dosage} {rx.frequency}",
                                            "since": str(rx.start_date)})
        adm = db.scalar(select(Admission).where(Admission.patient_id == p.id).order_by(Admission.admitted_at.desc()).limit(1))
        n_adm = db.scalar(select(func.count()).select_from(Admission).where(Admission.patient_id == p.id))
        if adm:
            r = ev.ref_record("admission", adm.id, f"Admission: {adm.reason}", adm.admitted_at.date().isoformat())
            state = "currently admitted" if adm.status == "admitted" else \
                f"discharged {adm.discharged_at.date()} to {adm.discharge_disposition} after {adm.length_of_stay_days} days"
            lines.append(f"Most recent admission [{r}]: {adm.admitted_at.date()} {adm.reason} ({adm.department.name}), {state}. "
                         f"Total admissions on record: {n_adm}.")
            data["last_admission"] = {"ref": r, "text": f"{adm.admitted_at.date()} {adm.reason}, {state}"}
    ev.data["patient"] = data
    ev.add_block("database", f"Patient {p.mrn}", "\n".join(lines))
    return ToolResult("ok", "\n".join(lines), f"Loaded {p.mrn}")


def get_patient_records(ctx: ToolContext, a: RecordsArgs) -> ToolResult:
    p = _patient(ctx, a.patient, clinical=True)
    rows = ctx.db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == p.id)
                          .order_by(MedicalRecord.visit_date.desc(), MedicalRecord.id.desc()).limit(a.limit)).all()
    lines, data = [], []
    for r in rows:
        rid = ctx.evidence.ref_record("medical_record", r.id, f"{r.record_type.replace('_', ' ')}: {r.chief_complaint}",
                                      str(r.visit_date))
        text = (f"[{rid}] {r.visit_date} {r.record_type.replace('_', ' ')} ({r.doctor.full_name if r.doctor else 'n/a'}): "
                f"{r.chief_complaint}. {r.diagnosis_summary or ''} Plan: {r.treatment_plan or 'n/a'} "
                f"Notes: {(r.notes or '')[:260]}")
        lines.append(text)
        data.append({"ref": rid, "date": str(r.visit_date), "type": r.record_type, "complaint": r.chief_complaint,
                     "summary": r.diagnosis_summary, "plan": r.treatment_plan})
    ctx.evidence.data["records"] = data
    body = "\n".join(lines) or "No medical records on file."
    ctx.evidence.add_block("database", f"Medical records for {p.mrn} (newest first)", body)
    return ToolResult("ok", body, f"{len(rows)} records")


def get_patient_timeline(ctx: ToolContext, a: TimelineArgs) -> ToolResult:
    p = _patient(ctx, a.patient, clinical=True)
    since = datetime.now(UTC).date() - timedelta(days=30 * a.months)
    events = build_timeline(ctx.db, p.id, since=since)
    lines, data = [], []
    for e in events[:60]:
        rid = ctx.evidence.ref_record(e.source_type, e.source_id, e.title, e.at.date().isoformat())
        lines.append(f"[{rid}] {e.at.date()} {e.category}: {e.title}" + (f" - {e.detail}" if e.detail else ""))
        data.append({"ref": rid, "date": e.at.date().isoformat(), "category": e.category, "title": e.title,
                     "detail": e.detail})
    ctx.evidence.data["timeline"] = data
    body = "\n".join(lines) or "No events in this period."
    ctx.evidence.add_block("database", f"Timeline for {p.mrn}, last {a.months} months (newest first)", body)
    return ToolResult("ok", body, f"{len(events)} events")


def get_prescriptions(ctx: ToolContext, a: PrescriptionArgs) -> ToolResult:
    p = _patient(ctx, a.patient, clinical=True)
    stmt = select(Prescription, Medication).join(Medication).where(Prescription.patient_id == p.id,
                                                                   Prescription.admission_id.is_(None))
    if a.status == "active":
        stmt = stmt.where(Prescription.status == "active")
    rows = ctx.db.execute(stmt.order_by(Prescription.start_date.desc())).all()
    lines, data = [], []
    for rx, m in rows:
        rid = ctx.evidence.ref_record("prescription", rx.id, f"{m.name} {rx.dosage} {rx.frequency}", str(rx.start_date))
        end = f" until {rx.end_date}" if rx.end_date else ""
        lines.append(f"[{rid}] {m.name} ({m.drug_class.replace('_', ' ')}) {rx.dosage} {rx.frequency}, {rx.status}, "
                     f"from {rx.start_date}{end}" + (f"; reason: {rx.change_reason}" if rx.change_reason else "")
                     + ("; high-alert medication" if m.is_high_alert else ""))
        data.append({"ref": rid, "medication": m.name, "dosage": rx.dosage, "frequency": rx.frequency,
                     "status": rx.status, "start": str(rx.start_date), "reason": rx.change_reason})
    ctx.evidence.data["prescriptions"] = data
    body = "\n".join(lines) or "No prescriptions found."
    ctx.evidence.add_block("database", f"{'Active' if a.status == 'active' else 'All'} outpatient prescriptions for {p.mrn}",
                           body)
    return ToolResult("ok", body, f"{len(rows)} prescriptions")


def get_lab_reports(ctx: ToolContext, a: LabArgs) -> ToolResult:
    p = _patient(ctx, a.patient, clinical=True)
    stmt = select(LabReport).where(LabReport.patient_id == p.id)
    if a.test_code:
        stmt = stmt.where(LabReport.test_code == a.test_code.upper())
    rows = ctx.db.scalars(stmt.order_by(LabReport.collected_at.desc()).limit(400)).all()
    by_test: dict[str, list[LabReport]] = {}
    for lab in rows:
        by_test.setdefault(lab.test_code, []).append(lab)
    lines, data = [], {}
    for code, labs in by_test.items():
        # latest value, plus a short trend for tests that are followed over time
        recent = labs[: (6 if code in ("HBA1C", "EGFR") or a.test_code else 1)]
        parts = []
        for lab in recent:
            rid = ctx.evidence.ref_record("lab_report", lab.id, f"{lab.test_name} {lab.value:g} {lab.unit}",
                                          lab.collected_at.date().isoformat())
            flag = f" ({lab.flag})" if lab.flag != "normal" else ""
            parts.append(f"[{rid}] {lab.collected_at.date()}: {lab.value:g} {lab.unit}{flag}")
            data.setdefault(code, []).append({"ref": rid, "date": lab.collected_at.date().isoformat(),
                                              "value": lab.value, "unit": lab.unit, "flag": lab.flag,
                                              "name": lab.test_name})
        ref = labs[0]
        rng = f"reference {ref.reference_low if ref.reference_low is not None else ''}-" \
              f"{ref.reference_high if ref.reference_high is not None else ''}"
        lines.append(f"{ref.test_name} ({code}, {rng}): " + "; ".join(parts))
    ctx.evidence.data["labs"] = data
    body = "\n".join(lines) or "No laboratory results found."
    ctx.evidence.add_block("database", f"Laboratory results for {p.mrn} (newest first)", body)
    return ToolResult("ok", body, f"{len(by_test)} tests")


def get_appointments(ctx: ToolContext, a: AppointmentArgs) -> ToolResult:
    now = datetime.now(UTC)
    stmt = (select(Appointment).join(Patient, Patient.id == Appointment.patient_id)
            .join(Doctor, Doctor.id == Appointment.doctor_id).where(ctx.policy.patient_predicate()))
    if a.patient:
        stmt = stmt.where(Appointment.patient_id == _patient(ctx, a.patient, clinical=False).id)
    elif ctx.patient_id is not None and not a.doctor:
        stmt = stmt.where(Appointment.patient_id == _patient(ctx, None, clinical=False).id)
    if a.doctor:
        stmt = stmt.where(Doctor.full_name.ilike(f"%{a.doctor.strip()[:40]}%"))
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if a.period == "today":
        stmt = stmt.where(Appointment.scheduled_start >= start_today,
                          Appointment.scheduled_start < start_today + timedelta(days=1))
    elif a.period == "upcoming":
        stmt = stmt.where(Appointment.scheduled_start >= start_today, Appointment.status.in_(["scheduled", "checked_in"]))
    elif a.period == "past":
        stmt = stmt.where(Appointment.scheduled_start < now)
    order = Appointment.scheduled_start.desc() if a.period == "past" else Appointment.scheduled_start
    rows = ctx.db.scalars(stmt.order_by(order).limit(20)).all()
    lines, data = [], []
    for ap in rows:
        ctx.evidence.patient_ids.add(ap.patient_id)  # named in the evidence: audited and pseudonymised like any other
        rid = ctx.evidence.ref_record("appointment", ap.id, f"{ap.scheduled_start:%Y-%m-%d %H:%M} {ap.reason}",
                                      ap.scheduled_start.date().isoformat())
        lines.append(f"[{rid}] {ap.scheduled_start:%Y-%m-%d %H:%M} UTC - {ap.patient.full_name} ({ap.patient.mrn}) with "
                     f"{ap.doctor.full_name}: {ap.reason} [{ap.appointment_type.replace('_', ' ')}, {ap.status}]")
        data.append({"ref": rid, "when": f"{ap.scheduled_start:%Y-%m-%d %H:%M}", "patient": ap.patient.full_name,
                     "mrn": ap.patient.mrn, "doctor": ap.doctor.full_name, "reason": ap.reason, "status": ap.status})
    ctx.evidence.data["appointments"] = data
    scope = f"doctor '{a.doctor}'" if a.doctor else (a.patient or "patient in context" if (a.patient or ctx.patient_id) else "all visible patients")
    body = "\n".join(lines) or "No matching appointments."
    ctx.evidence.add_block("database", f"Appointments ({a.period}, {scope})", body)
    return ToolResult("ok", body, f"{len(rows)} appointments")


def search_documents(ctx: ToolContext, a: SearchArgs) -> ToolResult:
    retriever = HybridRetriever(ctx.db, ctx.policy)
    filters = RetrievalFilters(doc_types=[a.doc_type] if a.doc_type else None, patient_id=ctx.patient_id)
    with ctx.timer.stage("retrieval_total"):
        result = retriever.retrieve(a.query, filters)
    for stage, ms in result.stage_ms.items():
        ctx.timer.stages[stage] = round(ctx.timer.stages.get(stage, 0) + ms, 2)
    ctx.evidence.retrieval = result.summary()
    policy = get_settings().injection_policy
    kept = []
    for chunk in result.chunks:
        if chunk.flags.get("injection_suspected") and policy == "quarantine":
            ctx.evidence.withheld_sources.append({"document_title": chunk.document_title,
                                                  "section": chunk.section_path, "chunk_id": chunk.chunk_id,
                                                  "patterns": chunk.flags.get("injection_patterns", [])})
            continue
        kept.append((ctx.evidence.ref_chunk(chunk), chunk))
    ctx.evidence.data.setdefault("chunks", []).extend(kept)
    if not kept:
        return ToolResult("ok", "No relevant passages were found in the documents you can access.", "0 passages")
    text = "\n".join(f"[{sid}] {c.document_title} v{c.doc_version} - {c.section_path or 'body'} "
                     f"(p. {c.page_start}): {c.text[:500]}" for sid, c in kept)
    return ToolResult("ok", text, f"{len(kept)} passages")


def get_document_source(ctx: ToolContext, a: SourceArgs) -> ToolResult:
    chunk = ctx.evidence.sources.get(a.source_id.strip().upper())
    if chunk is None:
        return ToolResult("not_found", f"Unknown source id {a.source_id}. Use ids returned by search_documents.",
                          "unknown source")
    return ToolResult("ok", f"[{a.source_id}] {chunk.document_title} - {chunk.section_path}\n{chunk.text}", "source text")


def _prediction_text(pred, ref: str | None) -> str:
    if pred.status != "ok":
        return f"Not applicable: {pred.reason}"
    if pred.prediction_type == "readmission_30d":
        head = (f"Model {pred.model_name} v{pred.model_version} ({pred.model_algorithm}): estimated probability of "
                f"readmission within 30 days {pred.value:.1%} (risk band '{pred.label}'; model alert threshold "
                f"{pred.threshold:.1%}; average rate in training data {pred.context['base_rate']:.1%}). "
                f"Test-set ROC-AUC {pred.context['test_roc_auc']}, PR-AUC {pred.context['test_pr_auc']}.")
    else:
        actual = pred.reference.actual_length_of_stay_days if pred.reference else None
        head = (f"Model {pred.model_name} v{pred.model_version} ({pred.model_algorithm}): estimated length of stay "
                f"{pred.value:.1f} days (80% interval {pred.interval[0]}-{pred.interval[1]} days; test MAE "
                f"{pred.context['test_mae_days']} days, R2 {pred.context['test_r2']})."
                + (f" Actual length of that stay: {actual} days." if actual is not None else ""))
    scored = f" Scored admission [{ref}]: {pred.reference.reason} on {pred.reference.admitted_at.date()}." if ref else ""
    factors = "\n".join(f"- {f.label} = {f.value}: contribution {f.contribution:+.4f} "
                        f"({'towards higher' if f.direction == 'up' else 'towards lower'} prediction)" for f in pred.factors)
    notes = " ".join(pred.notes)
    attribution = "tree-path attributions approximating SHAP" if pred.explanation_method == "tree_path" else "SHAP attributions"
    return (f"{head}{scored}\nModel factors (additive {attribution}, {pred.explanation_space} scale; they describe "
            f"the model, not causes):\n{factors}" + (f"\nNotes: {notes}" if notes else "")
            + f"\nLimitations: {' '.join(pred.limitations)}")


def _predict(ctx: ToolContext, a: PatientArgs, fn, key: str, title: str) -> ToolResult:
    p = _patient(ctx, a.patient, clinical=True)
    with ctx.timer.stage("ml_inference"):
        pred = fn(ctx.db, p, ctx.user.id)
    ctx.evidence.predictions.append(pred)
    ref = None
    if pred.reference:
        ref = ctx.evidence.ref_record("admission", pred.reference.admission_id, f"Admission: {pred.reference.reason}",
                                      pred.reference.admitted_at.date().isoformat())
    if pred.model_version:
        ctx.evidence.model_versions.append(f"{pred.model_name}@{pred.model_version}")
    ctx.evidence.data[key] = {"prediction": pred, "ref": ref}
    text = _prediction_text(pred, ref)
    ctx.evidence.add_block("prediction", f"{title} for {p.mrn}", text)
    return ToolResult("ok", text, f"{pred.value:.3f}" if pred.value is not None else pred.status)


def predict_readmission_tool(ctx: ToolContext, a: PatientArgs) -> ToolResult:
    return _predict(ctx, a, predict_readmission, "readmission", "30-day readmission prediction")


def predict_los_tool(ctx: ToolContext, a: PatientArgs) -> ToolResult:
    return _predict(ctx, a, predict_length_of_stay, "los", "Length-of-stay prediction")


def find_similar_patients(ctx: ToolContext, a: SimilarArgs) -> ToolResult:
    p = _patient(ctx, a.patient, clinical=True)
    with ctx.timer.stage("similarity"):
        sim = similar_patients(ctx.db, ctx.policy, p, k=a.k)
    ctx.evidence.similarity = sim
    lines = []
    refs = []
    for r in sim.results:
        rid = ctx.evidence.ref_record("patient", r.patient_id, f"{r.full_name} ({r.mrn})")
        refs.append(rid)
        ctx.evidence.patient_ids.add(r.patient_id)
        lines.append(f"[{rid}] {r.mrn} {r.full_name}, {r.age:.0f}y {r.sex}, similarity {r.similarity:.2f}; shared "
                     f"diagnosis groups: {', '.join(r.shared_diagnosis_categories) or 'none'}; shared medication groups: "
                     f"{', '.join(r.shared_medication_groups) or 'none'}; admissions in 2 years: {r.admissions_2y}; "
                     f"mean stay {r.mean_los_days if r.mean_los_days is not None else 'n/a'} days; last HbA1c "
                     f"{r.last_hba1c if r.last_hba1c is not None else 'n/a'}; last eGFR "
                     f"{r.last_egfr if r.last_egfr is not None else 'n/a'}. Diagnoses: {'; '.join(r.diagnoses[:4])}")
    cp = sim.cohort_patterns
    if cp:
        lines.append(f"Cohort patterns across these {cp['cohort_size']} patients: {cp['discharges']} discharges, "
                     f"{cp['readmissions_within_30d']} followed by readmission within 30 days (rate "
                     f"{cp['readmission_rate'] if cp['readmission_rate'] is not None else 'n/a'}), mean length of stay "
                     f"{cp['mean_length_of_stay_days']} days. Common diagnoses: "
                     + "; ".join(f"{d['description']} ({d['patients']})" for d in cp["common_diagnoses"])
                     + ". Common active medications: "
                     + "; ".join(f"{m['medication']} ({m['patients']})" for m in cp["common_active_medications"]) + ".")
    lines.append(f"{sim.candidate_scope} {sim.disclaimer}")
    ctx.evidence.data["similar"] = {"out": sim, "refs": refs}
    text = "\n".join(lines)
    ctx.evidence.add_block("similarity", f"Patients most similar to {p.mrn}", text)
    return ToolResult("ok", text, f"{len(sim.results)} similar patients")


@dataclass
class ToolDef:
    name: str
    description: str
    args: type[_Args]
    fn: Callable[[ToolContext, _Args], ToolResult]
    permissions: tuple[Perm, ...]
    capability: str

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, _clean_schema(self.args.model_json_schema()))


TOOLS: dict[str, ToolDef] = {t.name: t for t in [
    ToolDef("get_patient", "Demographics, allergies, active problems, current medications and latest admission "
            "for one patient.", PatientArgs, get_patient, (Perm.PATIENTS_READ_DEMOGRAPHICS,), "SQL"),
    ToolDef("get_patient_records", "Recent clinical notes (visits, emergency notes, discharge summaries).",
            RecordsArgs, get_patient_records, (Perm.PATIENTS_READ_CLINICAL,), "SQL"),
    ToolDef("get_patient_timeline", "Chronological events: admissions, discharges, visits, diagnoses, medication "
            "starts/changes/stops, abnormal labs.", TimelineArgs, get_patient_timeline, (Perm.PATIENTS_READ_CLINICAL,), "SQL"),
    ToolDef("get_prescriptions", "Outpatient prescriptions, active or full history with change reasons.",
            PrescriptionArgs, get_prescriptions, (Perm.PATIENTS_READ_CLINICAL,), "SQL"),
    ToolDef("get_lab_reports", "Laboratory results with reference ranges and trends.", LabArgs, get_lab_reports,
            (Perm.PATIENTS_READ_CLINICAL,), "SQL"),
    ToolDef("get_appointments", "Appointments filtered by patient, doctor surname and period.", AppointmentArgs,
            get_appointments, (Perm.APPOINTMENTS_READ,), "SQL"),
    ToolDef("search_documents", "Hybrid search (semantic + keyword, reranked) over hospital guidelines, policies, "
            "protocols and authorized reports.", SearchArgs, search_documents, (Perm.DOCUMENTS_READ,), "RAG"),
    ToolDef("get_document_source", "Full text of a passage previously returned by search_documents.", SourceArgs,
            get_document_source, (Perm.DOCUMENTS_READ,), "RAG"),
    ToolDef("predict_readmission", "30-day readmission risk model with SHAP factor attributions.", PatientArgs,
            predict_readmission_tool, (Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL), "ML"),
    ToolDef("predict_length_of_stay", "Length-of-stay model estimate for the current or latest admission.",
            PatientArgs, predict_los_tool, (Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL), "ML"),
    ToolDef("find_similar_patients", "Patients with the most similar structured clinical profile, restricted to "
            "patients the user may access, plus their historical patterns.", SimilarArgs, find_similar_patients,
            (Perm.ML_READ, Perm.PATIENTS_READ_CLINICAL), "SIMILARITY"),
]}


def tools_for(user: User) -> list[ToolDef]:
    """Only tools the user is permitted to use are even offered to the model."""
    codes = user.permission_codes
    return [t for t in TOOLS.values() if all(p.value in codes for p in t.permissions)]


def execute_tool(ctx: ToolContext, name: str, arguments: dict, calls: list[ToolCallOut]) -> ToolResult:
    t0 = time.perf_counter()
    tool = TOOLS.get(name)
    safe_args = {k: (v if isinstance(v, (int, float, bool)) or v is None else str(v)[:80]) for k, v in arguments.items()}

    def done(result: ToolResult) -> ToolResult:
        calls.append(ToolCallOut(name=name, arguments=safe_args, status=result.status, summary=result.summary,
                                 ms=round((time.perf_counter() - t0) * 1000, 1)))
        if result.status in ("denied", "not_found") and tool is not None:
            ctx.evidence.add_block("tool_status", f"{name} could not be completed", result.text)
        return result

    if tool is None:
        return done(ToolResult("error", f"Unknown tool '{name}'.", "unknown tool"))
    missing = [p.value for p in tool.permissions if p.value not in ctx.user.permission_codes]
    if missing:
        audit("ai.tool_denied", user=ctx.user, outcome="denied", details={"tool": name, "required": missing})
        return done(ToolResult("denied", f"Access denied: the {ctx.user.role.name.lower()} role cannot use {name}.",
                               "permission denied"))
    try:
        args = tool.args.model_validate(arguments)
    except ValidationError as exc:
        return done(ToolResult("error", f"Invalid arguments for {name}: {exc.errors()[0]['msg']}", "invalid arguments"))
    try:
        return done(tool.fn(ctx, args))
    except NotFoundError as exc:
        return done(ToolResult("not_found", exc.message, "not found or not accessible"))
    except PermissionDeniedError as exc:
        return done(ToolResult("denied", exc.message, "permission denied"))
    except ServiceUnavailableError as exc:
        return done(ToolResult("error", exc.message, "service unavailable"))
    except AppError as exc:
        return done(ToolResult("error", exc.message, "error"))
    except Exception:
        logger.exception("tool failed", extra={"fields": {"tool": name}})
        ctx.db.rollback()
        return done(ToolResult("error", f"{name} failed unexpectedly.", "internal error"))


def care_team(db: Session, patient_id: int) -> list[tuple[int, str, str]]:
    return db.execute(select(User.id, User.full_name, CareAssignment.care_role).join(CareAssignment)
                      .where(CareAssignment.patient_id == patient_id, CareAssignment.active)).all()
