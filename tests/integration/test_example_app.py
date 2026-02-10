"""Integration tests for the example application.

Property 1: Plugin Factory Contract
Property 2: Command Registration Completeness
Property 3: Echo Agent Protocol Compliance
Property 4: Echo Agent Compaction
Property 5: Greet Command Output
Property 6: Stats Command Output
Validates: Requirements 3.1-3.6, 4.1-4.6, 6.1-6.6
"""

from unittest.mock import MagicMock

import pytest

from agent_repl.constants import DEFAULT_CLAUDE_MODEL
from agent_repl.command_registry import CommandRegistry
from agent_repl.session import Session
from agent_repl.types import (
    AppContext,
    CommandContext,
    Config,
    ConversationTurn,
    StreamEventType,
    TokenStatistics,
)
from examples.demo_plugin import DemoPlugin, create_plugin
from examples.echo_agent import EchoAgent


def _make_app_context(app_name="demo"):
    """Create a minimal AppContext with mock TUI for testing."""
    config = Config(
        app_name=app_name, app_version="0.1.0", default_model="test-model"
    )
    session = Session()
    tui = MagicMock()
    cmd_reg = CommandRegistry()
    stats = TokenStatistics()
    return AppContext(
        config=config, session=session, tui=tui,
        command_registry=cmd_reg, stats=stats,
    )


class TestProperty1PluginFactoryContract:
    """Property 1: create_plugin() returns valid Plugin.

    Validates: Requirements 3.1, 3.2, 6.1
    """

    def test_create_plugin_returns_demo_plugin(self):
        plugin = create_plugin()
        assert isinstance(plugin, DemoPlugin)

    def test_plugin_has_name(self):
        plugin = create_plugin()
        assert plugin.name == "demo"

    def test_plugin_has_description(self):
        plugin = create_plugin()
        assert isinstance(plugin.description, str)
        assert len(plugin.description) > 0

    def test_get_commands_returns_list(self):
        plugin = create_plugin()
        commands = plugin.get_commands()
        assert isinstance(commands, list)
        assert len(commands) >= 2

    @pytest.mark.asyncio
    async def test_on_load_is_awaitable(self):
        plugin = create_plugin()
        ctx = _make_app_context()
        await plugin.on_load(ctx)

    @pytest.mark.asyncio
    async def test_on_unload_is_awaitable(self):
        plugin = create_plugin()
        await plugin.on_unload()


class TestProperty2CommandRegistrationCompleteness:
    """Property 2: All plugin commands register in CommandRegistry.

    Validates: Requirements 3.3, 3.6, 6.2
    """

    def test_all_commands_registerable(self):
        plugin = create_plugin()
        registry = CommandRegistry()
        for cmd in plugin.get_commands():
            registry.register(cmd)

        assert registry.get("greet") is not None
        assert registry.get("stats") is not None

    def test_commands_retrievable_by_name(self):
        plugin = create_plugin()
        registry = CommandRegistry()
        for cmd in plugin.get_commands():
            registry.register(cmd)

        greet = registry.get("greet")
        assert greet.name == "greet"
        stats = registry.get("stats")
        assert stats.name == "stats"


