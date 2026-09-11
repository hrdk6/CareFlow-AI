"""Deterministic synthetic hospital generator.

Patients are simulated chronologically (visits -> labs -> medication changes -> admissions ->
discharges) so that histories are internally consistent: a rising HbA1c leads to treatment
escalation, falling eGFR leads to a metformin dose reduction, admissions produce inpatient labs,
orders and discharge summaries, some discharges are followed by 30-day readmissions.

Everything generated here is FICTIONAL and flagged is_synthetic=True.
"""
import math
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.auth.rbac import PERMISSION_DESCRIPTIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.core.security import hash_password
from app.models import (
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
    Permission,
    Prescription,
    Role,
    User,
)
from app.seed import catalog as C

DEMO_MRN = "P1024"


def at(d: date, hour: int = 9, minute: int = 0) -> datetime:
    return datetime.combine(d, time(hour, minute), tzinfo=UTC)


@dataclass
class ClinicalState:
    a1c: float | None
    egfr: float
    ldl: float
    bnp: float
    a1c_drift: float
    egfr_drift: float


@dataclass
class PatientCtx:
    patient: Patient
    archetype: str
    doctor: Doctor
    conditions: set[str]
    state: ClinicalState
    frailty: float
    active_rx: dict[str, Prescription] = field(default_factory=dict)
    last_ldl: date | None = None
    last_uacr: date | None = None


