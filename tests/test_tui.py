"""Unit tests for the TUI shell module.

Property 1: Delta Concatenation Integrity
Property 2: Streaming Lifecycle Safety
Property 5: Backward Compatibility
Validates: Requirements 2.1-2.7, 3.1-3.4, stream_rendering 1-6
"""


from io import StringIO
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from rich.console import Console
from rich.text import Text

from agent_repl.exceptions import ClipboardError
from agent_repl.session import Session
from agent_repl.tui import TUIShell, _LeftGutter, _rich_color_to_pt_style
from agent_repl.types import ConversationTurn, Theme


class TestTUIShell:
    def test_set_completions(self):
        tui = TUIShell()
        tui.set_completions(["/help", "/quit", "/version"])
        assert list(tui._completer.words) == ["/help", "/quit", "/version"]

    def test_set_completions_updates(self):
        tui = TUIShell()
        tui.set_completions(["/help"])
        tui.set_completions(["/help", "/quit"])
        assert list(tui._completer.words) == ["/help", "/quit"]

    def test_display_text_no_crash(self, capsys):
        tui = TUIShell()
        tui.display_text("Hello **world**")
        # Just verify no exception is raised

    def test_display_error_no_crash(self, capsys):
        tui = TUIShell()
        tui.display_error("Something went wrong")

    def test_display_info_no_crash(self, capsys):
        tui = TUIShell()
        tui.display_info("Info message")

    def test_display_tool_result_no_crash(self, capsys):
        tui = TUIShell()
        tui.display_tool_result("read_file", "file contents", is_error=False)

    def test_display_tool_result_error_no_crash(self, capsys):
        tui = TUIShell()
        tui.display_tool_result("read_file", "not found", is_error=True)

    def test_spinner_start_stop(self):
        tui = TUIShell()
        # stop_spinner should be safe to call even if not started
        tui.stop_spinner()
        assert tui._spinner_running is False

    def test_spinner_idempotent_stop(self):
        tui = TUIShell()
        tui.stop_spinner()
        tui.stop_spinner()
        assert tui._spinner_running is False


class TestStreamingAPI:
    """Tests for the start_stream / append_stream / finish_stream API."""

    def test_basic_stream_lifecycle(self):
        tui = TUIShell()
        tui.start_stream()
        tui.append_stream("hello ")
        tui.append_stream("world")
        result = tui.finish_stream()
        assert result == "hello world"

    def test_finish_stream_returns_concatenated_text(self):
        tui = TUIShell()
        tui.start_stream()
        tui.append_stream("a")
        tui.append_stream("b")
        tui.append_stream("c")
        result = tui.finish_stream()
        assert result == "abc"

    def test_empty_stream_returns_empty(self):
        tui = TUIShell()
        tui.start_stream()
        result = tui.finish_stream()
        assert result == ""

    def test_stream_cleans_up_state(self):
        tui = TUIShell()
        tui.start_stream()
        tui.finish_stream()
        assert tui._live is None
        assert tui._stream_text is None


class TestProperty1DeltaConcatenationIntegrity:
    """Property 1: For any sequence of text deltas, finish_stream() returns
    their exact concatenation.

    Feature: stream_rendering, Property 1: Delta Concatenation Integrity
    """

    @settings(max_examples=100)
    @given(
        deltas=st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                ),
                min_size=0,
                max_size=50,
            ),
            min_size=0,
            max_size=20,
        )
    )
    def test_concatenation_integrity(self, deltas):
        tui = TUIShell()
        tui.start_stream()
        for delta in deltas:
            tui.append_stream(delta)
        result = tui.finish_stream()
        assert result == "".join(deltas)


