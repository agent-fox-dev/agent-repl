"""File context resolver for agent_repl - reads file/directory content for @mentions."""

from __future__ import annotations

from pathlib import Path

from agent_repl.exceptions import FileContextError
from agent_repl.types import FileContent


def resolve_file_context(paths: list[str]) -> list[FileContent]:
    """Resolve a list of file/directory paths into FileContent objects.

    For file paths: read full content.
    For directory paths (ending in /): read all files recursively.
    Raises FileContextError for non-existent or binary files.
    """
    results: list[FileContent] = []
    for path_str in paths:
        p = Path(path_str)
        if not p.exists():
            raise FileContextError(f"Path does not exist: {path_str}")

        if p.is_dir():
            results.extend(_resolve_directory(p))
        else:
            results.append(_resolve_file(p))

    return results


def _resolve_file(path: Path) -> FileContent:
    """Read a single file and return its content."""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise FileContextError(f"Binary or non-text file: {path}")
    return FileContent(path=str(path), content=content)


def _resolve_directory(path: Path) -> list[FileContent]:
    """Read all files in a directory recursively."""
    results: list[FileContent] = []
    for child in sorted(path.rglob("*")):
        if child.is_file():
            results.append(_resolve_file(child))
    return results
