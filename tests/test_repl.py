"""Tests for repl module.

Covers Requirements 1.1-1.8, 1.E1-1.E3, Property 18.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.exceptions import QuitRequestedError
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.repl import REPL
from agent_repl.session import Session
from agent_repl.types import (
    CommandContext,
    Config,
    MessageContext,
    SlashCommand,
    StreamEvent,
    StreamEventType,
)


async def _noop(ctx: CommandContext) -> None:
    pass


def _make_tui(*inputs: str | BaseException) -> MagicMock:
    """Create a mock TUI that returns inputs in sequence, ending with EOFError."""
    tui = MagicMock()
    side_effects: list[str | BaseException] = list(inputs) + [EOFError()]
    tui.prompt_input = AsyncMock(side_effect=side_effects)
    tui.show_error = MagicMock()
    tui.show_info = MagicMock()
    tui.show_markdown = MagicMock()
    tui.start_spinner = MagicMock()
    tui.stop_spinner = MagicMock()
    tui.start_live_text = MagicMock()
    tui.append_live_text = MagicMock()
    tui.finalize_live_text = MagicMock()
    tui.set_last_response = MagicMock()
    return tui


async def _empty_stream() -> AsyncIterator[StreamEvent]:
    return
    yield  # Make it an async generator


async def _text_stream(text: str) -> AsyncIterator[StreamEvent]:
    yield StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": text})


def _make_mock_agent(stream_fn=None):
    """Create a mock agent plugin."""
    agent = MagicMock()
    agent.name = "TestAgent"
    agent.default_model = "test-model"
    if stream_fn is None:
        stream_fn = _empty_stream
    agent.send_message = AsyncMock(return_value=stream_fn())
    return agent


def _make_repl(
    tui: MagicMock,
    registry: CommandRegistry | None = None,
    plugin_registry: PluginRegistry | None = None,
    config: Config | None = None,
) -> REPL:
    """Create a REPL instance with defaults."""
    return REPL(
        session=Session(),
        tui=tui,
        command_registry=registry or CommandRegistry(),
        plugin_registry=plugin_registry or PluginRegistry(),
        config=config or Config(),
    )


class TestEmptyInput:
    """Requirement 1.2: Empty input re-prompts silently."""

    @pytest.mark.asyncio
    async def test_empty_input_continues(self):
        tui = _make_tui("", "   ", "\t")
        repl = _make_repl(tui)
        await repl.run()
        # Should have prompted 4 times (3 empties + final EOFError)
        assert tui.prompt_input.call_count == 4
        tui.show_error.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_continues(self):
        tui = _make_tui("   \n  ")
        repl = _make_repl(tui)
        await repl.run()
        assert tui.prompt_input.call_count == 2
        tui.show_error.assert_not_called()


class TestSlashCommandDispatch:
    """Requirements 1.6, 1.E3: Slash command dispatch."""

    @pytest.mark.asyncio
    async def test_known_command_dispatched(self):
        handler = AsyncMock()
        reg = CommandRegistry()
        reg.register(SlashCommand(name="test", description="Test", handler=handler))
        tui = _make_tui("/test some args")
        repl = _make_repl(tui, registry=reg)
        await repl.run()
        handler.assert_called_once()
        ctx = handler.call_args[0][0]
        assert isinstance(ctx, CommandContext)
        assert ctx.args == "some args"

    @pytest.mark.asyncio
    async def test_unknown_command_shows_error(self):
        tui = _make_tui("/nonexistent")
        repl = _make_repl(tui)
        await repl.run()
        tui.show_error.assert_called_once()
        assert "Unknown command: /nonexistent" in tui.show_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_command_context_has_all_fields(self):
        handler = AsyncMock()
        reg = CommandRegistry()
        reg.register(SlashCommand(name="ctx", description="Ctx", handler=handler))
        config = Config(app_name="testapp")
        pr = PluginRegistry()
        session = Session()
        tui = _make_tui("/ctx arg1 arg2")
        repl = REPL(
            session=session,
            tui=tui,
            command_registry=reg,
            plugin_registry=pr,
            config=config,
        )
        await repl.run()
        ctx = handler.call_args[0][0]
        assert ctx.session is session
        assert ctx.tui is tui
        assert ctx.config is config
        assert ctx.registry is reg
        assert ctx.plugin_registry is pr
        assert ctx.args == "arg1 arg2"


class TestQuit:
    """Requirement 1.3: /quit terminates the loop."""

    @pytest.mark.asyncio
    async def test_quit_exits_loop(self):
        async def quit_handler(ctx: CommandContext) -> None:
            raise QuitRequestedError()

        reg = CommandRegistry()
        reg.register(SlashCommand(name="quit", description="Quit", handler=quit_handler))
        tui = _make_tui("/quit", "should not reach")
        repl = _make_repl(tui, registry=reg)
        await repl.run()
        # Only prompted once (then QuitRequestedError breaks the loop)
        assert tui.prompt_input.call_count == 1


class TestCtrlCCtrlD:
    """Requirements 1.4, 1.5: Ctrl+C/D handling."""

    @pytest.mark.asyncio
    async def test_ctrl_c_exits_when_no_task(self):
        tui = MagicMock()
        tui.prompt_input = AsyncMock(side_effect=KeyboardInterrupt())
        repl = _make_repl(tui)
        await repl.run()
        tui.prompt_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_ctrl_d_exits_when_no_task(self):
        tui = MagicMock()
        tui.prompt_input = AsyncMock(side_effect=EOFError())
        repl = _make_repl(tui)
        await repl.run()
        tui.prompt_input.assert_called_once()


class TestFreeTextDispatch:
    """Requirements 1.7, 1.E1: Free text forwarding to agent."""

    @pytest.mark.asyncio
    async def test_free_text_sent_to_agent(self):
        agent = _make_mock_agent()
        pr = PluginRegistry()
        pr.set_agent(agent)
        tui = _make_tui("hello world")
        repl = _make_repl(tui, plugin_registry=pr)
        await repl.run()
        agent.send_message.assert_called_once()
        msg_ctx = agent.send_message.call_args[0][0]
        assert isinstance(msg_ctx, MessageContext)
        assert msg_ctx.message == "hello world"

    @pytest.mark.asyncio
    async def test_no_agent_shows_error(self):
        tui = _make_tui("hello world")
        repl = _make_repl(tui)
        await repl.run()
        tui.show_error.assert_called_once()
        assert "No agent configured" in tui.show_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_free_text_adds_user_turn(self):
        agent = _make_mock_agent()
        pr = PluginRegistry()
        pr.set_agent(agent)
        session = Session()
        tui = _make_tui("test message")
        repl = REPL(
            session=session,
            tui=tui,
            command_registry=CommandRegistry(),
            plugin_registry=pr,
            config=Config(),
        )
        await repl.run()
        history = session.get_history()
        # At least a user turn and assistant turn
        assert len(history) >= 1
        assert history[0].role == "user"
        assert history[0].content == "test message"

    @pytest.mark.asyncio
    async def test_free_text_with_mentions(self):
        agent = _make_mock_agent()
        pr = PluginRegistry()
        pr.set_agent(agent)
        tui = _make_tui("check @/tmp/test_file.txt")
        with patch("agent_repl.repl.resolve_mentions") as mock_resolve:
            mock_resolve.return_value = []
            repl = _make_repl(tui, plugin_registry=pr)
            await repl.run()
            mock_resolve.assert_called_once()
            assert "/tmp/test_file.txt" in mock_resolve.call_args[0][0]


class TestAgentErrors:
    """Requirements 1.E2: Agent exception handling."""

    @pytest.mark.asyncio
    async def test_agent_send_message_exception(self):
        agent = MagicMock()
        agent.name = "TestAgent"
        agent.default_model = "test"
        agent.send_message = AsyncMock(side_effect=RuntimeError("connection failed"))
        pr = PluginRegistry()
        pr.set_agent(agent)
        tui = _make_tui("hello")
        repl = _make_repl(tui, plugin_registry=pr)
        await repl.run()
        tui.show_error.assert_called_once()
        assert "Agent error" in tui.show_error.call_args[0][0]
        assert "connection failed" in tui.show_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_agent_error_continues_loop(self):
        """After agent error, loop should continue and prompt again."""
        agent = MagicMock()
        agent.name = "TestAgent"
        agent.default_model = "test"
        # First call fails, second returns empty stream
        agent.send_message = AsyncMock(
            side_effect=[RuntimeError("fail"), _empty_stream()]
        )
        pr = PluginRegistry()
        pr.set_agent(agent)
        tui = _make_tui("first", "second")
        repl = _make_repl(tui, plugin_registry=pr)
        await repl.run()
        # Should have prompted 3 times: "first", "second", EOFError
        assert tui.prompt_input.call_count == 3
        assert agent.send_message.call_count == 2


class TestCommandErrors:
    """Requirement 1.E2/10.9: Command handler exception recovery."""

    @pytest.mark.asyncio
    async def test_command_error_shows_message(self):
        async def bad_handler(ctx: CommandContext) -> None:
            raise ValueError("something broke")

        reg = CommandRegistry()
        reg.register(SlashCommand(name="bad", description="Bad", handler=bad_handler))
        tui = _make_tui("/bad")
        repl = _make_repl(tui, registry=reg)
        await repl.run()
        tui.show_error.assert_called_once()
        assert "Command error" in tui.show_error.call_args[0][0]
        assert "something broke" in tui.show_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_command_error_continues_loop(self):
        """After command error, loop should continue."""
        call_count = 0

        async def fail_then_ok(ctx: CommandContext) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("fail first time")

        reg = CommandRegistry()
        reg.register(SlashCommand(name="cmd", description="Cmd", handler=fail_then_ok))
        tui = _make_tui("/cmd", "/cmd")
        repl = _make_repl(tui, registry=reg)
        await repl.run()
        assert call_count == 2
        # Error shown only once (first call)
        assert tui.show_error.call_count == 1


class TestProperty18:
    """Property 18: Graceful Error Recovery.

    For any exception raised by a plugin command handler during REPL execution,
    the REPL SHALL display the error, not crash, and present a new prompt.
    """

    @pytest.mark.asyncio
    @given(
        error_message=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    )
    @settings(max_examples=20)
    async def test_any_exception_recovers(self, error_message: str):
        async def raise_error(ctx: CommandContext) -> None:
            raise RuntimeError(error_message)

        reg = CommandRegistry()
        reg.register(SlashCommand(name="err", description="Err", handler=raise_error))
        tui = _make_tui("/err")
        repl = _make_repl(tui, registry=reg)
        await repl.run()
        # REPL did not crash
        tui.show_error.assert_called_once()
        # Error message was displayed
        assert error_message in tui.show_error.call_args[0][0]
        # Loop continued to prompt again (then EOFError)
        assert tui.prompt_input.call_count == 2


class TestAsyncModel:
    """Requirement 1.8: asyncio concurrency model."""

    @pytest.mark.asyncio
    async def test_run_is_coroutine(self):
        tui = _make_tui()
        repl = _make_repl(tui)
        # run() should be a coroutine
        coro = repl.run()
        assert asyncio.iscoroutine(coro)
        await coro


class TestMultipleInputTypes:
    """Integration: mixed input types in a single session."""

    @pytest.mark.asyncio
    async def test_mixed_inputs(self):
        handler = AsyncMock()
        reg = CommandRegistry()
        reg.register(SlashCommand(name="test", description="Test", handler=handler))
        agent = _make_mock_agent()
        pr = PluginRegistry()
        pr.set_agent(agent)

        # Empty → skip, command → dispatch, free text → agent, unknown → error
        tui = _make_tui("", "/test", "hello", "/unknown")
        repl = _make_repl(tui, registry=reg, plugin_registry=pr)

        # Reset the mock so send_message returns fresh stream each call
        agent.send_message = AsyncMock(return_value=_empty_stream())

        await repl.run()
        handler.assert_called_once()
        agent.send_message.assert_called_once()
        assert tui.show_error.call_count == 1  # unknown command
        assert "Unknown command: /unknown" in tui.show_error.call_args[0][0]
