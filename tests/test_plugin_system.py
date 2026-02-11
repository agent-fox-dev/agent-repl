"""Tests for plugin_registry module.

Covers Requirements 10.4-10.6, 10.E1, 10.E2 and Properties 15-16.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.exceptions import PluginError
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.types import (
    AgentPlugin,
    MessageContext,
    Plugin,
    PluginContext,
    SlashCommand,
    StreamEvent,
)

# --- Test helpers ---


async def _noop(ctx: object) -> None:
    pass


class FakePlugin:
    """A minimal Plugin implementation for testing."""

    def __init__(
        self,
        name: str = "fake",
        description: str = "A fake plugin",
        commands: list[SlashCommand] | None = None,
        hints: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self._commands = commands or []
        self._hints = hints or []

    def get_commands(self) -> list[SlashCommand]:
        return self._commands

    async def on_load(self, context: PluginContext) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return self._hints


class FakeAgentPlugin(FakePlugin):
    """A minimal AgentPlugin implementation for testing."""

    def __init__(
        self,
        name: str = "fake_agent",
        description: str = "A fake agent",
        default_model: str = "test-model",
        commands: list[SlashCommand] | None = None,
        hints: list[str] | None = None,
    ):
        super().__init__(name, description, commands, hints)
        self.default_model = default_model

    async def send_message(self, context: MessageContext) -> AsyncIterator[StreamEvent]:
        return
        yield  # make it an async generator

    async def compact_history(self, session: Any) -> str:
        return "summary"


# --- Unit tests ---


class TestPluginRegistryRegister:
    """Requirement 10.4: Store plugins and register their commands."""

    def test_register_plugin(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        plugin = FakePlugin(name="test")
        pr.register(plugin, cr)
        assert len(pr.plugins) == 1
        assert pr.plugins[0].name == "test"

    def test_register_plugin_commands(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        cmd = SlashCommand(name="greet", description="Say hello", handler=_noop)
        plugin = FakePlugin(name="test", commands=[cmd])
        pr.register(plugin, cr)
        assert cr.get("greet") is cmd

    def test_register_multiple_plugins(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        pr.register(FakePlugin(name="p1"), cr)
        pr.register(FakePlugin(name="p2"), cr)
        assert len(pr.plugins) == 2

    def test_register_agent_plugin(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        agent = FakeAgentPlugin(name="claude")
        pr.register(agent, cr)
        assert pr.active_agent is agent
        assert len(pr.plugins) == 1


class TestSetAgent:
    """Requirements 10.5, 10.6: Single agent constraint."""

    def test_set_agent(self):
        pr = PluginRegistry()
        agent = FakeAgentPlugin(name="claude")
        pr.set_agent(agent)
        assert pr.active_agent is agent

    def test_second_agent_raises(self):
        """10.6: Multiple agents raises PluginError."""
        pr = PluginRegistry()
        pr.set_agent(FakeAgentPlugin(name="agent1"))
        with pytest.raises(PluginError, match="agent1.*already active"):
            pr.set_agent(FakeAgentPlugin(name="agent2"))

    def test_no_agent_initially(self):
        pr = PluginRegistry()
        assert pr.active_agent is None


class TestPlugins:
    """PluginRegistry.plugins property returns a copy."""

    def test_returns_copy(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        pr.register(FakePlugin(name="test"), cr)
        plugins = pr.plugins
        plugins.append(FakePlugin(name="injected"))
        assert len(pr.plugins) == 1


class TestGetStatusHints:
    """PluginRegistry.get_status_hints collects from all plugins."""

    def test_empty(self):
        pr = PluginRegistry()
        assert pr.get_status_hints() == []

    def test_single_plugin_hints(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        pr.register(FakePlugin(name="p1", hints=["hint1", "hint2"]), cr)
        assert pr.get_status_hints() == ["hint1", "hint2"]

    def test_multiple_plugin_hints(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        pr.register(FakePlugin(name="p1", hints=["a"]), cr)
        pr.register(FakePlugin(name="p2", hints=["b", "c"]), cr)
        assert pr.get_status_hints() == ["a", "b", "c"]

    def test_no_hints(self):
        pr = PluginRegistry()
        cr = CommandRegistry()
        pr.register(FakePlugin(name="p1"), cr)
        assert pr.get_status_hints() == []


class TestProtocolCheck:
    """Verify FakePlugin and FakeAgentPlugin satisfy the protocols."""

    def test_fake_plugin_is_plugin(self):
        assert isinstance(FakePlugin(), Plugin)

    def test_fake_agent_is_agent_plugin(self):
        assert isinstance(FakeAgentPlugin(), AgentPlugin)

    def test_fake_agent_is_also_plugin(self):
        assert isinstance(FakeAgentPlugin(), Plugin)


# --- Property-based tests ---


@pytest.mark.property
class TestPluginSystemProperties:
    @given(
        command_names=st.lists(
            st.text(
                alphabet=st.characters(categories=("L", "N")),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=10,
        ),
    )
    def test_property15_command_registration(self, command_names: list[str]):
        """Property 15: All commands from get_commands() are in registry after register()."""
        pr = PluginRegistry()
        cr = CommandRegistry()
        commands = [
            SlashCommand(name=n, description=f"cmd {n}", handler=_noop) for n in command_names
        ]
        plugin = FakePlugin(name="test", commands=commands)
        pr.register(plugin, cr)

        # Every command from get_commands() must be findable in the registry
        for cmd in commands:
            registered = cr.get(cmd.name)
            assert registered is not None
            # Last-write-wins for duplicates, so the registered command's name matches
            assert registered.name == cmd.name

    @given(
        n_agents=st.integers(min_value=2, max_value=5),
    )
    def test_property16_agent_singleton(self, n_agents: int):
        """Property 16: Second agent registration raises PluginError."""
        pr = PluginRegistry()
        cr = CommandRegistry()

        # First agent succeeds
        pr.register(FakeAgentPlugin(name="agent0"), cr)
        assert pr.active_agent is not None

        # Subsequent agents all fail
        for i in range(1, n_agents):
            with pytest.raises(PluginError):
                pr.register(FakeAgentPlugin(name=f"agent{i}"), cr)

        # Only one agent is active, and only the first plugin + the first agent are stored
        # (subsequent registrations raise before appending to _plugins)
        assert pr.active_agent.name == "agent0"
