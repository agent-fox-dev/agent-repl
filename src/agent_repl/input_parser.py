from __future__ import annotations

import re
from dataclasses import dataclass, field

# Matches @<non-whitespace> but not bare @ at end or @ followed by whitespace
_MENTION_RE = re.compile(r"@(\S+)")


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: str


@dataclass(frozen=True)
class ParsedFreeText:
    text: str
    mentions: list[str] = field(default_factory=list)


type ParseResult = ParsedCommand | ParsedFreeText | None


def parse_input(raw: str) -> ParseResult:
    """Classify raw user input as a slash command, free text, or empty.

    Returns None for empty/whitespace-only input, ParsedCommand for slash
    commands, or ParsedFreeText for everything else (with extracted @path
    mentions).
    """
    stripped = raw.strip()
    if not stripped:
        return None

    # Slash command: must start with / followed by at least one non-whitespace char
    if stripped.startswith("/") and len(stripped) > 1 and not stripped[1].isspace():
        # Split on first whitespace to get command name and args
        parts = stripped.split(None, 1)
        name = parts[0][1:]  # strip leading /
        args = parts[1] if len(parts) > 1 else ""
        return ParsedCommand(name=name, args=args)

    # Free text: extract @path mentions
    mentions = _MENTION_RE.findall(stripped)
    return ParsedFreeText(text=stripped, mentions=mentions)
