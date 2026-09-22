"""HL7 FHIR R4 representation of a patient's record (read-only export).

One searchset Bundle per patient (Patient/$everything); resources reference each other by relative id.

Terminologies
  diagnoses         ICD-10-CM                    http://hl7.org/fhir/sid/icd-10-cm (the codes carry CM extensions)
  laboratory        LOINC, values in UCUM         http://loinc.org, http://unitsofmeasure.org
  medicines         WHO ATC, plus the formulary   http://www.whocc.no/atc
  routes            SNOMED CT                     http://snomed.info/sct
  notes             LOINC document types          (discharge summary, progress note, ...)
  observations      LOINC vital signs             (respiratory rate, SpO2, pulse, temperature, blood pressure)
  statuses/classes  HL7 terminology               http://terminology.hl7.org/CodeSystem/...

Every resource carries meta.security HTEST ("test health data"): the whole hospital is synthetic.
Signed co-pilot summaries are exported with a Provenance resource naming the clinician as author and the
drafting model as a Device in the assembler role, so the receiving system can tell what a machine wrote.

Mapping notes: the seed data does not record which eGFR equation was used, so eGFR is mapped to the
current CKD-EPI 2021 LOINC code; medicines without an ATC mapping (IV dextrose) carry only the formulary code.
"""
import base64
import html
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Admission,
    Appointment,
    Diagnosis,
    Doctor,
    ImagingStudy,
    LabReport,
    MedicalRecord,
    Medication,
    MLPrediction,
    Patient,
    Prescription,
    VitalSigns,
)
from app.services.news2 import CONSCIOUSNESS

FHIR_VERSION = "4.0.1"
FHIR_JSON = "application/fhir+json"
NS = "https://careflow.demo/fhir"  # namespace for CareFlow's own identifier and code systems
MRN_SYSTEM = f"{NS}/sid/mrn"
STAFF_SYSTEM = f"{NS}/sid/staff-code"
FORMULARY_SYSTEM = f"{NS}/CodeSystem/formulary"
LAB_SYSTEM = f"{NS}/CodeSystem/lab-test"
OBS_SYSTEM = f"{NS}/CodeSystem/observations"  # bedside observations that have no LOINC equivalent here
HL7 = "http://terminology.hl7.org/CodeSystem"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
ATC_SYSTEM = "http://www.whocc.no/atc"
SNOMED = "http://snomed.info/sct"
DCM = "http://dicom.nema.org/resources/ontology/DCM"       # DICOM's own code system, used for modality
DICOM_UID = "urn:dicom:uid"
ACCESSION_SYSTEM = f"{NS}/sid/accession"
CXR_SOP_CLASS = "urn:oid:1.2.840.10008.5.1.4.1.1.1.1"      # Digital X-Ray Image Storage - For Presentation
BODY_SITE = {"CHEST": ("51185008", "Thoracic structure"), "THORAX": ("51185008", "Thoracic structure")}
HOSPITAL_ID = "careflow"

LAB_LOINC = {  # CareFlow test code -> (LOINC code, LOINC name, UCUM unit)
    "HBA1C": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "GLU": ("2345-7", "Glucose [Mass/volume] in Serum or Plasma", "mg/dL"),
    "CREAT": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL"),
    "EGFR": ("98979-8", "Glomerular filtration rate/1.73 sq M.predicted [Volume Rate/Area] in Serum, Plasma or "
             "Blood by Creatinine-based formula (CKD-EPI 2021)", "mL/min/{1.73_m2}"),
    "K": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma", "mmol/L"),
    "NA": ("2951-2", "Sodium [Moles/volume] in Serum or Plasma", "mmol/L"),
    "LDL": ("13457-7", "Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation", "mg/dL"),
    "BNP": ("30934-4", "Natriuretic peptide B [Mass/volume] in Serum or Plasma", "pg/mL"),
    "INR": ("6301-6", "INR in Platelet poor plasma by Coagulation assay", "{INR}"),
    "HGB": ("718-7", "Hemoglobin [Mass/volume] in Blood", "g/dL"),
    "WBC": ("6690-2", "Leukocytes [#/volume] in Blood by Automated count", "10*9/L"),
    "CRP": ("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma", "mg/L"),
    "TSH": ("3016-3", "Thyrotropin [Units/volume] in Serum or Plasma", "m[IU]/L"),
    "UACR": ("9318-7", "Albumin/Creatinine [Mass Ratio] in Urine", "mg/g"),
}
ATC = {
    "metformin": "A10BA02", "glipizide": "A10BB07", "sitagliptin": "A10BH01", "empagliflozin": "A10BK03",
    "liraglutide": "A10BJ02", "insulin glargine": "A10AE04", "insulin lispro": "A10AB04",
    "sodium chloride 0.9%": "B05XA03", "lisinopril": "C09AA03", "losartan": "C09CA01", "amlodipine": "C08CA01",
    "hydrochlorothiazide": "C03AA03", "metoprolol succinate": "C07AB02", "furosemide": "C03CA01",
    "spironolactone": "C03DA01", "atorvastatin": "C10AA05", "aspirin": "B01AC06", "clopidogrel": "B01AC04",
    "apixaban": "B01AF02", "warfarin": "B01AA03", "enoxaparin": "B01AB05", "potassium chloride": "A12BA01",
    "omeprazole": "A02BC01", "sertraline": "N06AB06", "levothyroxine": "H03AA01", "levetiracetam": "N03AX14",
    "sumatriptan": "N02CC01", "gabapentin": "N03AX12", "paracetamol": "N02BE01", "ibuprofen": "M01AE01",
    "morphine": "N02AA01", "salbutamol": "R03AC02", "tiotropium": "R03BB04", "budesonide": "R03BA02",
    "prednisone": "H02AB07", "ceftriaxone": "J01DD04", "azithromycin": "J01FA10", "cefazolin": "J01DB04",
    "nitrofurantoin": "J01XE01", "hydrocortisone 1% cream": "D07AA02", "calcipotriol ointment": "D05AX02",
}
ROUTE = {"oral": ("26643006", "Oral route"), "subcut": ("34206005", "Subcutaneous route"),
         "iv": ("47625008", "Intravenous route"), "inhaled": ("447694001", "Respiratory tract route"),
         "topical": ("6064005", "Topical route")}