class TestProperty2StreamingLifecycleSafety:
    """Property 2: append_stream() and finish_stream() raise RuntimeError
    if called without start_stream().

    Feature: stream_rendering, Property 2: Streaming Lifecycle Safety
    """

    def test_append_without_start_raises(self):
        tui = TUIShell()
        with pytest.raises(RuntimeError):
            tui.append_stream("text")

    def test_finish_without_start_raises(self):
        tui = TUIShell()
        with pytest.raises(RuntimeError):
            tui.finish_stream()

    def test_append_after_finish_raises(self):
        tui = TUIShell()
        tui.start_stream()
        tui.finish_stream()
        with pytest.raises(RuntimeError):
            tui.append_stream("text")

    def test_finish_after_finish_raises(self):
        tui = TUIShell()
        tui.start_stream()
        tui.finish_stream()
        with pytest.raises(RuntimeError):
            tui.finish_stream()


class TestProperty5BackwardCompatibility:
    """Property 5: display_text() remains functional independently of streaming.

    Feature: stream_rendering, Property 5: Backward Compatibility
    """

    def test_display_text_works_outside_stream(self):
        tui = TUIShell()
        # Should not raise
        tui.display_text("Hello **world**")

    def test_display_text_works_after_stream(self):
        tui = TUIShell()
        tui.start_stream()
        tui.append_stream("streamed")
        tui.finish_stream()
        # display_text should still work
        tui.display_text("non-streamed text")


# --- Color translation tests ---


class TestRichColorToPtStyle:
    """Tests for _rich_color_to_pt_style helper."""

    def test_named_color(self):
        assert _rich_color_to_pt_style("green") == "fg:green"

    def test_named_color_blue(self):
        assert _rich_color_to_pt_style("blue") == "fg:blue"

    def test_hex_color(self):
        assert _rich_color_to_pt_style("#5f87ff") == "#5f87ff"

    def test_empty_string(self):
        assert _rich_color_to_pt_style("") == ""

    def test_default_keyword(self):
        assert _rich_color_to_pt_style("default") == ""

    def test_dim_modifier(self):
        assert _rich_color_to_pt_style("dim") == ""

    def test_bold_modifier(self):
        assert _rich_color_to_pt_style("bold") == ""


# --- LeftGutter renderable tests ---


class TestLeftGutter:
    """Tests for _LeftGutter renderable."""

    def _render(self, renderable, width=40):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=width, color_system="standard")
        console.print(renderable)
        return buf.getvalue()

    def test_single_line_has_gutter(self):
        text = Text("Hello world")
        gutter = _LeftGutter(text, "blue")
        output = self._render(gutter)
        assert "▎" in output
        assert "Hello world" in output

    def test_every_line_has_gutter(self):
        text = Text("Line one\nLine two\nLine three")
        gutter = _LeftGutter(text, "blue")
        output = self._render(gutter)
        lines = [line for line in output.splitlines() if line.strip()]
        for line in lines:
            assert "▎" in line, f"Missing gutter in line: {line!r}"

    def test_empty_text_renders_minimal(self):
        """Empty text renders one line with gutter but no meaningful content."""
        text = Text("")
        gutter = _LeftGutter(text, "blue")
        buf = StringIO()
        console = Console(file=buf, width=40, no_color=True)
        console.print(gutter)
        output = buf.getvalue()
        # Rich renders empty Text as one line; gutter appears but no content
        content_after_bar = output.replace("▎", "").strip()
        assert content_after_bar == ""

    def test_bar_char_constant(self):
        assert _LeftGutter.BAR_CHAR == "▎"


# --- Themed TUI tests ---


