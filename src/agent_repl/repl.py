from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent_repl.exceptions import QuitRequestedError
from agent_repl.file_context import resolve_mentions
from agent_repl.input_parser import ParsedCommand, ParsedFreeText, parse_input
from agent_repl.stream_handler import StreamHandler
from agent_repl.types import CommandContext, ConversationTurn, MessageContext

if TYPE_CHECKING:
    from agent_repl.command_registry import CommandRegistry
    from agent_repl.plugin_registry import PluginRegistry
    from agent_repl.session import Session
    from agent_repl.tui import TUIShell
    from agent_repl.types import Config

logger = logging.getLogger(__name__)


class REPL:
    """Main read-eval-print loop.

    Reads user input, classifies it as a slash command or free text,
    dispatches accordingly, and handles errors gracefully.
    """

    def __init__(
        self,
        session: Session,
        tui: TUIShell,
        command_registry: CommandRegistry,
        plugin_registry: PluginRegistry,
        config: Config,
    ) -> None:
        self._session = session
        self._tui = tui
        self._command_registry = command_registry
        self._plugin_registry = plugin_registry
        self._config = config
        self._stream_handler = StreamHandler(tui, session)

    async def run(self) -> None:
        """Run the REPL loop until exit."""
        while True:
            try:
                raw = await self._tui.prompt_input()
            except (KeyboardInterrupt, EOFError):
                break

            parsed = parse_input(raw)
            if parsed is None:
                continue

            try:
                if isinstance(parsed, ParsedCommand):
                    await self._handle_command(parsed)
                elif isinstance(parsed, ParsedFreeText):
                    await self._handle_free_text(parsed)
            except QuitRequestedError:
                break

    async def _handle_command(self, parsed: ParsedCommand) -> None:
        """Dispatch a slash command to its registered handler."""
        cmd = self._command_registry.get(parsed.name)
        if cmd is None:
            self._tui.show_error(f"Unknown command: /{parsed.name}")
            return

        ctx = CommandContext(
            args=parsed.args,
            session=self._session,
            tui=self._tui,
            config=self._config,
            registry=self._command_registry,
            plugin_registry=self._plugin_registry,
        )
        try:
            await cmd.handler(ctx)
        except QuitRequestedError:
            raise
        except Exception as e:
            self._tui.show_error(f"Command error: {e}")

    async def _handle_free_text(self, parsed: ParsedFreeText) -> None:
        """Forward free text to the active agent."""
        agent = self._plugin_registry.active_agent
        if agent is None:
            self._tui.show_error("No agent configured.")
            return

        # Resolve @path mentions
        file_contexts = resolve_mentions(
            parsed.mentions, self._config.max_file_size
        )

        # Build message context
        msg_ctx = MessageContext(
            message=parsed.text,
            file_contexts=file_contexts,
            history=self._session.get_history(),
        )

        # Record user turn
        self._session.add_turn(
            ConversationTurn(
                role="user",
                content=parsed.text,
                file_contexts=file_contexts,
            )
        )

        # Send to agent and stream response
        try:
            stream = await agent.send_message(msg_ctx)
            await self._stream_handler.handle_stream(stream)
        except KeyboardInterrupt:
            self._tui.show_info("Cancelled.")
        except Exception as e:
            self._tui.show_error(f"Agent error: {e}")