LANGUAGE = {"English": "en", "Hindi": "hi", "Marathi": "mr", "Tamil": "ta", "Kannada": "kn", "Telugu": "te"}
GENDER = {"F": "female", "M": "male", "X": "other"}
PRIORITY = {"emergency": ("EM", "emergency"), "urgent": ("UR", "urgent"), "elective": ("EL", "elective")}
ADMIT_SOURCE = {"emergency_room": ("emd", "From accident/emergency department"),
                "physician_referral": ("gp", "General Practitioner referral"),
                "transfer": ("hosp-trans", "Transferred from other hospital"),
                "clinic": ("outp", "From outpatient department")}
DISPOSITION = {"home": ("home", "Home"), "home_health": ("home", "Home"), "skilled_nursing": ("snf", "Skilled nursing facility"),
               "rehab": ("rehab", "Rehabilitation"), "transfer": ("other-hcf", "Other healthcare facility"),
               "ama": ("aadvice", "Left against advice"), "expired": ("exp", "Expired")}
NOTE_TYPE = {"discharge_summary": ("18842-5", "Discharge summary"), "progress_note": ("11506-3", "Progress note"),
             "consultation": ("11488-4", "Consult note"), "emergency": ("34111-5", "Emergency department note"),
             "follow_up": ("11506-3", "Progress note"), "radiology_report": ("18748-4", "Diagnostic imaging study")}
APPOINTMENT_STATUS = {"scheduled": "booked", "checked_in": "arrived", "completed": "fulfilled",
                      "cancelled": "cancelled", "no_show": "noshow"}
APPOINTMENT_TYPE = {"follow_up": ("FOLLOWUP", "A follow up visit from a previous appointment"),
                    "outpatient": ("ROUTINE", "Routine appointment - default if not valued"),
                    "telehealth": ("ROUTINE", "Routine appointment - default if not valued"),
                    "emergency": ("EMERGENCY", "Emergency appointment")}
RX_STATUS = {"active": "active", "completed": "completed", "discontinued": "stopped"}
ALLERGY_CATEGORY = {"peanuts": "food", "latex": "environment"}  # everything else in the catalogue is a medicine
OUTCOME_CODE = {400: "invalid", 401: "login", 403: "forbidden", 404: "not-found", 409: "conflict", 422: "invalid",
                429: "throttled"}


def _meta() -> dict:
    return {"security": [{"system": f"{HL7}/v3-ActReason", "code": "HTEST", "display": "test health data"}]}


def cc(system: str, code: str, display: str | None = None, text: str | None = None) -> dict:
    coding = {"system": system, "code": code}
    if display:
        coding["display"] = display
    out: dict[str, Any] = {"coding": [coding]}
    if text:
        out["text"] = text
    return out


def ref(resource_type: str, rid: str, display: str | None = None) -> dict:
    out = {"reference": f"{resource_type}/{rid}"}
    if display:
        out["display"] = display
    return out


def instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _xhtml(text: str) -> str:
    """A Narrative div, escaped: the text comes from the record and must not be able to carry markup."""
    return f'<div xmlns="http://www.w3.org/1999/xhtml">{html.escape(text)}</div>' 


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", text).strip("-")[:60] or "model"


def _human_name(full: str) -> dict:
    """ "Dr. Ananya Rao" -> prefix Dr., given Ananya, family Rao."""
    parts = full.replace(",", " ").split()
    prefix = [parts.pop(0)] if parts and parts[0].rstrip(".") in ("Dr", "Mr", "Mrs", "Ms") else []
    name: dict[str, Any] = {"text": full}
    if prefix:
        name["prefix"] = prefix
    if parts:
        name["family"] = parts[-1] if len(parts) > 1 else parts[0]
        if len(parts) > 1:
            name["given"] = parts[:-1]
    return name


