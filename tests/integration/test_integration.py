"""Integration tests for BASE_CLI.

Validates: All requirements
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_repl.builtin_commands import get_builtin_commands
from agent_repl.command_registry import CommandRegistry
from agent_repl.repl import REPLCore
from agent_repl.session import Session
from agent_repl.types import (
    AppContext,
    Config,
    ConversationTurn,
    SlashCommand,
    StreamEvent,
    StreamEventType,
    TokenStatistics,
)


def _make_app_context(tui=None):
    config = Config(app_name="test", app_version="1.0", default_model="m")
    session = Session()
    if tui is None:
        tui = MagicMock()
    cmd_reg = CommandRegistry()
    stats = TokenStatistics()
    for cmd in get_builtin_commands():
        cmd_reg.register(cmd)
    return AppContext(
        config=config, session=session, tui=tui,
        command_registry=cmd_reg, stats=stats,
    )


def _make_mock_agent(events=None):
    """Create a mock agent that yields predetermined stream events."""
    agent = MagicMock()

    async def mock_send(*args, **kwargs):
        for event in (events or []):
            yield event

    agent.send_message = mock_send
    agent.compact_history = AsyncMock(return_value="summary")
    return agent


class TestEndToEndREPLFlow:
    """Start App with mock agent, send free-text, verify streamed output."""

    @pytest.mark.asyncio
    async def test_free_text_produces_response(self):
        ctx = _make_app_context()
        ctx.tui.finish_stream.return_value = "Hello world!"
        events = [
            StreamEvent(type=StreamEventType.TEXT_DELTA, content="Hello "),
            StreamEvent(type=StreamEventType.TEXT_DELTA, content="world!"),
            StreamEvent(
                type=StreamEventType.USAGE,
                metadata={"input_tokens": 10, "output_tokens": 5},
            ),
        ]
        agent = _make_mock_agent(events)

        input_count = 0

        async def mock_input():
            nonlocal input_count
            input_count += 1
            if input_count == 1:
                return "Say hello"
            raise SystemExit(0)

        ctx.tui.read_input = mock_input

        repl = REPLCore(ctx, agent=agent)
        await repl.run_loop()

        # Verify streaming API was used
        ctx.tui.start_stream.assert_called_once()
        ctx.tui.finish_stream.assert_called_once()

        # Verify history has user + assistant turns
        history = ctx.session.get_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[1].content == "Hello world!"

        # Verify token stats
        assert ctx.stats.total_input_tokens == 10
        assert ctx.stats.total_output_tokens == 5


class TestBuiltinCommandFlow:
    """Test /help, /version, /quit flows."""

    @pytest.mark.asyncio
    async def test_help_quit_flow(self):
        ctx = _make_app_context()
        input_seq = ["/help", "/quit"]
        idx = 0

        async def mock_input():
            nonlocal idx
            if idx < len(input_seq):
                val = input_seq[idx]
                idx += 1
                return val
            raise EOFError

        ctx.tui.read_input = mock_input
        repl = REPLCore(ctx)
        await repl.run_loop()

        ctx.tui.display_text.assert_called_once()
        output = ctx.tui.display_text.call_args[0][0]
        assert "/help" in output


class TestFullCompactCycle:
    """Build multi-turn history, /compact, verify single summary turn."""

    @pytest.mark.asyncio
    async def test_compact_cycle(self):
        ctx = _make_app_context()
        # Pre-populate history
        ctx.session.add_turn(ConversationTurn(role="user", content="hello"))
        ctx.session.add_turn(ConversationTurn(role="assistant", content="hi"))
        ctx.session.add_turn(ConversationTurn(role="user", content="how are you"))
        ctx.session.add_turn(ConversationTurn(role="assistant", content="good"))

        # Register compact command
        def handle_compact(cmd_ctx):
            cmd_ctx.app_context.session.replace_with_summary("Conversation summary")
            cmd_ctx.app_context.tui.display_info("History compacted.")

        ctx.command_registry.register(
            SlashCommand(
                name="compact", description="Compact", help_text="",
                handler=handle_compact,
            )
        )

        repl = REPLCore(ctx)
        await repl.handle_input("/compact")

        history = ctx.session.get_history()
        assert len(history) == 1
        assert history[0].content == "Conversation summary"


class TestAtMentionFlow:
    """Create temp files, send input with @path, verify content reaches agent."""

    @pytest.mark.asyncio
    async def test_file_context_included(self, tmp_path: Path):
        ctx = _make_app_context()
        ctx.tui.finish_stream.return_value = "ok"
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        received_context = []

        async def capturing_send(message, file_context, history):
            received_context.extend(file_context)
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, content="ok")

        agent = MagicMock()
        agent.send_message = capturing_send

        repl = REPLCore(ctx, agent=agent)
        await repl.handle_input(f"explain @{test_file}")

        assert len(received_context) == 1
        assert received_context[0].content == "print('hello')"


class TestErrorRecovery:
    """Trigger agent failure, verify REPL stays alive."""

    @pytest.mark.asyncio
    async def test_agent_failure_doesnt_crash(self):
        ctx = _make_app_context()

        async def failing_send(*args, **kwargs):
            raise ConnectionError("network error")
            yield  # noqa: E501

        agent = MagicMock()
        agent.send_message = failing_send

        input_seq = ["test message", "/quit"]
        idx = 0

        async def mock_input():
            nonlocal idx
            if idx < len(input_seq):
                val = input_seq[idx]
                idx += 1
                return val
            raise EOFError

        ctx.tui.read_input = mock_input
        repl = REPLCore(ctx, agent=agent)
        await repl.run_loop()

        # Error was displayed but REPL continued to /quit
        ctx.tui.display_error.assert_called()


class TestUnknownCommandFlow:
    """Enter unregistered /foo, verify error and suggestion."""

    @pytest.mark.asyncio
    async def test_unknown_command_error(self):
        ctx = _make_app_context()
        repl = REPLCore(ctx)
        await repl.handle_input("/nonexistent")

        ctx.tui.display_error.assert_called_once()
        msg = ctx.tui.display_error.call_args[0][0]
        assert "Unknown command" in msg
        assert "/help" in msg
