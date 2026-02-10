"""Unit and property tests for built-in commands.

Property 14: Version Consistency
Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

import importlib.metadata
from unittest.mock import MagicMock

import pytest

from agent_repl.builtin_commands import get_builtin_commands
from agent_repl.command_registry import CommandRegistry
from agent_repl.types import AppContext, CommandContext, Config, TokenStatistics


def _make_app_context():
    """Create a mock AppContext for testing."""
    config = Config(app_name="test-app", app_version="1.0.0", default_model="test-model")
    tui = MagicMock()
    session = MagicMock()
    cmd_reg = CommandRegistry()
    stats = TokenStatistics()

    for cmd in get_builtin_commands():
        cmd_reg.register(cmd)

    return AppContext(
        config=config,
        session=session,
        tui=tui,
        command_registry=cmd_reg,
        stats=stats,
    )


class TestBuiltinCommands:
    def test_get_builtin_commands_returns_three(self):
        cmds = get_builtin_commands()
        names = {c.name for c in cmds}
        assert names == {"help", "quit", "version"}

    def test_help_displays_commands(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("help")
        assert cmd is not None
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_text.assert_called_once()
        output = app_ctx.tui.display_text.call_args[0][0]
        assert "/help" in output
        assert "/quit" in output
        assert "/version" in output

    def test_quit_raises_system_exit(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("quit")
        assert cmd is not None
        ctx = CommandContext(args="", app_context=app_ctx)
        with pytest.raises(SystemExit):
            cmd.handler(ctx)

    def test_version_displays_version(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("version")
        assert cmd is not None
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        app_ctx.tui.display_info.assert_called_once()
        output = app_ctx.tui.display_info.call_args[0][0]
        expected_version = importlib.metadata.version("agent_repl")
        assert expected_version in output


class TestProperty14VersionConsistency:
    """Property 14: /version output matches pyproject.toml version.

    Feature: agent_repl, Property 14: Version Consistency
    """

    def test_version_matches_package_metadata(self):
        app_ctx = _make_app_context()
        cmd = app_ctx.command_registry.get("version")
        ctx = CommandContext(args="", app_context=app_ctx)
        cmd.handler(ctx)
        output = app_ctx.tui.display_info.call_args[0][0]
        pkg_version = importlib.metadata.version("agent_repl")
        assert pkg_version in output
