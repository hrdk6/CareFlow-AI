"""Post-generation grounding checks.

- Citation validation: every [S#]/[R#] in the answer must exist in the evidence store; unknown ids are
  removed (and counted) so the UI can never show a fabricated source.
- Identifier redaction: patient MRNs that the user cannot access are masked, as a last line of defence.
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.models import Patient

_CITE_ITEM = r"[SR]\d+(?:\s*[-–‑]\s*[SR]?\d+)?"  # "R3" or a range "R1-R5" / "R1-5"
CITE_GROUP = re.compile(rf"\[({_CITE_ITEM}(?:\s*[,;]\s*{_CITE_ITEM})*)\]")
_RANGE = re.compile(r"([SR])(\d+)\s*[-–‑]\s*(?:[SR])?(\d+)")
MAX_RANGE = 20
_LENTICULAR = re.compile(r"【([SR][^】]{0,40})】")
MRN = re.compile(r"\bP\d{4}\b")


def _expand(items: list[str]) -> list[str]:
    """Models sometimes cite ranges ("[R1-R5]"); expand them to individual ids so each one is validated."""
    out: list[str] = []
    for item in items:
        m = _RANGE.fullmatch(item)
        if m and 0 <= int(m.group(3)) - int(m.group(2)) < MAX_RANGE:
            out += [f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(item)
    return out


def validate_citations(text: str, valid_ids: set[str]) -> tuple[str, list[str], int]:
    used: list[str] = []
    removed = 0

    text = _LENTICULAR.sub(r"[\1]", text)  # some models cite as 【R1】

    def repl(match: re.Match) -> str:
        nonlocal removed
        ids = _expand([i.strip() for i in re.split(r"[,;]", match.group(1))])
        keep = [i for i in ids if i in valid_ids]
        removed += len(ids) - len(keep)
        for i in keep:
            if i not in used:
                used.append(i)
        return "".join(f"[{i}]" for i in keep)

    return CITE_GROUP.sub(repl, text), used, removed


def redact_unauthorized_mrns(text: str, db: Session, policy: AccessPolicy) -> tuple[str, int]:
    mrns = set(MRN.findall(text))
    if not mrns:
        return text, 0
    allowed = set(db.scalars(select(Patient.mrn).where(Patient.mrn.in_(mrns), policy.patient_predicate())))
    blocked = mrns - allowed
    for mrn in blocked:
        text = re.sub(rf"\b{mrn}\b", "[redacted]", text)
    return text, len(blocked)
