"""Prompt-injection heuristics for untrusted retrieved text.

Defense in depth - this scanner is ONE layer:
  1. Ingestion: chunks matching instruction-like patterns are flagged (visible to admins).
  2. Context building: flagged chunks are quarantined (withheld from the LLM, surfaced as a warning)
     and all retrieved text is neutralised and wrapped in data-only delimiters.
  3. Prompting: the system prompt states that documents are data and never instructions.
  4. Tools: every tool call is authorised by the backend against the real user, so even an obeyed
     injection cannot reach data the user could not already see.
  5. Output: citations are validated against the actual retrieved set.
Pattern matching cannot catch every attack; layers 3-5 do not depend on it.
"""
import re

PATTERNS: dict[str, re.Pattern] = {
    "override_instructions": re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|all|earlier|system|any)\b"
        r"[^.\n]{0,40}\b(instructions?|prompts?|rules?|directions?|guidelines?|polic(y|ies))", re.I),
    "role_reassignment": re.compile(
        r"\byou are (now|no longer)\b|\bact as (an? )?(admin|administrator|developer|system|unrestricted)|"
        r"\bdeveloper mode\b|\bjailbreak|\bnew instructions?\s*:", re.I),
    "system_prompt_probe": re.compile(
        r"\b(system prompt|hidden instructions|reveal (your|the) (instructions|prompt|rules))", re.I),
    "exfiltration": re.compile(
        r"\b(list|reveal|print|output|dump|send|email|export)\b[^.\n]{0,40}\b(all|every|entire)\b[^.\n]{0,30}"
        r"\b(patients?|records?|passwords?|credentials?|users?|database)", re.I),
    "fake_role_tags": re.compile(
        r"</?\s*(system|assistant|instructions?|tool_output|retrieved_documents?)\s*>|\[/?(system|inst)\]|"
        r"<\|im_(start|end)\|>", re.I),
    "tool_invocation": re.compile(r"\b(call|invoke|execute|run)\b[^.\n]{0,20}\b(the )?(tool|function)\b", re.I),
}


def scan(text: str) -> list[str]:
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]


_ANGLE_TAG = re.compile(r"<\s*(/?)\s*([a-zA-Z_|]+)\s*>")


def neutralize(text: str) -> str:
    """Make retrieved text unable to close or forge the prompt's structural delimiters."""
    text = _ANGLE_TAG.sub(lambda m: f"‹{m.group(1)}{m.group(2)}›", text)
    return text.replace("<<<", "««").replace(">>>", "»»")
