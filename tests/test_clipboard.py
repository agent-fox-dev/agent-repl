"""Unit and property tests for clipboard utility.

Property 1: Content Integrity
Property 4: Platform Dispatch
Property 5: Missing Utility Handling
Validates: Requirements 1.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.clipboard import copy_to_clipboard
from agent_repl.exceptions import ClipboardError


class TestCopyToClipboardMacOS:
    @patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/pbcopy")
    @patch("agent_repl.clipboard.subprocess.run")
    @patch("agent_repl.clipboard.sys")
    def test_calls_pbcopy(self, mock_sys, mock_run, mock_which):
        mock_sys.platform = "darwin"
        mock_run.return_value = MagicMock(returncode=0)

        copy_to_clipboard("hello")

        mock_run.assert_called_once_with(
            ["pbcopy"], input=b"hello", capture_output=True
        )

    @patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/pbcopy")
    @patch("agent_repl.clipboard.subprocess.run")
    @patch("agent_repl.clipboard.sys")
    def test_encodes_utf8(self, mock_sys, mock_run, mock_which):
        mock_sys.platform = "darwin"
        mock_run.return_value = MagicMock(returncode=0)

        copy_to_clipboard("hello \u2603 world")

        mock_run.assert_called_once_with(
            ["pbcopy"], input="hello \u2603 world".encode(), capture_output=True
        )


class TestCopyToClipboardLinuxX11:
    @patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/xclip")
    @patch("agent_repl.clipboard.subprocess.run")
    @patch("agent_repl.clipboard.os.environ", {})
    @patch("agent_repl.clipboard.sys")
    def test_calls_xclip(self, mock_sys, mock_run, mock_which):
        mock_sys.platform = "linux"
        mock_run.return_value = MagicMock(returncode=0)

        copy_to_clipboard("data")

        mock_run.assert_called_once_with(
            ["xclip", "-selection", "clipboard"],
            input=b"data",
            capture_output=True,
        )


class TestCopyToClipboardLinuxWayland:
    @patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/wl-copy")
    @patch("agent_repl.clipboard.subprocess.run")
    @patch("agent_repl.clipboard.os.environ", {"WAYLAND_DISPLAY": "wayland-0"})
    @patch("agent_repl.clipboard.sys")
    def test_calls_wl_copy_with_wayland_display(self, mock_sys, mock_run, mock_which):
        mock_sys.platform = "linux"
        mock_run.return_value = MagicMock(returncode=0)

        copy_to_clipboard("data")

        mock_run.assert_called_once_with(
            ["wl-copy"], input=b"data", capture_output=True
        )

    @patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/wl-copy")
    @patch("agent_repl.clipboard.subprocess.run")
    @patch(
        "agent_repl.clipboard.os.environ",
        {"XDG_SESSION_TYPE": "wayland"},
    )
    @patch("agent_repl.clipboard.sys")
    def test_calls_wl_copy_with_xdg_session_type(self, mock_sys, mock_run, mock_which):
        mock_sys.platform = "linux"
        mock_run.return_value = MagicMock(returncode=0)

        copy_to_clipboard("data")

        mock_run.assert_called_once_with(
            ["wl-copy"], input=b"data", capture_output=True
        )


class TestCopyToClipboardErrors:
    @patch("agent_repl.clipboard.shutil.which", return_value=None)
    @patch("agent_repl.clipboard.sys")
    def test_missing_utility_raises(self, mock_sys, mock_which):
        mock_sys.platform = "darwin"

        with pytest.raises(ClipboardError, match="Clipboard utility not found: pbcopy"):
            copy_to_clipboard("text")

    @patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/pbcopy")
    @patch("agent_repl.clipboard.subprocess.run")
    @patch("agent_repl.clipboard.sys")
    def test_subprocess_failure_raises(self, mock_sys, mock_run, mock_which):
        mock_sys.platform = "darwin"
        mock_run.return_value = MagicMock(returncode=1, stderr=b"pipe error")

        with pytest.raises(ClipboardError, match="Clipboard copy failed: pipe error"):
            copy_to_clipboard("text")

    @patch("agent_repl.clipboard.sys")
    def test_unsupported_platform_raises(self, mock_sys):
        mock_sys.platform = "win32"

        with pytest.raises(ClipboardError, match="Unsupported platform: win32"):
            copy_to_clipboard("text")


# --- Property tests ---


class TestProperty1ContentIntegrity:
    """Property 1: For any text, the bytes piped to the clipboard utility are
    identical to text.encode('utf-8').

    Feature: copy_last_output, Property 1: Content Integrity
    """

    @settings(max_examples=200)
    @given(text=st.text(min_size=0, max_size=500))
    def test_stdin_is_exact_utf8(self, text):
        with (
            patch("agent_repl.clipboard.sys") as mock_sys,
            patch("agent_repl.clipboard.subprocess.run") as mock_run,
            patch("agent_repl.clipboard.shutil.which", return_value="/usr/bin/pbcopy"),
        ):
            mock_sys.platform = "darwin"
            mock_run.return_value = MagicMock(returncode=0)

            copy_to_clipboard(text)

            call_args = mock_run.call_args
            assert call_args.kwargs["input"] == text.encode("utf-8")
