"""LLM provider factory. The provider is configuration (CAREFLOW_LLM_PROVIDER), not code."""
from functools import lru_cache

from app.core.config import get_settings


class ExtractiveProvider:
    """No language model: answers are assembled deterministically from retrieved evidence.

    Used when no LLM is configured or reachable. It never generates free text beyond templates and
    verbatim extracted sentences, so it cannot hallucinate - but it also cannot reason or compare.
    """

    name = "extractive"
    model = None
    supports_tools = False


@lru_cache
def get_llm_provider():
    s = get_settings()
    if s.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=s.llm_model, api_key=s.anthropic_api_key, timeout=s.llm_timeout_seconds,
                                 max_tokens=s.llm_max_tokens, effort=s.anthropic_effort,
                                 refusal_fallbacks=s.anthropic_refusal_fallbacks)
    if s.llm_provider == "openai_compatible":
        from app.llm.openai_compat import OpenAICompatibleProvider

        return OpenAICompatibleProvider(base_url=s.llm_base_url, model=s.llm_model, api_key=s.llm_api_key,
                                        timeout=s.llm_timeout_seconds, max_tokens=s.llm_max_tokens,
                                        reasoning_effort=s.llm_reasoning_effort)
    return ExtractiveProvider()
