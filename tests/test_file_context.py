"""Unit and property tests for the file context resolver.

Property 8: AT_MENTION File Inclusion
Property 9: AT_MENTION Directory Inclusion
Property 10: AT_MENTION Error Handling
Validates: Requirements 3.5, 3.6, 3.7
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.exceptions import FileContextError
from agent_repl.file_context import resolve_file_context


class TestResolveFileContext:
    def test_single_file(self, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        result = resolve_file_context([str(f)])
        assert len(result) == 1
        assert result[0].content == "print('hello')"
        assert result[0].path == str(f)

    def test_directory(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("aaa")
        (tmp_path / "b.txt").write_text("bbb")
        result = resolve_file_context([str(tmp_path)])
        assert len(result) == 2
        contents = {fc.content for fc in result}
        assert contents == {"aaa", "bbb"}

    def test_nested_directory(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.txt").write_text("top")
        (sub / "nested.txt").write_text("nested")
        result = resolve_file_context([str(tmp_path)])
        assert len(result) == 2

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileContextError, match="does not exist"):
            resolve_file_context(["/nonexistent/path/file.txt"])

    def test_binary_file_raises(self, tmp_path: Path):
        f = tmp_path / "binary.bin"
        f.write_bytes(bytes(range(256)))
        with pytest.raises(FileContextError, match="Binary"):
            resolve_file_context([str(f)])

    def test_multiple_files(self, tmp_path: Path):
        f1 = tmp_path / "one.txt"
        f2 = tmp_path / "two.txt"
        f1.write_text("one")
        f2.write_text("two")
        result = resolve_file_context([str(f1), str(f2)])
        assert len(result) == 2

    def test_empty_list(self):
        result = resolve_file_context([])
        assert result == []


class TestProperty8FileInclusion:
    """Property 8: File content is fully included.

    Feature: agent_repl, Property 8: AT_MENTION File Inclusion
    """

    @settings(max_examples=100)
    @given(
        content=st.text(
            alphabet=st.characters(
                blacklist_characters="\r",
                blacklist_categories=("Cs",),
            ),
            min_size=1,
            max_size=500,
        )
    )
    def test_full_content_included(self, content):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "test.txt"
            f.write_text(content)
            result = resolve_file_context([str(f)])
            assert len(result) == 1
            assert result[0].content == content


class TestProperty9DirectoryInclusion:
    """Property 9: All files in directory are included.

    Feature: agent_repl, Property 9: AT_MENTION Directory Inclusion
    """

    @settings(max_examples=50)
    @given(
        filenames=st.lists(
            st.from_regex(r"[a-z]{1,10}\.txt", fullmatch=True),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def test_all_directory_files_included(self, filenames):
        with tempfile.TemporaryDirectory() as td:
            for name in filenames:
                (Path(td) / name).write_text(f"content of {name}")
            result = resolve_file_context([td])
            assert len(result) == len(filenames)


class TestProperty10ErrorHandling:
    """Property 10: Non-existent paths raise FileContextError.

    Feature: agent_repl, Property 10: AT_MENTION Error Handling
    """

    @settings(max_examples=100)
    @given(
        name=st.from_regex(r"[a-z]{3,10}\.[a-z]{2,4}", fullmatch=True),
    )
    def test_nonexistent_raises(self, name):
        with pytest.raises(FileContextError):
            resolve_file_context([f"/nonexistent/{name}"])
