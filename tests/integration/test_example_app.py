"""Integration tests for the example application.

Tests that the example modules import correctly and the echo agent
responds properly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent_repl.command_registry import CommandRegistry
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.session import Session
from agent_repl.types import (
    Config,
    MessageContext,
    PluginContext,
    StreamEventType,
)


class TestExampleImports:
    """Test example modules import without error."""

    def test_echo_agent_imports(self):
        from examples.echo_agent import EchoAgentPlugin

        assert EchoAgentPlugin is not None

    def test_demo_plugin_imports(self):
        from examples.demo_plugin import DemoPlugin

        assert DemoPlugin is not None

    def test_demo_imports(self):
        # Just verify the module is importable (don't run main)
        import examples.demo

        assert hasattr(examples.demo, "main")

    def test_spawn_demo_imports(self):
        import examples.spawn_demo

        assert hasattr(examples.spawn_demo, "main")


class TestEchoAgent:
    """Test echo agent responds correctly."""

    def test_echo_agent_protocol(self):
        from examples.echo_agent import EchoAgentPlugin

        agent = EchoAgentPlugin()
        assert agent.name == "Echo"
        assert agent.default_model == "echo-1.0"
        assert agent.get_commands() == []

    @pytest.mark.asyncio
    async def test_echo_agent_responds(self):
        from examples.echo_agent import EchoAgentPlugin

        agent = EchoAgentPlugin()
        ctx = MessageContext(message="test input")
        stream = await agent.send_message(ctx)
        events = [e async for e in stream]

        # Should have TEXT_DELTA and USAGE
        assert len(events) == 2
        assert events[0].type == StreamEventType.TEXT_DELTA
        assert "test input" in events[0].data["text"]
        assert events[1].type == StreamEventType.USAGE

    @pytest.mark.asyncio
    async def test_echo_agent_compact(self):
        from examples.echo_agent import EchoAgentPlugin

        agent = EchoAgentPlugin()
        session = Session()
        summary = await agent.compact_history(session)
        assert "0 turns" in summary

    @pytest.mark.asyncio
    async def test_echo_agent_on_load(self):
        from examples.echo_agent import EchoAgentPlugin

        agent = EchoAgentPlugin()
        ctx = PluginContext(config=Config())
        await agent.on_load(ctx)
        # Should not raise

    def test_echo_agent_factory(self):
        from examples.echo_agent import create_plugin

        plugin = create_plugin()
        assert plugin.name == "Echo"


class TestDemoPlugin:
    """Test demo plugin commands are registered."""

    def test_demo_plugin_commands(self):
        from examples.demo_plugin import DemoPlugin

        plugin = DemoPlugin()
        commands = plugin.get_commands()
        names = {cmd.name for cmd in commands}
        assert names == {"greet", "time"}

    @pytest.mark.asyncio
    async def test_greet_handler(self):
        from examples.demo_plugin import DemoPlugin

        plugin = DemoPlugin()
        commands = {cmd.name: cmd for cmd in plugin.get_commands()}
        tui = MagicMock()
        tui.show_info = MagicMock()

        from agent_repl.types import CommandContext

        ctx = CommandContext(
            args="Alice",
            session=Session(),
            tui=tui,
            config=Config(),
            registry=CommandRegistry(),
            plugin_registry=PluginRegistry(),
        )
        await commands["greet"].handler(ctx)
        assert "Alice" in tui.show_info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_time_handler(self):
        from examples.demo_plugin import DemoPlugin

        plugin = DemoPlugin()
        commands = {cmd.name: cmd for cmd in plugin.get_commands()}
        tui = MagicMock()
        tui.show_info = MagicMock()

        from agent_repl.types import CommandContext

        ctx = CommandContext(
            args="",
            session=Session(),
            tui=tui,
            config=Config(),
            registry=CommandRegistry(),
            plugin_registry=PluginRegistry(),
        )
        await commands["time"].handler(ctx)
        assert "Current time" in tui.show_info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_on_load(self):
        from examples.demo_plugin import DemoPlugin

        plugin = DemoPlugin()
        assert plugin._loaded is False
        await plugin.on_load(PluginContext(config=Config()))
        assert plugin._loaded is True

    def test_status_hints(self):
        from examples.demo_plugin import DemoPlugin

        plugin = DemoPlugin()
        assert plugin.get_status_hints() == []
        plugin._loaded = True
        assert plugin.get_status_hints() == ["demo: active"]

    def test_factory(self):
        from examples.demo_plugin import create_plugin

        plugin = create_plugin()
        assert plugin.name == "demo"
