"""Tests for file_context module.

Covers Requirements 3.1-3.4, 3.E1-3.E5 and Properties 12-13.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.file_context import resolve_file_context, resolve_mentions
from agent_repl.types import FileContext

# --- Unit tests: file resolution ---


class TestResolveFile:
    """Requirements 3.1, 3.3, 3.4."""

    def test_read_text_file(self, tmp_path):
        """3.1: Read file as UTF-8 text."""
        f = tmp_path / "hello.py"
        f.write_text("print('hello')", encoding="utf-8")
        result = resolve_file_context(str(f))
        assert isinstance(result, FileContext)
        assert result.content == "print('hello')"
        assert result.error is None

    def test_read_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = resolve_file_context(str(f))
        assert isinstance(result, FileContext)
        assert result.content == ""
        assert result.error is None

    def test_size_limit_exceeded(self, tmp_path):
        """3.3: File exceeding size limit → error."""
        f = tmp_path / "big.txt"
        f.write_text("x" * 1000, encoding="utf-8")
        result = resolve_file_context(str(f), max_file_size=500)
        assert isinstance(result, FileContext)
        assert result.content is None
        assert "too large" in result.error
        assert "500" in result.error

    def test_size_limit_at_boundary(self, tmp_path):
        """File exactly at limit should succeed."""
        f = tmp_path / "exact.txt"
        f.write_text("x" * 100, encoding="utf-8")
        result = resolve_file_context(str(f), max_file_size=100)
        assert isinstance(result, FileContext)
        assert result.content == "x" * 100


class TestResolveFileErrors:
    """Requirements 3.E1, 3.E2, 3.E3."""

    def test_missing_path(self, tmp_path):
        """3.E1: Missing path → clear error."""
        result = resolve_file_context(str(tmp_path / "nonexistent.txt"))
        assert isinstance(result, FileContext)
        assert result.content is None
        assert "not found" in result.error.lower()

    def test_binary_file(self, tmp_path):
        """3.E2: Binary file → error."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\x03\xff")
        result = resolve_file_context(str(f))
        assert isinstance(result, FileContext)
        assert result.content is None
        assert "binary" in result.error.lower() or "Binary" in result.error

    def test_non_utf8_file(self, tmp_path):
        """3.E2: Non-UTF-8 file → error."""
        f = tmp_path / "latin.txt"
        # Latin-1 encoded text with bytes invalid in UTF-8
        f.write_bytes(b"caf\xe9 cr\xe8me")
        result = resolve_file_context(str(f))
        assert isinstance(result, FileContext)
        assert result.content is None
        assert result.error is not None


# --- Unit tests: directory resolution ---


class TestResolveDirectory:
    """Requirements 3.2, 3.E4, 3.E5."""

    def test_reads_text_files_sorted(self, tmp_path):
        """3.2: Non-recursive, sorted alphabetically."""
        (tmp_path / "c.txt").write_text("c", encoding="utf-8")
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0].content == "a"
        assert result[1].content == "b"
        assert result[2].content == "c"

    def test_non_recursive(self, tmp_path):
        """3.2: Does not descend into subdirectories."""
        (tmp_path / "top.txt").write_text("top", encoding="utf-8")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested", encoding="utf-8")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        paths = [r.path for r in result]
        assert any("top.txt" in p for p in paths)
        assert not any("nested.txt" in p for p in paths)

    def test_skips_binary_files(self, tmp_path):
        """3.4: Only text files."""
        (tmp_path / "text.txt").write_text("hello", encoding="utf-8")
        (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        # binary file should still appear but with an error
        text_results = [r for r in result if r.content is not None]
        error_results = [r for r in result if r.error is not None]
        assert len(text_results) == 1
        assert len(error_results) == 1

    def test_empty_directory(self, tmp_path):
        """3.E4: Empty directory → informational message."""
        empty = tmp_path / "empty"
        empty.mkdir()
        result = resolve_file_context(str(empty))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].error is not None
        assert "no text files" in result[0].error.lower()

    def test_gitignore_filtering(self, tmp_path):
        """3.E5: .gitignore patterns exclude matching files."""
        (tmp_path / ".gitignore").write_text("*.log\nsecret.txt\n", encoding="utf-8")
        (tmp_path / "app.py").write_text("code", encoding="utf-8")
        (tmp_path / "debug.log").write_text("log data", encoding="utf-8")
        (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
        (tmp_path / "readme.md").write_text("readme", encoding="utf-8")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        names = [_file_context_name(r) for r in result]
        # .gitignore itself is not ignored
        assert ".gitignore" in names
        assert "app.py" in names
        assert "readme.md" in names
        assert "debug.log" not in names
        assert "secret.txt" not in names

    def test_gitignore_comments_ignored(self, tmp_path):
        """Comments in .gitignore should not be treated as patterns."""
        (tmp_path / ".gitignore").write_text("# comment\n*.tmp\n", encoding="utf-8")
        (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
        (tmp_path / "remove.tmp").write_text("tmp", encoding="utf-8")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        names = [_file_context_name(r) for r in result]
        assert "keep.txt" in names
        assert "remove.tmp" not in names

    def test_no_gitignore(self, tmp_path):
        """No .gitignore → no filtering."""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.log").write_text("b", encoding="utf-8")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        assert len(result) == 2


def _file_context_name(fc: FileContext) -> str:
    """Extract just the filename from a FileContext path."""
    import os

    return os.path.basename(fc.path)


# --- Unit tests: resolve_mentions ---


class TestResolveMentions:
    def test_empty_mentions(self):
        result = resolve_mentions([])
        assert result == []

    def test_single_file_mention(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("code", encoding="utf-8")
        result = resolve_mentions([str(f)])
        assert len(result) == 1
        assert result[0].content == "code"

    def test_mixed_file_and_directory(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("code", encoding="utf-8")
        d = tmp_path / "mydir"
        d.mkdir()
        (d / "a.txt").write_text("a", encoding="utf-8")
        (d / "b.txt").write_text("b", encoding="utf-8")
        result = resolve_mentions([str(f), str(d)])
        assert len(result) == 3  # 1 file + 2 dir entries

    def test_missing_mention(self, tmp_path):
        result = resolve_mentions([str(tmp_path / "nope.txt")])
        assert len(result) == 1
        assert result[0].error is not None


# --- Property-based tests ---


@pytest.mark.property
class TestFileContextProperties:
    @given(
        size=st.integers(min_value=0, max_value=10000),
        limit=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=50)
    def test_property12_size_enforcement(self, size: int, limit: int):
        """Property 12: Files exceeding limit → error FileContext."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "test.txt"
            f.write_text("x" * size, encoding="utf-8")
            result = resolve_file_context(str(f), max_file_size=limit)
            assert isinstance(result, FileContext)
            if size > limit:
                assert result.error is not None
                assert result.content is None
            else:
                assert result.content is not None
                assert result.error is None

    def test_property13_directory_determinism(self, tmp_path):
        """Property 13: Directory results sorted by path."""
        names = ["z.txt", "m.txt", "a.txt", "f.txt"]
        for name in names:
            (tmp_path / name).write_text(name, encoding="utf-8")
        result = resolve_file_context(str(tmp_path))
        assert isinstance(result, list)
        result_names = [_file_context_name(r) for r in result]
        assert result_names == sorted(result_names)
