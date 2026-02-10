"""Core data types, protocols, and enums for agent_repl."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from agent_repl.command_registry import CommandRegistry
    from agent_repl.session import Session
    from agent_repl.tui import TUIShell


# --- Configuration ---


@dataclass
class Theme:
    prompt_color: str = "green"
    cli_output_color: str = "dim"
    agent_gutter_color: str = "blue"
    agent_text_color: str = ""
    tool_color: str = "cyan"
    tool_error_color: str = "red"


@dataclass
class Config:
    app_name: str
    app_version: str
    default_model: str
    agent_factory: Callable[[Config], AgentPlugin] | None = None
    plugins: list[str] = field(default_factory=list)
    theme: Theme = field(default_factory=Theme)


# --- Plugin Interface ---


@dataclass
class SlashCommand:
    name: str
    description: str
    help_text: str
    handler: Callable[[CommandContext], None]


class Plugin(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def get_commands(self) -> list[SlashCommand]: ...

    async def on_load(self, app_context: AppContext) -> None: ...

    async def on_unload(self) -> None: ...


# --- Agent Interface ---


class StreamEventType(Enum):
    TEXT_DELTA = "text_delta"
    TOOL_USE_START = "tool_use_start"
    TOOL_INPUT_DELTA = "tool_input_delta"
    TOOL_RESULT = "tool_result"
    USAGE = "usage"
    ERROR = "error"


@dataclass
class StreamEvent:
    type: StreamEventType
    content: str = ""
    metadata: dict = field(default_factory=dict)


class AgentPlugin(Plugin, Protocol):
    async def send_message(
        self,
        message: str,
        file_context: list[FileContent],
        history: list[ConversationTurn],
    ) -> AsyncIterator[StreamEvent]: ...

    async def compact_history(
        self,
        history: list[ConversationTurn],
    ) -> str: ...


# --- Session Types ---


@dataclass
class FileContent:
    path: str
    content: str


@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    content: str
    file_context: list[FileContent] = field(default_factory=list)
    tool_uses: list[dict] = field(default_factory=list)
    token_usage: TokenUsage | None = None


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TokenStatistics:
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def accumulate(self, usage: TokenUsage) -> None:
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens


# --- Input Parsing ---


class InputType(Enum):
    SLASH_COMMAND = "slash_command"
    FREE_TEXT = "free_text"


@dataclass
class ParsedInput:
    input_type: InputType
    raw: str
    command_name: str | None = None
    command_args: str | None = None
    at_mentions: list[str] = field(default_factory=list)


# --- Command Dispatch ---


@dataclass
class CommandContext:
    args: str
    app_context: AppContext


@dataclass
class AppContext:
    config: Config
    session: Session
    tui: TUIShell
    command_registry: CommandRegistry
    stats: TokenStatistics
