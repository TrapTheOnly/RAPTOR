from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class Turn:
    stop_reason: str
    content: list[Any]
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class LlmClient(Protocol):
    protocol: str
    display_name: str
    model_id: str

    def complete(
        self,
        *,
        system: list[dict],
        tools: list[dict],
        messages: list[dict],
        max_tokens: int,
        thinking_budget_tokens: int,
    ) -> Turn: ...

    def count_tokens(
        self,
        *,
        system: list[dict],
        tools: list[dict],
        messages: list[dict],
    ) -> int | None: ...
