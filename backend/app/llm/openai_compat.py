"""OpenAI-compatible chat-completions provider (Ollama, vLLM, LM Studio, OpenAI, Groq, ...)."""
import json
import logging

import httpx

from app.llm.base import ChatMessage, LLMError, LLMResult, LLMTimeoutError, ToolCall, ToolSpec

logger = logging.getLogger("careflow.llm")


class OpenAICompatibleProvider:
    name = "openai_compatible"
    supports_tools = True

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 120.0,
                 max_tokens: int = 1200, reasoning_effort: str | None = None):
        if not model:
            raise LLMError("CAREFLOW_LLM_MODEL must be set for the openai_compatible provider")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort

    @staticmethod
    def _messages(system: str, messages: list[ChatMessage]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            if m.role == "assistant":
                msg: dict = {"role": "assistant", "content": m.content or None}
                if m.tool_calls:
                    msg["tool_calls"] = [{"id": c.id, "type": "function",
                                          "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                                         for c in m.tool_calls]
                out.append(msg)
            elif m.role == "tool":
                out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
            else:
                out.append({"role": "user", "content": m.content})
        return out

    def chat(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
             max_tokens: int | None = None) -> LLMResult:
        payload: dict = {"model": self.model, "messages": self._messages(system, messages), "temperature": 0.1,
                         "max_tokens": max_tokens or self.max_tokens}
        if tools:
            payload["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                                  "parameters": t.parameters}} for t in tools]
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            resp = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"The language model did not respond within {self.timeout:.0f}s") from exc
        except httpx.HTTPError as exc:
            raise LLMError("The language model service is unreachable") from exc
        if resp.status_code >= 400:
            logger.warning("LLM HTTP error", extra={"fields": {"status": resp.status_code}})
            raise LLMError(f"The language model service returned HTTP {resp.status_code}")
        try:
            body = resp.json()
            choice = body["choices"][0]
            msg = choice["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError("The language model returned a malformed response") from exc
        calls = []
        for i, c in enumerate(msg.get("tool_calls") or []):
            fn = c.get("function", {})
            raw = fn.get("arguments") or "{}"
            try:
                args = raw if isinstance(raw, dict) else json.loads(raw)
                malformed = not isinstance(args, dict)
            except json.JSONDecodeError:
                args, malformed = {}, True
            calls.append(ToolCall(id=c.get("id") or f"call_{i}", name=fn.get("name", ""),
                                  arguments=args if isinstance(args, dict) else {}, malformed=malformed))
        usage = body.get("usage") or {}
        return LLMResult(text=(msg.get("content") or "").strip(), tool_calls=calls, model=body.get("model", self.model),
                         prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                         stop_reason=choice.get("finish_reason"))
