"""Pseudonymisation gateway: direct patient identifiers never reach a cloud language model.

Before a prompt is sent to a model hosted outside the hospital network, every direct identifier of the
patients it mentions - name, MRN, date of birth, phone, e-mail, address, emergency contact - is replaced
with a stable placeholder such as PATIENT_1 or MRN_1. The model reasons over the placeholders; its answer
and its tool-call arguments are mapped back on the server before anything else reads them, so the user
sees real names and the tools receive real identifiers.

Three passes, in this order, because each one is stronger than the next and should go first:

1. the dictionary - every identifier the database holds for the patients in the evidence. Deterministic
   and complete for them; it cannot miss a name the way a statistical tagger can;
2. shapes the database does not hold for this request - a phone number or e-mail typed into a question,
   another patient's MRN;
3. a named-entity model (app.privacy.ner) over what is left, for the people nobody ever issued to
   CareFlow: a relative named in a note, a clinician at another hospital. This pass is statistical and
   will miss some; that is why it runs last, over text the first two have already been through.

This is pseudonymisation, not de-identification: clinical dates, ages, diagnoses and results stay in the
prompt because summaries need them, and this hospital's own staff names stay (they are its directory, not
patient identifiers). Placeholders exist for one request and are never stored.
"""
import ipaddress
import re
from collections.abc import Iterable
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.access import AccessPolicy
from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMResult, ToolSpec
from app.models import Doctor, Patient, User
from app.schemas.ai import PrivacyOut

PREFIX = {"patient_name": "PATIENT", "mrn": "MRN", "date_of_birth": "DOB", "phone": "PHONE", "email": "EMAIL",
          "address": "ADDRESS", "contact_name": "CONTACT", "national_id": "NATIONAL_ID", "person": "PERSON"}
_KIND = {v: k for k, v in PREFIX.items()}
TOKEN = re.compile(r"\b(PATIENT|MRN|DOB|PHONE|EMAIL|ADDRESS|CONTACT|NATIONAL_ID|PERSON)_(\d+)\b",
                   re.IGNORECASE)
