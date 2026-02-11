"""Tests for app module.

Covers Requirements 10.4-10.6, 10.E1, 7.9, 15.1, 15.2.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_repl.app import App
from agent_repl.types import Config


def _make_mock_plugin(name: str = "test_plugin", commands: list | None = None):
    """Create a mock Plugin."""
    spec_attrs = [
        "name", "description", "get_commands",
        "on_load", "on_unload", "get_status_hints",
    ]
    plugin = MagicMock(spec=spec_attrs)
    plugin.name = name
    plugin.description = f"Mock {name}"
    plugin.get_commands = MagicMock(return_value=commands or [])
    plugin.on_load = AsyncMock()
    plugin.on_unload = AsyncMock()
    plugin.get_status_hints = MagicMock(return_value=[])
    return plugin


def _make_mock_agent(name: str = "TestAgent", model: str = "test-model"):
    """Create a mock AgentPlugin."""
    agent = MagicMock()
    agent.name = name
    agent.default_model = model
    agent.description = f"Mock agent {name}"
    agent.get_commands = MagicMock(return_value=[])
    agent.on_load = AsyncMock()
    agent.on_unload = AsyncMock()
    agent.get_status_hints = MagicMock(return_value=[])
    agent.send_message = AsyncMock()
    agent.compact_history = AsyncMock()
    # Make it pass isinstance checks for AgentPlugin
    agent.__class__ = type("MockAgent", (), {
        "__instancecheck__": classmethod(lambda cls, inst: True),
    })
    return agent


class TestInitialization:
    """Test that App.__init__ creates all subsystems."""

    def test_default_config(self):
        app = App()
        assert app._config.app_name == "agent_repl"
        assert app._config.app_version == "0.1.0"

    def test_custom_config(self):
        config = Config(app_name="myapp", app_version="2.0.0")
        app = App(config=config)
        assert app._config.app_name == "myapp"
        assert app._config.app_version == "2.0.0"

    def test_subsystems_created(self):
        app = App()
        assert app._session is not None
        assert app._tui is not None
        assert app._command_registry is not None
        assert app._plugin_registry is not None


class TestSetup:
    """Test _setup() method."""

    @pytest.mark.asyncio
    async def test_builtin_commands_registered(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            await app._setup()
        # Built-in commands should be registered
        assert app._command_registry.get("help") is not None
        assert app._command_registry.get("quit") is not None
        assert app._command_registry.get("version") is not None
        assert app._command_registry.get("copy") is not None
        assert app._command_registry.get("agent") is not None
        assert app._command_registry.get("stats") is not None

    @pytest.mark.asyncio
    async def test_completer_set(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            await app._setup()
        # Completer should have been set on TUI
        assert app._tui._completer is not None

    @pytest.mark.asyncio
    async def test_toolbar_provider_set(self):
        app = App()
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            await app._setup()
        assert app._tui._toolbar_provider is not None


class TestPluginLoading:
    """Test plugin loading from Config.plugins and config.toml."""

    @pytest.mark.asyncio
    async def test_plugins_from_config(self):
        plugin = _make_mock_plugin("config_plugin")
        config = Config(plugins=["myapp.plugins.test"])

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            app = App(config=config)
            await app._setup()

        mock_lp.assert_called_once_with("myapp.plugins.test")
        plugin.on_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_plugins_from_config_toml(self):
        plugin = _make_mock_plugin("toml_plugin")

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=["myapp.toml_plugin"])
            mock_lp.return_value = plugin
            app = App()
            await app._setup()

        mock_lp.assert_called_once_with("myapp.toml_plugin")

    @pytest.mark.asyncio
    async def test_plugin_on_load_failure_skipped(self):
        plugin = _make_mock_plugin("bad_plugin")
        plugin.on_load = AsyncMock(side_effect=RuntimeError("load failed"))
        config = Config(plugins=["myapp.bad"])

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = plugin
            app = App(config=config)
            await app._setup()

        # Plugin should not be in the registry (on_load failed)
        assert len(app._plugin_registry.plugins) == 1  # only builtin

    @pytest.mark.asyncio
    async def test_plugin_load_returns_none_skipped(self):
        config = Config(plugins=["myapp.missing"])

        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch("agent_repl.app.load_plugin") as mock_lp,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            mock_lp.return_value = None
            app = App(config=config)
            await app._setup()

        # Only builtin plugin registered
        assert len(app._plugin_registry.plugins) == 1


class TestAgentFactory:
    """Test agent_factory creates and registers agent."""

    @pytest.mark.asyncio
    async def test_agent_factory_creates_agent(self):
        agent = _make_mock_agent()

        def factory():
            return agent

        config = Config(agent_factory=factory)

        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app = App(config=config)
            await app._setup()

        agent.on_load.assert_called_once()
        assert app._plugin_registry.active_agent is agent

    @pytest.mark.asyncio
    async def test_agent_factory_not_provided(self):
        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app = App()
            await app._setup()

        assert app._plugin_registry.active_agent is None

    @pytest.mark.asyncio
    async def test_agent_factory_exception_handled(self):
        def bad_factory():
            raise RuntimeError("factory failed")

        config = Config(agent_factory=bad_factory)

        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app = App(config=config)
            # Should not raise
            await app._setup()

        assert app._plugin_registry.active_agent is None

    @pytest.mark.asyncio
    async def test_agent_on_load_failure_handled(self):
        agent = _make_mock_agent()
        agent.on_load = AsyncMock(side_effect=RuntimeError("on_load failed"))

        config = Config(agent_factory=lambda: agent)

        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app = App(config=config)
            await app._setup()

        assert app._plugin_registry.active_agent is None


class TestRun:
    """Test App.run() orchestration."""

    @pytest.mark.asyncio
    async def test_run_shows_banner(self):
        with (
            patch("agent_repl.app.load_config") as mock_lc,
            patch.object(App, "_setup", new_callable=AsyncMock) as mock_setup,
        ):
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app = App()

            # Make _setup actually set up the built-in subsystems
            async def real_setup():
                pass

            mock_setup.side_effect = real_setup

            # Mock the REPL run
            with patch("agent_repl.app.REPL") as mock_repl_cls:
                mock_repl_instance = MagicMock()
                mock_repl_instance.run = AsyncMock()
                mock_repl_cls.return_value = mock_repl_instance

                # Mock TUI show_banner
                app._tui = MagicMock()
                app._tui.show_banner = MagicMock()

                await app.run()

                app._tui.show_banner.assert_called_once()
                mock_repl_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_passes_agent_info_to_banner(self):
        agent = _make_mock_agent("Claude", "opus")
        config = Config(agent_factory=lambda: agent)

        with patch("agent_repl.app.load_config") as mock_lc:
            mock_lc.return_value = MagicMock(plugin_paths=[])
            app = App(config=config)

            # Patch REPL to avoid running loop
            with patch("agent_repl.app.REPL") as mock_repl_cls:
                mock_repl_instance = MagicMock()
                mock_repl_instance.run = AsyncMock()
                mock_repl_cls.return_value = mock_repl_instance

                # Spy on show_banner
                original_tui = app._tui
                app._tui = MagicMock(wraps=original_tui)
                app._tui.show_banner = MagicMock()
                app._tui._completer = None
                app._tui._toolbar_provider = None

                await app.run()

                app._tui.show_banner.assert_called_once_with(
                    "agent_repl", "0.1.0", "Claude", "opus"
                )


class TestPublicAPI:
    """Requirements 15.1, 15.2: Public API exports."""

    def test_app_importable_from_package(self):
        from agent_repl import App

        assert App is not None

    def test_all_exports(self):
        import agent_repl

        assert "App" in agent_repl.__all__
        assert "Config" in agent_repl.__all__
        assert "Plugin" in agent_repl.__all__
        assert "AgentPlugin" in agent_repl.__all__
        assert "SlashCommand" in agent_repl.__all__
        assert "StreamEvent" in agent_repl.__all__
        assert "StreamEventType" in agent_repl.__all__
        assert "Theme" in agent_repl.__all__
