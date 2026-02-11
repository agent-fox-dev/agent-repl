"""Tests for input_parser module.

Covers Requirements 2.1-2.4, 2.E1-2.E3 and Properties 1-3.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agent_repl.input_parser import ParsedCommand, ParsedFreeText, parse_input

# --- Unit tests ---


class TestEmptyInput:
    """Requirement: empty/whitespace input → None."""

    def test_empty_string(self):
        assert parse_input("") is None

    def test_whitespace_only(self):
        assert parse_input("   ") is None

    def test_tabs_and_newlines(self):
        assert parse_input("\t\n  ") is None


class TestSlashCommandParsing:
    """Requirements 2.1, 2.2, 2.E3."""

    def test_simple_command(self):
        result = parse_input("/help")
        assert isinstance(result, ParsedCommand)
        assert result.name == "help"
        assert result.args == ""

    def test_command_with_args(self):
        result = parse_input("/search foo bar")
        assert isinstance(result, ParsedCommand)
        assert result.name == "search"
        assert result.args == "foo bar"

    def test_command_with_leading_whitespace(self):
        result = parse_input("  /quit")
        assert isinstance(result, ParsedCommand)
        assert result.name == "quit"

    def test_command_args_preserve_internal_whitespace(self):
        result = parse_input("/echo   hello   world")
        assert isinstance(result, ParsedCommand)
        assert result.name == "echo"
        assert result.args == "hello   world"

    def test_command_single_char_name(self):
        result = parse_input("/q")
        assert isinstance(result, ParsedCommand)
        assert result.name == "q"

    def test_command_with_numbers(self):
        result = parse_input("/cmd123 arg")
        assert isinstance(result, ParsedCommand)
        assert result.name == "cmd123"

    def test_command_with_special_chars(self):
        result = parse_input("/cmd-name_v2 arg")
        assert isinstance(result, ParsedCommand)
        assert result.name == "cmd-name_v2"


class TestSlashEdgeCases:
    """Requirements 2.E1, 2.E2."""

    def test_bare_slash(self):
        """2.E1: bare / → free text."""
        result = parse_input("/")
        assert isinstance(result, ParsedFreeText)
        assert result.text == "/"

    def test_slash_followed_by_space(self):
        """2.E2: / followed by whitespace → free text."""
        result = parse_input("/ hello")
        assert isinstance(result, ParsedFreeText)
        assert result.text == "/ hello"

    def test_slash_with_only_spaces_after(self):
        result = parse_input("/   ")
        assert isinstance(result, ParsedFreeText)
        assert result.text == "/"


class TestFreeText:
    """Requirements 2.3, 2.4."""

    def test_plain_text(self):
        result = parse_input("hello world")
        assert isinstance(result, ParsedFreeText)
        assert result.text == "hello world"
        assert result.mentions == []

    def test_text_with_mention(self):
        result = parse_input("look at @src/main.py please")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == ["src/main.py"]

    def test_text_with_multiple_mentions(self):
        result = parse_input("compare @a.py and @b.py")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == ["a.py", "b.py"]

    def test_mention_at_start(self):
        result = parse_input("@file.txt is broken")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == ["file.txt"]

    def test_mention_at_end(self):
        result = parse_input("read @file.txt")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == ["file.txt"]

    def test_bare_at_sign_end(self):
        """2.4: @ at end of input → literal, not mention."""
        result = parse_input("email me @")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == []

    def test_at_with_space_after(self):
        """2.4: @ followed by whitespace → literal."""
        result = parse_input("contact @ support")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == []

    def test_mention_with_directory_path(self):
        result = parse_input("check @src/agent_repl/types.py")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == ["src/agent_repl/types.py"]

    def test_duplicate_mentions(self):
        result = parse_input("@a.py vs @a.py")
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == ["a.py", "a.py"]


# --- Property-based tests ---


@pytest.mark.property
class TestInputParserProperties:
    @given(s=st.text())
    def test_property1_classification_completeness(self, s: str):
        """Property 1: result is exactly one of None, ParsedCommand, ParsedFreeText."""
        result = parse_input(s)
        assert result is None or isinstance(result, (ParsedCommand, ParsedFreeText))

    @given(
        name=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"), blacklist_characters="/"
            ),
            min_size=1,
        ).filter(lambda s: not s[0].isspace() and not any(c.isspace() for c in s)),
        args=st.text().filter(lambda s: s.strip()),  # non-empty after strip
    )
    def test_property2_slash_command_with_args(self, name: str, args: str):
        """Property 2: /name args → ParsedCommand(name, args stripped)."""
        raw = f"/{name} {args}"
        result = parse_input(raw)
        assert isinstance(result, ParsedCommand)
        assert result.name == name
        # split(None, 1) strips leading whitespace from args
        expected_args = raw.strip().split(None, 1)
        assert result.args == (expected_args[1] if len(expected_args) > 1 else "")

    @given(
        name=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"), blacklist_characters="/"
            ),
            min_size=1,
        ).filter(lambda s: not s[0].isspace() and not any(c.isspace() for c in s)),
    )
    def test_property2_slash_command_no_args(self, name: str):
        """Property 2: /name with no args → ParsedCommand(name, '')."""
        raw = f"/{name}"
        result = parse_input(raw)
        assert isinstance(result, ParsedCommand)
        assert result.name == name
        assert result.args == ""

    @given(
        words=st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"), blacklist_characters="@"
                ),
                min_size=1,
            ),
            min_size=1,
            max_size=5,
        ),
        mention_indices=st.lists(st.integers(min_value=0, max_value=4), max_size=3),
    )
    def test_property3_mention_extraction(self, words: list[str], mention_indices: list[int]):
        """Property 3: @path tokens extracted in order."""
        # Build input with some words turned into @mentions
        parts = []
        expected_mentions = []
        for i, word in enumerate(words):
            if i in mention_indices:
                parts.append(f"@{word}")
                expected_mentions.append(word)
            else:
                parts.append(word)
        raw = " ".join(parts)
        result = parse_input(raw)
        if result is None:
            return  # empty after strip
        assert isinstance(result, ParsedFreeText)
        assert result.mentions == expected_mentions
