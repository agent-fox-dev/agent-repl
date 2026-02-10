"""Input parser for agent_repl - classifies user input and extracts references."""

from __future__ import annotations

import re

from agent_repl.types import InputType, ParsedInput

# Match @path references: @ followed by non-whitespace characters
# Supports file paths and directory paths (ending in /)
_AT_MENTION_PATTERN = re.compile(r"@(\S+)")


def parse_input(raw: str) -> ParsedInput:
    """Parse raw user input into a structured ParsedInput.

    Classifies input as SLASH_COMMAND if it starts with `/` followed by
    one or more non-whitespace characters, and as FREE_TEXT otherwise.
    """
    stripped = raw.strip()

    if _is_slash_command(stripped):
        return _parse_slash_command(stripped, raw)

    return _parse_free_text(stripped, raw)


def _is_slash_command(stripped: str) -> bool:
    """Check if input is a slash command: starts with / followed by non-whitespace."""
    if len(stripped) < 2:
        return False
    return stripped[0] == "/" and not stripped[1].isspace()


def _parse_slash_command(stripped: str, raw: str) -> ParsedInput:
    """Parse a slash command into command name and arguments."""
    # Split on first whitespace to get command name and args
    parts = stripped.split(None, 1)
    command_name = parts[0][1:]  # Remove leading /
    command_args = parts[1] if len(parts) > 1 else ""

    return ParsedInput(
        input_type=InputType.SLASH_COMMAND,
        raw=raw,
        command_name=command_name,
        command_args=command_args,
    )


def _parse_free_text(stripped: str, raw: str) -> ParsedInput:
    """Parse free text input, extracting @path references."""
    at_mentions = _AT_MENTION_PATTERN.findall(stripped)

    return ParsedInput(
        input_type=InputType.FREE_TEXT,
        raw=raw,
        at_mentions=at_mentions,
    )