def operation_outcome(status: int, code: str, message: str) -> dict:
    """The FHIR error body: CareFlow's error envelope, translated."""
    return {"resourceType": "OperationOutcome", "issue": [{
        "severity": "error", "code": OUTCOME_CODE.get(status, "exception" if status >= 500 else "processing"),
        "details": {"text": code}, "diagnostics": message}]}


def capability_statement(base: str) -> dict:
    exported = ["Practitioner", "Organization", "Encounter", "Condition", "Observation", "MedicationRequest",
                "AllergyIntolerance", "Appointment", "DocumentReference", "Provenance", "Device", "RiskAssessment",
                "ImagingStudy", "DiagnosticReport"]
    return {
        "resourceType": "CapabilityStatement", "id": "careflow", "status": "active", "date": "2026-09-18",
        "publisher": "CareFlow AI (portfolio demonstration, synthetic data)", "kind": "instance",
        "software": {"name": "CareFlow AI", "version": "1.0.0"},
        "implementation": {"description": "Read-only FHIR R4 export of synthetic patient records", "url": base},
        "fhirVersion": FHIR_VERSION, "format": [FHIR_JSON, "json"],
        "rest": [{
            "mode": "server",
            "documentation": "Every request is authenticated (bearer token or session cookie) and runs under the "
                             "caller's row-level access policy: patients outside the caller's care return 404. "
                             "Clinical resources require clinical read permission.",
            "resource": [{
                "type": "Patient", "interaction": [{"code": "read"}, {"code": "search-type"}],
                "searchParam": [{"name": "identifier", "type": "token",
                                 "documentation": f"Medical record number, e.g. {MRN_SYSTEM}|P1024"},
                                {"name": "name", "type": "string"}],
                "operation": [{"name": "everything",
                               "definition": "http://hl7.org/fhir/OperationDefinition/Patient-everything"}],
            }] + [{"type": t, "documentation": "Returned by Patient/$everything"} for t in exported],
        }],
    }


