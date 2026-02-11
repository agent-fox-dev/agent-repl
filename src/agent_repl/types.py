from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class StreamEventType(Enum):
    TEXT_DELTA = "text_delta"
    TOOL_USE_START = "tool_use_start"
    TOOL_RESULT = "tool_result"
    USAGE = "usage"
    ERROR = "error"


@dataclass(frozen=True)
class Theme:
    prompt_color: str = "green"
    gutter_color: str = "blue"
    error_color: str = "red"
    info_color: str = "cyan"


@dataclass(frozen=True)
class StreamEvent:
    type: StreamEventType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class FileContext:
    path: str
    content: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ToolUse:
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    is_error: bool = False


@dataclass
class ConversationTurn:
    role: str
    content: str
    file_contexts: list[FileContext] = field(default_factory=list)
    tool_uses: list[ToolUse] = field(default_factory=list)
    usage: TokenUsage | None = None


@dataclass
class SlashCommand:
    name: str
    description: str
    handler: Callable[[CommandContext], Awaitable[None]]
    cli_exposed: bool = False
    pinned: bool = False


@dataclass
class Config:
    app_name: str = "agent_repl"
    app_version: str = "0.1.0"
    theme: Theme = field(default_factory=Theme)
    agent_factory: Callable[..., AgentPlugin] | None = None
    plugins: list[str] = field(default_factory=list)
    pinned_commands: list[str] = field(default_factory=lambda: ["help", "quit"])
    max_pinned_display: int = 6
    max_file_size: int = 512_000
    cli_commands: list[str] = field(default_factory=list)


@dataclass
class SpawnConfig:
    prompt: str
    pre_hook: Callable[[], None] | None = None
    post_hook: Callable[[], None] | None = None


@dataclass
class MessageContext:
    message: str
    file_contexts: list[FileContext] = field(default_factory=list)
    history: list[ConversationTurn] = field(default_factory=list)


@dataclass
class CommandContext:
    args: str
    argv: list[str] = field(default_factory=list)
    session: Any = None
    tui: Any = None
    config: Config = field(default_factory=Config)
    registry: Any = None
    plugin_registry: Any = None


@dataclass
class PluginContext:
    config: Config = field(default_factory=Config)
    session: Any = None
    tui: Any = None
    registry: Any = None


@runtime_checkable
class Plugin(Protocol):
    name: str
    description: str

    def get_commands(self) -> list[SlashCommand]: ...
    async def on_load(self, context: PluginContext) -> None: ...
    async def on_unload(self) -> None: ...
    def get_status_hints(self) -> list[str]: ...


@runtime_checkable
class AgentPlugin(Plugin, Protocol):
    default_model: str

    async def send_message(self, context: MessageContext) -> AsyncIterator[StreamEvent]: ...
    async def compact_history(self, session: Any) -> str: ...