MRN_SHAPE = re.compile(r"\bP\d{4}\b")
# Identifiers found by shape. Indian mobile numbers (+91, ten digits starting 6-9) and Aadhaar-style
# 12-digit numbers match the demo hospital's setting. Order matters: phones before national ids.
_SHAPES: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("phone", re.compile(r"(?<![\w+])(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("national_id", re.compile(r"(?<![\d\w])[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("mrn", MRN_SHAPE),
]
_TITLES = ("Mr", "Mrs", "Ms", "Miss", "Shri", "Smt")
CLOUD_PROVIDERS = {"anthropic", "groq", "gemini"}
PREVIEW_CHARS = 6000  # the head of the request (evidence) and its tail (the question) are both kept


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _staff_forms(names: Iterable[str]) -> set[str]:
    """The ways a clinician's name appears in text: "Dr. Ananya Rao", "Ananya Rao", "Dr Rao", "Jiwoo Kim"."""
    out: set[str] = set()
    for full in names:
        bare = re.sub(r",\s*[A-Za-z]+$", "", re.sub(r"^Dr\.?\s+", "", full))
        out.update({full, bare})
        if full.startswith("Dr"):
            last = bare.split()[-1]
            out.update({f"Dr. {last}", f"Dr {last}"})
    return out


class IdentifierVault:
    """Placeholder <-> value mapping for one request."""

    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], str] = {}  # (kind, normalised value) -> placeholder
        self._display: dict[str, str] = {}  # placeholder -> the value restored in the answer
        self._next: dict[str, int] = {}
        self._literals: dict[str, str] = {}  # casefolded text -> placeholder
        self._ambiguous: set[str] = set()
        self._protected: set[str] = set()  # staff names, never replaced
        self._regex: re.Pattern | None = None
        self.finder = None  # app.privacy.ner.NameFinder, when the third pass is switched on
        self.patient_ids: set[int] = set()
        self.mrns: set[str] = set()
        self.used: set[str] = set()

    # ------------------------------------------------------------------ registration
    def token(self, kind: str, key: str, display: str) -> str:
        if (kind, key) not in self._tokens:
            n = self._next[kind] = self._next.get(kind, 0) + 1
            placeholder = f"{PREFIX[kind]}_{n}"
            self._tokens[(kind, key)] = placeholder
            self._display[placeholder] = display
        return self._tokens[(kind, key)]

    def _literal(self, text: str | None, placeholder: str) -> None:
        if not text or len(text.strip()) < 3:
            return
        key = text.strip().casefold()
        if key in self._ambiguous:
            return
        existing = self._literals.get(key)
        if existing is None:
            self._literals[key] = placeholder
        elif self._display[existing] != self._display[placeholder]:
            # The same text stands for two different people (two patients called Asha): replacing it could
            # restore the wrong name in the answer, so it is left alone and the longer forms do the work.
            # (A patient whose name matches another patient's emergency contact restores to the same text,
            # so that is not ambiguous.)
            del self._literals[key]
            self._ambiguous.add(key)
        self._regex = None

    def protect(self, names: Iterable[str]) -> None:
        self._protected.update(n.strip().casefold() for n in names if n and len(n.strip()) >= 3)
        self._regex = None

    def add_patient(self, p: Patient) -> None:
        if p.id in self.patient_ids:
            return
        self.patient_ids.add(p.id)
        self.mrns.add(p.mrn.upper())
        # Keyed by name, not id: two patients with the same full name restore to the same (correct) text.
        name = self.token("patient_name", p.full_name.casefold(), p.full_name)
        for form in (p.full_name, f"{p.last_name}, {p.first_name}", p.first_name,
                     *(f"{t}. {p.last_name}" for t in _TITLES), *(f"{t} {p.last_name}" for t in _TITLES)):
            self._literal(form, name)
        self._literal(p.mrn, self.token("mrn", p.mrn.upper(), p.mrn))
        dob = p.date_of_birth.isoformat()
        self._literal(dob, self.token("date_of_birth", dob, dob))
        for phone in (p.phone, p.emergency_contact_phone):
            if phone and len(_digits(phone)) >= 8:
                self._literal(phone, self.token("phone", _digits(phone)[-10:], phone))
        for kind, value in (("email", p.email), ("address", p.address), ("contact_name", p.emergency_contact_name)):
            if value:
                self._literal(value, self.token(kind, value.casefold(), value))

    # ------------------------------------------------------------------ transformation
    def _pattern(self) -> re.Pattern | None:
        if self._regex is None:
            alternatives = set(self._literals) | self._protected
            if not alternatives:
                return None
            # Longest first: at any position the longest known form wins ("Dr. Priya Nair" over "Priya").
            ordered = sorted(alternatives, key=len, reverse=True)
            self._regex = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, ordered)) + r")(?!\w)", re.IGNORECASE)
        return self._regex

    def _shape(self, kind: str, value: str) -> str:
        key = {"phone": _digits(value)[-10:], "national_id": _digits(value), "mrn": value.upper()}.get(
            kind, value.casefold())
        placeholder = self.token(kind, key, value)
        self.used.add(placeholder)
        return placeholder

    def pseudonymize(self, text: str) -> str:
        if not text:
            return text
        # Placeholder-shaped text that did not come from this vault (a document that says "PATIENT_1") must
        # not be "restored" into a real name in the answer.
        text = TOKEN.sub(lambda m: m.group(0).replace("_", "-"), text)
        pattern = self._pattern()
        if pattern is not None:
            def literal(m: re.Match) -> str:
                placeholder = self._literals.get(m.group(0).casefold())
                if placeholder is None:
                    return m.group(0)  # a staff name
                self.used.add(placeholder)
                return placeholder

            text = pattern.sub(literal, text)
        for kind, shape in _SHAPES:
            text = shape.sub(lambda m, kind=kind: self._shape(kind, m.group(0)), text)
        return self._mask_people(text)

    def _mask_people(self, text: str) -> str:
        """The third pass: people the database never issued an identifier for.

        It runs over text the dictionary has already been through, so a patient's name is a placeholder by
        now and cannot be double-masked, and this hospital's staff are skipped by name.
        """
        if self.finder is None:
            return text
        spans = self.finder.find(text)
        if not spans:
            return text
        out: list[str] = []
        cursor = 0
        for span in spans:
            if span.start < cursor:
                continue
            found = text[span.start:span.end].strip()
            key = found.casefold()
            if len(found) < 3 or key in self._protected or key in self._ambiguous or TOKEN.fullmatch(found):
                continue
            placeholder = self._literals.get(key) or self.token("person", key, found)
            self._literal(found, placeholder)
            self.used.add(placeholder)
            out.append(text[cursor:span.start])
            out.append(placeholder)
            cursor = span.end
        out.append(text[cursor:])
        return "".join(out)

    def reidentify(self, text: str) -> str:
        if not text:
            return text
        return TOKEN.sub(lambda m: self._display.get(f"{m.group(1).upper()}_{m.group(2)}", m.group(0)), text)

    def pseudonymize_obj(self, obj: Any) -> Any:
        return _walk(obj, self.pseudonymize)

    def reidentify_obj(self, obj: Any) -> Any:
        return _walk(obj, self.reidentify)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for placeholder in self.used:
            kind = _KIND[placeholder.rsplit("_", 1)[0]]
            out[kind] = out.get(kind, 0) + 1
        return dict(sorted(out.items()))


