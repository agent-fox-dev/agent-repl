from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from agent_repl.exceptions import AgentError
from agent_repl.types import (
    CommandContext,
    PluginContext,
    SlashCommand,
    StreamEvent,
    StreamEventType,
)

if TYPE_CHECKING:
    from agent_repl.types import MessageContext

logger = logging.getLogger(__name__)

# Try to import the SDK; set flag for graceful degradation (Req 11.E1)
try:
    import claude_agent_sdk as sdk

    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False
    logger.warning(
        "claude-agent-sdk is not installed. Claude agent will not be available. "
        "Install with: pip install claude-agent-sdk"
    )

_DEFAULT_MODEL = "claude-opus-4-6"

_AUTH_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_BEDROCK",
)

_AUTH_INSTRUCTIONS = (
    "No Claude authentication configured. Set one of:\n"
    "  ANTHROPIC_API_KEY=<key>   (direct Anthropic API)\n"
    "  CLAUDE_CODE_USE_VERTEX=1  (Google Vertex AI)\n"
    "  CLAUDE_CODE_USE_BEDROCK=1 (Amazon Bedrock)"
)


def _check_auth() -> None:
    """Validate that authentication credentials are configured."""
    if any(os.environ.get(var) for var in _AUTH_ENV_VARS):
        return
    raise AgentError(_AUTH_INSTRUCTIONS)


def _build_prompt(context: MessageContext) -> str:
    """Build a prompt string from the message and file contexts."""
    parts: list[str] = []

    # Include file contexts
    for fc in context.file_contexts:
        if fc.content is not None:
            parts.append(f"<file path=\"{fc.path}\">\n{fc.content}\n</file>")
        elif fc.error is not None:
            parts.append(f"[File {fc.path}: {fc.error}]")

    # Add the user's message
    parts.append(context.message)

    return "\n\n".join(parts)


class ClaudeAgentPlugin:
    """Default Claude agent plugin using claude-agent-sdk."""

    name: str = "Claude"
    description: str = "Anthropic Claude agent via claude-agent-sdk"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or _DEFAULT_MODEL
        self._session_started = False
        self._plugin_ctx: PluginContext | None = None
        self._tool_names: dict[str, str] = {}  # tool_use_id → tool_name

    @property
    def default_model(self) -> str:
        return self._model

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(
                name="clear",
                description="Clear conversation history",
                handler=_handle_clear,
                cli_exposed=True,
            ),
            SlashCommand(
                name="compact",
                description="Summarize and compact conversation history",
                handler=_handle_compact,
                cli_exposed=True,
            ),
        ]

    async def on_load(self, context: PluginContext) -> None:
        """Validate SDK and authentication on load."""
        if not _SDK_AVAILABLE:
            raise AgentError(
                "claude-agent-sdk is not installed. "
                "Install with: pip install claude-agent-sdk"
            )
        _check_auth()
        self._plugin_ctx = context

    async def on_unload(self) -> None:
        self._session_started = False
        self._plugin_ctx = None

    def get_status_hints(self) -> list[str]:
        return [f"model: {self._model}"]

    async def send_message(
        self, context: MessageContext
    ) -> AsyncIterator[StreamEvent]:
        """Send a message and return a stream of events."""
        prompt = _build_prompt(context)
        return self._stream_from_query(prompt)

    async def _stream_from_query(self, prompt: str) -> AsyncIterator[StreamEvent]:
        """Run the SDK query and translate messages to StreamEvents."""
        options = sdk.ClaudeAgentOptions(
            model=self._model,
            continue_conversation=self._session_started,
        )

        try:
            async for msg in sdk.query(prompt=prompt, options=options):
                for event in self._translate_message(msg):
                    yield event
        except sdk.ClaudeSDKError as e:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": str(e), "fatal": True},
            )

        self._session_started = True

    def _translate_message(self, msg: Any) -> list[StreamEvent]:
        """Translate a single SDK message to zero or more StreamEvents."""
        events: list[StreamEvent] = []

        if isinstance(msg, sdk.AssistantMessage):
            # Check for error field (11.E3)
            if msg.error is not None:
                fatal = msg.error in ("authentication_failed", "billing_error")
                events.append(
                    StreamEvent(
                        type=StreamEventType.ERROR,
                        data={"message": msg.error, "fatal": fatal},
                    )
                )
                return events

            # Update model from response
            if msg.model:
                self._model = msg.model

            for block in msg.content:
                if isinstance(block, sdk.TextBlock):
                    events.append(
                        StreamEvent(
                            type=StreamEventType.TEXT_DELTA,
                            data={"text": block.text},
                        )
                    )
                elif isinstance(block, sdk.ToolUseBlock):
                    self._tool_names[block.id] = block.name
                    events.append(
                        StreamEvent(
                            type=StreamEventType.TOOL_USE_START,
                            data={"name": block.name, "id": block.id},
                        )
                    )

        elif isinstance(msg, sdk.UserMessage):
            if isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, sdk.ToolResultBlock):
                        tool_name = self._tool_names.get(
                            block.tool_use_id, "unknown"
                        )
                        content_str = (
                            block.content
                            if isinstance(block.content, str)
                            else str(block.content or "")
                        )
                        events.append(
                            StreamEvent(
                                type=StreamEventType.TOOL_RESULT,
                                data={
                                    "name": tool_name,
                                    "id": block.tool_use_id,
                                    "result": content_str,
                                    "is_error": bool(block.is_error),
                                },
                            )
                        )

        elif isinstance(msg, sdk.ResultMessage):
            if msg.usage:
                events.append(
                    StreamEvent(
                        type=StreamEventType.USAGE,
                        data={
                            "input_tokens": msg.usage.get("input_tokens", 0),
                            "output_tokens": msg.usage.get("output_tokens", 0),
                        },
                    )
                )

        return events

    async def compact_history(self, session: Any) -> str:
        """Summarize conversation history by querying the agent."""
        history = session.get_history()
        if not history:
            return ""

        summary_parts: list[str] = []
        turns_text = "\n".join(
            f"{t.role}: {t.content}" for t in history if t.content
        )
        prompt = (
            "Please provide a concise summary of the following conversation. "
            "Capture the key topics, decisions, and context:\n\n"
            f"{turns_text}"
        )

        options = sdk.ClaudeAgentOptions(model=self._model)

        async for msg in sdk.query(prompt=prompt, options=options):
            if isinstance(msg, sdk.AssistantMessage):
                for block in msg.content:
                    if isinstance(block, sdk.TextBlock):
                        summary_parts.append(block.text)

        return "".join(summary_parts)


# --- Command Handlers ---


async def _handle_clear(ctx: CommandContext) -> None:
    """Clear conversation history."""
    ctx.session.clear()
    ctx.tui.show_info("Conversation history cleared.")


async def _handle_compact(ctx: CommandContext) -> None:
    """Summarize and compact conversation history."""
    agent = ctx.plugin_registry.active_agent
    if agent is None or not isinstance(agent, ClaudeAgentPlugin):
        ctx.tui.show_info("No agent available for compaction.")
        return

    ctx.tui.show_info("Compacting conversation history...")
    try:
        summary = await agent.compact_history(ctx.session)
        if summary:
            ctx.session.replace_with_summary(summary)
            ctx.tui.show_info("History compacted.")
        else:
            ctx.tui.show_info("No history to compact.")
    except Exception as e:
        ctx.tui.show_error(f"Compact failed: {e}")


def create_plugin(model: str | None = None) -> ClaudeAgentPlugin:
    """Factory function for plugin loading."""
    return ClaudeAgentPlugin(model=model)
