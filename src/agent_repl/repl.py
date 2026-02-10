"""REPL core for agent_repl - main read-eval-print loop."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from agent_repl.file_context import resolve_file_context
from agent_repl.input_parser import parse_input
from agent_repl.stream_handler import handle_stream
from agent_repl.types import (
    CommandContext,
    ConversationTurn,
    InputType,
)

if TYPE_CHECKING:
    from agent_repl.types import AppContext

logger = logging.getLogger(__name__)


class REPLCore:
    """Main REPL loop - reads input, dispatches to commands or agent."""

    def __init__(self, app_context: AppContext, agent: object | None = None) -> None:
        self._ctx = app_context
        self._agent = agent
        self._agent_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._running = False

    async def run_loop(self) -> None:
        """Run the main REPL loop until exit."""
        self._running = True

        while self._running:
            try:
                raw_input = await self._ctx.tui.read_input()
                await self.handle_input(raw_input)
            except (EOFError, KeyboardInterrupt):
                # Ctrl+C or Ctrl+D with no agent running -> exit
                if self._agent_task is None or self._agent_task.done():
                    self._running = False
                else:
                    await self.cancel_agent()
            except SystemExit:
                self._running = False

    async def handle_input(self, raw_input: str) -> None:
        """Parse and dispatch a single input."""
        parsed = parse_input(raw_input)

        if parsed.input_type == InputType.SLASH_COMMAND:
            await self._dispatch_command(parsed.command_name or "", parsed.command_args or "")
        else:
            await self._dispatch_free_text(parsed.raw, parsed.at_mentions)

    async def _dispatch_command(self, name: str, args: str) -> None:
        """Look up and execute a slash command."""
        cmd = self._ctx.command_registry.get(name)
        if cmd is None:
            self._ctx.tui.display_error(
                f"Unknown command: /{name}. "
                "Type /help to see available commands, "
                "or press Enter to forward this to the agent."
            )
            return

        try:
            ctx = CommandContext(args=args, app_context=self._ctx)
            result = cmd.handler(ctx)
            # Support async handlers
            if asyncio.iscoroutine(result):
                await result
        except SystemExit:
            raise
        except Exception as e:
            self._ctx.tui.display_error(f"Command /{name} failed: {e}")

    async def _dispatch_free_text(self, text: str, at_mentions: list[str]) -> None:
        """Resolve file context and send to agent."""
        if not text.strip():
            return

        if self._agent is None or not hasattr(self._agent, "send_message"):
            self._ctx.tui.display_error("No agent configured.")
            return

        # Resolve file context from @mentions
        file_context = []
        if at_mentions:
            try:
                file_context = resolve_file_context(at_mentions)
            except Exception as e:
                self._ctx.tui.display_error(str(e))
                return

        # Add user turn to session
        user_turn = ConversationTurn(
            role="user",
            content=text,
            file_context=file_context,
        )
        self._ctx.session.add_turn(user_turn)

        # Send to agent and handle stream
        try:
            history = self._ctx.session.get_history()
            stream = self._agent.send_message(text, file_context, history)  # type: ignore[union-attr]

            self._agent_task = asyncio.current_task()
            await handle_stream(stream, self._ctx.tui, self._ctx.session, self._ctx.stats)
        except asyncio.CancelledError:
            self._ctx.tui.stop_spinner()
            self._ctx.tui.display_info("Agent request cancelled.")
        except Exception as e:
            self._ctx.tui.stop_spinner()
            self._ctx.tui.display_error(f"Agent error: {e}")
        finally:
            self._agent_task = None

    async def cancel_agent(self) -> None:
        """Cancel the currently running agent task."""
        if self._agent_task is not None and not self._agent_task.done():
            self._agent_task.cancel()
            self._ctx.tui.stop_spinner()
