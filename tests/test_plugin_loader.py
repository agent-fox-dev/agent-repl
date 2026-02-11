"""Tests for plugin_loader module.

Covers Requirements 10.1-10.3.
"""

from __future__ import annotations

import logging
import types
from unittest.mock import MagicMock, patch

from agent_repl.plugin_loader import load_plugin


class TestSuccessfulLoad:
    """Requirement 10.1: Import module and call create_plugin() factory."""

    def test_loads_plugin(self):
        mock_plugin = MagicMock()
        mock_module = types.ModuleType("fake_plugin")
        mock_module.create_plugin = MagicMock(return_value=mock_plugin)

        with patch("agent_repl.plugin_loader.importlib.import_module", return_value=mock_module):
            result = load_plugin("fake_plugin")

        assert result is mock_plugin
        mock_module.create_plugin.assert_called_once()

    def test_returns_factory_result(self):
        sentinel = object()
        mock_module = types.ModuleType("my_module")
        mock_module.create_plugin = lambda: sentinel

        with patch("agent_repl.plugin_loader.importlib.import_module", return_value=mock_module):
            result = load_plugin("my_module")

        assert result is sentinel


class TestImportError:
    """Requirement 10.3: Import failure logs warning and returns None."""

    def test_missing_module(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = load_plugin("nonexistent.module.that.does.not.exist")

        assert result is None
        assert "Failed to import plugin module" in caplog.text
        assert "nonexistent.module.that.does.not.exist" in caplog.text

    def test_import_error_logged(self, caplog):
        with (
            patch(
                "agent_repl.plugin_loader.importlib.import_module",
                side_effect=ImportError("no such module"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = load_plugin("broken.module")

        assert result is None
        assert "no such module" in caplog.text


class TestMissingFactory:
    """Requirement 10.2: Module without create_plugin() logs warning and returns None."""

    def test_no_create_plugin(self, caplog):
        mock_module = types.ModuleType("no_factory")
        # Module exists but has no create_plugin attribute

        with (
            patch("agent_repl.plugin_loader.importlib.import_module", return_value=mock_module),
            caplog.at_level(logging.WARNING),
        ):
            result = load_plugin("no_factory")

        assert result is None
        assert "no create_plugin()" in caplog.text

    def test_create_plugin_not_callable(self, caplog):
        mock_module = types.ModuleType("bad_factory")
        mock_module.create_plugin = "not a function"

        with (
            patch("agent_repl.plugin_loader.importlib.import_module", return_value=mock_module),
            caplog.at_level(logging.WARNING),
        ):
            result = load_plugin("bad_factory")

        assert result is None
        assert "not callable" in caplog.text


class TestFactoryException:
    """Requirement 10.3 (extended): create_plugin() raises -> log warning, return None."""

    def test_factory_raises(self, caplog):
        mock_module = types.ModuleType("exploding")
        mock_module.create_plugin = MagicMock(side_effect=RuntimeError("boom"))

        with (
            patch("agent_repl.plugin_loader.importlib.import_module", return_value=mock_module),
            caplog.at_level(logging.WARNING),
        ):
            result = load_plugin("exploding")

        assert result is None
        assert "raised an error" in caplog.text
        assert "boom" in caplog.text

    def test_factory_raises_value_error(self, caplog):
        mock_module = types.ModuleType("bad_config")
        mock_module.create_plugin = MagicMock(side_effect=ValueError("bad config"))

        with (
            patch("agent_repl.plugin_loader.importlib.import_module", return_value=mock_module),
            caplog.at_level(logging.WARNING),
        ):
            result = load_plugin("bad_config")

        assert result is None
        assert "bad config" in caplog.text
