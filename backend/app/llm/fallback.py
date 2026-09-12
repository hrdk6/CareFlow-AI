"""Ordered LLM provider chain: Groq models first, then the cross-provider backup (Gemini).

Each request goes to the first provider that is not cooling down. If it fails for any reason the
orchestrator treats as recoverable (rate limit, timeout, missing or rejected key, outage, malformed
response), the SAME request goes to the next one. A provider that failed is skipped for
`cooldown_seconds` (so a rate-limited free tier is not hit again on every agent round) but is still
tried as a last resort if everything else fails. If every provider fails, the LLMError propagates and
the orchestrator returns the extractive answer.

Switching is silent to the user; each hop is logged and counted in careflow_component_errors_total.
"""
import logging
import time
from collections.abc import Callable

from app.llm.base import ChatMessage, LLMError, LLMProvider, LLMResult, ToolSpec
from app.observability.metrics import COMPONENT_ERRORS

logger = logging.getLogger("careflow.llm")


class FallbackProvider:
    def __init__(self, *providers: LLMProvider, cooldown_seconds: float = 30.0,
                 clock: Callable[[], float] = time.monotonic):
        if len(providers) < 2:
            raise ValueError("FallbackProvider needs at least two providers")
        self.providers = list(providers)
        self.primary = self.providers[0]
        self.name = self.primary.name
        self.model = self.primary.model
        self.supports_tools = all(p.supports_tools for p in self.providers)
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._skip_until = [0.0] * len(self.providers)
        self._errors = [""] * len(self.providers)

    def _label(self, i: int) -> str:
        p = self.providers[i]
        return f"{p.name}/{p.model}"

    def chat(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
             max_tokens: int | None = None) -> LLMResult:
        now = self._clock()
        ready = [i for i in range(len(self.providers)) if now >= self._skip_until[i]]
        cooling = [i for i in range(len(self.providers)) if now < self._skip_until[i]]
        last_exc: LLMError | None = None
        for i in ready + cooling:
            provider = self.providers[i]
            try:
                result = provider.chat(system, messages, tools=tools, max_tokens=max_tokens)
            except LLMError as exc:
                COMPONENT_ERRORS.labels("llm_primary" if i == 0 else "llm_backup").inc()
                logger.warning("LLM provider failed - trying the next one", extra={"fields": {
                    "provider": self._label(i), "error": exc.code}})
                self._errors[i] = exc.message
                self._skip_until[i] = self._clock() + self.cooldown_seconds
                last_exc = exc
                continue
            self._skip_until[i] = 0.0
            result.provider = result.provider or provider.name
            if i != 0:
                result.fallback_reason = f"{self._label(0)}: {self._errors[0] or 'unavailable'}"
            return result
        raise last_exc