class TestProperty3EchoAgentProtocolCompliance:
    """Property 3: Echo agent echoes message and yields USAGE event.

    Validates: Requirements 4.1, 4.2, 4.3, 6.3, 6.4
    """

    def test_echo_agent_has_name(self):
        agent = EchoAgent()
        assert agent.name == "echo"

    def test_echo_agent_has_description(self):
        agent = EchoAgent()
        assert isinstance(agent.description, str)
        assert len(agent.description) > 0

    @pytest.mark.asyncio
    async def test_send_message_echoes_content(self):
        agent = EchoAgent()
        events = []
        async for event in agent.send_message("hello world", [], []):
            events.append(event)

        text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
        assert len(text_events) >= 1
        assert text_events[0].content == "hello world"

    @pytest.mark.asyncio
    async def test_send_message_yields_usage(self):
        agent = EchoAgent()
        events = []
        async for event in agent.send_message("test", [], []):
            events.append(event)

        usage_events = [e for e in events if e.type == StreamEventType.USAGE]
        assert len(usage_events) == 1
        assert usage_events[0].metadata["input_tokens"] == len("test")
        assert usage_events[0].metadata["output_tokens"] == len("test")

    @pytest.mark.asyncio
    async def test_send_message_empty_string(self):
        agent = EchoAgent()
        events = []
        async for event in agent.send_message("", [], []):
            events.append(event)

        text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
        assert len(text_events) == 1
        assert text_events[0].content == ""

    def test_echo_agent_get_commands(self):
        agent = EchoAgent()
        commands = agent.get_commands()
        names = {cmd.name for cmd in commands}
        assert "clear" in names
        assert "compact" in names


class TestProperty4EchoAgentCompaction:
    """Property 4: compact_history returns non-empty summary.

    Validates: Requirements 4.4, 6.6
    """

    @pytest.mark.asyncio
    async def test_compact_non_empty_history(self):
        agent = EchoAgent()
        history = [
            ConversationTurn(role="user", content="hello"),
            ConversationTurn(role="assistant", content="hi there"),
        ]
        result = await agent.compact_history(history)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_compact_includes_turn_count(self):
        agent = EchoAgent()
        history = [
            ConversationTurn(role="user", content="a"),
            ConversationTurn(role="assistant", content="b"),
            ConversationTurn(role="user", content="c"),
        ]
        result = await agent.compact_history(history)
        assert "3" in result


class TestProperty5GreetCommandOutput:
    """Property 5: /greet displays text with app name.

    Validates: Requirements 3.4, 6.5
    """

    def test_greet_calls_display_text(self):
        ctx = _make_app_context(app_name="myapp")
        plugin = create_plugin()
        greet_cmd = next(c for c in plugin.get_commands() if c.name == "greet")
        cmd_ctx = CommandContext(args="", app_context=ctx)

        greet_cmd.handler(cmd_ctx)

        ctx.tui.display_text.assert_called_once()
        output = ctx.tui.display_text.call_args[0][0]
        assert isinstance(output, str)
        assert len(output) > 0
        assert "myapp" in output


class TestProperty6StatsCommandOutput:
    """Property 6: /stats displays token counts.

    Validates: Requirements 3.5, 6.5
    """

    def test_stats_displays_token_counts(self):
        ctx = _make_app_context()
        ctx.stats.total_input_tokens = 42
        ctx.stats.total_output_tokens = 17

        plugin = create_plugin()
        stats_cmd = next(c for c in plugin.get_commands() if c.name == "stats")
        cmd_ctx = CommandContext(args="", app_context=ctx)

        stats_cmd.handler(cmd_ctx)

        ctx.tui.display_info.assert_called_once()
        output = ctx.tui.display_info.call_args[0][0]
        assert "42" in output
        assert "17" in output

    def test_stats_with_zero_usage(self):
        ctx = _make_app_context()

        plugin = create_plugin()
        stats_cmd = next(c for c in plugin.get_commands() if c.name == "stats")
        cmd_ctx = CommandContext(args="", app_context=ctx)

        stats_cmd.handler(cmd_ctx)

        ctx.tui.display_info.assert_called_once()
        output = ctx.tui.display_info.call_args[0][0]
        assert "0" in output


class TestProperty7AppConstructionWithEchoAgent:
    """Property 7: App constructs with echo agent factory without error.

    Validates: Requirements 2.1, 4.6, 6.7, 6.8
    """

    def test_app_constructs_with_echo_agent_factory(self):
        config = Config(
            app_name="demo",
            app_version="0.1.0",
            default_model=DEFAULT_CLAUDE_MODEL,
            plugins=["examples.demo_plugin"],
            agent_factory=lambda cfg: EchoAgent(),
        )
        from agent_repl import App

        app = App(config)
        assert app is not None
