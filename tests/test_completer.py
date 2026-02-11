"""Tests for completer module.

Covers Requirements 4.6-4.9, 4.E1, 4.E2.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from prompt_toolkit.document import Document

from agent_repl.command_registry import CommandRegistry
from agent_repl.completer import SlashCommandCompleter
from agent_repl.types import SlashCommand


async def _noop(ctx: object) -> None:
    pass


def _cmd(name: str, description: str = "") -> SlashCommand:
    return SlashCommand(name=name, description=description or f"Desc for {name}", handler=_noop)


def _fmt_to_str(fmt_text: object) -> str:
    """Convert FormattedText or plain string to str."""
    if isinstance(fmt_text, str):
        return fmt_text
    # FormattedText is a list of (style, text) tuples
    return "".join(t[1] for t in fmt_text)


def _completions(completer: SlashCommandCompleter, text: str) -> list[str]:
    """Get completion display texts for given input text."""
    doc = Document(text, len(text))
    event = MagicMock()
    results = completer.get_completions(doc, event)
    return [_fmt_to_str(c.display) for c in results]


class TestBareSlash:
    """Requirement 4.6: Bare / shows pinned commands."""

    def test_bare_slash_returns_pinned(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("quit"))
        reg.register(_cmd("version"))
        completer = SlashCommandCompleter(reg, pinned_names=["help", "quit"])
        result = _completions(completer, "/")
        assert result == ["/help", "/quit"]

    def test_bare_slash_pinned_order(self):
        reg = CommandRegistry()
        reg.register(_cmd("quit"))
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=["quit", "help"])
        result = _completions(completer, "/")
        assert result == ["/quit", "/help"]

    def test_bare_slash_max_pinned(self):
        reg = CommandRegistry()
        for name in ["a", "b", "c", "d"]:
            reg.register(_cmd(name))
        completer = SlashCommandCompleter(
            reg, pinned_names=["a", "b", "c", "d"], max_pinned=2
        )
        result = _completions(completer, "/")
        assert len(result) == 2


class TestPrefixCompletion:
    """Requirement 4.7: /<prefix> shows matching commands alphabetically."""

    def test_prefix_match(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        reg.register(_cmd("history"))
        reg.register(_cmd("quit"))
        completer = SlashCommandCompleter(reg, pinned_names=[])
        result = _completions(completer, "/h")
        assert result == ["/help", "/history"]

    def test_prefix_exact(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=[])
        result = _completions(completer, "/help")
        assert result == ["/help"]

    def test_prefix_alphabetical_order(self):
        reg = CommandRegistry()
        reg.register(_cmd("zebra"))
        reg.register(_cmd("alpha"))
        reg.register(_cmd("able"))
        completer = SlashCommandCompleter(reg, pinned_names=[])
        result = _completions(completer, "/a")
        assert result == ["/able", "/alpha"]


class TestNoMatch:
    """Requirement 4.E1: No matches returns empty."""

    def test_no_match(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=[])
        result = _completions(completer, "/z")
        assert result == []

    def test_empty_registry(self):
        reg = CommandRegistry()
        completer = SlashCommandCompleter(reg, pinned_names=[])
        result = _completions(completer, "/h")
        assert result == []


class TestEmptyPinned:
    """Requirement 4.E2: Empty pinned list returns nothing for bare /."""

    def test_empty_pinned(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=[])
        result = _completions(completer, "/")
        assert result == []


class TestDismiss:
    """Requirement 4.8: ESC dismiss."""

    def test_dismiss(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=["help"])
        completer.dismiss()
        result = _completions(completer, "/")
        assert result == []

    def test_dismiss_prefix(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=[])
        completer.dismiss()
        result = _completions(completer, "/h")
        assert result == []

    def test_reset_dismiss(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=["help"])
        completer.dismiss()
        completer.reset_dismiss()
        result = _completions(completer, "/")
        assert result == ["/help"]


class TestNonSlashInput:
    """No completions for non-slash input."""

    def test_plain_text(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=["help"])
        result = _completions(completer, "hello")
        assert result == []

    def test_empty_input(self):
        reg = CommandRegistry()
        reg.register(_cmd("help"))
        completer = SlashCommandCompleter(reg, pinned_names=["help"])
        result = _completions(completer, "")
        assert result == []


class TestCompletionMetadata:
    """Verify completion objects have description metadata."""

    def test_completion_has_meta(self):
        reg = CommandRegistry()
        reg.register(_cmd("help", "Show help"))
        completer = SlashCommandCompleter(reg, pinned_names=["help"])
        doc = Document("/", 1)
        event = MagicMock()
        results = completer.get_completions(doc, event)
        assert len(results) == 1
        assert _fmt_to_str(results[0].display_meta) == "Show help"
