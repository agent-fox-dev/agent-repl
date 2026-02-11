"""Tests for tui module.

Covers Requirements 7.1-7.10, 7.E1, 7.E2.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from agent_repl.exceptions import ClipboardError
from agent_repl.tui import TUIShell
from agent_repl.types import Config, Theme


@pytest.fixture
def captured_tui() -> TUIShell:
    """Create a TUIShell with a captured console for output verification."""
    config = Config()
    tui = TUIShell(config)
    # Replace console with one that captures output
    tui._console = Console(file=StringIO(), force_terminal=True, width=80)
    return tui


def _get_output(tui: TUIShell) -> str:
    """Extract captured output from the TUI's console."""
    tui._console.file.seek(0)
    return tui._console.file.read()


class TestBanner:
    """Requirement 7.9: Startup banner."""

    def test_banner_contains_app_name(self, captured_tui: TUIShell):
        captured_tui.show_banner("MyApp", "1.0.0", None, None)
        output = _get_output(captured_tui)
        assert "MyApp" in output
        assert "1.0.0" in output

    def test_banner_contains_agent_info(self, captured_tui: TUIShell):
        captured_tui.show_banner("MyApp", "1.0.0", "Claude", "opus")
        output = _get_output(captured_tui)
        assert "Claude" in output
        assert "opus" in output

    def test_banner_no_agent(self, captured_tui: TUIShell):
        captured_tui.show_banner("MyApp", "1.0.0", None, None)
        output = _get_output(captured_tui)
        assert "MyApp" in output
        assert "/help" in output

    def test_banner_help_hint(self, captured_tui: TUIShell):
        captured_tui.show_banner("MyApp", "1.0.0", None, None)
        output = _get_output(captured_tui)
        assert "/help" in output

    def test_banner_agent_without_model(self, captured_tui: TUIShell):
        captured_tui.show_banner("MyApp", "1.0.0", "Echo", None)
        output = _get_output(captured_tui)
        assert "Echo" in output


class TestShowMarkdown:
    """Requirement 7.3: Markdown rendering with gutter bar."""

    def test_markdown_renders(self, captured_tui: TUIShell):
        captured_tui.show_markdown("**bold text**")
        output = _get_output(captured_tui)
        assert "bold text" in output

    def test_markdown_has_gutter(self, captured_tui: TUIShell):
        captured_tui.show_markdown("hello")
        output = _get_output(captured_tui)
        assert "┃" in output


class TestMessages:
    """Requirements 7.1: Info, error, warning messages."""

    def test_show_info(self, captured_tui: TUIShell):
        captured_tui.show_info("Information here")
        output = _get_output(captured_tui)
        assert "Information here" in output

    def test_show_error(self, captured_tui: TUIShell):
        captured_tui.show_error("Something failed")
        output = _get_output(captured_tui)
        assert "Something failed" in output

    def test_show_warning(self, captured_tui: TUIShell):
        captured_tui.show_warning("Be careful")
        output = _get_output(captured_tui)
        assert "Be careful" in output


class TestToolResult:
    """Requirement 7.5: Tool result panels."""

    def test_success_panel(self, captured_tui: TUIShell):
        captured_tui.show_tool_result("search", "found 5 results", is_error=False)
        output = _get_output(captured_tui)
        assert "search" in output
        assert "found 5 results" in output
        assert "✓" in output

    def test_error_panel(self, captured_tui: TUIShell):
        captured_tui.show_tool_result("search", "not found", is_error=True)
        output = _get_output(captured_tui)
        assert "search" in output
        assert "not found" in output
        assert "✗" in output


class TestSpinner:
    """Requirement 7.4: Spinner lifecycle."""

    def test_start_spinner(self, captured_tui: TUIShell):
        captured_tui.start_spinner("Working...")
        assert captured_tui._spinner_active is True
        captured_tui.stop_spinner()

    def test_stop_spinner(self, captured_tui: TUIShell):
        captured_tui.start_spinner()
        captured_tui.stop_spinner()
        assert captured_tui._spinner_active is False

    def test_stop_spinner_when_not_active(self, captured_tui: TUIShell):
        # Should not raise
        captured_tui.stop_spinner()
        assert captured_tui._spinner_active is False

    def test_double_start(self, captured_tui: TUIShell):
        captured_tui.start_spinner()
        captured_tui.start_spinner()  # Should not create second spinner
        assert captured_tui._spinner_active is True
        captured_tui.stop_spinner()