class FhirExporter:
    """Builds FHIR resources for one patient; referenced practitioners, organisations and devices are collected
    on the way and added to the bundle once each."""

    def __init__(self, db: Session, base: str):
        self.db = db
        self.base = base.rstrip("/")
        self.extra: dict[str, dict] = {}  # "Practitioner/D101" -> resource

    # ------------------------------------------------------------------ shared resources
    def _add(self, resource: dict) -> None:
        self.extra.setdefault(f"{resource['resourceType']}/{resource['id']}", resource)

    def practitioner(self, doctor: Doctor | None) -> dict | None:
        if doctor is None:
            return None
        telecom = [{"system": "phone", "value": doctor.phone, "use": "work"}] if doctor.phone else []
        if doctor.email:
            telecom.append({"system": "email", "value": doctor.email, "use": "work"})
        self._add({"resourceType": "Practitioner", "id": doctor.staff_code, "meta": _meta(),
                   "identifier": [{"system": STAFF_SYSTEM, "value": doctor.staff_code}], "active": doctor.is_active,
                   "name": [_human_name(doctor.full_name)], "telecom": telecom})
        return ref("Practitioner", doctor.staff_code, doctor.full_name)

    def organization(self, department=None) -> dict:
        self._add({"resourceType": "Organization", "id": HOSPITAL_ID, "meta": _meta(), "active": True,
                   "name": "CareFlow General Hospital", "alias": ["Synthetic demonstration hospital"],
                   "address": [{"city": "Pune", "state": "Maharashtra", "country": "IN"}]})
        if department is None:
            return ref("Organization", HOSPITAL_ID, "CareFlow General Hospital")
        rid = f"dept-{department.code.lower()}"
        self._add({"resourceType": "Organization", "id": rid, "meta": _meta(), "active": True, "name": department.name,
                   "type": [cc(f"{HL7}/organization-type", "dept", "Hospital Department")],
                   "partOf": ref("Organization", HOSPITAL_ID)})
        return ref("Organization", rid, department.name)

    def device(self, generated_by: str) -> dict:
        template = generated_by == "template"
        rid = f"model-{_slug(generated_by)}"
        self._add({"resourceType": "Device", "id": rid, "meta": _meta(),
                   "deviceName": [{"name": "CareFlow discharge template (no language model)" if template
                                   else generated_by, "type": "model-name"}],
                   "type": {"text": "Rule-based text assembly" if template
                            else "Large language model (discharge summary drafting)"}})
        return ref("Device", rid)

    # ------------------------------------------------------------------ patient
    def patient(self, p: Patient) -> dict:
        telecom = [{"system": "phone", "value": p.phone, "use": "mobile"}] if p.phone else []
        if p.email:
            telecom.append({"system": "email", "value": p.email, "use": "home"})
        resource: dict[str, Any] = {
            "resourceType": "Patient", "id": p.mrn, "meta": _meta(),
            "identifier": [{"use": "usual", "type": cc(f"{HL7}/v2-0203", "MR", "Medical record number"),
                            "system": MRN_SYSTEM, "value": p.mrn}],
            "active": p.status not in ("inactive", "deceased"),
            "name": [{"use": "official", "text": p.full_name, "family": p.last_name, "given": [p.first_name]}],
            "gender": GENDER.get(p.sex, "unknown"), "birthDate": p.date_of_birth.isoformat(),
            "deceasedBoolean": p.status == "deceased",
            "managingOrganization": self.organization(),
        }
        if telecom:
            resource["telecom"] = telecom
        if p.address:
            address: dict[str, Any] = {"use": "home", "text": p.address, "country": "IN"}
            m = re.search(r"([A-Za-z][A-Za-z ]+?)\s+(\d{6})$", p.address)
            if m:
                address["city"], address["postalCode"] = m.group(1), m.group(2)
            resource["address"] = [address]
        if p.preferred_language:
            code = LANGUAGE.get(p.preferred_language)
            language = cc("urn:ietf:bcp:47", code, p.preferred_language) if code else {}
            resource["communication"] = [{"language": {**language, "text": p.preferred_language}, "preferred": True}]
        if p.emergency_contact_name:
            contact: dict[str, Any] = {
                "relationship": [cc(f"{HL7}/v2-0131", "C", "Emergency Contact")],
                "name": {"text": p.emergency_contact_name}}
            if p.emergency_contact_relation:
                contact["relationship"].append({"text": p.emergency_contact_relation})
            if p.emergency_contact_phone:
                contact["telecom"] = [{"system": "phone", "value": p.emergency_contact_phone}]
            resource["contact"] = [contact]
        return resource

    # ------------------------------------------------------------------ clinical resources
    def allergies(self, p: Patient) -> list[dict]:
        out = []
        for i, a in enumerate(p.allergies or [], start=1):
            intolerance = a.get("reaction", "").lower() == "nausea"
            out.append({
                "resourceType": "AllergyIntolerance", "id": f"allergy-{p.mrn}-{i}", "meta": _meta(),
                "clinicalStatus": cc(f"{HL7}/allergyintolerance-clinical", "active", "Active"),
                "verificationStatus": cc(f"{HL7}/allergyintolerance-verification", "confirmed", "Confirmed"),
                "type": "intolerance" if intolerance else "allergy",
                "category": [ALLERGY_CATEGORY.get(a["substance"].lower(), "medication")],
                "criticality": "high" if a.get("severity") == "severe" else "low",
                "code": {"text": a["substance"]}, "patient": ref("Patient", p.mrn),
                "reaction": [{"manifestation": [{"text": a["reaction"]}], "severity": a["severity"]}]})
        return out

    def blood_group(self, p: Patient) -> list[dict]:
        if not p.blood_type:
            return []
        return [{"resourceType": "Observation", "id": f"blood-group-{p.mrn}", "meta": _meta(), "status": "final",
                 "category": [cc(f"{HL7}/observation-category", "laboratory", "Laboratory")],
                 "code": {"coding": [{"system": LOINC, "code": "882-1", "display": "ABO and Rh group [Type] in Blood"}],
                          "text": "Blood group"},
                 "subject": ref("Patient", p.mrn), "valueCodeableConcept": {"text": p.blood_type}}]

    def encounter(self, a: Admission, p: Patient) -> dict:
        resource: dict[str, Any] = {
            "resourceType": "Encounter", "id": f"adm-{a.id}", "meta": _meta(),
            "status": "in-progress" if a.status == "admitted" else "finished",
            "class": {"system": f"{HL7}/v3-ActCode", "code": "IMP", "display": "inpatient encounter"},
            "priority": cc(f"{HL7}/v3-ActPriority", *PRIORITY[a.admission_type]),
            "subject": ref("Patient", p.mrn),
            "period": {"start": instant(a.admitted_at), **({"end": instant(a.discharged_at)} if a.discharged_at else {})},
            "reasonCode": [{"text": a.reason}],
            "hospitalization": {"admitSource": cc(f"{HL7}/admit-source", *ADMIT_SOURCE[a.admission_source])},
            "serviceProvider": self.organization(a.department),
        }
        attending = self.practitioner(a.attending_doctor)
        if attending:
            resource["participant"] = [{"type": [cc(f"{HL7}/v3-ParticipationType", "ATND", "attender")],
                                        "individual": attending}]
        if a.discharge_disposition:
            code, display = DISPOSITION[a.discharge_disposition]
            resource["hospitalization"]["dischargeDisposition"] = cc(
                f"{HL7}/discharge-disposition", code, display, text=a.discharge_disposition.replace("_", " "))
        if a.length_of_stay_days is not None:
            resource["length"] = {"value": a.length_of_stay_days, "unit": "days", "system": UCUM, "code": "d"}
        if a.ward:
            resource["location"] = [{"location": {"display": f"Ward {a.ward}"}}]
        return resource

    def condition(self, d: Diagnosis, p: Patient) -> dict:
        resource: dict[str, Any] = {
            "resourceType": "Condition", "id": f"dx-{d.id}", "meta": _meta(),
            "clinicalStatus": cc(f"{HL7}/condition-clinical", d.status, d.status.title()),
            "verificationStatus": cc(f"{HL7}/condition-ver-status", "confirmed", "Confirmed"),
            "category": [cc(f"{HL7}/condition-category", "encounter-diagnosis", "Encounter Diagnosis")
                         if d.admission_id else cc(f"{HL7}/condition-category", "problem-list-item", "Problem List Item")],
            "code": {"coding": [{"system": ICD10CM, "code": d.icd10_code, "display": d.description}],
                     "text": d.description},
            "subject": ref("Patient", p.mrn), "onsetDateTime": d.diagnosed_on.isoformat(),
            "recordedDate": d.diagnosed_on.isoformat(),
        }
        if d.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{d.admission_id}")
        return resource

    def lab(self, lab: LabReport, p: Patient) -> dict:
        loinc = LAB_LOINC.get(lab.test_code)
        coding = [{"system": LOINC, "code": loinc[0], "display": loinc[1]}] if loinc else []
        coding.append({"system": LAB_SYSTEM, "code": lab.test_code, "display": lab.test_name})
        ucum = loinc[2] if loinc else None

        def quantity(value: float) -> dict:
            q: dict[str, Any] = {"value": value, "unit": lab.unit or ""}
            if ucum:
                q.update(system=UCUM, code=ucum)
            return q

        resource: dict[str, Any] = {
            "resourceType": "Observation", "id": f"lab-{lab.id}", "meta": _meta(),
            "status": "final" if lab.reported_at else "preliminary",
            "category": [cc(f"{HL7}/observation-category", "laboratory", "Laboratory")],
            "code": {"coding": coding, "text": lab.test_name}, "subject": ref("Patient", p.mrn),
            "effectiveDateTime": instant(lab.collected_at),
        }
        if lab.reported_at:
            resource["issued"] = instant(lab.reported_at)
        if lab.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{lab.admission_id}")
        if lab.value is not None:
            resource["valueQuantity"] = quantity(lab.value)
        elif lab.value_text:
            resource["valueString"] = lab.value_text
        if lab.flag == "critical" and lab.value is not None:
            high = lab.reference_high is not None and lab.value > lab.reference_high
            low = lab.reference_low is not None and lab.value < lab.reference_low
            code, display = ("HH", "Critical high") if high else ("LL", "Critical low") if low else ("AA", "Critical abnormal")
        else:
            code, display = {"normal": ("N", "Normal"), "low": ("L", "Low"), "high": ("H", "High"),
                             "critical": ("AA", "Critical abnormal")}[lab.flag]
        resource["interpretation"] = [cc(f"{HL7}/v3-ObservationInterpretation", code, display)]
        bounds = {k: quantity(v) for k, v in (("low", lab.reference_low), ("high", lab.reference_high)) if v is not None}
        if bounds:
            resource["referenceRange"] = [bounds]
        return resource

    def observation_set(self, v: VitalSigns, p: Patient) -> dict:
        """One set of bedside observations: the NEWS2 total as the value, each vital sign as a LOINC component.

        The vital-signs profile models each sign as its own Observation; one resource per set is used here so a
        bundle stays readable, and the components carry the same LOINC codes a receiver would look for.
        """
        def component(code: str, system: str, display: str, value: dict) -> dict:
            return {"code": cc(system, code, display), **value}

        def quantity(value: float, unit: str, ucum: str) -> dict:
            return {"valueQuantity": {"value": value, "unit": unit, "system": UCUM, "code": ucum}}

        components = [
            component("9279-1", LOINC, "Respiratory rate", quantity(v.respiratory_rate, "breaths/min", "/min")),
            component("59408-5", LOINC, "Oxygen saturation in Arterial blood by Pulse oximetry",
                      quantity(v.spo2, "%", "%")),
            component("8867-4", LOINC, "Heart rate", quantity(v.heart_rate, "beats/min", "/min")),
            component("8310-5", LOINC, "Body temperature", quantity(v.temperature, "Cel", "Cel")),
            component("8480-6", LOINC, "Systolic blood pressure", quantity(v.systolic_bp, "mmHg", "mm[Hg]")),
            component("consciousness", OBS_SYSTEM, "Level of consciousness (ACVPU)",
                      {"valueCodeableConcept": {"text": CONSCIOUSNESS[v.consciousness]}}),
            component("supplemental-oxygen", OBS_SYSTEM, "Receiving supplemental oxygen",
                      {"valueBoolean": v.on_oxygen}),
            component("spo2-scale", OBS_SYSTEM, "NEWS2 SpO2 scale", {"valueInteger": v.spo2_scale}),
        ]
        if v.diastolic_bp is not None:
            components.insert(5, component("8462-4", LOINC, "Diastolic blood pressure",
                                           quantity(v.diastolic_bp, "mmHg", "mm[Hg]")))
        resource: dict[str, Any] = {
            "resourceType": "Observation", "id": f"obs-{v.id}", "meta": _meta(), "status": "final",
            "category": [cc(f"{HL7}/observation-category", "vital-signs", "Vital Signs")],
            "code": {"coding": [{"system": OBS_SYSTEM, "code": "news2-observation-set",
                                 "display": "NEWS2 observation set"}],
                     "text": "Bedside observations with NEWS2 total score"},
            "subject": ref("Patient", p.mrn), "effectiveDateTime": instant(v.recorded_at),
            "valueInteger": v.news2_score,
            "interpretation": [cc(OBS_SYSTEM, v.news2_risk, f"NEWS2 clinical risk: {v.news2_risk.replace('_', '-')}")],
            "component": components,
        }
        if v.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{v.admission_id}")
        if v.recorded_by and v.recorded_by.doctor_id:
            doctor = self.db.get(Doctor, v.recorded_by.doctor_id)
            performer = self.practitioner(doctor)
            if performer:
                resource["performer"] = [performer]
        if v.notes:
            resource["note"] = [{"text": v.notes}]
        return resource

    def medication_request(self, rx: Prescription, med: Medication, p: Patient) -> dict:
        coding = [{"system": ATC_SYSTEM, "code": ATC[med.name]}] if med.name in ATC else []
        coding.append({"system": FORMULARY_SYSTEM, "code": med.name, "display": med.name})
        dosage: dict[str, Any] = {"text": f"{rx.dosage} {rx.frequency}",
                                  "timing": {"repeat": {"boundsPeriod": {
                                      "start": rx.start_date.isoformat(),
                                      **({"end": rx.end_date.isoformat()} if rx.end_date else {})}}}}
        if rx.route in ROUTE:
            dosage["route"] = cc(SNOMED, *ROUTE[rx.route])
        if rx.instructions:
            dosage["patientInstruction"] = rx.instructions
        resource: dict[str, Any] = {
            "resourceType": "MedicationRequest", "id": f"rx-{rx.id}", "meta": _meta(),
            "status": RX_STATUS[rx.status], "intent": "order",
            "category": [cc(f"{HL7}/medicationrequest-category", "inpatient" if rx.admission_id else "outpatient",
                            "Inpatient" if rx.admission_id else "Outpatient")],
            "medicationCodeableConcept": {"coding": coding, "text": med.name},
            "subject": ref("Patient", p.mrn), "authoredOn": rx.start_date.isoformat(),
            "dosageInstruction": [dosage],
        }
        requester = self.practitioner(rx.doctor)
        if requester:
            resource["requester"] = requester
        if rx.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{rx.admission_id}")
        if rx.change_reason:
            if rx.status == "discontinued":
                resource["statusReason"] = {"text": rx.change_reason}
            else:
                resource["note"] = [{"text": rx.change_reason}]
        if med.is_high_alert:
            resource.setdefault("note", []).append({"text": "High-alert medication (MED-POL-004)."})
        return resource

    def document(self, r: MedicalRecord, p: Patient) -> list[dict]:
        code, display = NOTE_TYPE[r.record_type]
        sections = [("Chief complaint", r.chief_complaint), ("Symptoms", r.symptoms), ("Assessment", r.diagnosis_summary),
                    ("Notes", r.notes), ("Plan", r.treatment_plan)]
        body = "\n\n".join(f"{title}\n{text}" for title, text in sections if text)
        resource: dict[str, Any] = {
            "resourceType": "DocumentReference", "id": f"doc-{r.id}", "meta": _meta(), "status": "current",
            "docStatus": "final", "type": cc(LOINC, code, display, text=r.record_type.replace("_", " ")),
            "subject": ref("Patient", p.mrn), "date": instant(r.created_at), "description": r.chief_complaint,
            "content": [{"attachment": {"contentType": "text/plain", "language": "en",
                                        "data": base64.b64encode(body.encode()).decode(), "title": display,
                                        "creation": r.visit_date.isoformat()}}],
        }
        author = self.practitioner(r.doctor)
        if author:
            resource["author"] = [author]
        if r.admission_id:
            resource["context"] = {"encounter": [ref("Encounter", f"adm-{r.admission_id}")]}
        out = [resource]
        prov = r.ai_provenance
        if prov and prov.get("kind") == "radiology_triage_shown":
            # Nothing in a radiology report is written by a model. This Provenance says who signed it, and
            # records the triage assessment the reader had in front of them as a source, not as an author.
            flagged = ", ".join(prov.get("flagged") or []) or "nothing"
            summary = (f"Read and signed by {prov['signed_by']}. A triage model ({prov.get('model') or 'none'}) "
                       f"had flagged {flagged}; the reader recorded '{prov.get('model_agreement')}'.")
            entry: dict[str, Any] = {
                "resourceType": "Provenance", "id": f"prov-doc-{r.id}", "meta": _meta(),
                "text": {"status": "generated", "div": _xhtml(summary)},
                "target": [ref("DocumentReference", f"doc-{r.id}")], "recorded": prov["signed_at"],
                "activity": cc(f"{HL7}/v3-DataOperation", "CREATE", "create"),
                "agent": [{"type": cc(f"{HL7}/provenance-participant-type", "author", "Author"),
                           "who": author or {"display": prov["signed_by"]}}]}
            if prov.get("risk_assessment_id"):
                entry["entity"] = [{"role": "source",
                                    "what": ref("RiskAssessment", f"risk-{prov['risk_assessment_id']}")}]
            out.append(entry)
        elif prov:
            # Who wrote what: the clinician is the author; the drafting model assembled the text they signed.
            summary = (f"Drafted by {prov['generated_by']}; reviewed, edited ({prov['edited_pct']}% of the text changed) "
                       f"and signed by {prov['signed_by']}.")
            agents = [{"type": cc(f"{HL7}/provenance-participant-type", "assembler", "Assembler"),
                       "who": self.device(prov["generated_by"])}]
            if author:
                agents.insert(0, {"type": cc(f"{HL7}/provenance-participant-type", "author", "Author"), "who": author})
            out.append({"resourceType": "Provenance", "id": f"prov-doc-{r.id}", "meta": _meta(),
                        "text": {"status": "generated", "div": _xhtml(summary)},
                        "target": [ref("DocumentReference", f"doc-{r.id}")], "recorded": prov["signed_at"],
                        "activity": cc(f"{HL7}/v3-DataOperation", "CREATE", "create"), "agent": agents})
        return out

    def appointment(self, ap: Appointment, p: Patient) -> dict:
        end = ap.scheduled_start + timedelta(minutes=ap.duration_minutes)
        resource: dict[str, Any] = {
            "resourceType": "Appointment", "id": f"appt-{ap.id}", "meta": _meta(),
            "status": APPOINTMENT_STATUS[ap.status],
            "appointmentType": cc(f"{HL7}/v2-0276", *APPOINTMENT_TYPE[ap.appointment_type],
                                  text=ap.appointment_type.replace("_", " ")),
            "reasonCode": [{"text": ap.reason}], "start": instant(ap.scheduled_start), "end": instant(end),
            "minutesDuration": ap.duration_minutes,
            "participant": [{"actor": ref("Patient", p.mrn, p.full_name), "status": "accepted"}],
        }
        doctor = self.practitioner(ap.doctor)
        if doctor:
            resource["participant"].append({"actor": doctor, "status": "accepted"})
        if ap.status == "cancelled" and ap.cancellation_reason:
            resource["cancelationReason"] = {"text": ap.cancellation_reason}
        return resource

    def risk_assessment(self, pred: MLPrediction, p: Patient) -> dict:
        mv = pred.model_version
        resource: dict[str, Any] = {
            "resourceType": "RiskAssessment", "id": f"risk-{pred.id}", "meta": _meta(), "status": "final",
            "subject": ref("Patient", p.mrn), "occurrenceDateTime": instant(pred.created_at),
            "method": {"text": f"{mv.model_name} v{mv.version} ({mv.algorithm})"},
            "prediction": [{"outcome": {"text": "Readmission within 30 days of discharge"},
                            "probabilityDecimal": round(pred.value, 4),
                            **({"qualitativeRisk": {"text": pred.label}} if pred.label else {})}],
            "note": [{"text": "Decision-support estimate from a statistical model trained on public de-identified "
                              "data; not a diagnosis."}],
        }
        if pred.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{pred.admission_id}")
            resource["basis"] = [ref("Encounter", f"adm-{pred.admission_id}")]
        return resource

    # ------------------------------------------------------------------ imaging
    def imaging_study(self, study: ImagingStudy, p: Patient) -> dict:
        """The study as DICOM describes it. The UIDs are the ones CareFlow minted when it de-identified the
        file - the sender's UIDs were themselves identifiers and are not exported."""
        modality = {"system": DCM, "code": study.modality}
        body = BODY_SITE.get((study.body_part or "").upper())
        series: dict[str, Any] = {
            "uid": study.series_uid, "number": 1, "modality": modality, "numberOfInstances": 1,
            "instance": [{"uid": study.sop_uid, "number": 1,
                          "sopClass": {"system": "urn:ietf:rfc:3986", "code": CXR_SOP_CLASS}}]}
        if body:
            series["bodySite"] = {"system": SNOMED, "code": body[0], "display": body[1]}
        if study.description:
            series["description"] = study.description
        resource: dict[str, Any] = {
            "resourceType": "ImagingStudy", "id": f"img-{study.id}", "meta": _meta(), "status": "available",
            "identifier": [{"system": DICOM_UID, "value": f"urn:oid:{study.study_uid}"},
                           {"use": "usual", "system": ACCESSION_SYSTEM, "value": study.accession,
                            "type": cc(f"{HL7}/v2-0203", "ACSN", "Accession ID")}],
            "subject": ref("Patient", p.mrn), "started": instant(study.acquired_at),
            "modality": [modality], "numberOfSeries": 1, "numberOfInstances": 1, "series": [series]}
        if study.description:
            resource["description"] = study.description
        if study.indication:
            resource["reasonCode"] = [{"text": study.indication}]
        if study.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{study.admission_id}")
        return resource

    def diagnostic_report(self, study: ImagingStudy, p: Patient) -> dict | None:
        """The radiologist's signed report. A draft is not exported: it is not a report yet."""
        report = study.report
        if report is None or report.status != "final":
            return None
        code, display = NOTE_TYPE["radiology_report"]
        body = f"FINDINGS\n{report.findings}\n\nIMPRESSION\n{report.impression}"
        resource: dict[str, Any] = {
            "resourceType": "DiagnosticReport", "id": f"rad-{report.id}", "meta": _meta(), "status": "final",
            "category": [cc(f"{HL7}/v2-0074", "RAD", "Radiology")],
            "code": cc(LOINC, code, display, text=study.description or "Chest radiograph"),
            "subject": ref("Patient", p.mrn), "effectiveDateTime": instant(study.acquired_at),
            "issued": instant(report.signed_at), "imagingStudy": [ref("ImagingStudy", f"img-{study.id}")],
            "conclusion": report.impression,
            "presentedForm": [{"contentType": "text/plain", "language": "en",
                               "data": base64.b64encode(body.encode()).decode(), "title": display}]}
        signer = report.reported_by
        performer = self.practitioner(
            self.db.get(Doctor, signer.doctor_id) if signer and signer.doctor_id else None)
        if performer:
            resource["performer"] = [performer]
        if study.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{study.admission_id}")
        return resource

    def triage_assessment(self, pred: MLPrediction, study: ImagingStudy, p: Patient) -> dict:
        """What the triage model said about a film: one prediction per finding it is allowed to report."""
        mv = pred.model_version
        findings = (pred.explanation or {}).get("findings", [])
        predictions = [{"outcome": {"text": f["label"]}, "probabilityDecimal": round(f["probability"], 4),
                        "rationale": f"ROC-AUC {f['roc_auc']} on the held-out test set"} for f in findings]
        if predictions and pred.label:
            predictions[0]["qualitativeRisk"] = {"text": pred.label}
        resource: dict[str, Any] = {
            "resourceType": "RiskAssessment", "id": f"risk-{pred.id}", "meta": _meta(), "status": "final",
            "subject": ref("Patient", p.mrn), "occurrenceDateTime": instant(pred.created_at),
            "method": {"text": f"{mv.model_name} v{mv.version} ({mv.algorithm})"},
            "basis": [ref("ImagingStudy", f"img-{study.id}")], "prediction": predictions,
            "note": [{"text": "Reading-order support from a statistical model: not a diagnosis and not a "
                              "report. Only findings that met the model card's publication bar are listed."}]}
        if study.admission_id:
            resource["encounter"] = ref("Encounter", f"adm-{study.admission_id}")
        return resource

    # ------------------------------------------------------------------ bundles
    def entry(self, resource: dict, mode: str) -> dict:
        return {"fullUrl": f"{self.base}/{resource['resourceType']}/{resource['id']}", "resource": resource,
                "search": {"mode": mode}}

    def searchset(self, matches: list[dict], includes: list[dict], self_url: str) -> dict:
        now = instant(datetime.now(UTC))
        return {"resourceType": "Bundle", "id": str(uuid.uuid4()), "meta": {"lastUpdated": now, **_meta()},
                "type": "searchset", "timestamp": now, "total": len(matches),
                "link": [{"relation": "self", "url": self_url}],
                "entry": [self.entry(r, "match") for r in matches] + [self.entry(r, "include") for r in includes]}

    def everything(self, p: Patient, self_url: str) -> dict:
        db = self.db
        resources: list[dict] = [*self.allergies(p), *self.blood_group(p)]
        resources += [self.encounter(a, p) for a in db.scalars(
            select(Admission).where(Admission.patient_id == p.id).order_by(Admission.admitted_at))]
        resources += [self.condition(d, p) for d in db.scalars(
            select(Diagnosis).where(Diagnosis.patient_id == p.id).order_by(Diagnosis.diagnosed_on, Diagnosis.id))]
        resources += [self.lab(lab, p) for lab in db.scalars(
            select(LabReport).where(LabReport.patient_id == p.id).order_by(LabReport.collected_at, LabReport.id))]
        resources += [self.observation_set(v, p) for v in db.scalars(
            select(VitalSigns).where(VitalSigns.patient_id == p.id).order_by(VitalSigns.recorded_at))]
        resources += [self.medication_request(rx, med, p) for rx, med in db.execute(
            select(Prescription, Medication).join(Medication).where(Prescription.patient_id == p.id)
            .order_by(Prescription.start_date, Prescription.id))]
        for r in db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == p.id)
                            .order_by(MedicalRecord.visit_date, MedicalRecord.id)):
            resources += self.document(r, p)
        resources += [self.appointment(ap, p) for ap in db.scalars(
            select(Appointment).where(Appointment.patient_id == p.id).order_by(Appointment.scheduled_start))]
        resources += [self.risk_assessment(pred, p) for pred in db.scalars(
            select(MLPrediction).where(MLPrediction.patient_id == p.id,
                                       MLPrediction.prediction_type == "readmission_30d")
            .order_by(MLPrediction.created_at))]
        for study in db.scalars(select(ImagingStudy).where(ImagingStudy.patient_id == p.id)
                                .order_by(ImagingStudy.acquired_at, ImagingStudy.id)).unique():
            resources.append(self.imaging_study(study, p))
            if study.triage is not None:
                resources.append(self.triage_assessment(study.triage, study, p))
            report = self.diagnostic_report(study, p)
            if report is not None:
                resources.append(report)
        patient = self.patient(p)
        return self.searchset([patient], resources + list(self.extra.values()), self_url)
