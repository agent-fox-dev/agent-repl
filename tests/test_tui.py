"""Tests for tui module.

Covers Requirements 7.1-7.10, 7.E1, 7.E2, and Spec 02 Requirements 1.1-1.6.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from rich.console import Console

from agent_repl.exceptions import ClipboardError
from agent_repl.tui import TUIShell, _format_compact_summary
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


class TestFormatCompactSummary:
    """Validates: Requirements 1.2, 1.3. Properties 2, 3."""

    def test_empty_dict(self):
        assert _format_compact_summary({}) == ""

    def test_single_key(self):
        assert _format_compact_summary({"command": "ls -la"}) == "command: ls -la"

    def test_multiple_keys(self):
        result = _format_compact_summary({"file": "x.py", "line": "10"})
        assert result == "file: x.py  line: 10"

    def test_long_value_truncated(self):
        long_val = "a" * 100
        result = _format_compact_summary({"key": long_val})
        assert result == f"key: {'a' * 60}..."
        # Value part should not exceed 63 chars (60 + "...")
        value_part = result.split(": ", 1)[1]
        assert len(value_part) == 63

    def test_none_value(self):
        result = _format_compact_summary({"key": None})
        assert result == 'key: ""'

    def test_nested_dict(self):
        result = _format_compact_summary({"data": {"nested": "value"}})
        assert result == 'data: {"nested": "value"}'

    def test_nested_dict_truncated(self):
        nested = {"k" + str(i): "v" * 20 for i in range(10)}
        result = _format_compact_summary({"data": nested})
        value_part = result.split(": ", 1)[1]
        assert value_part.endswith("...")
        assert len(value_part) <= 63

    def test_integer_value(self):
        result = _format_compact_summary({"count": 42})
        assert result == "count: 42"

    def test_boolean_value(self):
        result = _format_compact_summary({"flag": True})
        assert result == "flag: true"

    def test_list_value(self):
        result = _format_compact_summary({"items": [1, 2, 3]})
        assert result == "items: [1, 2, 3]"

    @pytest.mark.property
    @given(
        d=st.dictionaries(
            st.text(
                min_size=1, max_size=10,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            ),
            st.text(min_size=0, max_size=100),
            min_size=1,
            max_size=5,
        )
    )
    def test_property2_compact_summary_completeness(self, d: dict[str, str]):
        """Property 2: Every top-level key appears in the summary."""
        result = _format_compact_summary(d)
        for key in d:
            assert key in result

    @pytest.mark.property
    @given(
        d=st.dictionaries(
            st.text(
                min_size=1, max_size=10,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            ),
            st.text(min_size=0, max_size=200),
            min_size=1,
            max_size=5,
        )
    )
    def test_property3_value_truncation_bound(self, d: dict[str, str]):
        """Property 3: No rendered value exceeds 63 chars (60 + '...')."""
        result = _format_compact_summary(d)
        # Split on double-space separator, then check each pair
        for pair in result.split("  "):
            if ": " in pair:
                value_part = pair.split(": ", 1)[1]
                assert len(value_part) <= 63


class TestShowToolUse:
    """Validates: Requirements 1.1, 1.4, 1.5. Property 9."""

    def test_tool_name_rendered(self, captured_tui: TUIShell):
        captured_tui.show_tool_use("bash", {"command": "ls"})
        output = _get_output(captured_tui)
        assert "Using tool: bash" in output

    def test_compact_summary_rendered(self, captured_tui: TUIShell):
        captured_tui.show_tool_use("bash", {"command": "ls -la"})
        output = _get_output(captured_tui)
        assert "command: ls -la" in output

    def test_no_summary_for_empty_input(self, captured_tui: TUIShell):
        captured_tui.show_tool_use("bash", {})
        output = _get_output(captured_tui)
        assert "Using tool: bash" in output
        # Only the tool name line, no summary content
        lines = [x for x in output.strip().split("\n") if x.strip()]
        assert len(lines) == 1

    def test_multiple_input_keys(self, captured_tui: TUIShell):
        captured_tui.show_tool_use("edit", {"file": "x.py", "line": "10"})
        output = _get_output(captured_tui)
        assert "Using tool: edit" in output
        assert "file: x.py" in output
        assert "line: 10" in output

    @pytest.mark.property
    @given(
        tool_input=st.dictionaries(
            st.text(
                min_size=1, max_size=10,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            ),
            st.text(min_size=0, max_size=50),
            min_size=0,
            max_size=3,
        )
    )
    def test_property9_empty_input_omission(self, tool_input: dict[str, str]):
        """Property 9: Empty input dict produces only the tool name line."""
        config = Config()
        tui = TUIShell(config)
        tui._console = Console(file=StringIO(), force_terminal=True, width=200)
        tui.show_tool_use("test_tool", tool_input)
        output = _get_output(tui)
        non_empty_lines = [x for x in output.strip().split("\n") if x.strip()]
        if not tool_input:
            assert len(non_empty_lines) == 1
        else:
            assert len(non_empty_lines) == 2
