"""Cloud LLM providers (Groq primary, Gemini backup) and the fallback chain.

HTTP is exercised through httpx.MockTransport, so request payloads and error mapping are tested
without network access or real API keys.
"""
import json

import httpx
import pytest

from app.core.config import Settings
from app.llm.base import ChatMessage, LLMError, LLMTimeoutError, ToolSpec
from app.llm.fallback import FallbackProvider
from app.llm.openai_compat import OpenAICompatibleProvider
from app.llm.providers import GEMINI_BASE_URL, GROQ_BASE_URL, ExtractiveProvider, provider_from_settings
from tests.fakes import FAILURE, ScriptedLLM, text

OK_BODY = {"model": "openai/gpt-oss-120b", "choices": [{"finish_reason": "tool_calls", "message": {
    "content": None, "tool_calls": [{"id": "c1", "type": "function",
                                     "function": {"name": "get_patient", "arguments": '{"patient": "P1024"}'}}]}}],
    "usage": {"prompt_tokens": 50, "completion_tokens": 7}}


def groq(handler, api_key="gsk-test") -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(GROQ_BASE_URL, "openai/gpt-oss-120b", api_key=api_key, reasoning_effort="low",
                                    name="groq", require_key=True, max_tokens_field="max_completion_tokens",
                                    transport=httpx.MockTransport(handler))


def settings(**kw) -> Settings:
    base = {"environment": "test", "jwt_secret": "x" * 40, "groq_api_key": "gsk-test", "gemini_api_key": "gm-test"}
    return Settings(_env_file=None, **{**base, **kw})  # ignore the developer's backend/.env


def test_groq_request_payload_and_tool_call_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=OK_BODY)

    tool = ToolSpec("get_patient", "Look up a patient", {"type": "object", "properties": {}})
    r = groq(handler).chat("sys", [ChatMessage(role="user", content="hi")], tools=[tool])
    assert seen["url"] == f"{GROQ_BASE_URL}/chat/completions" and seen["auth"] == "Bearer gsk-test"
    body = seen["body"]
    assert body["model"] == "openai/gpt-oss-120b" and body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] > 0 and "max_tokens" not in body
    assert body["messages"][0] == {"role": "system", "content": "sys"} and body["tools"][0]["type"] == "function"
    assert r.provider == "groq" and r.prompt_tokens == 50
    assert r.tool_calls[0].name == "get_patient" and r.tool_calls[0].arguments == {"patient": "P1024"}


@pytest.mark.parametrize(("status", "fragment"), [(429, "rate limit"), (401, "rejected the API key"),
                                                  (503, "HTTP 503")])
def test_http_errors_become_llm_errors(status, fragment):
    with pytest.raises(LLMError, match=fragment):
        groq(lambda req: httpx.Response(status, json={"error": {"message": "nope"}})).chat("s", [])


def test_timeout_and_malformed_response():
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMTimeoutError):
        groq(slow).chat("s", [])
    with pytest.raises(LLMError, match="malformed"):
        groq(lambda req: httpx.Response(200, json={"unexpected": True})).chat("s", [])


def test_missing_key_fails_fast_without_a_network_call():
    calls = []
    p = groq(lambda req: calls.append(req) or httpx.Response(200, json=OK_BODY), api_key="")
    with pytest.raises(LLMError, match="API key is not configured"):
        p.chat("s", [])
    assert calls == [] and p.probe() is False


def named(name: str, *responses) -> ScriptedLLM:
    llm = ScriptedLLM(*responses)
    llm.name = name
    return llm


def test_fallback_uses_backup_when_primary_fails_and_reports_why():
    primary, backup = named("groq", FAILURE), named("gemini", text("backup answer"))
    r = FallbackProvider(primary, backup).chat("s", [])
    assert r.text == "backup answer" and r.provider == "gemini" and "scripted outage" in r.fallback_reason
    assert len(primary.requests) == 1 and len(backup.requests) == 1


