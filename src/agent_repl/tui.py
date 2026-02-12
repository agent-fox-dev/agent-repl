from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from agent_repl.clipboard import copy_to_clipboard
from agent_repl.exceptions import ClipboardError
from agent_repl.types import Config

_MAX_VALUE_LENGTH = 60
_COLLAPSE_THRESHOLD = 3


def _format_compact_summary(tool_input: dict[str, Any]) -> str:
    """Format tool input as compact key: value pairs, truncating long values."""
    if not tool_input:
        return ""

    parts: list[str] = []
    for key, value in tool_input.items():
        if value is None:
            rendered = '""'
        elif isinstance(value, str):
            rendered = value.replace("\n", "\\n")
        else:
            rendered = json.dumps(value)

        if len(rendered) > _MAX_VALUE_LENGTH:
            rendered = rendered[:_MAX_VALUE_LENGTH] + "..."

        parts.append(f"{key}: {rendered}")

    return "  ".join(parts)


class TUIShell:
    """Rich-based output rendering and prompt_toolkit-based async input."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._theme = config.theme
        self._console = Console()
        self._completer: Any = None
        self._toolbar_provider: Callable[[], list[str]] | None = None
        self._last_response: str | None = None

        # Live text state
        self._live_text_parts: list[str] = []
        self._live_active = False

        # Spinner state
        self._spinner_active = False
        self._status: Any = None

        # Collapsed tool results storage
        self._collapsed_results: list[str] = []

        # Build key bindings
        self._kb = KeyBindings()

        @self._kb.add("c-y")
        def _copy_handler(event: Any) -> None:
            if self._last_response is not None:
                self._do_copy(self._last_response)
            else:
                self._console.print(
                    Text("No response to copy.", style=self._theme.info_color)
                )

        self._prompt_session: PromptSession[str] = PromptSession(
            key_bindings=self._kb,
        )

    def show_banner(
        self,
        app_name: str,
        version: str,
        agent_name: str | None,
        model: str | None,
    ) -> None:
        """Render startup banner with app info, agent info, and /help hint."""
        self._console.print()
        self._console.print(
            Text(f"{app_name} v{version}", style="bold"),
        )
        if agent_name:
            agent_info = f"Agent: {agent_name}"
            if model:
                agent_info += f" ({model})"
            self._console.print(Text(agent_info, style=self._theme.info_color))
        self._console.print(
            Text("Type /help for available commands.", style="dim"),
        )
        self._console.print()

    def show_markdown(self, text: str) -> None:
        """Render text as Rich Markdown with a colored left gutter bar."""
        md = Markdown(text)
        gutter = Text("┃ ", style=self._theme.gutter_color)
        self._console.print(gutter, md, sep="")

    def show_info(self, text: str) -> None:
        """Render an informational message."""
        self._console.print(Text(text, style=self._theme.info_color))

    def show_error(self, text: str) -> None:
        """Render an error message."""
        self._console.print(Text(text, style=self._theme.error_color))

    def show_warning(self, text: str) -> None:
        """Render a warning message."""
        self._console.print(Text(text, style="yellow"))

    def show_tool_use(self, name: str, tool_input: dict[str, Any]) -> None:
        """Render tool invocation with name and compact input summary."""
        self._console.print(
            Text(f"Using tool: {name}", style=self._theme.info_color)
        )
        summary = _format_compact_summary(tool_input)
        if summary:
            self._console.print(Text(summary, style="dim"))

    def show_tool_result(self, name: str, result: str, is_error: bool) -> None:
        """Render tool result as dim text with optional collapse."""
        # Header line: icon + tool name in themed color
        color = self._theme.error_color if is_error else self._theme.info_color
        icon = "✗" if is_error else "✓"
        self._console.print(Text(f"{icon} {name}", style=color))

        if not result:
            return

        lines = result.split("\n")

        if is_error or len(lines) <= _COLLAPSE_THRESHOLD:
            # Show full output
            self._console.print(
                Text(result, style="dim"), highlight=False,
            )
        else:
            # Show first 3 lines + collapse hint
            visible = "\n".join(lines[:_COLLAPSE_THRESHOLD])
            self._console.print(
                Text(visible, style="dim"), highlight=False,
            )
            hidden = len(lines) - _COLLAPSE_THRESHOLD
            noun = "line" if hidden == 1 else "lines"
            self._console.print(
                Text(f"▸ {hidden} more {noun}", style="dim"),
            )
            self._collapsed_results.append(result)

    def clear_collapsed_results(self) -> None:
        """Clear stored collapsed tool results."""
        self._collapsed_results = []

    def start_spinner(self, text: str = "Thinking...") -> None:
        """Start a Rich spinner/status indicator."""
        if not self._spinner_active:
            self._status = self._console.status(text, spinner="dots")
            self._status.start()
            self._spinner_active = True

    def stop_spinner(self) -> None:
        """Stop and clear the spinner."""
        if self._spinner_active and self._status is not None:
            self._status.stop()
            self._status = None
            self._spinner_active = False

    def start_live_text(self) -> None:
        """Begin accumulating live text for streaming display."""
        self._live_text_parts = []
        self._live_active = True

    def append_live_text(self, text: str) -> None:
        """Append text to the live streaming display."""
        if self._live_active:
            self._live_text_parts.append(text)
            # Print inline without newline for streaming effect
            self._console.print(text, end="", highlight=False)

    def finalize_live_text(self) -> None:
        """Stop live display and finalize the streamed content."""
        if self._live_active:
            full_text = "".join(self._live_text_parts)
            self._live_active = False
            self._live_text_parts = []
            if full_text:
                # End the streaming line and show the gutter bar
                self._console.print()
                gutter = Text("┃", style=self._theme.gutter_color)
                self._console.print(gutter)
                self._last_response = full_text

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard, showing success or error message."""
        self._do_copy(text)

    def _do_copy(self, text: str) -> None:
        """Internal clipboard copy with feedback."""
        try:
            copy_to_clipboard(text)
            self.show_info("Copied to clipboard.")
        except ClipboardError as e:
            self.show_error(str(e))

    async def prompt_input(self) -> str:
        """Prompt the user for input asynchronously."""
        toolbar = self._build_toolbar()
        return await self._prompt_session.prompt_async(
            HTML(f"<style fg='{self._theme.prompt_color}'>❯ </style>"),
            completer=self._completer,
            bottom_toolbar=toolbar,
        )

    def set_completer(self, completer: Any) -> None:
        """Set the prompt_toolkit completer for slash commands."""
        self._completer = completer

    def set_toolbar_provider(self, provider: Callable[[], list[str]]) -> None:
        """Set the callback that provides bottom toolbar content."""
        self._toolbar_provider = provider

    def _build_toolbar(self) -> str | None:
        """Build toolbar text from provider hints."""
        if self._toolbar_provider is None:
            return None
        hints = self._toolbar_provider()
        if not hints:
            return None
        return " | ".join(hints)

    @property
    def console(self) -> Console:
        """Expose console for testing."""
        return self._console

    def set_last_response(self, text: str) -> None:
        """Set the last response text (used by stream handler)."""
        self._last_response = text

    @property
    def last_response(self) -> str | None:
        """Get the last assistant response for clipboard operations."""
        return self._last_response
