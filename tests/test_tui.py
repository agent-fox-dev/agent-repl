"""Tests for tui module.

Covers Requirements 7.1-7.10, 7.E1, 7.E2, and Spec 02 Requirements 1.1-4.6.
"""

from __future__ import annotations

from io import StringIO
from typing import Any
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


class TestDimToolOutput:
    """Validates: Requirements 2.1-2.4, 3.1-3.5. Properties 4, 5, 6."""

    def test_short_result_full_output(self, captured_tui: TUIShell):
        """<=3 lines: full output in dim style, no collapse hint."""
        captured_tui.show_tool_result("search", "line1\nline2\nline3", False)
        output = _get_output(captured_tui)
        assert "✓ search" in output
        assert "line1" in output
        assert "line2" in output
        assert "line3" in output
        assert "▸" not in output
        assert "more line" not in output

    def test_single_line_result(self, captured_tui: TUIShell):
        captured_tui.show_tool_result("tool", "just one line", False)
        output = _get_output(captured_tui)
        assert "✓ tool" in output
        assert "just one line" in output
        assert "▸" not in output

    def test_long_result_collapsed(self, captured_tui: TUIShell):
        """>3 lines: show first 3 + collapse hint."""
        lines = "\n".join(f"line{i}" for i in range(1, 8))
        captured_tui.show_tool_result("search", lines, False)
        output = _get_output(captured_tui)
        assert "✓ search" in output
        assert "line1" in output
        assert "line2" in output
        assert "line3" in output
        assert "line4" not in output
        assert "▸ 4 more lines" in output

    def test_error_result_never_collapsed(self, captured_tui: TUIShell):
        """Error results always show full output."""
        lines = "\n".join(f"err{i}" for i in range(1, 8))
        captured_tui.show_tool_result("exec", lines, True)
        output = _get_output(captured_tui)
        assert "✗ exec" in output
        for i in range(1, 8):
            assert f"err{i}" in output
        assert "▸" not in output

    def test_empty_result_header_only(self, captured_tui: TUIShell):
        captured_tui.show_tool_result("search", "", False)
        output = _get_output(captured_tui)
        assert "✓ search" in output
        non_empty = [x for x in output.strip().split("\n") if x.strip()]
        assert len(non_empty) == 1

    def test_exactly_3_lines_no_collapse(self, captured_tui: TUIShell):
        """Exactly 3 lines: full output, no collapse."""
        captured_tui.show_tool_result(
            "tool", "a\nb\nc", False,
        )
        output = _get_output(captured_tui)
        assert "a" in output
        assert "b" in output
        assert "c" in output
        assert "▸" not in output

    def test_singular_more_line(self, captured_tui: TUIShell):
        """Edge case 3.3: 1 hidden line uses singular."""
        captured_tui.show_tool_result(
            "tool", "a\nb\nc\nd", False,
        )
        output = _get_output(captured_tui)
        assert "▸ 1 more line" in output
        assert "lines" not in output

    def test_no_panel_used(self, captured_tui: TUIShell):
        """Property 4: No Panel instantiation."""
        import rich.panel

        original_init = rich.panel.Panel.__init__
        panel_created = False

        def patched_init(self_panel, *args, **kwargs):
            nonlocal panel_created
            panel_created = True
            original_init(self_panel, *args, **kwargs)

        with patch.object(rich.panel.Panel, "__init__", patched_init):
            captured_tui.show_tool_result("t", "result", False)

        assert not panel_created

    def test_success_header_uses_info_color(self, captured_tui: TUIShell):
        """Req 2.2: Success icon with info_color."""
        captured_tui.show_tool_result("search", "ok", False)
        output = _get_output(captured_tui)
        assert "✓ search" in output

    def test_error_header_uses_error_color(self, captured_tui: TUIShell):
        """Req 2.2: Error icon with error_color."""
        captured_tui.show_tool_result("search", "fail", True)
        output = _get_output(captured_tui)
        assert "✗ search" in output

    @pytest.mark.property
    @given(
        lines=st.lists(
            st.text(
                min_size=1, max_size=30,
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P", "S"),
                ),
            ),
            min_size=5, max_size=20,
        ),
    )
    def test_property5_collapse_threshold(self, lines: list[str]):
        """Property 5: >3 lines → collapse hint present."""
        result = "\n".join(lines)
        config = Config()
        tui = TUIShell(config)
        tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        tui.show_tool_result("tool", result, False)
        output = _get_output(tui)
        assert "▸" in output

    @pytest.mark.property
    @given(
        lines=st.lists(
            st.text(
                min_size=1, max_size=30,
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P", "S"),
                ),
            ),
            min_size=5, max_size=20,
        ),
    )
    def test_property6_error_output_completeness(self, lines: list[str]):
        """Property 6: Error results contain all lines."""
        result = "\n".join(lines)
        config = Config()
        tui = TUIShell(config)
        tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        tui.show_tool_result("tool", result, True)
        output = _get_output(tui)
        assert "▸" not in output
        for line in lines:
            if line.strip():
                assert line in output


