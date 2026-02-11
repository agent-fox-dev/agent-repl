"""Tests for builtin_commands module.

Covers Requirements 5.1-5.7, 5.E1-5.E4.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent_repl.builtin_commands import BuiltinCommandsPlugin
from agent_repl.command_registry import CommandRegistry
from agent_repl.exceptions import QuitRequestedError
from agent_repl.session import Session
from agent_repl.types import (
    CommandContext,
    Config,
    ConversationTurn,
    Plugin,
    TokenUsage,
)


@pytest.fixture
def plugin() -> BuiltinCommandsPlugin:
    return BuiltinCommandsPlugin()


@pytest.fixture
def registry(plugin: BuiltinCommandsPlugin) -> CommandRegistry:
    reg = CommandRegistry()
    for cmd in plugin.get_commands():
        reg.register(cmd)
    return reg


@pytest.fixture
def session() -> Session:
    return Session()


@pytest.fixture
def tui_mock() -> MagicMock:
    tui = MagicMock()
    tui.show_info = MagicMock()
    tui.show_error = MagicMock()
    tui.copy_to_clipboard = MagicMock()
    return tui


@pytest.fixture
def plugin_registry_mock() -> MagicMock:
    pr = MagicMock()
    pr.active_agent = None
    return pr


def _make_ctx(
    registry: CommandRegistry,
    session: Session,
    tui: MagicMock,
    plugin_registry: MagicMock,
    args: str = "",
) -> CommandContext:
    return CommandContext(
        args=args,
        session=session,
        tui=tui,
        config=Config(),
        registry=registry,
        plugin_registry=plugin_registry,
    )


class TestPluginProtocol:
    """Requirement 5.7: Built-ins are plugins."""

    def test_is_plugin(self, plugin: BuiltinCommandsPlugin):
        assert isinstance(plugin, Plugin)

    def test_has_name(self, plugin: BuiltinCommandsPlugin):
        assert plugin.name == "builtin"

    def test_has_description(self, plugin: BuiltinCommandsPlugin):
        assert plugin.description == "Built-in REPL commands"

    def test_get_commands_returns_six(self, plugin: BuiltinCommandsPlugin):
        commands = plugin.get_commands()
        assert len(commands) == 6
        names = {cmd.name for cmd in commands}
        assert names == {"help", "quit", "version", "copy", "agent", "stats"}

    @pytest.mark.asyncio
    async def test_on_load(self, plugin: BuiltinCommandsPlugin):
        # Should not raise
        await plugin.on_load(MagicMock())

    @pytest.mark.asyncio
    async def test_on_unload(self, plugin: BuiltinCommandsPlugin):
        # Should not raise
        await plugin.on_unload()

    def test_get_status_hints(self, plugin: BuiltinCommandsPlugin):
        assert plugin.get_status_hints() == []


class TestHelp:
    """Requirement 5.1: /help lists all commands."""

    @pytest.mark.asyncio
    async def test_help_lists_commands(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("help")
        await cmd.handler(ctx)
        # show_info called once per command (6 total)
        assert tui_mock.show_info.call_count == 6
        # Check some command names appear
        all_output = " ".join(call.args[0] for call in tui_mock.show_info.call_args_list)
        assert "/help" in all_output
        assert "/quit" in all_output
        assert "/version" in all_output

    @pytest.mark.asyncio
    async def test_help_empty_registry(
        self,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        empty_reg = CommandRegistry()
        ctx = _make_ctx(empty_reg, session, tui_mock, plugin_registry_mock)
        # Manually invoke the help handler
        from agent_repl.builtin_commands import _handle_help

        await _handle_help(ctx)
        tui_mock.show_info.assert_called_once()
        assert "No commands" in tui_mock.show_info.call_args[0][0]


class TestQuit:
    """Requirement 5.2: /quit exits REPL."""

    @pytest.mark.asyncio
    async def test_quit_raises_sentinel(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("quit")
        with pytest.raises(QuitRequestedError):
            await cmd.handler(ctx)


class TestVersion:
    """Requirement 5.3: /version shows app name and version."""

    @pytest.mark.asyncio
    async def test_version_display(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("version")
        await cmd.handler(ctx)
        tui_mock.show_info.assert_called_once()
        output = tui_mock.show_info.call_args[0][0]
        assert "agent_repl" in output
        assert "0.1.0" in output


class TestCopy:
    """Requirements 5.4, 5.E1, 5.E2: /copy."""

    @pytest.mark.asyncio
    async def test_copy_last_response(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        session.add_turn(ConversationTurn(role="assistant", content="Hello world"))
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("copy")
        await cmd.handler(ctx)
        tui_mock.copy_to_clipboard.assert_called_once_with("Hello world")

    @pytest.mark.asyncio
    async def test_copy_no_response(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        """5.E1: No response to copy."""
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("copy")
        await cmd.handler(ctx)
        tui_mock.show_info.assert_called_once()
        assert "No response" in tui_mock.show_info.call_args[0][0]
        tui_mock.copy_to_clipboard.assert_not_called()


class TestAgent:
    """Requirements 5.5, 5.E3: /agent."""

    @pytest.mark.asyncio
    async def test_agent_shows_info(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        agent_mock = MagicMock()
        agent_mock.name = "Claude"
        agent_mock.default_model = "opus"
        plugin_registry_mock.active_agent = agent_mock
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("agent")
        await cmd.handler(ctx)
        tui_mock.show_info.assert_called_once()
        output = tui_mock.show_info.call_args[0][0]
        assert "Claude" in output
        assert "opus" in output

    @pytest.mark.asyncio
    async def test_agent_no_agent(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        """5.E3: No agent active."""
        plugin_registry_mock.active_agent = None
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("agent")
        await cmd.handler(ctx)
        tui_mock.show_info.assert_called_once()
        assert "No agent" in tui_mock.show_info.call_args[0][0]


class TestStats:
    """Requirements 5.6, 5.E4: /stats."""

    @pytest.mark.asyncio
    async def test_stats_with_usage(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        session.add_turn(
            ConversationTurn(
                role="assistant",
                content="hi",
                usage=TokenUsage(input_tokens=500, output_tokens=2000),
            )
        )
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("stats")
        await cmd.handler(ctx)
        assert tui_mock.show_info.call_count == 2
        sent = tui_mock.show_info.call_args_list[0][0][0]
        received = tui_mock.show_info.call_args_list[1][0][0]
        assert "500 tokens" in sent
        assert "2.00 k tokens" in received

    @pytest.mark.asyncio
    async def test_stats_zero(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        """5.E4: No tokens exchanged shows zero."""
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("stats")
        await cmd.handler(ctx)
        assert tui_mock.show_info.call_count == 2
        sent = tui_mock.show_info.call_args_list[0][0][0]
        received = tui_mock.show_info.call_args_list[1][0][0]
        assert "0 tokens" in sent
        assert "0 tokens" in received

    @pytest.mark.asyncio
    async def test_stats_above_1000(
        self,
        registry: CommandRegistry,
        session: Session,
        tui_mock: MagicMock,
        plugin_registry_mock: MagicMock,
    ):
        session.add_turn(
            ConversationTurn(
                role="assistant",
                content="hi",
                usage=TokenUsage(input_tokens=3210, output_tokens=1500),
            )
        )
        ctx = _make_ctx(registry, session, tui_mock, plugin_registry_mock)
        cmd = registry.get("stats")
        await cmd.handler(ctx)
        sent = tui_mock.show_info.call_args_list[0][0][0]
        received = tui_mock.show_info.call_args_list[1][0][0]
        assert "3.21 k tokens" in sent
        assert "1.50 k tokens" in received