def test_fallback_not_used_when_primary_succeeds():
    backup = named("gemini")
    r = FallbackProvider(named("groq", text("primary answer")), backup).chat("s", [])
    assert r.provider == "groq" and r.fallback_reason is None and backup.requests == []


def test_fallback_cooldown_skips_a_failing_primary_then_retries_it():
    now = [0.0]
    primary = named("groq", FAILURE, text("primary is back"))
    fb = FallbackProvider(primary, named("gemini", text("b1"), text("b2")), cooldown_seconds=30, clock=lambda: now[0])
    assert fb.chat("s", []).text == "b1"
    now[0] = 10.0
    assert fb.chat("s", []).text == "b2" and len(primary.requests) == 1  # still cooling down: primary skipped
    now[0] = 31.0
    r = fb.chat("s", [])
    assert r.text == "primary is back" and r.provider == "groq" and len(primary.requests) == 2


def test_backup_failure_during_cooldown_retries_the_primary():
    now = [0.0]
    primary = named("groq", FAILURE, text("primary recovered"))
    fb = FallbackProvider(primary, named("gemini", text("b1"), FAILURE), cooldown_seconds=30, clock=lambda: now[0])
    assert fb.chat("s", []).text == "b1"
    now[0] = 5.0  # primary still cooling down, backup now fails (e.g. HTTP 503)
    r = fb.chat("s", [])
    assert r.text == "primary recovered" and r.provider == "groq" and r.fallback_reason is None


def test_both_providers_failing_propagates_llm_error():
    with pytest.raises(LLMError):
        FallbackProvider(named("groq", FAILURE), named("gemini", FAILURE)).chat("s", [])


def test_chain_tries_each_provider_in_order():
    first, second, third = named("groq", FAILURE), named("groq", FAILURE), named("gemini", text("third"))
    r = FallbackProvider(first, second, third).chat("s", [])
    assert r.text == "third" and r.provider == "gemini" and "scripted outage" in r.fallback_reason
    assert len(first.requests) == len(second.requests) == len(third.requests) == 1


def test_factory_builds_groq_model_chain_then_gemini():
    p = provider_from_settings(settings(llm_provider="groq", llm_fallback_provider="gemini"))
    assert isinstance(p, FallbackProvider) and p.name == "groq" and p.supports_tools
    assert [(q.name, q.model) for q in p.providers] == [
        ("groq", "openai/gpt-oss-120b"), ("groq", "qwen/qwen3.8-27b"), ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash")]
    groq_primary, qwen, gemini = p.providers[0], p.providers[1], p.providers[-1]
    assert groq_primary.base_url == GROQ_BASE_URL and groq_primary.api_key == "gsk-test"
    assert groq_primary.max_tokens_field == "max_completion_tokens" and groq_primary.timeout == 20.0
    # each model gets a reasoning_effort value its API accepts (gpt-oss rejects "none", Qwen rejects "low")
    assert groq_primary.reasoning_effort == "low" and qwen.reasoning_effort == "none"
    assert gemini.base_url == GEMINI_BASE_URL and gemini.api_key == "gm-test"


def test_factory_without_backup_or_with_extractive():
    single = settings(llm_provider="groq", groq_fallback_models="")
    assert not isinstance(provider_from_settings(single), FallbackProvider)
    same = settings(llm_provider="groq", groq_fallback_models="", llm_fallback_provider="groq")
    assert not isinstance(provider_from_settings(same), FallbackProvider)
    assert isinstance(provider_from_settings(settings(llm_provider="extractive", llm_fallback_provider="gemini")),
                      ExtractiveProvider)


def test_standard_key_names_are_accepted(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "from-groq-env")
    monkeypatch.setenv("GEMINI_API_KEY", "from-gemini-env")
    s = Settings(_env_file=None, environment="test", jwt_secret="x" * 40)
    assert s.groq_api_key == "from-groq-env" and s.gemini_api_key == "from-gemini-env"
