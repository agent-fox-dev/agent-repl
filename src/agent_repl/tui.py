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
        self._audit_logger: Any = None

        # Live text state
        self._live_text_parts: list[str] = []
        self._live_active = False

        # Spinner state
        self._spinner_active = False
        self._status: Any = None

        # Collapsed tool results storage
        self._collapsed_results: list[str] = []

        # Choice prompt state (used during prompt_choice)
        self._choice_selected: int = 0
        self._choice_count: int = 0
        self._choice_list: list[str] = []

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

        @self._kb.add("c-o")
        def _expand_handler(event: Any) -> None:
            if self._live_active or self._spinner_active:
                return
            if self._collapsed_results:
                self.show_expanded_result()
            else:
                self._console.print(
                    Text(
                        "No collapsed output to expand.",
                        style=self._theme.info_color,
                    )
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

        # Audit: log banner info
        banner_content = f"{app_name} v{version}"
        if agent_name:
            banner_content += f" | Agent: {agent_name}"
            if model:
                banner_content += f" ({model})"
        self._audit("SYSTEM", banner_content)

    def show_markdown(self, text: str) -> None:
        """Render text as Rich Markdown with a colored left gutter bar."""
        md = Markdown(text)
        gutter = Text("┃ ", style=self._theme.gutter_color)
        self._console.print(gutter, md, sep="")

    def _audit(self, entry_type: str, content: str) -> None:
        """Log to audit trail if logger is set and active."""
        if self._audit_logger is not None and self._audit_logger.active:
            self._audit_logger.log(entry_type, content)

    def show_info(self, text: str) -> None:
        """Render an informational message."""
        self._console.print(Text(text, style=self._theme.info_color))
        self._audit("INFO", text)

    def show_error(self, text: str) -> None:
        """Render an error message."""
        self._console.print(Text(text, style=self._theme.error_color))
        self._audit("ERROR", text)

    def show_warning(self, text: str) -> None:
        """Render a warning message."""
        self._console.print(Text(text, style="yellow"))
        self._audit("WARNING", text)

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
        self._audit("TOOL_RESULT", f"{icon} {name}: {result}")

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
                Text(
                    f"▸ {hidden} more {noun} (Ctrl+O to expand)",
                    style="dim",
                ),
            )
            self._collapsed_results.append(result)

    def show_expanded_result(self) -> None:
        """Display full output of the most recently collapsed tool result."""
        if self._collapsed_results:
            self._console.print(
                Text(self._collapsed_results[-1], style="dim"),
                highlight=False,
            )

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
                self._audit("AGENT", full_text)

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

    def set_audit_logger(self, audit_logger: Any) -> None:
        """Set the audit logger for recording output."""
        self._audit_logger = audit_logger

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

    async def prompt_choice(
        self, prompt: str, choices: list[str],
    ) -> str | dict[str, Any]:
        """Display numbered choice list with arrow navigation.

        Returns ``{"index": N, "value": "..."}`` or ``"reject"``.
        """
        self._console.print(Text(prompt))

        n = len(choices)
        self._choice_selected = 0
        self._choice_count = n
        self._choice_list = choices

        self._render_choice_list()

        # Dedicated key bindings for arrow navigation
        choice_kb = KeyBindings()

        @choice_kb.add("up")
        def _up(event: Any) -> None:
            self._move_choice_up()
            self._render_choice_list()

        @choice_kb.add("down")
        def _down(event: Any) -> None:
            self._move_choice_down()
            self._render_choice_list()

        choice_session: PromptSession[str] = PromptSession(
            key_bindings=choice_kb,
        )

        while True:
            try:
                answer = await choice_session.prompt_async(
                    HTML(f"<style fg='{self._theme.info_color}'>? </style>"),
                )
            except KeyboardInterrupt:
                return "reject"

            answer = answer.strip().lower()

            if answer == "r":
                return "reject"
            elif answer == "":
                # Enter with no text confirms highlighted choice
                idx = self._choice_selected
                return {"index": idx, "value": choices[idx]}

            try:
                num = int(answer)
                if 1 <= num <= n:
                    return {"index": num - 1, "value": choices[num - 1]}
                else:
                    self._console.print(
                        Text(
                            f"Invalid. Enter 1-{n} or r to reject.",
                            style="dim",
                        )
                    )
            except ValueError:
                self._console.print(
                    Text(
                        f"Invalid. Enter 1-{n} or r to reject.",
                        style="dim",
                    )
                )

    def _render_choice_list(self) -> None:
        """Render the numbered choice list with current highlight."""
        for i, choice in enumerate(self._choice_list):
            if i == self._choice_selected:
                line = Text(f"▸ {i + 1}) {choice}", style="bold")
            else:
                line = Text()
                line.append(f"  {i + 1}) ", style=self._theme.info_color)
                line.append(choice)
            self._console.print(line)
        self._console.print(
            Text("  r) Reject", style=self._theme.error_color),
        )

    def _move_choice_up(self) -> None:
        """Move choice selection up with wrap-around."""
        self._choice_selected = (
            (self._choice_selected - 1) % self._choice_count
        )

    def _move_choice_down(self) -> None:
        """Move choice selection down with wrap-around."""
        self._choice_selected = (
            (self._choice_selected + 1) % self._choice_count
        )

    async def prompt_approval(self, prompt: str, choices: list[str]) -> str:
        """Display binary approval prompt. Returns 'approve' or 'reject'."""
        # Render prompt text
        self._console.print(Text(prompt))

        # Render choice labels
        approve_label = choices[0] if len(choices) > 0 else "Approve"
        reject_label = choices[1] if len(choices) > 1 else "Reject"
        line = Text()
        line.append(f"[a] {approve_label}", style=self._theme.info_color)
        line.append("  ")
        line.append(f"[r] {reject_label}", style=self._theme.error_color)
        self._console.print(line)

        # Dedicated prompt session for approval input
        approval_session: PromptSession[str] = PromptSession()

        while True:
            try:
                answer = await approval_session.prompt_async(
                    HTML(f"<style fg='{self._theme.info_color}'>? </style>"),
                )
            except KeyboardInterrupt:
                return "reject"

            answer = answer.strip().lower()
            if answer in ("a", "1"):
                return "approve"
            elif answer in ("r", "2"):
                return "reject"
            else:
                self._console.print(
                    Text(
                        "Invalid input. Enter a/1 to approve or r/2 to reject.",
                        style="dim",
                    )
                )

    async def prompt_text_input(self, prompt: str) -> str:
        """Display text input prompt. Returns input string or 'reject'."""
        # Render prompt text
        self._console.print(Text(prompt))

        # Render abort hint
        self._console.print(
            Text("(type r or /reject to abort)", style="dim"),
        )

        # Dedicated prompt session for text input
        text_session: PromptSession[str] = PromptSession()

        while True:
            try:
                answer = await text_session.prompt_async(
                    HTML(f"<style fg='{self._theme.info_color}'>? </style>"),
                )
            except KeyboardInterrupt:
                return "reject"

            if not answer.strip():
                self._console.print(
                    Text("Input required. Please enter a response.", style="dim"),
                )
                continue

            if answer.strip() in ("r", "/reject"):
                return "reject"

            return answer.strip()

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
