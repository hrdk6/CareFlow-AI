"""Deterministic query router.

Most hospital questions fall into a small set of recognisable shapes, so routing is rule-based:
it is instant, free, predictable, testable and cannot be prompt-injected. Each matched intent maps
to a fixed tool plan. Only when NO rule matches (confidence "low") does the orchestrator hand the
question to the LLM with tool calling, if an LLM provider is configured.

Capabilities: SQL (structured records), RAG (documents), ML (predictions), SIMILARITY, LLM (synthesis).
"""
import re
from dataclasses import dataclass, field
from enum import StrEnum


class Intent(StrEnum):
    PATIENT_SUMMARY = "patient_summary"
    TREATMENT_CHANGES = "treatment_changes"
    PATIENT_FACT = "patient_fact"
    APPOINTMENTS = "appointments"
    DOCUMENT_QA = "document_qa"
    READMISSION = "readmission_risk"
    LENGTH_OF_STAY = "length_of_stay"
    EXPLAIN_PREDICTION = "explain_prediction"
    GUIDELINE_COMPARISON = "guideline_comparison"
    SIMILAR_PATIENTS = "similar_patients"
    GENERAL = "general"


CAPABILITIES = {
    Intent.PATIENT_SUMMARY: ["SQL", "LLM"],
    Intent.TREATMENT_CHANGES: ["SQL", "LLM"],
    Intent.PATIENT_FACT: ["SQL"],
    Intent.APPOINTMENTS: ["SQL"],
    Intent.DOCUMENT_QA: ["RAG", "LLM"],
    Intent.READMISSION: ["SQL", "ML"],
    Intent.LENGTH_OF_STAY: ["SQL", "ML"],
    Intent.EXPLAIN_PREDICTION: ["SQL", "ML", "LLM"],
    Intent.GUIDELINE_COMPARISON: ["SQL", "RAG", "LLM"],
    Intent.SIMILAR_PATIENTS: ["SIMILARITY", "SQL", "LLM"],
    Intent.GENERAL: ["LLM"],
}

MRN_RE = re.compile(r"\bP\d{4}\b", re.I)
DOCTOR_RE = re.compile(r"\bDr\.?\s+([A-Z][a-zA-Z'\-]+)")
PATIENT_REF_RE = re.compile(r"\b(this|the|my|current)\s+patient\b|\b(her|his|their)\b|\bpatient'?s\b", re.I)

_RULES: list[tuple[Intent, re.Pattern]] = [
    (Intent.SIMILAR_PATIENTS, re.compile(r"\bsimilar (historical )?patients?\b|\bpatients? (like|similar to)\b|"
                                         r"\bcomparable patients?\b|\bsimilar cases?\b", re.I)),
    (Intent.GUIDELINE_COMPARISON, re.compile(
        r"\b(compare|comparison|consistent|in line|aligned?|adher\w*|deviat\w*|follow\w*|meet\w*)\b.*"
        r"\b(guideline|policy|protocol|standard|recommendation)s?\b|"
        r"\b(guideline|protocol)s?\b.*\b(compare|versus|vs\.?)\b", re.I)),
    (Intent.EXPLAIN_PREDICTION, re.compile(
        r"\bwhy\b.*\b(risk|readmi\w*|predict\w*|score|flag\w*|length of stay)\b|"
        r"\b(explain|factors?|drivers?|contribut\w*)\b.*\b(risk|readmi\w*|predict\w*)\b", re.I)),
    (Intent.READMISSION, re.compile(r"\breadmi\w*\b|\b(re-?admission|readmit)\b|\brisk of (coming back|return)", re.I)),
    (Intent.LENGTH_OF_STAY, re.compile(r"\blength of stay\b|\bLOS\b|\bhow long\b.*\b(stay|admit\w*|hospital)\b|"
                                       r"\bexpected (discharge|stay)\b", re.I)),
    (Intent.TREATMENT_CHANGES, re.compile(r"\b(treatment|medication|medicine|drug|therapy|dose|dosing)\s+changes?\b|"
                                          r"\bwhat changed\b|\bchanges? (in|to) (her|his|their|the) (treatment|medications?)\b|"
                                          r"\b(major|recent) changes\b", re.I)),
    (Intent.PATIENT_SUMMARY, re.compile(r"\bsummar\w*\b|\b(medical |clinical )?history\b|\boverview\b|\btimeline\b|"
                                        r"\bwhat happened\b|\bbrief me\b|\bcatch me up\b", re.I)),
    (Intent.APPOINTMENTS, re.compile(r"\bappointments?\b|\bschedul\w*\b|\bclinic list\b|\bbooked\b|\bvisits? (today|tomorrow)\b",
                                     re.I)),
    (Intent.DOCUMENT_QA, re.compile(r"\b(guidelines?|polic(y|ies)|protocols?|procedures?|sop|according to|"
                                    r"our (hospital|rules?)|what does (our|the) .* say|recommend\w*|"
                                    r"high-alert|critical values?|visiting hours|wi-?fi|hand hygiene|triage|news2)\b",
                                    re.I)),
    (Intent.PATIENT_FACT, re.compile(r"\b(age|old|born|date of birth|dob|allerg\w*|medications?|meds|prescri\w*|"
                                     r"labs?|lab results?|hba1c|a1c|egfr|creatinine|glucose|potassium|ldl|bnp|inr|"
                                     r"diagnos\w*|conditions?|problems?|blood type|contact|phone|emergency contact|"
                                     r"admissions?|admitted|discharged?|status|doctor|attending|care team)\b", re.I)),
    (Intent.GENERAL, re.compile(r"\b(what can you do|help|how do i use|who are you|capabilit\w*)\b", re.I)),
]

