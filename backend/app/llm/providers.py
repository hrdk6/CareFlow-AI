"""LLM provider factory. The provider chain is configuration, not code.

    CAREFLOW_LLM_PROVIDER=groq             Groq cloud: CAREFLOW_GROQ_MODEL, then CAREFLOW_GROQ_FALLBACK_MODELS
    CAREFLOW_LLM_FALLBACK_PROVIDER=gemini  then Google Gemini (free-tier model)
"""
from functools import lru_cache

from app.core.config import Settings, get_settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class ExtractiveProvider:
    """No language model: answers are assembled deterministically from retrieved evidence.

    Used when no LLM is configured or reachable. It never generates free text beyond templates and
    verbatim extracted sentences, so it cannot hallucinate - but it also cannot reason or compare.
    """

    name = "extractive"
    model = None
    supports_tools = False


def groq_reasoning_effort(model: str, s: Settings) -> str | None:
    """Groq models accept different values (verified against the API): gpt-oss takes low|medium|high,
    Qwen takes none|default. Qwen runs with reasoning off - faster and fewer tokens per minute."""
    m = model.lower()
    if "gpt-oss" in m:
        return s.groq_reasoning_effort
    if "qwen" in m:
        return "none"
    return None


def groq_provider(s: Settings, model: str):
    from app.llm.openai_compat import OpenAICompatibleProvider

    return OpenAICompatibleProvider(GROQ_BASE_URL, model, api_key=s.groq_api_key, timeout=s.groq_timeout_seconds,
                                    max_tokens=s.groq_max_tokens, reasoning_effort=groq_reasoning_effort(model, s),
                                    name="groq", require_key=True, max_tokens_field="max_completion_tokens")


def groq_chain(s: Settings) -> list:
    """Each Groq model has its own free-tier tokens-per-minute allowance, so chaining them multiplies capacity."""
    models = [s.groq_model] + [m.strip() for m in s.groq_fallback_models.split(",") if m.strip()]
    return [groq_provider(s, m) for m in dict.fromkeys(models)]


def build_provider(name: str, s: Settings):
    if name == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=s.llm_model, api_key=s.anthropic_api_key, timeout=s.llm_timeout_seconds,
                                 max_tokens=s.llm_max_tokens, effort=s.anthropic_effort,
                                 refusal_fallbacks=s.anthropic_refusal_fallbacks)
    if name == "groq":
        return groq_provider(s, s.groq_model)
    if name in ("openai_compatible", "gemini"):
        from app.llm.openai_compat import OpenAICompatibleProvider

        if name == "gemini":
            return OpenAICompatibleProvider(GEMINI_BASE_URL, s.gemini_model, api_key=s.gemini_api_key,
                                            timeout=s.llm_timeout_seconds, max_tokens=s.gemini_max_tokens,
                                            reasoning_effort=s.gemini_reasoning_effort, name="gemini",
                                            require_key=True)
        return OpenAICompatibleProvider(s.llm_base_url, s.llm_model, api_key=s.llm_api_key,
                                        timeout=s.llm_timeout_seconds, max_tokens=s.llm_max_tokens,
                                        reasoning_effort=s.llm_reasoning_effort)
    return ExtractiveProvider()


def provider_from_settings(s: Settings):
    primary = build_provider(s.llm_provider, s)
    if primary.name == "extractive":
        return primary
    names = [s.llm_provider]
    if s.llm_fallback_provider not in ("none", "extractive", s.llm_provider):
        names.append(s.llm_fallback_provider)
    chain: list = []
    for name in names:
        chain += groq_chain(s) if name == "groq" else [build_provider(name, s)]
    if len(chain) == 1:
        return chain[0]  # the extractive answer is always the final safety net inside the orchestrator
    from app.llm.fallback import FallbackProvider

    return FallbackProvider(*chain, cooldown_seconds=s.llm_fallback_cooldown_seconds)


@lru_cache
def get_llm_provider():
    return provider_from_settings(get_settings())