class TestThemedTUI:
    """Tests for theme integration in TUIShell."""

    def test_default_theme_applied(self):
        tui = TUIShell()
        assert tui._theme.prompt_color == "green"
        assert tui._theme.agent_gutter_color == "blue"

    def test_custom_theme_applied(self):
        theme = Theme(prompt_color="cyan", agent_gutter_color="red")
        tui = TUIShell(theme=theme)
        assert tui._theme.prompt_color == "cyan"
        assert tui._theme.agent_gutter_color == "red"

    def test_none_theme_uses_default(self):
        tui = TUIShell(theme=None)
        assert tui._theme.prompt_color == "green"

    def test_display_text_no_gutter(self, capsys):
        """display_text should not produce gutter bar character."""
        tui = TUIShell()
        tui.display_text("Hello world")
        captured = capsys.readouterr()
        assert "▎" not in captured.out

    def test_display_error_no_gutter(self, capsys):
        """display_error should not produce gutter bar character."""
        tui = TUIShell()
        tui.display_error("bad thing happened")
        captured = capsys.readouterr()
        assert "▎" not in captured.out

    def test_display_info_no_gutter(self, capsys):
        """display_info should not produce gutter bar character."""
        tui = TUIShell()
        tui.display_info("some info")
        captured = capsys.readouterr()
        assert "▎" not in captured.out

    def test_display_tool_result_no_gutter(self, capsys):
        """display_tool_result should not produce gutter bar character."""
        tui = TUIShell()
        tui.display_tool_result("read", "data", is_error=False)
        captured = capsys.readouterr()
        assert "▎" not in captured.out

    def test_stream_has_gutter_in_final_render(self):
        """finish_stream should render with gutter bar."""
        buf = StringIO()
        theme = Theme(agent_gutter_color="blue")
        tui = TUIShell(theme=theme)
        tui._console = Console(file=buf, force_terminal=True, width=60, color_system="standard")
        tui.start_stream()
        tui.append_stream("Agent response text")
        tui.finish_stream()
        output = buf.getvalue()
        assert "▎" in output
        assert "Agent response text" in output

    def test_empty_stream_returns_empty(self):
        """Empty stream should return empty string and not print final markdown."""
        tui = TUIShell()
        tui.start_stream()
        result = tui.finish_stream()
        assert result == ""

    def test_method_signatures_stable(self):
        """Public methods should accept the same positional arguments as before."""
        tui = TUIShell()
        # display_text(str)
        tui.display_text("test")
        # display_error(str)
        tui.display_error("err")
        # display_info(str)
        tui.display_info("info")
        # display_tool_result(str, str, bool)
        tui.display_tool_result("tool", "content", False)
        # start_stream(), append_stream(str), finish_stream() -> str
        tui.start_stream()
        tui.append_stream("text")
        result = tui.finish_stream()
        assert isinstance(result, str)


# --- Ctrl+Y copy shortcut tests ---


class TestCtrlYBinding:
    """Tests for Ctrl+Y clipboard copy shortcut."""

    @patch("agent_repl.clipboard.copy_to_clipboard")
    def test_ctrl_y_copies_last_output(self, mock_clipboard):
        tui = TUIShell()
        session = Session()
        session.add_turn(ConversationTurn(role="assistant", content="# Hello"))
        tui.set_session(session)

        tui._copy_last_output_to_clipboard()

        mock_clipboard.assert_called_once_with("# Hello")

    @patch("agent_repl.clipboard.copy_to_clipboard")
    def test_ctrl_y_no_output(self, mock_clipboard):
        tui = TUIShell()
        session = Session()
        tui.set_session(session)

        tui._copy_last_output_to_clipboard()

        mock_clipboard.assert_not_called()

    @patch("agent_repl.clipboard.copy_to_clipboard")
    def test_ctrl_y_no_session(self, mock_clipboard):
        tui = TUIShell()
        # No set_session call

        tui._copy_last_output_to_clipboard()

        mock_clipboard.assert_not_called()

    @patch(
        "agent_repl.clipboard.copy_to_clipboard",
        side_effect=ClipboardError("Clipboard utility not found: pbcopy"),
    )
    def test_ctrl_y_clipboard_error(self, mock_clipboard):
        tui = TUIShell()
        session = Session()
        session.add_turn(ConversationTurn(role="assistant", content="text"))
        tui.set_session(session)

        # Should not raise — error is displayed via display_error
        tui._copy_last_output_to_clipboard()

    def test_key_bindings_created(self):
        tui = TUIShell()
        # Verify the key bindings object exists and has at least one binding
        assert tui._key_bindings is not None
        assert len(tui._key_bindings.bindings) > 0

    def test_ctrl_y_binding_registered(self):
        tui = TUIShell()
        keys = [b.keys for b in tui._key_bindings.bindings]
        # prompt-toolkit stores keys as tuples
        assert ("c-y",) in keys
