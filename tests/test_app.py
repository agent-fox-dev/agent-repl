"""Unit tests for the App class and consumer API.

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 12.4
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_repl.app import App
from agent_repl.types import Config, SlashCommand


class TestApp:
    def test_app_accepts_config(self):
        config = Config(app_name="test", app_version="1.0", default_model="m")
        app = App(config)
        assert app._config is config

    @pytest.mark.asyncio
    async def test_builtin_commands_registered(self):
        config = Config(
            app_name="test",
            app_version="1.0",
            default_model="m",
            agent_factory=lambda c: None,
        )
        app = App(config)

        with patch("agent_repl.app.TUIShell") as mock_tui_cls, \
             patch("agent_repl.app.REPLCore") as mock_repl_cls:
            mock_tui = MagicMock()
            mock_tui_cls.return_value = mock_tui
            mock_repl = MagicMock()
            mock_repl.run_loop = AsyncMock()
            mock_repl_cls.return_value = mock_repl

            await app._run_async()

            mock_repl.run_loop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_custom_agent_factory_used(self):
        mock_agent = MagicMock()
        mock_agent.get_commands.return_value = []
        mock_agent.on_load = AsyncMock()

        def factory(config):
            return mock_agent

        config = Config(
            app_name="test",
            app_version="1.0",
            default_model="m",
            agent_factory=factory,
        )
        app = App(config)

        with patch("agent_repl.app.TUIShell") as mock_tui_cls, \
             patch("agent_repl.app.REPLCore") as mock_repl_cls:
            mock_tui_cls.return_value = MagicMock()
            mock_repl = MagicMock()
            mock_repl.run_loop = AsyncMock()
            mock_repl_cls.return_value = mock_repl

            await app._run_async()

            mock_repl_cls.assert_called_once()
            call_kwargs = mock_repl_cls.call_args
            assert call_kwargs[1].get("agent") is mock_agent

    @pytest.mark.asyncio
    async def test_plugin_commands_registered(self):
        mock_agent = MagicMock()
        mock_cmd = SlashCommand(
            name="custom", description="Custom cmd", help_text="",
            handler=lambda ctx: None,
        )
        mock_agent.get_commands.return_value = [mock_cmd]
        mock_agent.on_load = AsyncMock()

        config = Config(
            app_name="test",
            app_version="1.0",
            default_model="m",
            agent_factory=lambda c: mock_agent,
        )
        app = App(config)

        with patch("agent_repl.app.TUIShell") as mock_tui_cls, \
             patch("agent_repl.app.REPLCore") as mock_repl_cls:
            mock_tui = MagicMock()
            mock_tui_cls.return_value = mock_tui
            mock_repl = MagicMock()
            mock_repl.run_loop = AsyncMock()
            mock_repl_cls.return_value = mock_repl

            await app._run_async()

            mock_tui.set_completions.assert_called_once()
            completions = mock_tui.set_completions.call_args[0][0]
            assert "/custom" in completions
            assert "/help" in completions


class TestPackageExports:
    """Verify package is importable as a library (Req 10.4, 12.4)."""

    def test_imports(self):
        from agent_repl import (
            App,
            Config,
        )

        assert App is not None
        assert Config is not None
