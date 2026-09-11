"""Scripted LLM providers for deterministic tests of the orchestration layer.

These are test doubles for the *transport*; the orchestrator, tools, authorization, evidence and
grounding code under test are all real.
"""
from app.llm.base import ChatMessage, LLMError, LLMResult, LLMTimeoutError, ToolCall


class ScriptedLLM:
    """Returns queued responses in order and records every request it receives."""

    name = "scripted"
    model = "scripted-test-model"
    supports_tools = True

    def __init__(self, *responses: LLMResult):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def chat(self, system, messages: list[ChatMessage], tools=None, max_tokens=None) -> LLMResult:
        self.requests.append({"system": system, "messages": list(messages), "tools": tools})
        if not self.responses:
            return LLMResult(text="Done.", tool_calls=[], model=self.model)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def text(answer: str) -> LLMResult:
    return LLMResult(text=answer, tool_calls=[], model="scripted-test-model", prompt_tokens=100, completion_tokens=20)


def tool_call(name: str, **arguments) -> LLMResult:
    return LLMResult(text="", tool_calls=[ToolCall(id=f"call_{name}", name=name, arguments=arguments)],
                     model="scripted-test-model", prompt_tokens=80, completion_tokens=10)


def malformed_call(name: str) -> LLMResult:
    return LLMResult(text="", tool_calls=[ToolCall(id="bad", name=name, arguments={}, malformed=True)],
                     model="scripted-test-model")


FAILURE = LLMError("scripted outage")
TIMEOUT = LLMTimeoutError("scripted timeout")
