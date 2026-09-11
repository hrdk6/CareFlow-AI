"""Provider-neutral LLM interface used by the orchestrator."""
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.errors import ServiceUnavailableError


class LLMError(ServiceUnavailableError):
    code = "llm_unavailable"


class LLMTimeoutError(LLMError):
    code = "llm_timeout"


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    malformed: bool = False  # arguments were not valid JSON


@dataclass
class ChatMessage:
    role: str  # user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    tool_name: str | None = None
    is_error: bool = False
    provider_raw: Any = None  # provider-native assistant content, replayed verbatim (e.g. thinking blocks)


@dataclass
class LLMResult:
    text: str
    tool_calls: list[ToolCall]
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    stop_reason: str | None = None
    raw_content: Any = None


class LLMProvider(Protocol):
    name: str
    model: str
    supports_tools: bool

    def chat(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
             max_tokens: int | None = None) -> LLMResult: ...
