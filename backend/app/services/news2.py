"""National Early Warning Score 2 (NEWS2, Royal College of Physicians, 2017) and the hospital's escalation rules.

NEWS2 is a deterministic track-and-trigger score, not a model: seven observations are banded and summed.
The same function scores seeded observations, the nurse's live preview and every saved set, so the value
on the ward board is always the one the chart defines.

  parameter            3        2        1        0          1         2         3
  respiration rate    <=8               9-11     12-20                21-24     >=25
  SpO2 scale 1        <=91     92-93    94-95    >=96
  SpO2 scale 2 (*)    <=83     84-85    86-87    88-92,      93-94 O2  95-96 O2  >=97 O2
                                                  >=93 air
  air or oxygen                oxygen            air
  systolic BP         <=90     91-100   101-110  111-219                         >=220
  pulse               <=40              41-50    51-90       91-110    111-130   >=131
  consciousness                                  alert                           new confusion, V, P, U
  temperature         <=35.0            35.1-36  36.1-38.0   38.1-39.0 >=39.1

  (*) scale 2 is for patients with confirmed hypercapnic respiratory failure, on a clinician's instruction.

Clinical risk: 0-4 low; 3 in any single parameter low-medium; 5-6 medium; 7 or more high. The response
text below paraphrases the RCP chart; the hospital's own rapid-response triggers come from its Patient Safety
Guidelines (section 6) and are applied separately in `rapid_response_triggers`.
"""
from dataclasses import dataclass
from typing import Literal

Risk = Literal["low", "low_medium", "medium", "high"]
# NEWS2 is validated for acutely ill adults. It is not for children, and the RCP excludes pregnancy too;
# a hospital would use a paediatric early warning score instead, which this demo does not implement.
ADULT_AGE = 16
NOT_FOR_CHILDREN = ("NEWS2 is validated for adults (16 and over). For a younger patient the hospital's paediatric "
                    "early warning chart applies; CareFlow does not implement one, so this score is shown for the "
                    "values only and is not a clinical risk band.")
CONSCIOUSNESS = {"A": "Alert", "C": "New confusion", "V": "Responds to voice", "P": "Responds to pain",
                 "U": "Unresponsive"}


@dataclass(frozen=True)
class Observations:
    respiratory_rate: int
    spo2: int
    on_oxygen: bool
    systolic_bp: int
    heart_rate: int
    consciousness: str  # A, C, V, P or U
    temperature: float
    spo2_scale: int = 1


@dataclass(frozen=True)
class News2:
    score: int
    risk: Risk
    parameters: dict[str, int]
    single_parameter_3: bool
    response: str
    monitoring: str
    due_within_hours: float  # minimum observation frequency for this score

    @property
    def label(self) -> str:
        return {"low": "Low", "low_medium": "Low-medium", "medium": "Medium", "high": "High"}[self.risk]


def _band(value: float, bands: list[tuple[float, int]]) -> int:
    """bands: (upper bound inclusive, points), ascending; the last bound is infinity."""
    for upper, points in bands:
        if value <= upper:
            return points
    raise ValueError(value)


INF = float("inf")


def score(o: Observations) -> News2:
    if o.spo2_scale == 2:
        if o.on_oxygen and o.spo2 >= 93:
            spo2 = _band(o.spo2, [(94, 1), (96, 2), (INF, 3)])
        else:
            spo2 = _band(o.spo2, [(83, 3), (85, 2), (87, 1), (INF, 0)])
    else:
        spo2 = _band(o.spo2, [(91, 3), (93, 2), (95, 1), (INF, 0)])
    parameters = {
        "respiratory_rate": _band(o.respiratory_rate, [(8, 3), (11, 1), (20, 0), (24, 2), (INF, 3)]),
        "spo2": spo2,
        "air_or_oxygen": 2 if o.on_oxygen else 0,
        "systolic_bp": _band(o.systolic_bp, [(90, 3), (100, 2), (110, 1), (219, 0), (INF, 3)]),
        "heart_rate": _band(o.heart_rate, [(40, 3), (50, 1), (90, 0), (110, 1), (130, 2), (INF, 3)]),
        "consciousness": 0 if o.consciousness == "A" else 3,
        "temperature": _band(round(o.temperature, 1), [(35.0, 3), (36.0, 1), (38.0, 0), (39.0, 1), (INF, 2)]),
    }
    total = sum(parameters.values())
    single_3 = any(v == 3 for v in parameters.values())
    if total >= 7:
        risk: Risk = "high"
        response = ("Emergency response: inform the medical team immediately for senior review, with assessment by a "
                    "team with critical-care skills; consider transfer to a higher level of care.")
        monitoring, hours = "Continuous monitoring", 0.5
    elif total >= 5:
        risk = "medium"
        response = ("Urgent response: inform the medical team immediately for urgent assessment by a clinician "
                    "competent in acute illness; care in a monitored area.")
        monitoring, hours = "At least hourly", 1.0
    elif single_3:
        risk = "low_medium"
        response = ("Urgent ward-based response: inform the medical team, who review the patient and decide whether "
                    "to escalate care.")
        monitoring, hours = "At least hourly", 1.0
    elif total >= 1:
        risk = "low"
        response = "The registered nurse assesses the patient and decides whether to observe more often or escalate."
        monitoring, hours = "At least every 4-6 hours", 4.0
    else:
        risk = "low"
        response = "Continue routine observations."
        monitoring, hours = "At least every 12 hours", 12.0
    return News2(total, risk, parameters, single_3, response, monitoring, hours)


def applies_to(age: int | None) -> bool:
    return age is None or age >= ADULT_AGE


def rapid_response_triggers(current: Observations, news2: News2, previous: Observations | None) -> list[str]:
    """Patient Safety Guidelines section 6: call the rapid response team when any of these applies."""
    triggers = []
    if news2.score >= 7:
        triggers.append(f"NEWS2 of {news2.score} (7 or more)")
    if current.consciousness != "A" and (previous is None or previous.consciousness == "A"):
        triggers.append(f"New drop in consciousness ({CONSCIOUSNESS[current.consciousness].lower()})")
    if current.respiratory_rate > 30:
        triggers.append(f"Respiratory rate {current.respiratory_rate}/min (above 30)")
    if current.systolic_bp < 90:
        triggers.append(f"Systolic blood pressure {current.systolic_bp} mmHg (below 90)")
    return triggers