class HospitalGenerator:
    def __init__(self, db: Session, *, seed: int = 7, n_patients: int = 240, anchor: date | None = None,
                 demo_password: str):
        self.db = db
        self.rng = random.Random(seed)
        self.n_patients = n_patients
        self.anchor = anchor or date.today()
        self.demo_password = demo_password
        self.departments: dict[str, Department] = {}
        self.doctors: dict[str, Doctor] = {}
        self.meds: dict[str, Medication] = {}
        self.users: dict[str, User] = {}
        self.taken_slots: set[tuple[int, datetime]] = set()
        self.assignments: set[tuple[int, int]] = set()

    # ================================================================== reference data
    def run(self) -> dict:
        self._roles()
        self._departments()
        self._doctors()
        self._users()
        self._formulary()
        self.db.flush()
        for i in range(self.n_patients):
            mrn = f"P{1001 + i}"
            if mrn == DEMO_MRN:
                self._demo_patient()
            else:
                self._random_patient(mrn)
        self._nurse_assignments()
        self.db.flush()
        return {"patients": self.n_patients, "doctors": len(self.doctors), "users": len(self.users)}

    def _roles(self) -> None:
        perms = {p: Permission(code=p.value, description=PERMISSION_DESCRIPTIONS[p]) for p in PERMISSION_DESCRIPTIONS}
        self.db.add_all(perms.values())
        self.roles = {}
        for role, granted in ROLE_PERMISSIONS.items():
            r = Role(name=role.value, description=ROLE_DESCRIPTIONS[role], permissions=[perms[p] for p in granted])
            self.db.add(r)
            self.roles[role.value] = r

    def _departments(self) -> None:
        for code, name, desc in C.DEPARTMENTS:
            d = Department(code=code, name=name, description=desc)
            self.db.add(d)
            self.departments[code] = d
        self.db.flush()

    def _doctors(self) -> None:
        for code, name, specialty, dept, availability in C.DOCTORS:
            handle = name.split()[-1].lower()
            doc = Doctor(staff_code=code, full_name=name, specialty=specialty,
                         department_id=self.departments[dept].id, email=f"{handle}.{code.lower()}@careflow.demo",
                         phone=f"+1-555-01{code[1:]}", availability=availability)
            self.db.add(doc)
            self.doctors[code] = doc
        self.db.flush()

    def _users(self) -> None:
        pw = hash_password(self.demo_password)
        for email, name, role, doctor_code, dept in C.USERS:
            u = User(email=email, full_name=name, password_hash=pw, role=self.roles[role],
                     doctor_id=self.doctors[doctor_code].id if doctor_code else None,
                     department_id=self.departments[dept].id if dept else None)
            self.db.add(u)
            self.users[email] = u
        self.db.flush()
        self.user_by_doctor = {u.doctor_id: u for u in self.users.values() if u.doctor_id}

    def _formulary(self) -> None:
        for m in C.FORMULARY:
            med = Medication(name=m.name, drug_class=m.drug_class, is_high_alert=m.high_alert, default_route=m.route)
            self.db.add(med)
            self.meds[m.name] = med

    # ================================================================== primitives
    def _poisson(self, lam: float) -> int:
        limit, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.rng.random()
            if p <= limit:
                return k
            k += 1

    def _weekday(self, d: date) -> date:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    def _assign(self, patient_id: int, user: User | None, care_role: str) -> None:
        if user is None or (patient_id, user.id) in self.assignments:
            return
        self.assignments.add((patient_id, user.id))
        self.db.add(CareAssignment(patient_id=patient_id, user_id=user.id, care_role=care_role))

    def _diagnosis(self, ctx: PatientCtx, code: str, on: date, *, admission: Admission | None = None,
                   primary: bool = False, status: str | None = None) -> Diagnosis:
        cond = C.CONDITIONS[code]
        dx = Diagnosis(patient_id=ctx.patient.id, icd10_code=code, description=cond.description,
                       category=cond.category, is_chronic=cond.chronic, is_primary=primary,
                       status=status or ("active" if cond.chronic else "resolved"), diagnosed_on=on,
                       admission_id=admission.id if admission else None)
        self.db.add(dx)
        return dx

    def _rx(self, ctx: PatientCtx, med: str, dose: str, freq: str, start: date, doctor: Doctor, *,
            admission: Admission | None = None, end: date | None = None, status: str = "active",
            reason: str | None = None, instructions: str | None = None) -> Prescription:
        m = self.meds[med]
        rx = Prescription(patient_id=ctx.patient.id, medication_id=m.id, doctor_id=doctor.id,
                          admission_id=admission.id if admission else None, dosage=dose, frequency=freq,
                          route=m.default_route, start_date=start, end_date=end, status=status,
                          change_reason=reason, instructions=instructions,
                          duration_days=(end - start).days + 1 if end else None)
        self.db.add(rx)
        if admission is None and status == "active":
            ctx.active_rx[med] = rx
        return rx

    def _rx_change(self, ctx: PatientCtx, med: str, dose: str, freq: str, on: date, reason: str,
                   doctor: Doctor | None = None) -> None:
        old = ctx.active_rx.pop(med, None)
        if old is not None:
            old.status, old.end_date = "discontinued", on
        self._rx(ctx, med, dose, freq, on, doctor or ctx.doctor, reason=reason)

    def _rx_stop(self, ctx: PatientCtx, med: str, on: date, reason: str) -> None:
        old = ctx.active_rx.pop(med, None)
        if old is not None:
            old.status, old.end_date, old.change_reason = "discontinued", on, reason

    def _lab_value(self, ctx: PatientCtx, code: str, *, acute: str | None = None, day: int = 0) -> float:
        r, s = self.rng, ctx.state
        female = ctx.patient.sex == "F"
        if code == "HBA1C":
            return round(s.a1c if s.a1c else r.gauss(5.3, 0.25), 1)
        if code == "GLU":
            if acute == "hyperglycemia":
                return round(max(160, r.gauss(430 - day * 55, 30)))
            if acute == "hypoglycemia" and day == 0:
                return round(r.uniform(38, 52))
            base = 95 + ((s.a1c or 5.3) - 5.3) * 30
            return round(max(60, r.gauss(base, 18)))
        if code == "EGFR":
            return round(max(8, r.gauss(s.egfr, 2.5)))
        if code == "CREAT":
            return round(max(0.4, (0.95 if not female else 0.8) * (90 / max(s.egfr, 8)) ** 0.9 + r.gauss(0, 0.05)), 2)
        if code == "K":
            return round(r.gauss(4.7 if s.egfr < 45 else 4.3, 0.35), 1)
        if code == "NA":
            return round(r.gauss(133 if acute == "hyperglycemia" and day == 0 else 139, 2.2))
        if code == "LDL":
            return round(r.gauss(s.ldl, 10))
        if code == "BNP":
            return round(max(10, r.gauss(s.bnp * (2.5 if acute == "hf_exacerbation" else 1), s.bnp * 0.15)))
        if code == "INR":
            return round(r.uniform(2.0, 3.3) if "warfarin" in ctx.active_rx else r.gauss(1.0, 0.08), 1)
        if code == "HGB":
            return round(r.gauss(12.6 if female else 13.8, 1.0) - (1.8 if acute == "hip_fracture" else 0), 1)
        if code == "WBC":
            infected = acute in {"pneumonia", "uti", "cellulitis", "copd"}
            return round(r.gauss(14.5 - day * 1.5 if infected else 7.2, 1.4), 1)
        if code == "CRP":
            return round(max(1, r.gauss(140 - day * 25, 20) if acute else r.gauss(3, 1.5)), 1)
        if code == "TSH":
            return round(max(0.2, r.gauss(2.2, 0.8)), 2)
        if code == "UACR":
            return round(max(5, r.gauss(180 if s.egfr < 60 else 45, 40)))
        raise KeyError(code)

    def _lab(self, ctx: PatientCtx, code: str, when: datetime, *, admission: Admission | None = None,
             acute: str | None = None, day: int = 0, value: float | None = None,
             doctor: Doctor | None = None) -> LabReport:
        spec = C.LABS[code]
        v = self._lab_value(ctx, code, acute=acute, day=day) if value is None else value
        flag = "normal"
        if spec.low is not None and v < spec.low:
            flag = "low"
        if spec.high is not None and v > spec.high:
            flag = "high"
        if (spec.critical_low is not None and v <= spec.critical_low) or (
                spec.critical_high is not None and v >= spec.critical_high):
            flag = "critical"
        lab = LabReport(patient_id=ctx.patient.id, admission_id=admission.id if admission else None,
                        ordered_by_doctor_id=(doctor or ctx.doctor).id, test_code=code, test_name=spec.name,
                        value=v, unit=spec.unit, reference_low=spec.low, reference_high=spec.high, flag=flag,
                        collected_at=when, reported_at=when + timedelta(hours=3))
        self.db.add(lab)
        return lab

    def _slot(self, doctor: Doctor, d: date, live: bool) -> datetime:
        for _ in range(50):
            slot = at(d, self.rng.randint(9, 16), self.rng.choice([0, 30]))
            if not live or (doctor.id, slot) not in self.taken_slots:
                if live:
                    self.taken_slots.add((doctor.id, slot))
                return slot
        d2 = d + timedelta(days=1)
        return self._slot(doctor, self._weekday(d2), live)

    # ================================================================== clinical events
    def _visit_labs(self, ctx: PatientCtx, d: date) -> list[str]:
        codes: list[str] = []
        cs = ctx.conditions
        if "E11.9" in cs:
            codes += ["HBA1C", "GLU", "CREAT", "EGFR", "K"]
            if ctx.last_uacr is None or (d - ctx.last_uacr).days > 330:
                codes.append("UACR")
                ctx.last_uacr = d
        if cs & {"I10", "N18.3"}:
            codes += ["CREAT", "EGFR", "K", "NA"]
        if "I50.9" in cs:
            codes += ["BNP", "K", "CREAT", "NA"]
        if "warfarin" in ctx.active_rx:
            codes.append("INR")
        if "E03.9" in cs:
            codes.append("TSH")
        if cs & {"E78.5", "I25.10", "E11.9"} and (ctx.last_ldl is None or (d - ctx.last_ldl).days > 330):
            codes.append("LDL")
            ctx.last_ldl = d
        return list(dict.fromkeys(codes))

    def _evolve(self, ctx: PatientCtx, days: int, overrides: dict | None) -> None:
        s = ctx.state
        years = days / 365
        if s.a1c is not None:
            s.a1c = min(13.5, max(5.6, s.a1c + s.a1c_drift * years * 2 + self.rng.gauss(0, 0.15)))
        s.egfr = max(10, s.egfr + s.egfr_drift * years + self.rng.gauss(0, 1.0))
        for k, v in (overrides or {}).items():
            setattr(s, k, v)

    def _diabetes_rules(self, ctx: PatientCtx, d: date) -> list[str]:
        """Rule-based treatment adjustments mirroring the demo diabetes guideline."""
        s, rx, notes = ctx.state, ctx.active_rx, []
        if "E11.9" not in ctx.conditions or s.a1c is None:
            return notes
        if "metformin" in rx and s.egfr < 30:
            self._rx_stop(ctx, "metformin", d, f"Stopped - eGFR {s.egfr:.0f} below 30")
            notes.append(f"Metformin stopped because eGFR is {s.egfr:.0f}.")
        elif "metformin" in rx and s.egfr < 45 and rx["metformin"].dosage == "1000 mg":
            self._rx_change(ctx, "metformin", "500 mg", "twice daily", d, f"Dose reduced - eGFR {s.egfr:.0f}")
            notes.append(f"Metformin reduced to 500 mg twice daily for eGFR {s.egfr:.0f}.")
        elif s.a1c > 7.5 and "metformin" in rx and rx["metformin"].dosage == "500 mg" and s.egfr >= 45:
            self._rx_change(ctx, "metformin", "1000 mg", "twice daily", d, f"Dose increased - HbA1c {s.a1c:.1f}%")
            s.a1c -= 0.4
            notes.append("Metformin increased to 1000 mg twice daily.")
        elif s.a1c > 8.0 and not ({"empagliflozin", "sitagliptin"} & set(rx)):
            drug, dose = ("empagliflozin", "10 mg") if s.egfr >= 30 else ("sitagliptin", "50 mg")
            self._rx(ctx, drug, dose, "once daily", d, ctx.doctor, reason=f"Added - HbA1c {s.a1c:.1f}% above target")
            s.a1c -= 0.5
            notes.append(f"{drug.capitalize()} {dose} daily added.")
        elif s.a1c > 9.0 and "insulin glargine" not in rx:
            self._rx(ctx, "insulin glargine", "10 units", "once nightly", d, ctx.doctor,
                     reason=f"Basal insulin started - HbA1c {s.a1c:.1f}%")
            s.a1c -= 0.8
            notes.append("Basal insulin glargine 10 units nightly started.")
        return notes

    def _visit(self, ctx: PatientCtx, d: date, *, doctor: Doctor | None = None, overrides: dict | None = None,
               last_visit: date | None = None, actions: list[tuple] | None = None, force_complete: bool = False,
               new_conditions: tuple[str, ...] = ()) -> None:
        doctor = doctor or ctx.doctor
        d = self._weekday(d)
        roll = self.rng.random()
        status = "completed" if force_complete or roll < 0.9 else ("no_show" if roll < 0.95 else "cancelled")
        self.db.add(Appointment(
            patient_id=ctx.patient.id, doctor_id=doctor.id, department_id=doctor.department_id,
            scheduled_start=self._slot(doctor, d, live=False), duration_minutes=30, appointment_type="follow_up",
            reason=f"{C.CONDITIONS[sorted(ctx.conditions)[0]].description} follow-up" if ctx.conditions else "Review",
            status=status, cancellation_reason="Patient request" if status == "cancelled" else None))
        if status != "completed":
            return
        self._evolve(ctx, (d - last_visit).days if last_visit else 0, overrides)
        for code in new_conditions:
            ctx.conditions.add(code)
            self._diagnosis(ctx, code, d)
        when = at(d, 8, 15)
        values = {code: self._lab(ctx, code, when, doctor=doctor) for code in self._visit_labs(ctx, d)}
        if actions is None:
            notes = self._diabetes_rules(ctx, d)
        else:
            notes = []
            for act in actions:
                kind, med, *rest = act
                if kind == "change":
                    self._rx_change(ctx, med, rest[0], rest[1], d, rest[2], doctor)
                elif kind == "start":
                    self._rx(ctx, med, rest[0], rest[1], d, doctor, reason=rest[2])
                elif kind == "stop":
                    self._rx_stop(ctx, med, d, rest[0])
                notes.append(rest[-1] + ".")
        self.db.add(self._visit_record(ctx, d, doctor, values, notes))

    def _visit_record(self, ctx: PatientCtx, d: date, doctor: Doctor, labs: dict[str, LabReport],
                      changes: list[str]) -> MedicalRecord:
        cond_names = [C.CONDITIONS[c].description for c in sorted(ctx.conditions)]
        lab_txt = ", ".join(f"{lab.test_name} {lab.value:g} {lab.unit}" + (f" ({lab.flag})" if lab.flag != "normal" else "")
                            for lab in labs.values())
        symptom = self.rng.choice(["No new symptoms reported.", "Reports mild fatigue.",
                                   "Reports good adherence to medication.", "Occasional dizziness on standing.",
                                   "Increased thirst over the past month." if "E11.9" in ctx.conditions
                                   else "Sleeping well."])
        a1c = labs.get("HBA1C")
        summary = "; ".join(cond_names[:4])
        if a1c:
            summary += f". HbA1c {a1c.value:g}% ({'at' if a1c.value < 7 else 'above'} target)"
        plan = " ".join(changes) if changes else "Continue current medications."
        plan += " Next review in 3 months with repeat labs."
        return MedicalRecord(
            patient_id=ctx.patient.id, doctor_id=doctor.id, visit_date=d, record_type="follow_up",
            chief_complaint="Scheduled follow-up of chronic conditions", symptoms=symptom,
            diagnosis_summary=summary,
            notes=f"Reviewed history and current medications ({len(ctx.active_rx)} active). Results today: "
                  f"{lab_txt or 'none drawn'}. Synthetic record.",
            treatment_plan=plan)

    def _ed_visit(self, ctx: PatientCtx, d: date, reason: str | None = None) -> None:
        doc = self.doctors[self.rng.choice(["D701", "D702"])]
        reason = reason or self.rng.choice(["Dizziness", "Chest discomfort", "Minor fall", "Shortness of breath",
                                            "Abdominal pain"])
        self.db.add(Appointment(patient_id=ctx.patient.id, doctor_id=doc.id, department_id=doc.department_id,
                                scheduled_start=at(d, self.rng.randint(0, 23), self.rng.choice([0, 20, 40])),
                                duration_minutes=60, appointment_type="emergency", reason=reason, status="completed"))
        self.db.add(MedicalRecord(
            patient_id=ctx.patient.id, doctor_id=doc.id, visit_date=d, record_type="emergency",
            chief_complaint=reason, symptoms=f"{reason}; vital signs stable after assessment.",
            diagnosis_summary="Assessed in the emergency department; no admission required.",
            notes="Observed for 4 hours. Synthetic record.", treatment_plan="Discharged home; follow up with primary team."))

    def _admission(self, ctx: PatientCtx, start: date, key: str, *, los: int | None = None,
                   disposition: str | None = None, attending: Doctor | None = None, current: bool = False,
                   discharge_actions: list[tuple] | None = None, extra_dx: tuple[str, ...] = (),
                   admit_hour: int | None = None) -> Admission:
        ev = C.ACUTE[key]
        los = los if los is not None else self.rng.randint(*ev.los)
        dept_code = ev.department or C.ARCHETYPES[ctx.archetype].department
        attending = attending or (ctx.doctor if ctx.doctor.department_id == self.departments[dept_code].id
                                  else self.doctors[C.ARCHETYPES_DOCTOR_BY_DEPT[dept_code]])
        elective = key == "knee_replacement"
        admitted_at = at(start, admit_hour if admit_hour is not None else self.rng.randint(6, 22), 0)
        age = (start - ctx.patient.date_of_birth).days / 365
        if disposition is None:
            r = self.rng.random()
            frail = ctx.frailty + (0.25 if age > 75 else 0)
            disposition = "home" if r > 0.35 + frail * 0.3 else self.rng.choice(
                ["home_health", "home_health", "skilled_nursing", "rehab"])
        discharged_at = None if current else admitted_at + timedelta(days=los, hours=self.rng.randint(-4, 4))
        adm = Admission(
            patient_id=ctx.patient.id, department_id=self.departments[dept_code].id, attending_doctor_id=attending.id,
            admitted_at=admitted_at, discharged_at=discharged_at,
            admission_type="elective" if elective else self.rng.choice(["emergency"] * 4 + ["urgent"]),
            admission_source="physician_referral" if elective else "emergency_room", reason=ev.reason,
            discharge_disposition=None if current else disposition, status="admitted" if current else "discharged",
            ward=f"{dept_code}-{self.rng.randint(1, 4)}")
        if elective:
            adm.admission_type = "elective"
        self.db.add(adm)
        self.db.flush()
        self._assign(ctx.patient.id, self.user_by_doctor.get(attending.id), "attending")

        self._diagnosis(ctx, ev.code, start, admission=adm, primary=True, status="active" if current else "resolved")
        for code in extra_dx:
            self._diagnosis(ctx, code, start, admission=adm, status="active" if current else "resolved")
        # Inpatient labs: basic metabolic panel + blood count daily, plus event-specific tests on day 0.
        last_day = (self.anchor - start).days if current else los
        for day in range(0, max(1, last_day) + (0 if current else 1)):
            when = admitted_at + timedelta(days=day, hours=1 if day == 0 else 0)
            if current and when.date() > self.anchor:
                break
            codes = ["NA", "K", "CREAT", "EGFR", "GLU", "HGB", "WBC"]
            if day == 0:
                codes += list(ev.labs)
                if "E11.9" in ctx.conditions and "HBA1C" not in codes and self.rng.random() < 0.5:
                    codes.append("HBA1C")
            if day == 0 and key in {"pneumonia", "uti", "cellulitis", "copd"}:
                codes.append("CRP")
            for code in dict.fromkeys(codes):
                self._lab(ctx, code, when, admission=adm, acute=key, day=day, doctor=attending)
        # Inpatient orders: continued chronic meds + acute treatment + VTE prophylaxis.
        end = None if current else discharged_at.date()
        rx_status = "active" if current else "completed"
        for med, rx in list(ctx.active_rx.items()):
            if med == "metformin" and key == "hyperglycemia":
                continue  # held while on insulin sliding scale
            self._rx(ctx, med, rx.dosage, rx.frequency, start, attending, admission=adm, end=end, status=rx_status,
                     instructions="Continued from home medication list")
        for med, dose, freq in ev.meds:
            self._rx(ctx, med, dose, freq, start, attending, admission=adm, end=end, status=rx_status,
                     instructions="Inpatient order")
        if age >= 18 and key not in {"hypoglycemia"}:
            self._rx(ctx, "enoxaparin", "40 mg", "once daily", start, attending, admission=adm, end=end,
                     status=rx_status, instructions="VTE prophylaxis")
        self.db.add(MedicalRecord(
            patient_id=ctx.patient.id, doctor_id=attending.id, admission_id=adm.id, visit_date=start,
            record_type="emergency" if adm.admission_source == "emergency_room" else "consultation",
            chief_complaint=ev.reason, symptoms=self._acute_symptoms(key),
            diagnosis_summary=f"Admitted with {ev.reason.lower()}.",
            notes=f"Admitted to {self.departments[dept_code].name} via {adm.admission_source.replace('_', ' ')}. "
                  "Synthetic record.",
            treatment_plan="; ".join(f"{m} {d} {f}" for m, d, f in ev.meds) or "Supportive care"))
        if not current:
            for act in discharge_actions or []:
                kind, med, *rest = act
                if kind == "start":
                    self._rx(ctx, med, rest[0], rest[1], discharged_at.date(), attending, reason=rest[2])
                elif kind == "change":
                    self._rx_change(ctx, med, rest[0], rest[1], discharged_at.date(), rest[2], attending)
                    self._rx(ctx, med, rest[0], rest[1], start + timedelta(days=1), attending, admission=adm,
                             end=end, status="completed", reason=rest[2].replace("Dose", "Inpatient dose"))
            meds_txt = ", ".join(f"{m} {rx.dosage} {rx.frequency}" for m, rx in ctx.active_rx.items())
            self.db.add(MedicalRecord(
                patient_id=ctx.patient.id, doctor_id=attending.id, admission_id=adm.id,
                visit_date=discharged_at.date(), record_type="discharge_summary",
                chief_complaint=f"Discharge: {ev.reason}",
                diagnosis_summary=f"{C.CONDITIONS[ev.code].description}. Length of stay {los} days.",
                notes=f"Clinically improved. Discharged to {disposition.replace('_', ' ')}. "
                      f"Discharge medications: {meds_txt}. Synthetic record.",
                treatment_plan="Follow up with primary team within 7-14 days. Return if symptoms recur."))
        return adm

    def _acute_symptoms(self, key: str) -> str:
        return {
            "hyperglycemia": "Polyuria, polydipsia, fatigue and blurred vision for several days.",
            "hypoglycemia": "Sweating, confusion and tremor; capillary glucose low on arrival.",
            "pneumonia": "Fever, productive cough and shortness of breath.",
            "uti": "Dysuria, frequency and fever.",
            "cellulitis": "Painful spreading erythema of the lower leg.",
            "hf_exacerbation": "Worsening breathlessness, orthopnea and ankle swelling.",
            "af_rvr": "Palpitations and light-headedness.",
            "angina": "Chest pain at rest lasting 20 minutes.",
            "stroke": "Sudden right-sided weakness and slurred speech.",
            "seizure": "Witnessed generalized seizure.",
            "hip_fracture": "Fall at home with right hip pain, unable to bear weight.",
            "knee_replacement": "Chronic right knee pain limiting mobility; elective surgery.",
            "asthma": "Wheeze and increased work of breathing.",
            "copd": "Increased dyspnea and sputum production.",
        }[key]

    def _future_appointment(self, ctx: PatientCtx, d: date, reason: str | None = None,
                            hour: int | None = None) -> None:
        d = self._weekday(d)
        if hour is not None:
            slot = at(d, hour, 0)
            self.taken_slots.add((ctx.doctor.id, slot))
        else:
            slot = self._slot(ctx.doctor, d, live=True)
        status = "checked_in" if d == self.anchor and slot.hour < 11 and self.rng.random() < 0.5 else "scheduled"
        self.db.add(Appointment(
            patient_id=ctx.patient.id, doctor_id=ctx.doctor.id, department_id=ctx.doctor.department_id,
            scheduled_start=slot, duration_minutes=30, appointment_type="follow_up",
            reason=reason or "Routine follow-up", status=status))

    # ================================================================== patients
    def _new_patient(self, mrn: str, archetype: str, first: str, last: str, sex: str, dob: date) -> Patient:
        r = self.rng
        allergies = [dict(zip(("substance", "reaction", "severity"), a, strict=True))
                     for a in r.sample(C.ALLERGIES, k=r.choice([0, 0, 0, 1, 1, 2]))]
        contact_first = r.choice(C.FIRST_F + C.FIRST_M)
        p = Patient(
            mrn=mrn, first_name=first, last_name=last, date_of_birth=dob, sex=sex,
            phone=f"+1-555-{r.randint(200, 999)}-{r.randint(1000, 9999)}",
            email=f"{first.lower()}.{last.lower()}{r.randint(1, 99)}@example.com",
            address=f"{r.randint(1, 999)} {r.choice(C.STREETS)}, {C.CITY}",
            preferred_language=r.choice(C.LANGUAGES), blood_type=r.choice(C.BLOOD_TYPES),
            emergency_contact_name=f"{contact_first} {last}",
            emergency_contact_phone=f"+1-555-{r.randint(200, 999)}-{r.randint(1000, 9999)}",
            emergency_contact_relation=r.choice(["Spouse", "Daughter", "Son", "Sibling", "Parent", "Friend"]),
            allergies=allergies, status="active",
            primary_department_id=self.departments[C.ARCHETYPES[archetype].department].id)
        self.db.add(p)
        self.db.flush()
        return p

    def _random_patient(self, mrn: str) -> None:
        r = self.rng
        archetype = r.choices(list(C.ARCHETYPES), weights=[a.weight for a in C.ARCHETYPES.values()])[0]
        arch = C.ARCHETYPES[archetype]
        sex = r.choice("FM")
        age = r.randint(*arch.age)
        dob = self.anchor - timedelta(days=age * 365 + r.randint(0, 364))
        first = r.choice(C.FIRST_F if sex == "F" else C.FIRST_M)
        patient = self._new_patient(mrn, archetype, first, r.choice(C.LAST), sex, dob)
        conditions = {code for code, p in arch.chronic if r.random() < p} or {arch.chronic[0][0]}
        diabetic = "E11.9" in conditions
        state = ClinicalState(
            a1c=r.uniform(6.4, 9.2) if diabetic else None,
            egfr=r.uniform(32, 58) if "N18.3" in conditions else r.uniform(62, 105) - max(0, age - 60) * 0.6,
            ldl=r.uniform(70, 160), bnp=r.uniform(250, 700) if "I50.9" in conditions else r.uniform(15, 80),
            a1c_drift=r.uniform(-0.2, 0.45), egfr_drift=r.uniform(-4, 0) if "N18.3" in conditions else r.uniform(-1.5, 0.5))
        frailty = min(1.0, max(0.0, r.gauss(0.35, 0.2) + (age - 60) / 100))
        ctx = PatientCtx(patient, archetype, self.doctors[r.choice(arch.doctors)], conditions, state, frailty)
        self._assign(patient.id, self.user_by_doctor.get(ctx.doctor.id), "attending")

        since = self.anchor - timedelta(days=r.randint(420, 1100))
        for code in sorted(conditions):
            onset = since - timedelta(days=r.randint(0, 2500))
            onset = max(onset, dob + timedelta(days=365 * min(age, 18) // 2))
            self._diagnosis(ctx, code, onset)
            for med, dose, freq in C.CONDITIONS[code].meds:
                if med not in ctx.active_rx:
                    self._rx(ctx, med, dose, freq, max(onset, since - timedelta(days=30)), ctx.doctor)

        # Event schedule.
        events: list[tuple[date, str]] = []
        t = since
        while t < self.anchor - timedelta(days=10):
            events.append((t, "visit"))
            t += timedelta(days=r.randint(80, 170))
        years = (self.anchor - since).days / 365
        for _ in range(self._poisson(arch.ed_rate * years * (0.6 + frailty))):
            events.append((since + timedelta(days=r.randint(20, (self.anchor - since).days - 3)), "ed"))
        n_adm = self._poisson(arch.admit_rate * years * (0.4 + frailty))
        for _ in range(n_adm):
            events.append((since + timedelta(days=r.randint(30, max(31, (self.anchor - since).days - 20))), "admit"))
        current = r.random() < 0.08 + 0.1 * frailty
        events.sort()

        last_visit, busy_until = None, date.min
        for d, kind in events:
            if d <= busy_until:
                continue
            if kind == "visit":
                self._visit(ctx, d, last_visit=last_visit)
                last_visit = d
            elif kind == "ed":
                self._ed_visit(ctx, d)
            else:
                adm = self._admission(ctx, d, r.choice(arch.acute))
                busy_until = adm.discharged_at.date()
                # Readmission within 30 days - more likely for frail patients.
                if r.random() < 0.10 + 0.35 * frailty and busy_until + timedelta(days=30) < self.anchor:
                    re_day = busy_until + timedelta(days=r.randint(3, 28))
                    readm = self._admission(ctx, re_day, r.choice(arch.acute))
                    busy_until = readm.discharged_at.date()
        status = "active"
        if current and busy_until < self.anchor - timedelta(days=2):
            start = self.anchor - timedelta(days=r.randint(0, 6))
            self._admission(ctx, start, r.choice(arch.acute), current=True)
            status = "admitted"
        elif busy_until != date.min and (self.anchor - busy_until).days <= 14:
            status = "discharged"
        patient.status = status
        if status != "admitted" and r.random() < 0.6:
            offset = 0 if r.random() < 0.15 else r.randint(1, 45)
            self._future_appointment(ctx, self.anchor + timedelta(days=offset))

    def _demo_patient(self) -> None:
        """P1024 - hand-authored history used by the end-to-end demo (see docs/demo.md)."""
        A = self.anchor
        patient = self._new_patient(DEMO_MRN, "diabetes", "Evelyn", "Hart", "F", date(A.year - 67, 3, 14))
        patient.allergies = [{"substance": "Penicillin", "reaction": "Rash", "severity": "moderate"},
                             {"substance": "Sulfonamides", "reaction": "Hives", "severity": "mild"}]
        patient.blood_type, patient.preferred_language = "A+", "English"
        rao, okoro, chen = self.doctors["D101"], self.doctors["D102"], self.doctors["D103"]
        state = ClinicalState(a1c=7.2, egfr=64, ldl=112, bnp=60, a1c_drift=0, egfr_drift=0)
        ctx = PatientCtx(patient, "diabetes", rao, {"E11.9", "I10", "E78.5"}, state, frailty=0.6)
        self._assign(patient.id, self.users["dr.rao@careflow.demo"], "attending")
        self._diagnosis(ctx, "E11.9", date(2012, 5, 10))
        self._diagnosis(ctx, "I10", date(2015, 9, 2))
        self._diagnosis(ctx, "E78.5", date(2016, 1, 20))
        self._rx(ctx, "metformin", "500 mg", "twice daily", date(2012, 5, 10), rao)
        self._rx(ctx, "lisinopril", "20 mg", "once daily", date(2015, 9, 2), rao)
        self._rx(ctx, "atorvastatin", "20 mg", "once nightly", date(2016, 1, 20), rao)

        def days_ago(n: int) -> date:
            return A - timedelta(days=n)

        visits = [
            (900, 7.2, 64, None, ()), (810, 7.3, 63, None, ()),
            (715, 7.7, 61, [("change", "metformin", "1000 mg", "twice daily", "Dose increased - HbA1c 7.7% above target")], ()),
            (620, 7.5, 60, None, ()), (530, 7.9, 58, None, ()),
            (440, 8.2, 56, [("start", "empagliflozin", "10 mg", "once daily", "Added - HbA1c 8.2% above target")], ()),
            (350, 8.3, 53, None, ()),
            (260, 8.6, 49, None, ("N18.3",)),
            (170, 8.9, 44, [("change", "metformin", "500 mg", "twice daily", "Dose reduced - eGFR 44 (below 45)")], ()),
        ]
        prev = None
        for ago, a1c, egfr, actions, new_dx in visits:
            d = days_ago(ago)
            self._visit(ctx, d, overrides={"a1c": a1c, "egfr": egfr}, last_visit=prev, actions=actions or [],
                        force_complete=True, new_conditions=new_dx)
            prev = d
        self._admission(ctx, days_ago(330), "pneumonia", los=5, disposition="home", attending=okoro, admit_hour=14)
        self._ed_visit(ctx, days_ago(280), "Symptomatic low blood glucose at home")
        ctx.state.a1c = 9.1
        self._admission(ctx, days_ago(120), "hyperglycemia", los=6, disposition="home", attending=rao, admit_hour=11,
                        discharge_actions=[("start", "insulin glargine", "10 units", "once nightly",
                                            "Basal insulin started - HbA1c 9.1%")])
        self._admission(ctx, days_ago(52), "uti", los=4, disposition="home", attending=chen, admit_hour=19,
                        extra_dx=("E11.65",))
        self._ed_visit(ctx, days_ago(75), "Dizziness and dehydration")
        ctx.state.a1c = 9.4
        self._admission(ctx, days_ago(13), "hyperglycemia", los=7, disposition="home_health", attending=rao,
                        admit_hour=10, extra_dx=("E86.0",),
                        discharge_actions=[("change", "insulin glargine", "16 units", "once nightly",
                                            "Dose increased - persistent hyperglycemia, HbA1c 9.4%")])
        patient.status = "discharged"
        self._future_appointment(ctx, A + timedelta(days=2), "Post-discharge diabetes follow-up", hour=10)
        self._assign(patient.id, self.users["nurse.kim@careflow.demo"], "nurse")

    def _nurse_assignments(self) -> None:
        """Nurse Kim covers the General Medicine ward: current GM inpatients plus a few recent discharges."""
        nurse = self.users["nurse.kim@careflow.demo"]
        gm = self.departments["GM"].id
        admitted = self.db.query(Admission.patient_id).filter(Admission.department_id == gm,
                                                               Admission.status == "admitted").all()
        recent = (self.db.query(Admission.patient_id).filter(Admission.department_id == gm,
                                                              Admission.status == "discharged")
                  .order_by(Admission.discharged_at.desc()).limit(8).all())
        for (pid,) in admitted + recent:
            self._assign(pid, nurse, "nurse")


# Department -> default attending when an event occurs outside the patient's home department.
C.ARCHETYPES_DOCTOR_BY_DEPT = {"GM": "D102", "CARD": "D201", "NEUR": "D301", "ORTH": "D401", "PED": "D501",
                               "DERM": "D601", "EM": "D701"}
