"""FHIR R4 export: valid resources, resolvable references, standard terminologies, the same access policy."""
import base64
import importlib
from collections import Counter

from sqlalchemy import select

from app.interop.fhir import ICD10CM, LOINC, MRN_SYSTEM, UCUM, FhirExporter
from app.models import Admission, AuditLog
from app.schemas.discharge import DischargeSignIn
from app.services.discharge import DischargeCopilot


def _validate(resource: dict) -> None:
    """Validate against the fhir.resources models (FHIR R4B: identical to R4 for every resource exported here)."""
    rt = resource["resourceType"]
    model = getattr(importlib.import_module(f"fhir.resources.R4B.{rt.lower()}"), rt)
    model.model_validate(resource)


def _references(node, found: list[str]) -> list[str]:
    if isinstance(node, dict):
        if isinstance(node.get("reference"), str):
            found.append(node["reference"])
        for value in node.values():
            _references(value, found)
    elif isinstance(node, list):
        for value in node:
            _references(value, found)
    return found


def _everything(client, auth, mrn="P1024", role="doctor"):
    return client.get(f"/fhir/Patient/{mrn}/$everything", headers=auth(role))


def test_everything_is_a_valid_bundle_with_resolvable_references(client, auth):
    r = _everything(client, auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/fhir+json")
    bundle = r.json()
    _validate(bundle)
    entries = [e["resource"] for e in bundle["entry"]]
    for resource in entries:
        _validate(resource)
        assert resource["meta"]["security"][0]["code"] == "HTEST"  # every resource is marked as test data
    ids = {f"{x['resourceType']}/{x['id']}" for x in entries}
    assert len(ids) == len(entries)  # no duplicates
    dangling = [ref for ref in _references(entries, []) if ref not in ids]
    assert not dangling, dangling
    assert bundle["type"] == "searchset" and bundle["total"] == 1
    assert [e["search"]["mode"] for e in bundle["entry"]].count("match") == 1

    counts = Counter(x["resourceType"] for x in entries)
    assert counts["Patient"] == 1 and counts["AllergyIntolerance"] == 2 and counts["Encounter"] >= 4  # P1024's stays
    assert counts["Observation"] > 50 and counts["MedicationRequest"] > 10 and counts["DocumentReference"] > 5


def test_resources_use_standard_terminologies(client, auth):
    entries = [e["resource"] for e in _everything(client, auth).json()["entry"]]
    patient = next(x for x in entries if x["resourceType"] == "Patient")
    assert patient["id"] == "P1024" and patient["identifier"][0]["system"] == MRN_SYSTEM
    assert patient["gender"] == "female" and patient["communication"][0]["language"]["coding"][0]["code"] == "mr"

    conditions = [x for x in entries if x["resourceType"] == "Condition"]
    assert any(c["code"]["coding"][0] == {"system": ICD10CM, "code": "E11.9",
                                          "display": "Type 2 diabetes mellitus without complications"} for c in conditions)
    a1c = next(x for x in entries if x["resourceType"] == "Observation" and x["code"]["coding"][0]["code"] == "4548-4")
    assert a1c["code"]["coding"][0]["system"] == LOINC
    assert a1c["valueQuantity"]["system"] == UCUM and a1c["valueQuantity"]["code"] == "%"
    assert a1c["interpretation"][0]["coding"][0]["code"] in ("N", "H")
    metformin = next(x for x in entries if x["resourceType"] == "MedicationRequest"
                     and x["medicationCodeableConcept"]["text"] == "metformin")
    assert metformin["medicationCodeableConcept"]["coding"][0] == {"system": "http://www.whocc.no/atc", "code": "A10BA02"}
    assert metformin["dosageInstruction"][0]["route"]["coding"][0]["code"] == "26643006"  # SNOMED CT oral route
    encounter = next(x for x in entries if x["resourceType"] == "Encounter")
    assert encounter["class"]["code"] == "IMP" and encounter["serviceProvider"]["reference"].startswith("Organization/")
    note = next(x for x in entries if x["resourceType"] == "DocumentReference"
                and x["type"]["coding"][0]["code"] == "18842-5")  # LOINC discharge summary
    assert "Chief complaint" in base64.b64decode(note["content"][0]["attachment"]["data"]).decode()
    risk = [x for x in entries if x["resourceType"] == "RiskAssessment"]
    assert all(0 <= x["prediction"][0]["probabilityDecimal"] <= 1 for x in risk)


def test_export_follows_the_access_policy(client, auth, restricted_patient, db):
    assert client.get("/fhir/Patient/P1024", headers=auth("reception")).status_code == 200  # demographics only
    denied = _everything(client, auth, role="reception")
    assert denied.status_code == 403 and denied.json()["resourceType"] == "OperationOutcome"
    assert denied.json()["issue"][0]["code"] == "forbidden"
    for mrn, role in ((restricted_patient.mrn, "doctor"), ("P1024", "cardio"), ("P9999", "doctor")):
        missing = _everything(client, auth, mrn=mrn, role=role)
        assert missing.status_code == 404 and missing.json()["issue"][0]["code"] == "not-found"
    anonymous = client.get("/fhir/Patient/P1024")
    assert anonymous.status_code == 401 and anonymous.json()["issue"][0]["code"] == "login"
    _everything(client, auth)
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "fhir.export").order_by(AuditLog.id.desc()).limit(1))
    assert audit.details["resources"]["Patient"] == 1  # counts only, never content


