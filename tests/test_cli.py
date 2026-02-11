"""Tests for CLI slash command invocation.

Covers Requirements 13.1-13.5, 13.E1-13.E3, Property 17.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.app import App
from agent_repl.types import CommandContext, Config, SlashCommand


async def _noop(ctx: CommandContext) -> None:
    pass


async def _failing(ctx: CommandContext) -> None:
    raise ValueError("handler failed")


class TestSuccessfulInvocation:
    """Requirements 13.1, 13.5: Successful CLI command invocation."""

    @pytest.mark.asyncio
    async def test_cli_command_returns_zero(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            # /version is cli_exposed=True by default
            result = await app.run_cli_command("version", [])

        assert result == 0

    @pytest.mark.asyncio
    async def test_cli_command_strips_dashes(self):
        """--version maps to /version."""
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("--version", [])

        assert result == 0

    @pytest.mark.asyncio
    async def test_cli_command_handler_called(self):
        """Handler receives correct CommandContext."""
        handler = AsyncMock()
        plugin = MagicMock()
        plugin.name = "test"
        plugin.description = "test"
        plugin.get_commands = MagicMock(return_value=[
            SlashCommand(
                name="mycmd",
                description="My command",
                handler=handler,
                cli_exposed=True,
            ),
        ])
        plugin.on_load = AsyncMock()
        plugin.on_unload = AsyncMock()
        plugin.get_status_hints = MagicMock(return_value=[])

        config = Config(plugins=["test_plugin"])
        app = App(config=config)

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            result = await app.run_cli_command("mycmd", ["arg1", "arg2"])

        assert result == 0
        handler.assert_called_once()
        ctx = handler.call_args[0][0]
        assert ctx.args == "arg1 arg2"
        assert ctx.argv == ["arg1", "arg2"]

    @pytest.mark.asyncio
    async def test_no_repl_started(self):
        """CLI command exits without starting REPL (13.5)."""
        app = App()
        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.REPL") as mock_repl,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            await app.run_cli_command("version", [])

        # REPL should never be instantiated
        mock_repl.assert_not_called()


class TestParameterPassing:
    """Requirement 13.3: Parameters passed to handler."""

    @pytest.mark.asyncio
    async def test_args_joined(self):
        handler = AsyncMock()
        plugin = MagicMock()
        plugin.name = "test"
        plugin.description = "test"
        plugin.get_commands = MagicMock(return_value=[
            SlashCommand(
                name="cmd", description="Cmd", handler=handler, cli_exposed=True
            ),
        ])
        plugin.on_load = AsyncMock()
        plugin.on_unload = AsyncMock()
        plugin.get_status_hints = MagicMock(return_value=[])

        config = Config(plugins=["test_plugin"])
        app = App(config=config)

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            await app.run_cli_command("cmd", ["one", "two", "three"])

        ctx = handler.call_args[0][0]
        assert ctx.args == "one two three"
        assert ctx.argv == ["one", "two", "three"]

    @pytest.mark.asyncio
    async def test_no_args(self):
        handler = AsyncMock()
        plugin = MagicMock()
        plugin.name = "test"
        plugin.description = "test"
        plugin.get_commands = MagicMock(return_value=[
            SlashCommand(
                name="cmd", description="Cmd", handler=handler, cli_exposed=True
            ),
        ])
        plugin.on_load = AsyncMock()
        plugin.on_unload = AsyncMock()
        plugin.get_status_hints = MagicMock(return_value=[])

        config = Config(plugins=["test_plugin"])
        app = App(config=config)

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            await app.run_cli_command("cmd", [])

        ctx = handler.call_args[0][0]
        assert ctx.args == ""
        assert ctx.argv == []


class TestNonCliCommand:
    """Requirement 13.4, 13.E1: Non-CLI commands rejected."""

    @pytest.mark.asyncio
    async def test_non_cli_exposed_returns_one(self):
        """Command exists but cli_exposed=False → error, exit 1."""
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            # /help exists but cli_exposed=False
            result = await app.run_cli_command("help", [])

        assert result == 1

    @pytest.mark.asyncio
    async def test_non_cli_shows_error(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app._tui = MagicMock()
            app._tui.show_error = MagicMock()
            app._tui.show_info = MagicMock()
            app._tui._completer = None
            app._tui._toolbar_provider = None
            await app.run_cli_command("help", [])

        app._tui.show_error.assert_called_once()
        assert "not available as a CLI command" in app._tui.show_error.call_args[0][0]


class TestUnknownCommand:
    """Requirement 13.E1: Unknown flag shows error and available commands."""

    @pytest.mark.asyncio
    async def test_unknown_returns_one(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("--nonexistent", [])

        assert result == 1

    @pytest.mark.asyncio
    async def test_unknown_shows_available(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app._tui = MagicMock()
            app._tui.show_error = MagicMock()
            app._tui.show_info = MagicMock()
            app._tui._completer = None
            app._tui._toolbar_provider = None
            await app.run_cli_command("--nonexistent", [])

        # Should show error and available commands
        app._tui.show_error.assert_called_once()
        assert "Unknown command" in app._tui.show_error.call_args[0][0]
        # show_info called with available commands list
        assert app._tui.show_info.call_count >= 1


class TestHandlerException:
    """Requirement 13.E2: Handler exception → error, exit non-zero."""

    @pytest.mark.asyncio
    async def test_handler_exception_returns_one(self):
        plugin = MagicMock()
        plugin.name = "test"
        plugin.description = "test"
        plugin.get_commands = MagicMock(return_value=[
            SlashCommand(
                name="bad",
                description="Bad",
                handler=_failing,
                cli_exposed=True,
            ),
        ])
        plugin.on_load = AsyncMock()
        plugin.on_unload = AsyncMock()
        plugin.get_status_hints = MagicMock(return_value=[])

        config = Config(plugins=["test_plugin"])
        app = App(config=config)

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            result = await app.run_cli_command("bad", [])

        assert result == 1

    @pytest.mark.asyncio
    async def test_handler_exception_shows_error(self):
        plugin = MagicMock()
        plugin.name = "test"
        plugin.description = "test"
        plugin.get_commands = MagicMock(return_value=[
            SlashCommand(
                name="bad",
                description="Bad",
                handler=_failing,
                cli_exposed=True,
            ),
        ])
        plugin.on_load = AsyncMock()
        plugin.on_unload = AsyncMock()
        plugin.get_status_hints = MagicMock(return_value=[])

        config = Config(plugins=["test_plugin"])
        app = App(config=config)

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            app._tui = MagicMock()
            app._tui.show_error = MagicMock()
            app._tui._completer = None
            app._tui._toolbar_provider = None
            await app.run_cli_command("bad", [])

        app._tui.show_error.assert_called_once()
        assert "handler failed" in app._tui.show_error.call_args[0][0]


class TestProperty17:
    """Property 17: CLI Command Filtering.

    For any set of registered commands, only commands with cli_exposed=True
    SHALL be available for CLI invocation.
    """

    @pytest.mark.asyncio
    @given(
        name=st.text(
            alphabet=st.characters(whitelist_categories=("Ll",)),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=20)
    async def test_non_exposed_rejected(self, name: str):
        """Commands without cli_exposed=True are rejected."""
        handler = AsyncMock()
        plugin = MagicMock()
        plugin.name = "test"
        plugin.description = "test"
        plugin.get_commands = MagicMock(return_value=[
            SlashCommand(
                name=name,
                description=f"Test {name}",
                handler=handler,
                cli_exposed=False,
            ),
        ])
        plugin.on_load = AsyncMock()
        plugin.on_unload = AsyncMock()
        plugin.get_status_hints = MagicMock(return_value=[])

        config = Config(plugins=["test_plugin"])
        app = App(config=config)

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            result = await app.run_cli_command(name, [])

        # Non-CLI-exposed commands may collide with built-in CLI commands
        # (e.g., "version" which is cli_exposed=True). If not a built-in,
        # the handler should NOT be called and result should be 1.
        if result == 0:
            # Must be a built-in CLI command that was matched instead
            handler.assert_not_called()
        else:
            assert result == 1
            handler.assert_not_called()


class TestCliExposedCommands:
    """Verify correct commands are CLI-exposed."""

    @pytest.mark.asyncio
    async def test_version_is_cli_exposed(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("version", [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_help_not_cli_exposed(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("help", [])
        assert result == 1

    @pytest.mark.asyncio
    async def test_quit_not_cli_exposed(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("quit", [])
        assert result == 1

    @pytest.mark.asyncio
    async def test_copy_not_cli_exposed(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("copy", [])
        assert result == 1

    @pytest.mark.asyncio
    async def test_agent_not_cli_exposed(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("agent", [])
        assert result == 1

    @pytest.mark.asyncio
    async def test_stats_not_cli_exposed(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            result = await app.run_cli_command("stats", [])
        assert result == 1
