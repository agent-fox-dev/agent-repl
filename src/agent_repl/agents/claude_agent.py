"""Claude agent plugin for agent_repl - default AI agent using the Claude Code SDK."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from claude_code_sdk import (
    AssistantMessage,
    CLIConnectionError,
    CLINotFoundError,
    CLIJSONDecodeError,
    ClaudeCodeOptions,
    ClaudeSDKClient,
    ProcessError,
    ResultMessage,
    TextBlock,
)

from agent_repl.constants import DEFAULT_CLAUDE_MODEL
from agent_repl.exceptions import AgentError
from agent_repl.types import (
    CommandContext,
    ConversationTurn,
    FileContent,
    SlashCommand,
    StreamEvent,
    StreamEventType,
)

if TYPE_CHECKING:
    from agent_repl.types import AppContext


def _use_vertex() -> bool:
    """Return True if Vertex AI auth is selected (CLAUDE_CODE_USE_VERTEX + ANTHROPIC_VERTEX_PROJECT_ID)."""
    if os.environ.get("CLAUDE_CODE_USE_VERTEX", "").strip().lower() not in ("1", "true", "yes"):
        return False
    return bool(os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "").strip())


def _use_api_key() -> bool:
    """Return True if Anthropic API key auth is selected (ANTHROPIC_API_KEY set)."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _create_client(model: str):  # type: ignore[no-untyped-def]
    """Create client from environment using claude_code_sdk. Auth: Vertex (CLAUDE_CODE_USE_VERTEX, ANTHROPIC_VERTEX_PROJECT_ID, CLOUD_ML_REGION) or API key (ANTHROPIC_API_KEY)."""
    if not _use_vertex() and not _use_api_key():
        raise AgentError(
            "No Claude authentication configured. "
            "For Vertex AI set CLAUDE_CODE_USE_VERTEX=1, ANTHROPIC_VERTEX_PROJECT_ID, and optionally CLOUD_ML_REGION. "
            "For the API set ANTHROPIC_API_KEY."
        )
    options = ClaudeCodeOptions(model=model)
    return ClaudeSDKClient(options=options)


class ClaudeAgentPlugin:
    """Agent plugin that integrates with Claude via the Claude Code SDK."""

    def __init__(self, model: str = DEFAULT_CLAUDE_MODEL) -> None:
        self._model = model
        self._app_context: AppContext | None = None
        self._client = _create_client(model)

    @property
    def name(self) -> str:
        return "claude"

    @property
    def description(self) -> str:
        return "Claude AI agent powered by Claude Code SDK"

    def get_commands(self) -> list[SlashCommand]:
        """Return /clear and /compact commands."""
        return [
            SlashCommand(
                name="clear",
                description="Clear conversation history",
                help_text="Reset the conversation history to empty.",
                handler=self._handle_clear,
            ),
            SlashCommand(
                name="compact",
                description="Compact conversation history",
                help_text="Summarize and replace the conversation history.",
                handler=self._handle_compact,
            ),
        ]

    async def on_load(self, app_context: AppContext) -> None:
        self._app_context = app_context

    async def on_unload(self) -> None:
        pass

    async def send_message(
        self,
        message: str,
        file_context: list[FileContent],
        history: list[ConversationTurn],
    ) -> AsyncIterator[StreamEvent]:
        """Send a message to Claude and yield stream events."""
        prompt = self._build_prompt_string(history, message, file_context)

        try:
            async with self._client:
                await self._client.query(prompt)
                async for msg in self._client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                yield StreamEvent(
                                    type=StreamEventType.TEXT_DELTA,
                                    content=block.text,
                                )
                    elif isinstance(msg, ResultMessage) and getattr(msg, "usage", None):
                        usage = msg.usage or {}
                        yield StreamEvent(
                            type=StreamEventType.USAGE,
                            metadata={
                                "input_tokens": usage.get("input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                            },
                        )
        except (CLINotFoundError, CLIConnectionError) as e:
            raise AgentError(
                f"Claude Code connection failed: {e}. "
                "Ensure Claude Code CLI is installed and auth is set (ANTHROPIC_API_KEY or Vertex env vars)."
            )
        except ProcessError as e:
            raise AgentError(f"Claude Code process failed: {e}")
        except CLIJSONDecodeError as e:
            raise AgentError(f"Invalid response from Claude Code: {e}")

    async def compact_history(
        self,
        history: list[ConversationTurn],
    ) -> str:
        """Summarize the conversation history using Claude."""
        prompt = self._build_prompt_string(
            history,
            "Please provide a concise summary of our conversation so far. "
            "Focus on key topics, decisions, and context that would be needed "
            "to continue the conversation.",
            [],
        )

        try:
            async with self._client:
                await self._client.query(prompt)
                parts: list[str] = []
                async for msg in self._client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                parts.append(block.text)
                return "".join(parts).strip() or "(No summary generated)"
        except (CLINotFoundError, CLIConnectionError) as e:
            raise AgentError(
                f"Authentication/connection failed: {e}. "
                "Ensure Claude Code CLI is installed and auth is set (ANTHROPIC_API_KEY or Vertex env vars)."
            )
        except ProcessError as e:
            raise AgentError(f"Compaction failed: {e}")
        except Exception as e:
            raise AgentError(f"Compaction failed: {e}")

    def _build_prompt_string(
        self,
        history: list[ConversationTurn],
        current_message: str,
        file_context: list[FileContent],
    ) -> str:
        """Build a single prompt string (history as context + current message) for the Claude Code SDK."""
        parts: list[str] = []
        for turn in history:
            prefix = "User: " if turn.role == "user" else "Assistant: "
            parts.append(prefix + turn.content)
        content = current_message
        if file_context:
            context_parts = []
            for fc in file_context:
                context_parts.append(f"<file path=\"{fc.path}\">\n{fc.content}\n</file>")
            content = "\n\n".join(context_parts) + "\n\n" + content
        parts.append("User: " + content)
        return "\n\n".join(parts)

    def _handle_clear(self, ctx: CommandContext) -> None:
        """Handle /clear command."""
        ctx.app_context.session.clear()
        ctx.app_context.tui.display_info("Conversation history cleared.")

    def _handle_compact(self, ctx: CommandContext) -> None:
        """Handle /compact command - this is sync but calls async internally."""
        import asyncio

        async def _do_compact() -> None:
            history = ctx.app_context.session.get_history()
            if not history:
                ctx.app_context.tui.display_info("Nothing to compact.")
                return
            try:
                summary = await self.compact_history(history)
                ctx.app_context.session.replace_with_summary(summary)
                ctx.app_context.tui.display_info("History compacted.")
            except AgentError as e:
                ctx.app_context.tui.display_error(str(e))

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_do_compact())
        else:
            loop.run_until_complete(_do_compact())
