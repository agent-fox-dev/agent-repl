"""TUI shell for agent_repl - terminal user interface using rich and prompt_toolkit."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.segment import Segment
from rich.style import Style
from rich.text import Text

from agent_repl.completer import SlashCommandCompleter
from agent_repl.types import SlashCommand, Theme

if TYPE_CHECKING:
    from agent_repl.session import Session


def _rich_color_to_pt_style(rich_color: str) -> str:
    """Convert a Rich color name to a prompt_toolkit style string."""
    if not rich_color or rich_color == "default":
        return ""
    # Modifiers like "dim" or "bold" have no prompt_toolkit fg equivalent
    if rich_color in {"dim", "bold", "italic", "underline", "blink", "reverse", "strike"}:
        return ""
    # Hex colors pass through
    if rich_color.startswith("#"):
        return rich_color
    # Named colors
    return f"fg:{rich_color}"


class _LeftGutter:
    """Renders content with a colored left gutter bar."""

    BAR_CHAR = "▎"

    def __init__(self, renderable: RenderableType, style: str) -> None:
        self.renderable = renderable
        self.style = style

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        inner_options = options.update_width(options.max_width - 2)
        lines = console.render_lines(self.renderable, inner_options)
        bar = Segment(self.BAR_CHAR + " ", Style.parse(self.style))
        new_line = Segment.line()
        for line in lines:
            yield bar
            yield from line
            yield new_line


class TUIShell:
    """Terminal user interface with rich output and prompt_toolkit input."""

    def __init__(self, theme: Theme | None = None) -> None:
        self._theme = theme or Theme()
        self._console = Console()
        self._history = InMemoryHistory()
        self._completer: SlashCommandCompleter = SlashCommandCompleter([], [])
        self._app_session: Session | None = None
        self._key_bindings = self._create_key_bindings()
        self._session: PromptSession[str] = PromptSession(
            history=self._history,
            completer=self._completer,
            complete_while_typing=True,
            key_bindings=self._key_bindings,
        )
        self._spinner_task: asyncio.Task[Any] | None = None
        self._spinner_running = False
        self._stream_text: Text | None = None
        self._live: Live | None = None

    def set_session(self, session: Session) -> None:
        """Set the session reference for clipboard operations."""
        self._app_session = session

    def _create_key_bindings(self) -> KeyBindings:
        """Create prompt-toolkit key bindings."""
        kb = KeyBindings()

        @kb.add("c-y")
        def _copy_last_output(event: Any) -> None:
            self._copy_last_output_to_clipboard()

        return kb

    def _copy_last_output_to_clipboard(self) -> None:
        """Copy the last assistant output to the system clipboard."""
        from agent_repl.clipboard import copy_to_clipboard
        from agent_repl.exceptions import ClipboardError

        if self._app_session is None:
            return

        text = self._app_session.get_last_assistant_content()
        if text is None:
            self.display_info("No agent output to copy.")
            return

        try:
            copy_to_clipboard(text)
        except ClipboardError as e:
            self.display_error(str(e))
            return

        self.display_info("Copied to clipboard.")

    async def read_input(self) -> str:
        """Prompt the user for input with history and tab completion."""
        self._console.print(Rule(style=self._theme.prompt_color))
        pt_style = _rich_color_to_pt_style(self._theme.prompt_color)
        prompt = FormattedText([(pt_style, "> ")])
        return await self._session.prompt_async(prompt)

    def display_text(self, text: str) -> None:
        """Render markdown-formatted text in the output area."""
        self._console.print(Markdown(text))

    def display_tool_result(self, name: str, content: str, is_error: bool) -> None:
        """Render a tool result with visual distinction."""
        style = self._theme.tool_error_color if is_error else self._theme.tool_color
        title = f"Tool: {name}" + (" (error)" if is_error else "")
        self._console.print(Panel(content, title=title, border_style=style))

    def display_error(self, message: str) -> None:
        """Render an error message in red."""
        self._console.print(f"[bold red]Error:[/bold red] {message}")

    def display_info(self, message: str) -> None:
        """Render an informational message."""
        self._console.print(message, style=self._theme.cli_output_color)

    def start_stream(self) -> None:
        """Begin a live display context for streaming text."""
        style = self._theme.agent_text_color or None
        self._stream_text = Text(style=style)
        gutter = _LeftGutter(self._stream_text, self._theme.agent_gutter_color)
        self._live = Live(
            gutter, console=self._console, auto_refresh=True, transient=True
        )
        self._live.start()

    def append_stream(self, text: str) -> None:
        """Append a text fragment to the live display."""
        if self._live is None or self._stream_text is None:
            raise RuntimeError("append_stream() called without start_stream()")
        self._stream_text.append(text)
        self._live.update(_LeftGutter(self._stream_text, self._theme.agent_gutter_color))

    def finish_stream(self) -> str:
        """End the live display, render final markdown, return full text."""
        if self._live is None or self._stream_text is None:
            raise RuntimeError("finish_stream() called without start_stream()")
        full_text = self._stream_text.plain
        self._live.stop()
        self._live = None
        self._stream_text = None
        if full_text:
            self._console.print(
                _LeftGutter(Markdown(full_text), self._theme.agent_gutter_color)
            )
        return full_text

    def start_spinner(self) -> None:
        """Start the spinner animation."""
        if self._spinner_running:
            return
        self._spinner_running = True
        self._spinner_task = asyncio.create_task(self._spin())

    def stop_spinner(self) -> None:
        """Stop the spinner animation."""
        self._spinner_running = False
        if self._spinner_task is not None:
            self._spinner_task.cancel()
            self._spinner_task = None
            # Clear the spinner line
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    async def _spin(self) -> None:
        """Internal spinner animation loop."""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        try:
            while self._spinner_running:
                sys.stdout.write(f"\r{frames[idx]} Thinking...")
                sys.stdout.flush()
                idx = (idx + 1) % len(frames)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    def set_completer(
        self,
        commands: list[SlashCommand],
        pinned_names: list[str],
    ) -> None:
        """Update the slash command completer with current commands."""
        self._completer.update_commands(commands, pinned_names)