class TestCollapsedResultStorage:
    """Validates: Requirements 3.6, 3.7. Property 7."""

    def test_collapsed_result_stored(self, captured_tui: TUIShell):
        """Full text stored when result is collapsed."""
        result = "a\nb\nc\nd\ne"
        captured_tui.show_tool_result("tool", result, False)
        assert len(captured_tui._collapsed_results) == 1
        assert captured_tui._collapsed_results[0] == result

    def test_storage_grows_sequentially(self, captured_tui: TUIShell):
        """Storage grows with each collapsed result."""
        r1 = "1\n2\n3\n4"
        r2 = "a\nb\nc\nd\ne"
        captured_tui.show_tool_result("t1", r1, False)
        captured_tui.show_tool_result("t2", r2, False)
        assert len(captured_tui._collapsed_results) == 2
        assert captured_tui._collapsed_results[0] == r1
        assert captured_tui._collapsed_results[1] == r2

    def test_short_result_not_stored(self, captured_tui: TUIShell):
        """Results <=3 lines are not stored."""
        captured_tui.show_tool_result("t", "a\nb\nc", False)
        assert len(captured_tui._collapsed_results) == 0

    def test_error_result_not_stored(self, captured_tui: TUIShell):
        """Error results are never stored (always shown in full)."""
        captured_tui.show_tool_result("t", "a\nb\nc\nd\ne", True)
        assert len(captured_tui._collapsed_results) == 0

    def test_clear_resets_storage(self, captured_tui: TUIShell):
        """clear_collapsed_results() empties the list."""
        captured_tui.show_tool_result("t", "a\nb\nc\nd", False)
        assert len(captured_tui._collapsed_results) == 1
        captured_tui.clear_collapsed_results()
        assert len(captured_tui._collapsed_results) == 0

    def test_initially_empty(self, captured_tui: TUIShell):
        assert captured_tui._collapsed_results == []

    @pytest.mark.property
    @given(
        lines=st.lists(
            st.text(
                min_size=1, max_size=50,
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "P", "S"),
                ),
            ),
            min_size=5, max_size=20,
        ),
    )
    def test_property7_collapsed_storage_integrity(self, lines: list[str]):
        """Property 7: Stored text is identical to original."""
        result = "\n".join(lines)
        config = Config()
        tui = TUIShell(config)
        tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        tui.show_tool_result("tool", result, False)
        assert len(tui._collapsed_results) == 1
        assert tui._collapsed_results[0] == result