def _walk(obj: Any, fn) -> Any:
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_walk(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk(v, fn) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------------------------- policy
def _is_local(host: str) -> bool:
    if host == "localhost" or "." not in host:  # Docker service names such as "ollama"
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith((".local", ".internal"))
    return ip.is_loopback or ip.is_private


def leaves_network(provider) -> bool:
    """True when any model in the provider chain is hosted outside this network."""
    for p in getattr(provider, "providers", [provider]):
        if p.name in CLOUD_PROVIDERS:
            return True
        base_url = getattr(p, "base_url", None)
        if base_url and not _is_local(urlparse(base_url).hostname or ""):
            return True
    return False


def pseudonymization_enabled(provider, mode: str) -> bool:
    """mode: auto (cloud models only), on (every model), off."""
    if provider.name == "extractive" or mode == "off":
        return False
    return mode == "on" or leaves_network(provider)


# ---------------------------------------------------------------------------------------------- gateway
class PrivacyGateway:
    """Wraps the LLM provider for one request: prompts go out pseudonymised, answers come back restored.

    The vault grows as evidence is gathered (tools add patients mid-conversation), and every patient
    added is one the user may access, so the replacement counts reveal nothing about other patients.
    """

    def __init__(self, db: Session, policy: AccessPolicy, provider, *, enabled: bool,
                 evidence_patient_ids: set[int] | None = None):
        self.db = db
        self.policy = policy
        self.inner = provider
        self.enabled = enabled
        self.vault = IdentifierVault()
        if enabled and get_settings().privacy_ner:
            from app.privacy.ner import get_name_finder

            self.vault.finder = get_name_finder()  # loaded on first use, not here
        self._evidence_ids = evidence_patient_ids if evidence_patient_ids is not None else set()
        self._pending: set[int] = set()
        self._staff_loaded = False
        self.calls = 0
        self.answered_by: str | None = None
        self.sent_preview: str | None = None
        self.name = provider.name
        self.model = provider.model
        self.supports_tools = provider.supports_tools

    def include(self, *patient_ids: int | None) -> None:
        """Patients to mask even before any tool has loaded them (the patient in context)."""
        self._pending.update(pid for pid in patient_ids if pid is not None)

    def seed_names(self, text: str) -> None:
        """Mask accessible patients named in full in the question itself ("How is Sunita Deshpande?")."""
        if not self.enabled:
            return
        words = {w.casefold() for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)}
        if not words:
            return
        rows = self.db.scalars(select(Patient).where(
            self.policy.patient_predicate(), func.lower(Patient.first_name).in_(words),
            func.lower(Patient.last_name).in_(words)).limit(20))
        for p in rows:
            if re.search(rf"(?<!\w){re.escape(p.full_name)}(?!\w)", text, re.IGNORECASE):
                self.vault.add_patient(p)

    def _sync(self, texts: Iterable[str]) -> None:
        if not self._staff_loaded:
            staff = [*self.db.scalars(select(Doctor.full_name)), *self.db.scalars(select(User.full_name))]
            self.vault.protect(_staff_forms(staff))
            self._staff_loaded = True
        wanted = (self._evidence_ids | self._pending) - self.vault.patient_ids
        mrns = {m.upper() for t in texts if t for m in MRN_SHAPE.findall(t)} - self.vault.mrns
        conditions = []
        if wanted:
            conditions.append(Patient.id.in_(wanted))
        if mrns:
            conditions.append(Patient.mrn.in_(mrns))
        if conditions:
            for p in self.db.scalars(select(Patient).where(or_(*conditions), self.policy.patient_predicate())):
                self.vault.add_patient(p)

    def chat(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
             max_tokens: int | None = None) -> LLMResult:
        self.calls += 1
        if not self.enabled:
            result = self.inner.chat(system, messages, tools=tools, max_tokens=max_tokens)
            self.answered_by = result.provider or self.inner.name
            return result
        self._sync(m.content for m in messages)
        outgoing = [replace(m, content=self.vault.pseudonymize(m.content),
                            tool_calls=[replace(c, arguments=self.vault.pseudonymize_obj(c.arguments))
                                        for c in m.tool_calls])
                    for m in messages]
        self.sent_preview = "\n\n".join(m.content for m in outgoing if m.role != "assistant" and m.content)
        result = self.inner.chat(system, outgoing, tools=tools, max_tokens=max_tokens)
        self.answered_by = result.provider or self.inner.name
        # provider_raw (e.g. Claude's thinking blocks) stays as the model wrote it: it is replayed to the
        # model, which only ever saw placeholders.
        result.text = self.vault.reidentify(result.text)
        result.tool_calls = [replace(c, arguments=self.vault.reidentify_obj(c.arguments)) for c in result.tool_calls]
        return result

    def summary(self) -> PrivacyOut | None:
        """None when no language model was called (nothing left the server)."""
        if self.calls == 0:
            return None
        if not self.enabled:
            return PrivacyOut(applied=False, destination=self.answered_by or self.inner.name)
        counts = self.vault.counts()
        finder = self.vault.finder
        return PrivacyOut(applied=True, destination=self.answered_by or self.inner.name, replaced=counts,
                          total=sum(counts.values()), preview=_clip(self.sent_preview),
                          name_model=bool(finder is not None and finder.available))


def _clip(text: str | None) -> str | None:
    if not text or len(text) <= PREVIEW_CHARS:
        return text or None
    head, tail = PREVIEW_CHARS * 3 // 4, PREVIEW_CHARS // 4
    return f"{text[:head]}\n\n[... {len(text) - head - tail:,} characters not shown ...]\n\n{text[-tail:]}"
