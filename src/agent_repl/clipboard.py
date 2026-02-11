from __future__ import annotations

import os
import subprocess
import sys

from agent_repl.exceptions import ClipboardError


def copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard.

    Raises ClipboardError on failure (unsupported platform, missing utility,
    or command failure).
    """
    cmd = _get_clipboard_command()
    try:
        result = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        utility = cmd[0]
        raise ClipboardError(
            f"Clipboard utility '{utility}' is not installed. "
            f"Please install it to enable clipboard support."
        )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ClipboardError(
            f"Clipboard command failed (exit code {result.returncode}): {stderr}"
        )


def _get_clipboard_command() -> list[str]:
    """Determine the clipboard command for the current platform."""
    if sys.platform == "darwin":
        return ["pbcopy"]

    if sys.platform.startswith("linux"):
        if os.environ.get("WAYLAND_DISPLAY"):
            return ["wl-copy"]
        if os.environ.get("DISPLAY"):
            return ["xclip", "-selection", "clipboard"]
        raise ClipboardError(
            "No display server detected on Linux. "
            "Set WAYLAND_DISPLAY or DISPLAY environment variable."
        )

    raise ClipboardError(f"Unsupported platform for clipboard: {sys.platform}")