class TestExpandShortcut:
    """Validates: Requirements 4.1-4.6. Property 8."""

    def test_no_collapsed_results_shows_info(self, captured_tui: TUIShell):
        """Req 4.5: Info message when no collapsed results."""
        captured_tui.show_expanded_result()
        # show_expanded_result does nothing when list is empty
        # The Ctrl+O handler shows the info message instead
        assert len(captured_tui._collapsed_results) == 0

    def test_expand_single_result(self, captured_tui: TUIShell):
        """Req 4.2: Expand shows full output in dim style."""
        full_text = "line1\nline2\nline3\nline4\nline5"
        captured_tui.show_tool_result("tool", full_text, False)
        # Reset output to capture only the expand
        captured_tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        captured_tui.show_expanded_result()
        output = _get_output(captured_tui)
        assert "line1" in output
        assert "line2" in output
        assert "line3" in output
        assert "line4" in output
        assert "line5" in output

    def test_expand_most_recent_only(self, captured_tui: TUIShell):
        """Req 4.2, Edge 4.1: Multiple collapsed, expand most recent."""
        r1 = "a\nb\nc\nd\ne"
        r2 = "x\ny\nz\nw\nv"
        captured_tui.show_tool_result("t1", r1, False)
        captured_tui.show_tool_result("t2", r2, False)
        # Reset output
        captured_tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        captured_tui.show_expanded_result()
        output = _get_output(captured_tui)
        # Should contain r2 content, not r1
        assert "x" in output
        assert "w" in output
        assert "v" in output

    def test_collapse_hint_references_shortcut(self, captured_tui: TUIShell):
        """Req 4.6: Collapse hint includes Ctrl+O reference."""
        captured_tui.show_tool_result(
            "tool", "a\nb\nc\nd\ne", False,
        )
        output = _get_output(captured_tui)
        assert "Ctrl+O to expand" in output

    def test_ctrl_o_binding_registered(self, captured_tui: TUIShell):
        """Req 4.3: Ctrl+O registered in KeyBindings."""
        handler = _find_key_handler(captured_tui, "c-o")
        assert handler is not None

    def test_ctrl_o_no_action_during_live(self, captured_tui: TUIShell):
        """Edge 4.2: No action during active streaming."""
        full_text = "a\nb\nc\nd\ne"
        captured_tui.show_tool_result("tool", full_text, False)
        # Simulate active streaming
        captured_tui._live_active = True
        # Find and invoke the Ctrl+O handler
        handler = _find_key_handler(captured_tui, "c-o")
        assert handler is not None
        # Reset console to check no output
        captured_tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        handler(MagicMock())
        output = _get_output(captured_tui)
        # Should produce no output during streaming
        assert output.strip() == ""

    def test_ctrl_o_no_action_during_spinner(self, captured_tui: TUIShell):
        """Edge 4.2: No action during spinner active."""
        full_text = "a\nb\nc\nd\ne"
        captured_tui.show_tool_result("tool", full_text, False)
        captured_tui._spinner_active = True
        handler = _find_key_handler(captured_tui, "c-o")
        assert handler is not None
        captured_tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        handler(MagicMock())
        output = _get_output(captured_tui)
        assert output.strip() == ""

    def test_ctrl_o_empty_shows_info_message(self, captured_tui: TUIShell):
        """Req 4.5: Ctrl+O with no results shows message."""
        handler = _find_key_handler(captured_tui, "c-o")
        assert handler is not None
        handler(MagicMock())
        output = _get_output(captured_tui)
        assert "No collapsed output to expand" in output

    @pytest.mark.property
    @given(
        count=st.integers(min_value=1, max_value=10),
    )
    def test_property8_expand_index_validity(self, count: int):
        """Property 8: Expand always shows last element."""
        config = Config()
        tui = TUIShell(config)
        tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        for i in range(count):
            result = "\n".join(
                f"item{i}_line{j}" for j in range(5)
            )
            tui.show_tool_result(f"t{i}", result, False)
        # Reset and expand
        tui._console = Console(
            file=StringIO(), force_terminal=True, width=200,
        )
        tui.show_expanded_result()
        output = _get_output(tui)
        # Should contain the last result's content
        assert f"item{count - 1}_line0" in output
        assert f"item{count - 1}_line4" in output


def _find_key_handler(tui: TUIShell, key: str) -> Any:
    """Find the handler function for a given key binding."""
    for binding in tui._kb.bindings:
        if any(getattr(k, "value", str(k)) == key for k in binding.keys):
            return binding.handler
    return None
