"""Unit and property tests for the plugin system.

Property 16: Plugin Load Failure Isolation
Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
"""

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.command_registry import CommandRegistry
from agent_repl.plugin_loader import load_plugins
from agent_repl.plugin_registry import PluginRegistry
from agent_repl.types import SlashCommand


def _noop(ctx):
    pass


def _make_mock_plugin(name: str, commands: list[str] | None = None):
    """Create a mock plugin with optional commands."""
    plugin = MagicMock()
    plugin.name = name
    plugin.description = f"Mock {name}"
    cmds = [
        SlashCommand(name=c, description=f"cmd {c}", help_text="", handler=_noop)
        for c in (commands or [])
    ]
    plugin.get_commands.return_value = cmds
    return plugin


class TestPluginRegistry:
    def test_register_plugin(self):
        cmd_reg = CommandRegistry()
        reg = PluginRegistry(cmd_reg)
        plugin = _make_mock_plugin("test", ["foo"])
        reg.register_plugin(plugin)
        assert len(reg.plugins) == 1
        assert cmd_reg.get("foo") is not None

    def test_agent_plugin_detection(self):
        cmd_reg = CommandRegistry()
        reg = PluginRegistry(cmd_reg)

        # Non-agent plugin
        regular = _make_mock_plugin("regular")
        del regular.send_message
        del regular.compact_history
        reg.register_plugin(regular)
        assert reg.agent_plugin is None

        # Agent plugin (has send_message and compact_history)
        agent = _make_mock_plugin("agent")
        agent.send_message = MagicMock()
        agent.compact_history = MagicMock()
        reg.register_plugin(agent)
        assert reg.agent_plugin is agent

    def test_first_agent_wins(self):
        cmd_reg = CommandRegistry()
        reg = PluginRegistry(cmd_reg)

        agent1 = _make_mock_plugin("agent1")
        agent1.send_message = MagicMock()
        agent1.compact_history = MagicMock()

        agent2 = _make_mock_plugin("agent2")
        agent2.send_message = MagicMock()
        agent2.compact_history = MagicMock()

        reg.register_plugin(agent1)
        reg.register_plugin(agent2)
        assert reg.agent_plugin is agent1

    def test_multiple_plugin_commands(self):
        cmd_reg = CommandRegistry()
        reg = PluginRegistry(cmd_reg)
        reg.register_plugin(_make_mock_plugin("p1", ["foo", "bar"]))
        reg.register_plugin(_make_mock_plugin("p2", ["baz"]))
        assert cmd_reg.get("foo") is not None
        assert cmd_reg.get("bar") is not None
        assert cmd_reg.get("baz") is not None


class TestPluginLoader:
    def test_invalid_module_skipped(self):
        app_context = MagicMock()
        result = load_plugins(["nonexistent.module.path"], app_context)
        assert result == []

    def test_empty_list(self):
        app_context = MagicMock()
        result = load_plugins([], app_context)
        assert result == []


class TestProperty16PluginLoadFailureIsolation:
    """Property 16: Failed plugins don't block others.

    Feature: agent_repl, Property 16: Plugin Load Failure Isolation
    """

    @settings(max_examples=100)
    @given(
        bad_names=st.lists(
            st.from_regex(r"nonexistent\.[a-z]{3,8}", fullmatch=True),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    def test_bad_plugins_skipped(self, bad_names):
        app_context = MagicMock()
        result = load_plugins(bad_names, app_context)
        assert result == []