class TestLiveText:
    """Requirements 7.2: Live text streaming."""

    def test_start_live_text(self, captured_tui: TUIShell):
        captured_tui.start_live_text()
        assert captured_tui._live_active is True

    def test_append_live_text(self, captured_tui: TUIShell):
        captured_tui.start_live_text()
        captured_tui.append_live_text("hello ")
        captured_tui.append_live_text("world")
        assert captured_tui._live_text_parts == ["hello ", "world"]

    def test_finalize_live_text(self, captured_tui: TUIShell):
        captured_tui.start_live_text()
        captured_tui.append_live_text("hello world")
        captured_tui.finalize_live_text()
        assert captured_tui._live_active is False
        assert captured_tui._live_text_parts == []
        assert captured_tui.last_response == "hello world"

    def test_finalize_empty_live_text(self, captured_tui: TUIShell):
        captured_tui.start_live_text()
        captured_tui.finalize_live_text()
        assert captured_tui._live_active is False
        assert captured_tui.last_response is None

    def test_finalize_not_active(self, captured_tui: TUIShell):
        # Should not raise when not active
        captured_tui.finalize_live_text()


class TestClipboard:
    """Requirements 7.6, 7.E1: Ctrl+Y clipboard."""

    @patch("agent_repl.tui.copy_to_clipboard")
    def test_copy_success(self, mock_copy: MagicMock, captured_tui: TUIShell):
        captured_tui.copy_to_clipboard("test text")
        mock_copy.assert_called_once_with("test text")
        output = _get_output(captured_tui)
        assert "Copied" in output

    @patch("agent_repl.tui.copy_to_clipboard", side_effect=ClipboardError("no clipboard"))
    def test_copy_failure(self, mock_copy: MagicMock, captured_tui: TUIShell):
        captured_tui.copy_to_clipboard("test text")
        output = _get_output(captured_tui)
        assert "no clipboard" in output

    def test_last_response_initially_none(self, captured_tui: TUIShell):
        """7.E1: No response to copy."""
        assert captured_tui.last_response is None

    def test_set_last_response(self, captured_tui: TUIShell):
        captured_tui.set_last_response("response text")
        assert captured_tui.last_response == "response text"


class TestCompleter:
    """Requirement 7.7, 4.9: Completer integration."""

    def test_set_completer(self, captured_tui: TUIShell):
        mock_completer = MagicMock()
        captured_tui.set_completer(mock_completer)
        assert captured_tui._completer is mock_completer


class TestToolbar:
    """Requirement 7.8: Toolbar provider."""

    def test_set_toolbar_provider(self, captured_tui: TUIShell):
        def provider() -> list[str]:
            return ["hint1", "hint2"]

        captured_tui.set_toolbar_provider(provider)
        assert captured_tui._toolbar_provider is provider

    def test_build_toolbar(self, captured_tui: TUIShell):
        captured_tui.set_toolbar_provider(lambda: ["hint1", "hint2"])
        result = captured_tui._build_toolbar()
        assert result == "hint1 | hint2"

    def test_build_toolbar_empty_hints(self, captured_tui: TUIShell):
        captured_tui.set_toolbar_provider(lambda: [])
        result = captured_tui._build_toolbar()
        assert result is None

    def test_build_toolbar_no_provider(self, captured_tui: TUIShell):
        result = captured_tui._build_toolbar()
        assert result is None


class TestTheme:
    """Requirement 7.10: Theming via Theme object."""

    def test_custom_theme(self):
        theme = Theme(prompt_color="magenta", gutter_color="yellow")
        config = Config(theme=theme)
        tui = TUIShell(config)
        assert tui._theme.prompt_color == "magenta"
        assert tui._theme.gutter_color == "yellow"

    def test_default_theme(self, captured_tui: TUIShell):
        assert captured_tui._theme.prompt_color == "green"
        assert captured_tui._theme.gutter_color == "blue"
        assert captured_tui._theme.error_color == "red"
        assert captured_tui._theme.info_color == "cyan"
