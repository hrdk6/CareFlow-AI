"""Static catalogs for the synthetic hospital. Every person and organisation here is fictional."""
from dataclasses import dataclass

DEPARTMENTS = [
    ("GM", "General Medicine", "Adult internal medicine, including diabetes and endocrine care"),
    ("CARD", "Cardiology", "Heart failure, arrhythmia and coronary disease"),
    ("NEUR", "Neurology", "Stroke, epilepsy and headache disorders"),
    ("ORTH", "Orthopedics", "Fractures, joint replacement and spine"),
    ("PED", "Pediatrics", "Care for patients under 18"),
    ("DERM", "Dermatology", "Skin conditions"),
    ("EM", "Emergency Medicine", "Emergency department"),
]

_WEEK = {"mon": [["09:00", "13:00"], ["14:00", "17:00"]], "tue": [["09:00", "13:00"], ["14:00", "17:00"]],
         "wed": [["09:00", "13:00"]], "thu": [["09:00", "13:00"], ["14:00", "17:00"]], "fri": [["09:00", "12:00"]]}
_SHIFT = {d: [["08:00", "20:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}

# staff_code, name, specialty, department, availability
DOCTORS = [
    ("D101", "Dr. Ananya Rao", "Endocrinology", "GM", _WEEK),
    ("D102", "Dr. Samuel Okoro", "Internal Medicine", "GM", _WEEK),
    ("D103", "Dr. Laura Chen", "Internal Medicine", "GM", _WEEK),
    ("D201", "Dr. Kwame Mensah", "Cardiology", "CARD", _WEEK),
    ("D202", "Dr. Elena Petrova", "Cardiology", "CARD", _WEEK),
    ("D301", "Dr. Arjun Iyer", "Neurology", "NEUR", _WEEK),
    ("D302", "Dr. Sofia Marin", "Neurology", "NEUR", _WEEK),
    ("D401", "Dr. Daniel Brooks", "Orthopedic Surgery", "ORTH", _WEEK),
    ("D402", "Dr. Hana Sato", "Orthopedic Surgery", "ORTH", _WEEK),
    ("D501", "Dr. Grace Adeyemi", "Pediatrics", "PED", _WEEK),
    ("D502", "Dr. Lucas Moreau", "Pediatrics", "PED", _WEEK),
    ("D601", "Dr. Priya Nair", "Dermatology", "DERM", _WEEK),
    ("D701", "Dr. Omar Haddad", "Emergency Medicine", "EM", _SHIFT),
    ("D702", "Dr. Julia Novak", "Emergency Medicine", "EM", _SHIFT),
]

# email, full name, role, doctor staff code, department code
USERS = [
    ("admin@careflow.demo", "Hardik", "ADMIN", None, None),
    ("dr.rao@careflow.demo", "Dr. Ananya Rao", "DOCTOR", "D101", "GM"),
    ("dr.mensah@careflow.demo", "Dr. Kwame Mensah", "DOCTOR", "D201", "CARD"),
    ("nurse.kim@careflow.demo", "Jiwoo Kim, RN", "NURSE", None, "GM"),
    ("reception@careflow.demo", "Sam Rivera", "RECEPTIONIST", None, None),
]


@dataclass(frozen=True)
class Med:
    name: str
    drug_class: str
    high_alert: bool = False
    route: str = "oral"


FORMULARY = [
    Med("metformin", "biguanide"), Med("glipizide", "sulfonylurea"), Med("sitagliptin", "dpp4_inhibitor"),
    Med("empagliflozin", "sglt2_inhibitor"), Med("liraglutide", "glp1_agonist", route="subcut"),
    Med("insulin glargine", "insulin", True, "subcut"), Med("insulin lispro", "insulin", True, "subcut"),
    Med("dextrose 10%", "iv_fluid", True, "iv"), Med("sodium chloride 0.9%", "iv_fluid", route="iv"),
    Med("lisinopril", "ace_inhibitor"), Med("losartan", "arb"), Med("amlodipine", "calcium_channel_blocker"),
    Med("hydrochlorothiazide", "thiazide"), Med("metoprolol succinate", "beta_blocker"),
    Med("furosemide", "loop_diuretic"), Med("spironolactone", "mra"), Med("atorvastatin", "statin"),
    Med("aspirin", "antiplatelet"), Med("clopidogrel", "antiplatelet"),
    Med("apixaban", "anticoagulant", True), Med("warfarin", "anticoagulant", True),
    Med("enoxaparin", "anticoagulant", True, "subcut"), Med("potassium chloride", "electrolyte", True),
    Med("omeprazole", "ppi"), Med("sertraline", "ssri"), Med("levothyroxine", "thyroid"),
    Med("levetiracetam", "anticonvulsant"), Med("sumatriptan", "triptan"), Med("gabapentin", "gabapentinoid"),
    Med("paracetamol", "analgesic"), Med("ibuprofen", "nsaid"), Med("morphine", "opioid", True),
    Med("salbutamol", "bronchodilator", route="inhaled"), Med("tiotropium", "bronchodilator", route="inhaled"),
    Med("budesonide", "inhaled_corticosteroid", route="inhaled"), Med("prednisone", "corticosteroid"),
    Med("ceftriaxone", "antibiotic", route="iv"), Med("azithromycin", "antibiotic"),
    Med("cefazolin", "antibiotic", route="iv"), Med("nitrofurantoin", "antibiotic"),
    Med("hydrocortisone 1% cream", "topical_corticosteroid", route="topical"),
    Med("calcipotriol ointment", "topical_vitamin_d", route="topical"),
]
DIABETES_CLASSES = {"biguanide", "sulfonylurea", "dpp4_inhibitor", "sglt2_inhibitor", "glp1_agonist", "insulin"}


@dataclass(frozen=True)
class Condition:
    code: str
    description: str
    category: str
    chronic: bool
    meds: tuple[tuple[str, str, str], ...] = ()  # (medication, dose, frequency) started at diagnosis


CONDITIONS = {c.code: c for c in [
    Condition("E11.9", "Type 2 diabetes mellitus without complications", "diabetes", True,
              (("metformin", "500 mg", "twice daily"),)),
    Condition("E11.65", "Type 2 diabetes mellitus with hyperglycemia", "diabetes", False),
    Condition("E11.649", "Type 2 diabetes mellitus with hypoglycemia without coma", "diabetes", False),
    Condition("I10", "Essential (primary) hypertension", "circulatory", True, (("lisinopril", "10 mg", "once daily"),)),
    Condition("E78.5", "Hyperlipidemia, unspecified", "other", True, (("atorvastatin", "20 mg", "once nightly"),)),
    Condition("N18.3", "Chronic kidney disease, stage 3", "genitourinary", True),
    Condition("I50.9", "Heart failure, unspecified", "circulatory", True,
              (("furosemide", "40 mg", "once daily"), ("metoprolol succinate", "50 mg", "once daily"),
               ("spironolactone", "25 mg", "once daily"))),
    Condition("I48.91", "Atrial fibrillation, unspecified", "circulatory", True,
              (("apixaban", "5 mg", "twice daily"), ("metoprolol succinate", "50 mg", "once daily"))),
    Condition("I25.10", "Atherosclerotic heart disease of native coronary artery", "circulatory", True,
              (("aspirin", "81 mg", "once daily"), ("atorvastatin", "40 mg", "once nightly"))),
    Condition("I20.0", "Unstable angina", "circulatory", False),
    Condition("K21.9", "Gastro-esophageal reflux disease without esophagitis", "digestive", True,
              (("omeprazole", "20 mg", "once daily"),)),
    Condition("F32.9", "Major depressive disorder, single episode", "other", True, (("sertraline", "50 mg", "once daily"),)),
    Condition("E03.9", "Hypothyroidism, unspecified", "other", True, (("levothyroxine", "75 mcg", "once daily"),)),
    Condition("J18.9", "Pneumonia, unspecified organism", "respiratory", False),
    Condition("N39.0", "Urinary tract infection, site not specified", "genitourinary", False),
    Condition("L03.90", "Cellulitis, unspecified", "other", False),
    Condition("E86.0", "Dehydration", "other", False),
    Condition("G40.909", "Epilepsy, unspecified, not intractable", "other", True,
              (("levetiracetam", "500 mg", "twice daily"),)),
    Condition("G43.909", "Migraine, unspecified", "other", True, (("sumatriptan", "50 mg", "as needed"),)),
    Condition("I63.9", "Cerebral infarction, unspecified", "circulatory", False),
    Condition("M17.11", "Primary osteoarthritis, right knee", "musculoskeletal", True,
              (("paracetamol", "1 g", "three times daily as needed"),)),
    Condition("M54.50", "Low back pain, unspecified", "musculoskeletal", True, (("gabapentin", "300 mg", "once nightly"),)),
    Condition("S72.001A", "Fracture of neck of right femur, initial encounter", "injury", False),
    Condition("J45.909", "Asthma, uncomplicated", "respiratory", True,
              (("salbutamol", "2 puffs", "as needed"), ("budesonide", "200 mcg", "twice daily"))),
    Condition("J45.901", "Asthma with acute exacerbation", "respiratory", False),
    Condition("L20.9", "Atopic dermatitis, unspecified", "other", True,
              (("hydrocortisone 1% cream", "thin layer", "twice daily"),)),
    Condition("L40.0", "Psoriasis vulgaris", "other", True, (("calcipotriol ointment", "thin layer", "once daily"),)),
    Condition("J44.9", "Chronic obstructive pulmonary disease, unspecified", "respiratory", True,
              (("tiotropium", "18 mcg", "once daily"), ("salbutamol", "2 puffs", "as needed"))),
    Condition("J44.1", "COPD with acute exacerbation", "respiratory", False),
]}


@dataclass(frozen=True)
class Lab:
    code: str
    name: str
    unit: str
    low: float | None
    high: float | None
    critical_low: float | None = None
    critical_high: float | None = None


LABS = {lab.code: lab for lab in [
    Lab("HBA1C", "Hemoglobin A1c", "%", 4.0, 5.6),
    Lab("GLU", "Glucose", "mg/dL", 70, 140, 54, 400),
    Lab("CREAT", "Creatinine", "mg/dL", 0.6, 1.2, None, 4.0),
    Lab("EGFR", "eGFR", "mL/min/1.73m2", 60, None, 15, None),
    Lab("K", "Potassium", "mmol/L", 3.5, 5.1, 3.0, 6.0),
    Lab("NA", "Sodium", "mmol/L", 135, 145, 125, 155),
    Lab("LDL", "LDL cholesterol", "mg/dL", None, 100),
    Lab("BNP", "B-type natriuretic peptide", "pg/mL", None, 100),
    Lab("INR", "INR", "ratio", 0.8, 1.2, None, 4.5),
    Lab("HGB", "Hemoglobin", "g/dL", 12.0, 16.5, 7.0, None),
    Lab("WBC", "White blood cell count", "10^9/L", 4.0, 11.0, 2.0, 30.0),
    Lab("CRP", "C-reactive protein", "mg/L", None, 5.0),
    Lab("TSH", "Thyroid stimulating hormone", "mIU/L", 0.4, 4.0),
    Lab("UACR", "Urine albumin-creatinine ratio", "mg/g", None, 30),
]}


@dataclass(frozen=True)
class AcuteEvent:
    code: str
    reason: str
    los: tuple[int, int]
    meds: tuple[tuple[str, str, str], ...]
    labs: tuple[str, ...] = ()
    department: str | None = None  # defaults to archetype department


ACUTE = {
    "hyperglycemia": AcuteEvent("E11.65", "Hyperglycemia with poor glycemic control", (3, 8),
                                (("insulin lispro", "sliding scale", "before meals"),
                                 ("sodium chloride 0.9%", "1 L", "over 8 hours")), ("HBA1C",)),
    "hypoglycemia": AcuteEvent("E11.649", "Symptomatic hypoglycemia", (1, 3),
                               (("dextrose 10%", "100 mL", "as needed"),), ("HBA1C",)),
    "pneumonia": AcuteEvent("J18.9", "Community-acquired pneumonia", (3, 9),
                            (("ceftriaxone", "1 g", "once daily"), ("azithromycin", "500 mg", "once daily")), ("CRP",)),
    "uti": AcuteEvent("N39.0", "Urinary tract infection with fever", (2, 6),
                      (("ceftriaxone", "1 g", "once daily"),), ("CRP",)),
    "cellulitis": AcuteEvent("L03.90", "Cellulitis of the lower limb", (3, 8),
                             (("cefazolin", "2 g", "every 8 hours"),), ("CRP",)),
    "hf_exacerbation": AcuteEvent("I50.9", "Acute decompensated heart failure", (4, 10),
                                  (("furosemide", "40 mg IV", "twice daily"),
                                   ("potassium chloride", "20 mmol", "once daily")), ("BNP",), "CARD"),
    "af_rvr": AcuteEvent("I48.91", "Atrial fibrillation with rapid ventricular response", (2, 5),
                         (("metoprolol succinate", "50 mg", "twice daily"),), ("BNP",), "CARD"),
    "angina": AcuteEvent("I20.0", "Unstable angina", (2, 6),
                         (("aspirin", "300 mg", "loading dose then 81 mg daily"), ("clopidogrel", "75 mg", "once daily"),
                          ("atorvastatin", "80 mg", "once nightly")), (), "CARD"),
    "stroke": AcuteEvent("I63.9", "Acute ischemic stroke", (4, 12),
                         (("aspirin", "300 mg", "once daily"), ("atorvastatin", "80 mg", "once nightly")), (), "NEUR"),
    "seizure": AcuteEvent("G40.909", "Breakthrough seizure", (1, 4),
                          (("levetiracetam", "750 mg", "twice daily"),), (), "NEUR"),
    "hip_fracture": AcuteEvent("S72.001A", "Fall with fracture of the right femoral neck", (4, 10),
                               (("morphine", "2.5 mg", "every 4 hours as needed"),), ("HGB",), "ORTH"),
    "knee_replacement": AcuteEvent("M17.11", "Elective right total knee arthroplasty", (2, 5),
                                   (("cefazolin", "2 g", "every 8 hours for 24 hours"),), (), "ORTH"),
    "asthma": AcuteEvent("J45.901", "Acute asthma exacerbation", (1, 3),
                         (("salbutamol", "5 mg nebulised", "every 4 hours"), ("prednisone", "1 mg/kg", "once daily")),
                         (), "PED"),
    "copd": AcuteEvent("J44.1", "COPD with acute exacerbation", (3, 8),
                       (("prednisone", "40 mg", "once daily"), ("salbutamol", "5 mg nebulised", "every 4 hours"),
                        ("azithromycin", "500 mg", "once daily")), ("CRP",)),
}


@dataclass(frozen=True)
class Archetype:
    weight: float
    age: tuple[int, int]
    department: str
    doctors: tuple[str, ...]
    chronic: tuple[tuple[str, float], ...]
    acute: tuple[str, ...]
    admit_rate: float  # expected admissions per year
    ed_rate: float


ARCHETYPES = {
    "diabetes": Archetype(0.40, (40, 88), "GM", ("D101", "D102", "D103"),
                          (("E11.9", 1.0), ("I10", 0.7), ("E78.5", 0.6), ("N18.3", 0.3), ("I50.9", 0.12),
                           ("K21.9", 0.2), ("F32.9", 0.15), ("E03.9", 0.1)),
                          ("hyperglycemia", "hypoglycemia", "pneumonia", "uti", "cellulitis", "hf_exacerbation"),
                          0.55, 0.45),
    "cardiac": Archetype(0.20, (45, 90), "CARD", ("D201", "D202"),
                         (("I10", 0.9), ("I50.9", 0.45), ("I48.91", 0.35), ("I25.10", 0.5), ("E78.5", 0.6),
                          ("E11.9", 0.25), ("N18.3", 0.15)),
                         ("hf_exacerbation", "af_rvr", "angina", "pneumonia"), 0.5, 0.35),
    "neuro": Archetype(0.10, (25, 85), "NEUR", ("D301", "D302"),
                       (("G40.909", 0.45), ("G43.909", 0.4), ("I10", 0.4), ("E78.5", 0.3)),
                       ("stroke", "seizure"), 0.3, 0.3),
    "ortho": Archetype(0.10, (35, 90), "ORTH", ("D401", "D402"),
                       (("M17.11", 0.6), ("M54.50", 0.4), ("I10", 0.4), ("E11.9", 0.2)),
                       ("hip_fracture", "knee_replacement"), 0.25, 0.2),
    "pediatric": Archetype(0.08, (2, 17), "PED", ("D501", "D502"),
                           (("J45.909", 0.65), ("L20.9", 0.4)), ("asthma", "pneumonia"), 0.2, 0.4),
    "derm": Archetype(0.07, (18, 75), "DERM", ("D601",),
                      (("L40.0", 0.6), ("L20.9", 0.4), ("I10", 0.2)), ("cellulitis",), 0.05, 0.05),
    "respiratory": Archetype(0.05, (50, 88), "GM", ("D102", "D103"),
                             (("J44.9", 1.0), ("I10", 0.5), ("E11.9", 0.3)), ("copd", "pneumonia"), 0.6, 0.5),
}

# Fictional Indian patient identities. List lengths are kept stable: the seeded random stream (and therefore
# every generated history, admission and prediction) depends on them.
FIRST_F = ["Aarti", "Anjali", "Asha", "Bhavna", "Deepa", "Divya", "Gauri", "Geeta", "Kavita", "Lakshmi",
           "Madhuri", "Meena", "Neha", "Nirmala", "Pooja", "Priyanka", "Radha", "Rekha", "Revathi", "Sangeeta",
           "Shalini", "Shobha", "Smita", "Sneha", "Swati", "Uma", "Usha", "Vandana", "Vidya", "Yamini"]
FIRST_M = ["Aakash", "Abhishek", "Ajay", "Amit", "Anil", "Arvind", "Ashok", "Deepak", "Ganesh", "Harish",
           "Imran", "Karthik", "Mahesh", "Manoj", "Mohan", "Nitin", "Pradeep", "Rahul", "Rajesh", "Ramesh",
           "Ravi", "Sachin", "Sandeep", "Sanjay", "Suresh", "Tushar", "Varun", "Vijay", "Vikram", "Yusuf"]
LAST = ["Agarwal", "Bhat", "Banerjee", "Chatterjee", "Chavan", "Das", "Desai", "Deshmukh", "Dubey", "Fernandes",
        "Gupta", "Hegde", "Iyer", "Jadhav", "Jain", "Joshi", "Kamath", "Kapoor", "Khan", "Kulkarni",
        "Kumar", "Menon", "Mehta", "Mishra", "Mukherjee", "Naidu", "Nair", "Pandey", "Patel", "Patil",
        "Pillai", "Rao", "Reddy", "Saxena", "Shah", "Sharma", "Shetty", "Singh", "Sinha", "Srivastava",
        "Thakur", "Trivedi", "Verma", "Yadav", "Bose", "Gaikwad", "Kaur", "Qureshi"]
STREETS = ["MG Road, Pune 411001", "Baner Road, Pune 411045", "Shivaji Nagar, Pune 411005", "Kothrud, Pune 411038",
           "Andheri East, Mumbai 400069", "Dadar West, Mumbai 400028", "Indiranagar, Bengaluru 560038",
           "Jayanagar, Bengaluru 560041", "Banjara Hills, Hyderabad 500034", "Anna Nagar, Chennai 600040"]
ALLERGIES = [("Penicillin", "Rash", "moderate"), ("Sulfonamides", "Hives", "mild"), ("Latex", "Contact dermatitis", "mild"),
             ("Iodinated contrast", "Anaphylaxis", "severe"), ("Codeine", "Nausea", "mild"), ("Peanuts", "Anaphylaxis", "severe")]
BLOOD_TYPES = ["O+", "O+", "A+", "A+", "B+", "AB+", "O-", "A-"]
LANGUAGES = ["English"] * 5 + ["Hindi"] * 3 + ["Marathi", "Tamil", "Kannada", "Telugu"]
