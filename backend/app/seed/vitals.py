"""Synthetic bedside observations for the patients currently in hospital.

Each inpatient gets a set of observations every 4-6 hours over (up to) the last three days of the stay, shaped by
the reason for admission (fever with infections, fast pulse in atrial fibrillation, low saturations in COPD on
the COPD-specific SpO2 scale) and settling as the stay goes on. A few patients - at least one on the General
Medicine ward - deteriorate over the last hours, and some are overdue their next set, so the ward board has
something to show.

Uses its own random stream, so the rest of the seeded hospital (and every model prediction on it) is unchanged.
"""
import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Admission, CareAssignment, User, VitalSigns
from app.services.news2 import Observations, score

# Deviations from normal on admission, by the reason for admission: (temperature, pulse, resp. rate, SpO2, SBP)
PROFILES = {
    "pneumonia": (1.4, 20, 6, -5, -8), "urinary tract": (1.3, 16, 3, -1, -10), "cellulitis": (1.0, 12, 2, 0, 0),
    "hyperglycemia": (0.2, 14, 3, 0, -12), "hypoglycemia": (0.0, 8, 0, 0, 0), "heart failure": (0.0, 18, 6, -5, 10),
    "atrial fibrillation": (0.1, 40, 3, -1, -5), "angina": (0.0, 10, 2, 0, 15), "stroke": (0.2, 6, 1, -1, 45),
    "seizure": (0.4, 12, 2, -1, 5), "fracture": (0.3, 14, 2, -1, 10), "arthroplasty": (0.4, 8, 1, 0, 0),
    "asthma": (0.1, 20, 7, -5, 0), "copd": (0.5, 16, 7, -2, 5),
}
BASE = {"temperature": 36.8, "heart_rate": 78, "respiratory_rate": 16, "spo2": 97, "systolic_bp": 128}


def _profile(reason: str) -> tuple[float, float, float, float, float]:
    r = reason.lower()
    return next((v for k, v in PROFILES.items() if k in r), (0.3, 8, 2, -1, 0))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def seed_vitals(db: Session, *, seed: int = 7, now: datetime | None = None) -> int:
    """Add observations for current inpatients. Idempotent: does nothing if any observations exist."""
    if db.scalar(select(func.count()).select_from(VitalSigns)):
        return 0
    rng = random.Random(seed + 7919)
    now = now or datetime.now(UTC)
    admissions = db.scalars(select(Admission).where(Admission.status == "admitted").order_by(Admission.id)).all()
    nurses = dict(db.execute(select(CareAssignment.patient_id, User.id).join(User, User.id == CareAssignment.user_id)
                             .where(CareAssignment.care_role == "nurse", CareAssignment.active)).all())
    # Every fifth inpatient deteriorates, and at least one on the General Medicine ward.
    worsening = {a.id for i, a in enumerate(admissions) if i % 5 == 2}
    gm = [a for a in admissions if a.department.code == "GM"]
    if gm and not worsening & {a.id for a in gm}:
        worsening.add(gm[len(gm) // 2].id)
    added = 0
    for adm in admissions:
        temp_d, hr_d, rr_d, spo2_d, sbp_d = _profile(adm.reason)
        copd = "copd" in adm.reason.lower()
        # Each patient has their own resting baseline, so a settled ward is not a row of identical zeros.
        base = {"respiratory_rate": rng.gauss(0, 2.2), "heart_rate": rng.gauss(0, 8), "spo2": rng.gauss(0, 1.6),
                "systolic_bp": rng.gauss(0, 9), "temperature": rng.gauss(0, 0.25)}
        start = max(adm.admitted_at, now - timedelta(hours=72))
        # Stop 0.5-7 hours before now: some patients are due, some are overdue.
        end = now - timedelta(hours=rng.uniform(0.5, 7.0))
        t = start
        while t <= end:
            hours_in = (t - adm.admitted_at).total_seconds() / 3600
            # The admission problem eases over the stay, but someone still in hospital is rarely back to normal.
            settle = max(0.25, math.exp(-hours_in / 36))
            decline = 0.0
            if adm.id in worsening:
                decline = _clamp(1 - (end - t).total_seconds() / 3600 / 10, 0, 1)  # the last 10 hours
            on_oxygen = copd or (spo2_d < -3 and settle > 0.5) or decline > 0.7
            o = Observations(
                respiratory_rate=round(_clamp(BASE["respiratory_rate"] + base["respiratory_rate"] + rr_d * settle
                                              + 8 * decline + rng.gauss(0, 1.2), 8, 40)),
                spo2=round(_clamp((89 if copd else BASE["spo2"]) + base["spo2"] + spo2_d * settle - 4 * decline
                                  + (2 if on_oxygen and not copd else 0) + rng.gauss(0, 0.8), 80, 100)),
                on_oxygen=on_oxygen,
                systolic_bp=round(_clamp(BASE["systolic_bp"] + base["systolic_bp"] + sbp_d * settle - 24 * decline
                                         + rng.gauss(0, 7), 70, 220)),
                heart_rate=round(_clamp(BASE["heart_rate"] + base["heart_rate"] + hr_d * settle + 26 * decline
                                        + rng.gauss(0, 5), 40, 170)),
                consciousness="C" if decline > 0.95 else "A",
                temperature=round(_clamp(BASE["temperature"] + base["temperature"] + temp_d * settle + 1.0 * decline
                                         + rng.gauss(0, 0.2), 35.0, 40.5), 1),
                spo2_scale=2 if copd else 1)
            n = score(o)
            db.add(VitalSigns(patient_id=adm.patient_id, admission_id=adm.id, recorded_at=t,
                              recorded_by_user_id=nurses.get(adm.patient_id), respiratory_rate=o.respiratory_rate,
                              spo2=o.spo2, spo2_scale=o.spo2_scale, on_oxygen=o.on_oxygen, systolic_bp=o.systolic_bp,
                              diastolic_bp=round(o.systolic_bp * 0.62 + rng.gauss(0, 4)), heart_rate=o.heart_rate,
                              temperature=o.temperature, consciousness=o.consciousness, news2_score=n.score,
                              news2_risk=n.risk, source="seed"))
            added += 1
            # The next set follows the score's own schedule (hourly when worrying), with a little slack.
            gap = min(n.due_within_hours, 6.0) if n.score >= 5 or n.single_parameter_3 else rng.uniform(4.0, 6.0)
            t += timedelta(hours=max(gap, 1.0) * rng.uniform(0.9, 1.15))
    db.flush()
    return added
