"""Anthropic Messages API provider (official `anthropic` SDK).

Manual tool loop (driven by the orchestrator) rather than the beta Tool Runner, because every tool
call must pass through CareFlow's own authorization/audit layer and evidence store. Assistant turns
are replayed with their original content blocks (thinking + tool_use) as the API requires.
Refusal fallbacks are enabled by default (server-side, `fallbacks: "default"`); disable with
CAREFLOW_ANTHROPIC_REFUSAL_FALLBACKS=false.
"""
import logging

import anthropic

from app.llm.base import ChatMessage, LLMError, LLMResult, LLMTimeoutError, ToolCall, ToolSpec

logger = logging.getLogger("careflow.llm")
DEFAULT_MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"
    supports_tools = True

    def __init__(self, model: str = "", api_key: str = "", timeout: float = 120.0, max_tokens: int = 16000,
                 effort: str | None = None, refusal_fallbacks: bool = True):
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max(max_tokens, 4000)  # adaptive thinking shares the output budget
        self.effort = effort
        self.refusal_fallbacks = refusal_fallbacks
        # api_key=None lets the SDK resolve ANTHROPIC_API_KEY / auth-token / profile credentials.
        self.client = anthropic.Anthropic(api_key=api_key or None, timeout=timeout, max_retries=2)

    @staticmethod
    def _messages(messages: list[ChatMessage]) -> list[dict]:
        out: list[dict] = []
        pending_results: list[dict] = []
        for m in messages:
            if m.role == "tool":
                pending_results.append({"type": "tool_result", "tool_use_id": m.tool_call_id,
                                        "content": m.content, "is_error": m.is_error})
                continue
            if pending_results:  # all results of one assistant turn go back in a single user message
                out.append({"role": "user", "content": pending_results})
                pending_results = []
            if m.role == "assistant":
                content = m.provider_raw if m.provider_raw is not None else (
                    ([{"type": "text", "text": m.content}] if m.content else [])
                    + [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in m.tool_calls])
                out.append({"role": "assistant", "content": content})
            else:
                out.append({"role": "user", "content": m.content})
        if pending_results:
            out.append({"role": "user", "content": pending_results})
        return out

    def chat(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
             max_tokens: int | None = None) -> LLMResult:
        kwargs: dict = {"model": self.model, "max_tokens": max(max_tokens or 0, self.max_tokens), "system": system,
                        "messages": self._messages(messages), "thinking": {"type": "adaptive"}}
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        if tools:
            kwargs["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters}
                               for t in tools]
        try:
            if self.refusal_fallbacks:
                resp = self.client.beta.messages.create(betas=[FALLBACK_BETA], extra_body={"fallbacks": "default"},
                                                        **kwargs)
            else:
                resp = self.client.messages.create(**kwargs)
        except anthropic.APITimeoutError as exc:
            raise LLMTimeoutError("The language model did not respond in time") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("The language model is rate limited - try again shortly") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMError("Anthropic credentials are missing or invalid") from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Anthropic API error", extra={"fields": {"status": exc.status_code}})
            raise LLMError(f"The language model service returned HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("The language model service is unreachable") from exc

        if resp.stop_reason == "refusal":
            return LLMResult(text="The language model declined to answer this request.", tool_calls=[],
                             model=resp.model, stop_reason="refusal")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        calls = [ToolCall(id=b.id, name=b.name, arguments=dict(b.input) if isinstance(b.input, dict) else {},
                          malformed=not isinstance(b.input, dict))
                 for b in resp.content if b.type == "tool_use"]
        return LLMResult(text=text, tool_calls=calls, model=resp.model, prompt_tokens=resp.usage.input_tokens,
                         completion_tokens=resp.usage.output_tokens, stop_reason=resp.stop_reason,
                         raw_content=resp.content)
