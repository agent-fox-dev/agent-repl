"""Clipboard utility for agent_repl - platform-aware copy to system clipboard."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from agent_repl.exceptions import ClipboardError


def _get_clipboard_cmd() -> list[str]:
    """Return the clipboard command and args for the current platform."""
    if sys.platform == "darwin":
        return ["pbcopy"]

    if sys.platform.startswith("linux"):
        # Check for Wayland first
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return ["wl-copy"]
        return ["xclip", "-selection", "clipboard"]

    raise ClipboardError(f"Unsupported platform: {sys.platform}")


def copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard.

    Raises:
        ClipboardError: If the clipboard utility is not found or the
                        subprocess fails.
    """
    cmd = _get_clipboard_cmd()
    utility = cmd[0]

    if shutil.which(utility) is None:
        raise ClipboardError(f"Clipboard utility not found: {utility}")

    result = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ClipboardError(f"Clipboard copy failed: {stderr}")