# Intents whose plan requires a patient.
PATIENT_INTENTS = {Intent.PATIENT_SUMMARY, Intent.TREATMENT_CHANGES, Intent.PATIENT_FACT, Intent.READMISSION,
                   Intent.LENGTH_OF_STAY, Intent.EXPLAIN_PREDICTION, Intent.GUIDELINE_COMPARISON,
                   Intent.SIMILAR_PATIENTS}

# Requests for autonomous clinical decisions - answered with information, never recommendations.
DECISION_RE = re.compile(r"\b(what|which) (dose|drug|medication|treatment) should (i|we)\b|\bshould (i|we) "
                         r"(prescribe|give|start|stop|increase|decrease|discharge)\b|\bdiagnose (this|the|my)\b|"
                         r"\bwhat is (the|her|his) diagnosis\b", re.I)


@dataclass
class RoutePlan:
    intents: list[Intent]
    capabilities: list[str]
    confidence: str  # high | low
    mrn: str | None = None
    doctor_name: str | None = None
    refers_to_patient: bool = False
    decision_request: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def needs_patient(self) -> bool:
        return any(i in PATIENT_INTENTS for i in self.intents)

    @property
    def label(self) -> str:
        return " + ".join(self.capabilities)


def route(query: str, *, has_patient_context: bool = False) -> RoutePlan:
    q = query.strip()
    mrn_match = MRN_RE.search(q)
    doctor = DOCTOR_RE.search(q)
    refers = bool(PATIENT_REF_RE.search(q)) or bool(mrn_match)
    intents: list[Intent] = [intent for intent, pattern in _RULES if pattern.search(q)]

    # Resolve overlaps: more specific composite intents subsume their parts.
    if Intent.EXPLAIN_PREDICTION in intents:
        intents = [i for i in intents if i not in (Intent.READMISSION, Intent.PATIENT_FACT)]
    if Intent.GUIDELINE_COMPARISON in intents:
        intents = [i for i in intents if i not in (Intent.DOCUMENT_QA, Intent.PATIENT_FACT, Intent.TREATMENT_CHANGES)]
    if Intent.SIMILAR_PATIENTS in intents:
        intents = [i for i in intents if i not in (Intent.PATIENT_FACT,)]
        if Intent.PATIENT_SUMMARY in intents:  # "find similar patients and summarise" -> summary of the cohort
            intents.remove(Intent.PATIENT_SUMMARY)
    if Intent.TREATMENT_CHANGES in intents and Intent.PATIENT_SUMMARY in intents:
        intents.remove(Intent.PATIENT_SUMMARY)
    if Intent.PATIENT_SUMMARY in intents or Intent.TREATMENT_CHANGES in intents:
        intents = [i for i in intents if i != Intent.PATIENT_FACT]
    if Intent.APPOINTMENTS in intents:
        intents = [i for i in intents if i != Intent.PATIENT_FACT]
    if Intent.DOCUMENT_QA in intents and Intent.PATIENT_FACT in intents and not (refers or has_patient_context):
        intents.remove(Intent.PATIENT_FACT)  # "which medications are high-alert?" is a policy question
    if Intent.DOCUMENT_QA in intents and Intent.PATIENT_FACT in intents and not refers:
        intents.remove(Intent.PATIENT_FACT)
    if Intent.GENERAL in intents and len(intents) > 1:
        intents.remove(Intent.GENERAL)
    if Intent.PATIENT_FACT in intents and not (refers or has_patient_context):
        intents.remove(Intent.PATIENT_FACT)

    confidence = "high" if intents else "low"
    if not intents:
        # Unrecognised: a patient-scoped question defaults to the record, anything else to the knowledge base.
        intents = [Intent.PATIENT_FACT] if refers or has_patient_context else [Intent.DOCUMENT_QA]
    capabilities: list[str] = []
    for intent in intents:
        for cap in CAPABILITIES[intent]:
            if cap not in capabilities:
                capabilities.append(cap)
    if "LLM" in capabilities:  # synthesis always happens last
        capabilities = [c for c in capabilities if c != "LLM"] + ["LLM"]
    return RoutePlan(intents=intents, capabilities=capabilities, confidence=confidence,
                     mrn=mrn_match.group(0).upper() if mrn_match else None,
                     doctor_name=doctor.group(1) if doctor else None, refers_to_patient=refers,
                     decision_request=bool(DECISION_RE.search(q)))
