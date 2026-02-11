from __future__ import annotations

import fnmatch
from pathlib import Path

from agent_repl.constants import DEFAULT_MAX_FILE_SIZE
from agent_repl.types import FileContext


def _parse_gitignore(directory: Path) -> list[str]:
    """Parse .gitignore in the given directory and return a list of patterns."""
    gitignore = directory / ".gitignore"
    if not gitignore.is_file():
        return []
    patterns = []
    try:
        for line in gitignore.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    except OSError:
        return []
    return patterns


def _is_gitignored(filename: str, patterns: list[str]) -> bool:
    """Check if a filename matches any gitignore pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def _is_text_file(path: Path) -> bool:
    """Heuristic check for whether a file is text (not binary)."""
    try:
        chunk = path.read_bytes()[:8192]
        if b"\x00" in chunk:
            return False
        return True
    except OSError:
        return False


def resolve_file_context(
    path: str,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> FileContext | list[FileContext]:
    """Resolve a single @path reference to file content(s).

    For a file path, returns a single FileContext.
    For a directory path, returns a list of FileContext objects (sorted by path).
    """
    target = Path(path)

    if not target.exists():
        return FileContext(path=path, error=f"Path not found: {path}")

    if target.is_file():
        return _resolve_single_file(target, max_file_size)

    if target.is_dir():
        return _resolve_directory(target, max_file_size)

    return FileContext(path=path, error=f"Unsupported path type: {path}")


def _resolve_single_file(filepath: Path, max_file_size: int) -> FileContext:
    """Read a single file and return a FileContext."""
    path_str = str(filepath)

    try:
        size = filepath.stat().st_size
    except OSError as e:
        return FileContext(path=path_str, error=f"Cannot stat file: {e}")

    if size > max_file_size:
        return FileContext(
            path=path_str,
            error=f"File too large: {size} bytes (limit: {max_file_size} bytes)",
        )

    if not _is_text_file(filepath):
        return FileContext(path=path_str, error=f"Binary file, skipped: {path_str}")

    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return FileContext(path=path_str, error=f"Not valid UTF-8: {path_str}")
    except OSError as e:
        return FileContext(path=path_str, error=f"Cannot read file: {e}")

    return FileContext(path=path_str, content=content)


def _resolve_directory(dirpath: Path, max_file_size: int) -> list[FileContext]:
    """Read all text files in a directory (non-recursive), sorted alphabetically."""
    patterns = _parse_gitignore(dirpath)
    results: list[FileContext] = []

    try:
        entries = sorted(dirpath.iterdir(), key=lambda p: p.name)
    except OSError as e:
        return [FileContext(path=str(dirpath), error=f"Cannot read directory: {e}")]

    for entry in entries:
        if not entry.is_file():
            continue
        if _is_gitignored(entry.name, patterns):
            continue
        result = _resolve_single_file(entry, max_file_size)
        results.append(result)

    if not results:
        return [FileContext(path=str(dirpath), error=f"No text files found in: {dirpath}")]

    return results


def resolve_mentions(
    mentions: list[str],
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> list[FileContext]:
    """Resolve a list of @path mentions to FileContext objects."""
    results: list[FileContext] = []
    for mention in mentions:
        resolved = resolve_file_context(mention, max_file_size)
        if isinstance(resolved, list):
            results.extend(resolved)
        else:
            results.append(resolved)
    return results
