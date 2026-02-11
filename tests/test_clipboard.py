"""Tests for clipboard module.

Covers Requirements 9.1-9.3, 9.E1-9.E3 and Property 14.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agent_repl.clipboard import copy_to_clipboard
from agent_repl.exceptions import ClipboardError


class TestMacOS:
    """Requirement 9.1: macOS uses pbcopy."""

    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run")
    def test_uses_pbcopy(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        copy_to_clipboard("hello")
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0] == ["pbcopy"]
        assert args[1]["input"] == "hello"

    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run")
    def test_pbcopy_success(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        copy_to_clipboard("test text")  # should not raise


class TestLinuxWayland:
    """Requirement 9.2: Linux Wayland uses wl-copy."""

    @patch("agent_repl.clipboard.os.environ", {"WAYLAND_DISPLAY": "wayland-0"})
    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run")
    def test_uses_wl_copy(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "linux"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        copy_to_clipboard("wayland text")
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["wl-copy"]


class TestLinuxX11:
    """Requirement 9.3: Linux X11 uses xclip."""

    @patch("agent_repl.clipboard.os.environ", {"DISPLAY": ":0"})
    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run")
    def test_uses_xclip(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "linux"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        copy_to_clipboard("x11 text")
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["xclip", "-selection", "clipboard"]


class TestMissingUtility:
    """Requirement 9.E1: Missing utility → descriptive error."""

    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_pbcopy(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "darwin"
        with pytest.raises(ClipboardError, match="pbcopy.*not installed"):
            copy_to_clipboard("text")

    @patch("agent_repl.clipboard.os.environ", {"WAYLAND_DISPLAY": "wayland-0"})
    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_wl_copy(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "linux"
        with pytest.raises(ClipboardError, match="wl-copy.*not installed"):
            copy_to_clipboard("text")

    @patch("agent_repl.clipboard.os.environ", {"DISPLAY": ":0"})
    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_xclip(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "linux"
        with pytest.raises(ClipboardError, match="xclip.*not installed"):
            copy_to_clipboard("text")


class TestUnsupportedPlatform:
    """Requirement 9.E2: Unsupported platform → descriptive error."""

    @patch("agent_repl.clipboard.sys")
    def test_windows(self, mock_sys: MagicMock):
        mock_sys.platform = "win32"
        with pytest.raises(ClipboardError, match="Unsupported platform.*win32"):
            copy_to_clipboard("text")

    @patch("agent_repl.clipboard.os.environ", {})
    @patch("agent_repl.clipboard.sys")
    def test_linux_no_display(self, mock_sys: MagicMock):
        mock_sys.platform = "linux"
        with pytest.raises(ClipboardError, match="No display server"):
            copy_to_clipboard("text")


class TestCommandFailure:
    """Requirement 9.E3: Command failure → error with stderr."""

    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run")
    def test_nonzero_exit(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stderr="pipe broken"
        )
        with pytest.raises(ClipboardError, match="exit code 1.*pipe broken"):
            copy_to_clipboard("text")

    @patch("agent_repl.clipboard.sys")
    @patch("agent_repl.clipboard.subprocess.run")
    def test_empty_stderr(self, mock_run: MagicMock, mock_sys: MagicMock):
        mock_sys.platform = "darwin"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=2, stderr=""
        )
        with pytest.raises(ClipboardError, match="exit code 2"):
            copy_to_clipboard("text")


class TestClipboardProperty14:
    """Property 14: For any platform, exactly one mechanism or error."""

    @patch("agent_repl.clipboard.subprocess.run")
    def test_darwin_selects_pbcopy(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        with patch("agent_repl.clipboard.sys") as mock_sys:
            mock_sys.platform = "darwin"
            copy_to_clipboard("test")
            assert mock_run.call_count == 1
            assert mock_run.call_args[0][0] == ["pbcopy"]

    @patch("agent_repl.clipboard.subprocess.run")
    def test_linux_wayland_selects_wl_copy(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        with (
            patch("agent_repl.clipboard.sys") as mock_sys,
            patch("agent_repl.clipboard.os.environ", {"WAYLAND_DISPLAY": "w"}),
        ):
            mock_sys.platform = "linux"
            copy_to_clipboard("test")
            assert mock_run.call_count == 1
            assert mock_run.call_args[0][0] == ["wl-copy"]

    @patch("agent_repl.clipboard.subprocess.run")
    def test_linux_x11_selects_xclip(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        with (
            patch("agent_repl.clipboard.sys") as mock_sys,
            patch("agent_repl.clipboard.os.environ", {"DISPLAY": ":0"}),
        ):
            mock_sys.platform = "linux"
            copy_to_clipboard("test")
            assert mock_run.call_count == 1
            assert mock_run.call_args[0][0] == ["xclip", "-selection", "clipboard"]

    def test_unsupported_raises_error(self):
        with patch("agent_repl.clipboard.sys") as mock_sys:
            mock_sys.platform = "freebsd"
            with pytest.raises(ClipboardError):
                copy_to_clipboard("test")
