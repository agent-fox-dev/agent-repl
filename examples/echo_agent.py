"""Echo agent plugin for credential-free testing.

This module demonstrates implementing the AgentPlugin protocol with a simple
echo agent that repeats the user's message back. No external API credentials
or network access are required.

Usage:
    from examples.echo_agent import EchoAgentPlugin

    config = Config(agent_factory=EchoAgentPlugin)
    app = App(config=config)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agent_repl.types import (
    MessageContext,
    PluginContext,
    SlashCommand,
    StreamEvent,
    StreamEventType,
)


class EchoAgentPlugin:
    """An agent that echoes back the user's message.

    Implements the full AgentPlugin protocol without requiring any external
    credentials or network access. Useful for testing and development.
    """

    name: str = "Echo"
    description: str = "Echo agent for testing (no credentials required)"
    default_model: str = "echo-1.0"

    def get_commands(self) -> list[SlashCommand]:
        return []

    async def on_load(self, context: PluginContext) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return [f"model: {self.default_model}"]

    async def send_message(
        self, context: MessageContext
    ) -> AsyncIterator[StreamEvent]:
        """Echo the user's message back as a stream of events."""
        return self._echo_stream(context)

    async def _echo_stream(
        self, context: MessageContext
    ) -> AsyncIterator[StreamEvent]:
        """Generate echo response events."""
        # Include file context info if any
        parts: list[str] = []
        for fc in context.file_contexts:
            if fc.content is not None:
                parts.append(f"[File: {fc.path} ({len(fc.content)} chars)]")
            elif fc.error:
                parts.append(f"[File error: {fc.path}: {fc.error}]")

        # Echo the message
        echo_text = f"Echo: {context.message}"
        if parts:
            echo_text = "\n".join(parts) + "\n\n" + echo_text

        yield StreamEvent(
            type=StreamEventType.TEXT_DELTA,
            data={"text": echo_text},
        )

        # Report usage
        yield StreamEvent(
            type=StreamEventType.USAGE,
            data={
                "input_tokens": len(context.message.split()),
                "output_tokens": len(echo_text.split()),
            },
        )

    async def compact_history(self, session: Any) -> str:
        """Return a simple summary string."""
        history = session.get_history()
        turn_count = len(history)
        return f"Session summary: {turn_count} turns exchanged."


def create_plugin() -> EchoAgentPlugin:
    """Factory function for plugin loading."""
    return EchoAgentPlugin()