def test_search_and_capability_statement(client, auth, restricted_patient):
    found = client.get(f"/fhir/Patient?identifier={MRN_SYSTEM}|P1024", headers=auth("doctor")).json()
    _validate(found)
    assert found["total"] == 1 and found["entry"][0]["resource"]["id"] == "P1024"
    assert client.get("/fhir/Patient?identifier=urn:other|P1024", headers=auth("doctor")).json()["total"] == 0
    hidden = client.get(f"/fhir/Patient?identifier={restricted_patient.mrn}", headers=auth("doctor")).json()
    assert hidden["total"] == 0  # outside the caller's care: not found, like the rest of the API
    capability = client.get("/fhir/metadata").json()  # public, as FHIR servers' metadata is
    _validate(capability)
    assert capability["fhirVersion"] == "4.0.1"
    assert capability["rest"][0]["resource"][0]["operation"][0]["name"] == "everything"


def test_a_signed_co_pilot_summary_is_exported_with_provenance(db, users, demo_patient):
    adm = db.scalar(select(Admission).where(Admission.patient_id == demo_patient.id)
                    .order_by(Admission.admitted_at.desc()).limit(1))
    copilot = DischargeCopilot(db, users["doctor"])  # template drafting: no language model in tests
    d = copilot.draft(adm.id)
    record = copilot.sign(adm.id, DischargeSignIn(draft_id=d.draft_id, presenting_problem=d.sections[0].text,
                                                  hospital_course=d.sections[1].text,
                                                  follow_up_plan=d.follow_up_plan)).record
    bundle = FhirExporter(db, "https://example.test/fhir").everything(demo_patient, "https://example.test/x")
    resources = {f"{e['resource']['resourceType']}/{e['resource']['id']}": e["resource"] for e in bundle["entry"]}
    provenance = resources[f"Provenance/prov-doc-{record.id}"]
    _validate(provenance)
    assert provenance["target"] == [{"reference": f"DocumentReference/doc-{record.id}"}]
    roles = {a["type"]["coding"][0]["code"]: a["who"]["reference"] for a in provenance["agent"]}
    assert roles["author"] == "Practitioner/D101" and roles["assembler"] in resources
    _validate(resources[roles["assembler"]])


# Required bindings from the FHIR R4 specification. fhir.resources checks structure and cardinality but not
# terminology bindings, so the codes this export emits for required-binding elements are checked here.
REQUIRED = {
    ("Observation", "status"): {"registered", "preliminary", "final", "amended", "corrected", "cancelled",
                                "entered-in-error", "unknown"},
    ("Encounter", "status"): {"planned", "arrived", "triaged", "in-progress", "onleave", "finished", "cancelled",
                              "entered-in-error", "unknown"},
    ("MedicationRequest", "status"): {"active", "on-hold", "cancelled", "completed", "entered-in-error", "stopped",
                                      "draft", "unknown"},
    ("MedicationRequest", "intent"): {"proposal", "plan", "order", "original-order", "reflex-order", "filler-order",
                                      "instance-order", "option"},
    ("Appointment", "status"): {"proposed", "pending", "booked", "arrived", "fulfilled", "cancelled", "noshow",
                                "entered-in-error", "checked-in", "waitlist"},
    ("AllergyIntolerance", "type"): {"allergy", "intolerance"},
    ("AllergyIntolerance", "criticality"): {"low", "high", "unable-to-assess"},
    ("DocumentReference", "status"): {"current", "superseded", "entered-in-error"},
    ("DocumentReference", "docStatus"): {"preliminary", "final", "amended", "entered-in-error"},
    ("RiskAssessment", "status"): {"registered", "preliminary", "final", "amended", "corrected", "cancelled",
                                   "entered-in-error", "unknown"},
    ("Patient", "gender"): {"male", "female", "other", "unknown"},
}
CLINICAL_STATUS = {"active", "recurrence", "relapse", "inactive", "remission", "resolved"}


def test_required_code_bindings(client, auth):
    bundle = _everything(client, auth).json()
    assert {e["search"]["mode"] for e in bundle["entry"]} <= {"match", "include", "outcome"}
    for e in bundle["entry"]:
        r = e["resource"]
        for (rt, element), allowed in REQUIRED.items():
            if r["resourceType"] == rt and element in r:
                assert r[element] in allowed, (rt, element, r[element])
        if r["resourceType"] == "AllergyIntolerance":
            assert set(r["category"]) <= {"food", "medication", "environment", "biologic"}
            assert r["reaction"][0]["severity"] in {"mild", "moderate", "severe"}
        if r["resourceType"] == "Condition":
            assert r["clinicalStatus"]["coding"][0]["code"] in CLINICAL_STATUS
        if r["resourceType"] == "Appointment":
            assert {p["status"] for p in r["participant"]} <= {"accepted", "declined", "tentative", "needs-action"}
