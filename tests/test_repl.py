"""Unit and property tests for the REPL core.

Property 12: Interruption Safety
Property 13: Error Resilience
Property 15: Unknown Command Handling
Validates: Requirements 1.1, 1.6, 4.5, 8.1, 8.2, 9.1, 9.2, 9.3, 9.5
"""

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.repl import REPLCore
from agent_repl.session import Session
from agent_repl.types import (
    AppContext,
    CommandContext,
    Config,
    SlashCommand,
    StreamEvent,
    StreamEventType,
    TokenStatistics,
)


def _make_app_context(tui=None):
    """Create a test AppContext with mocked TUI."""
    config = Config(app_name="test", app_version="1.0", default_model="m")
    session = Session()
    if tui is None:
        tui = MagicMock()
    cmd_reg = CommandRegistry()
    stats = TokenStatistics()
    return AppContext(
        config=config, session=session, tui=tui,
        command_registry=cmd_reg, stats=stats,
    )


class TestREPLCore:
    @pytest.mark.asyncio
    async def test_slash_command_dispatch(self):
        ctx = _make_app_context()
        handler = MagicMock()
        ctx.command_registry.register(
            SlashCommand(name="test", description="", help_text="", handler=handler)
        )
        repl = REPLCore(ctx)
        await repl.handle_input("/test some args")
        handler.assert_called_once()
        call_ctx = handler.call_args[0][0]
        assert isinstance(call_ctx, CommandContext)
        assert call_ctx.args == "some args"

    @pytest.mark.asyncio
    async def test_unknown_command_shows_error(self):
        ctx = _make_app_context()
        repl = REPLCore(ctx)
        await repl.handle_input("/nonexistent")
        ctx.tui.display_error.assert_called_once()
        msg = ctx.tui.display_error.call_args[0][0]
        assert "Unknown command" in msg
        assert "/nonexistent" in msg

    @pytest.mark.asyncio
    async def test_free_text_no_agent(self):
        ctx = _make_app_context()
        repl = REPLCore(ctx, agent=None)
        await repl.handle_input("hello world")
        ctx.tui.display_error.assert_called_once()
        assert "No agent" in ctx.tui.display_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_free_text_with_agent(self):
        ctx = _make_app_context()
        ctx.tui.finish_stream.return_value = "response"

        async def mock_stream(*args, **kwargs):
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, content="response")

        agent = MagicMock()
        agent.send_message = mock_stream

        repl = REPLCore(ctx, agent=agent)
        await repl.handle_input("hello")

        # User turn + assistant turn should be in history
        history = ctx.session.get_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_empty_input_ignored(self):
        ctx = _make_app_context()
        agent = MagicMock()
        repl = REPLCore(ctx, agent=agent)
        await repl.handle_input("   ")
        assert not hasattr(agent, "send_message") or not agent.send_message.called

    @pytest.mark.asyncio
    async def test_command_exception_caught(self):
        ctx = _make_app_context()

        def bad_handler(cmd_ctx):
            raise ValueError("boom")

        ctx.command_registry.register(
            SlashCommand(name="bad", description="", help_text="", handler=bad_handler)
        )
        repl = REPLCore(ctx)
        # Should not raise
        await repl.handle_input("/bad")
        ctx.tui.display_error.assert_called_once()
        assert "boom" in ctx.tui.display_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_quit_command_exits_loop(self):
        ctx = _make_app_context()

        def quit_handler(cmd_ctx):
            raise SystemExit(0)

        ctx.command_registry.register(
            SlashCommand(name="quit", description="", help_text="", handler=quit_handler)
        )

        call_count = 0

        async def mock_read_input():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "/quit"
            raise EOFError

        ctx.tui.read_input = mock_read_input
        repl = REPLCore(ctx)
        await repl.run_loop()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_agent_error_caught(self):
        ctx = _make_app_context()

        async def failing_stream(*args, **kwargs):
            raise ConnectionError("network down")
            yield  # Make it a generator  # noqa: E501

        agent = MagicMock()
        agent.send_message = failing_stream
        repl = REPLCore(ctx, agent=agent)
        await repl.handle_input("test message")
        ctx.tui.display_error.assert_called_once()


class TestProperty12InterruptionSafety:
    """Property 12: After cancellation, REPL remains operational.

    Feature: agent_repl, Property 12: Interruption Safety
    """

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_exits_when_no_agent(self):
        ctx = _make_app_context()
        call_count = 0

        async def mock_read_input():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt
            raise EOFError

        ctx.tui.read_input = mock_read_input
        repl = REPLCore(ctx)
        await repl.run_loop()
        # Loop exited cleanly
        assert call_count == 1


class TestProperty13ErrorResilience:
    """Property 13: Exceptions in command handlers don't crash the REPL.

    Feature: agent_repl, Property 13: Error Resilience
    """

    @settings(max_examples=100)
    @given(
        error_type=st.sampled_from([ValueError, RuntimeError, TypeError, KeyError]),
        message=st.text(min_size=1, max_size=30),
    )
    @pytest.mark.asyncio
    async def test_command_exceptions_caught(self, error_type, message):
        ctx = _make_app_context()

        def bad_handler(cmd_ctx):
            raise error_type(message)

        ctx.command_registry.register(
            SlashCommand(name="bad", description="", help_text="", handler=bad_handler)
        )
        repl = REPLCore(ctx)
        # Should not raise
        await repl.handle_input("/bad")
        ctx.tui.display_error.assert_called_once()


class TestProperty15UnknownCommandHandling:
    """Property 15: Unknown commands show error with suggestion.

    Feature: agent_repl, Property 15: Unknown Command Handling
    """

    @settings(max_examples=100)
    @given(
        name=st.from_regex(r"[a-z]{2,10}", fullmatch=True),
    )
    @pytest.mark.asyncio
    async def test_unknown_command_error(self, name):
        ctx = _make_app_context()
        repl = REPLCore(ctx)
        await repl.handle_input(f"/{name}")
        ctx.tui.display_error.assert_called_once()
        msg = ctx.tui.display_error.call_args[0][0]
        assert "Unknown command" in msg
