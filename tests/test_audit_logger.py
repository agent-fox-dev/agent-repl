"""Tests for AuditLogger class."""

from __future__ import annotations

import os
import re
import tempfile
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agent_repl.audit_logger import AuditLogger


class TestAuditLoggerInit:
    """Test AuditLogger initialization."""

    def test_default_directory(self):
        logger = AuditLogger()
        assert logger._directory == ".af"

    def test_custom_directory(self):
        logger = AuditLogger(directory="/tmp/custom")
        assert logger._directory == "/tmp/custom"

    def test_initially_inactive(self):
        logger = AuditLogger()
        assert logger.active is False

    def test_file_path_initially_none(self):
        logger = AuditLogger()
        assert logger.file_path is None


class TestGenerateFilename:
    """Test _generate_filename() method."""

    def test_filename_pattern(self):
        logger = AuditLogger()
        filename = logger._generate_filename()
        assert re.match(r"audit_\d{8}_\d{6}\.log", filename)

    def test_filename_uses_current_time(self):
        from datetime import datetime

        logger = AuditLogger()
        before = datetime.now()
        filename = logger._generate_filename()
        after = datetime.now()

        # Extract date/time from filename
        match = re.match(r"audit_(\d{8})_(\d{6})\.log", filename)
        assert match is not None
        date_str = match.group(1)
        time_str = match.group(2)

        # Verify the date/time is between before and after
        file_date = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
        assert before.replace(microsecond=0) <= file_date <= after.replace(
            microsecond=0
        ) + __import__("datetime").timedelta(seconds=1)


class TestStart:
    """Test start() method."""

    def test_creates_file_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            assert os.path.exists(path)
            assert path.startswith(tmpdir)
            logger.stop()

    def test_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = os.path.join(tmpdir, "subdir")
            logger = AuditLogger(directory=sub)
            path = logger.start()
            assert os.path.isdir(sub)
            assert os.path.exists(path)
            logger.stop()

    def test_sets_active_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            logger.start()
            assert logger.active is True
            logger.stop()

    def test_sets_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            assert logger.file_path == path
            logger.stop()

    def test_returns_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            assert isinstance(path, str)
            assert path.endswith(".log")
            logger.stop()

    def test_writes_system_started_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.stop()
            with open(path) as f:
                lines = f.readlines()
            assert "[SYSTEM] Audit started" in lines[0]

    def test_raises_oserror_on_unwritable_directory(self):
        logger = AuditLogger(directory="/nonexistent/path/that/cannot/exist")
        with pytest.raises(OSError):
            logger.start()


class TestStop:
    """Test stop() method."""

    def test_closes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            logger.start()
            logger.stop()
            assert logger._file is not None
            assert logger._file.closed

    def test_sets_active_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            logger.start()
            logger.stop()
            assert logger.active is False

    def test_writes_system_stopped_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.stop()
            with open(path) as f:
                lines = f.readlines()
            assert "[SYSTEM] Audit stopped" in lines[-1]

    def test_noop_when_not_active(self):
        logger = AuditLogger()
        # Should not raise
        logger.stop()

    def test_flushes_before_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "test entry")
            logger.stop()
            with open(path) as f:
                content = f.read()
            assert "test entry" in content
            assert "Audit stopped" in content


class TestLog:
    """Test log() method."""

    def test_writes_formatted_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "hello world")
            logger.stop()
            with open(path) as f:
                lines = f.readlines()
            # Line 0: started, Line 1: hello world, Line 2: stopped
            assert "[INFO] hello world" in lines[1]

    def test_noop_when_inactive(self):
        logger = AuditLogger()
        # Should not raise - no file open
        logger.log("INFO", "this should be a no-op")

    def test_flushes_after_each_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "entry one")
            # Read file while logger is still active - entry should be flushed
            with open(path) as f:
                content = f.read()
            assert "entry one" in content
            logger.stop()

    def test_disables_auditing_on_io_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            logger.start()
            # Close the file to force I/O error
            logger._file.close()
            logger.log("INFO", "this will fail")
            assert logger.active is False

    def test_entry_format_matches_regex(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "test content")
            logger.stop()
            pattern = re.compile(
                r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\] \[\w+\] .*"
            )
            with open(path) as f:
                for line in f:
                    assert pattern.match(line.rstrip("\n")), f"Line didn't match: {line!r}"

    def test_multiline_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("AGENT", "line one\nline two\nline three")
            logger.stop()
            with open(path) as f:
                content = f.read()
            assert "line one\nline two\nline three" in content

    def test_empty_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "")
            logger.stop()
            with open(path) as f:
                lines = f.readlines()
            # Should have: started, empty info, stopped
            assert len(lines) == 3
            assert "[INFO] \n" == lines[1].split("] ", 1)[1]


class TestStartStopBookends:
    """Test Property 5: Start/Stop Bookends."""

    def test_first_entry_is_system_started(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "middle")
            logger.stop()
            with open(path) as f:
                lines = f.readlines()
            assert "[SYSTEM] Audit started" in lines[0]

    def test_last_entry_is_system_stopped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log("INFO", "middle")
            logger.stop()
            with open(path) as f:
                lines = f.readlines()
            assert "[SYSTEM] Audit stopped" in lines[-1]


class TestTimestampOrdering:
    """Test Property 1: Entry Timestamp Ordering."""

    def test_timestamps_are_monotonically_ordered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            for i in range(10):
                logger.log("INFO", f"entry {i}")
            logger.stop()

            timestamps = []
            with open(path) as f:
                for line in f:
                    match = re.match(r"\[(.+?)\]", line)
                    if match:
                        timestamps.append(match.group(1))

            for i in range(1, len(timestamps)):
                assert timestamps[i] >= timestamps[i - 1]


class TestFileCreationOnStart:
    """Test Property 7: File Creation on Start."""

    def test_file_created_with_correct_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            filename = os.path.basename(path)
            assert re.match(r"audit_\d{8}_\d{6}\.log", filename)
            logger.stop()


class TestGracefulFailure:
    """Test Property 8: Graceful Failure."""

    def test_io_error_disables_auditing_no_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            logger.start()
            # Simulate I/O error by closing file
            logger._file.close()
            # Should not raise
            logger.log("INFO", "will fail gracefully")
            assert logger.active is False

    def test_io_error_logs_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            logger.start()
            logger._file.close()
            with patch("agent_repl.audit_logger.logger") as mock_logger:
                logger.log("INFO", "will fail")
                mock_logger.warning.assert_called_once()


# --- Property-based tests ---


class TestPropertyEntryFormatCompliance:
    """Property 2: Entry Format Compliance."""

    @given(
        entry_type=st.sampled_from(
            ["SYSTEM", "INPUT", "COMMAND", "INFO", "ERROR", "WARNING", "AGENT", "TOOL_RESULT"]
        ),
        content=st.text(min_size=0, max_size=200).filter(
            lambda s: "\n" not in s and "\r" not in s
        ),
    )
    @settings(max_examples=50)
    def test_property_entry_format(self, entry_type: str, content: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            logger.log(entry_type, content)
            logger.stop()

            pattern = re.compile(
                r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\] \[\w+\] .*"
            )
            with open(path) as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line:
                        assert pattern.match(line), f"Line didn't match: {line!r}"


class TestPropertyNoOpWhenInactive:
    """Property 4: No-Op When Inactive."""

    @given(
        entry_type=st.sampled_from(["INFO", "ERROR", "INPUT"]),
        content=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=20)
    def test_property_noop_inactive(self, entry_type: str, content: str):
        logger = AuditLogger()
        assert logger.active is False
        # Should not raise, no file open
        logger.log(entry_type, content)
        assert logger.active is False


class TestPropertyFlushPerEntry:
    """Property 3: Flush Per Entry."""

    def test_property_flush_per_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            for i in range(5):
                logger.log("INFO", f"entry {i}")
                # Each entry should be readable immediately after writing
                with open(path) as f:
                    content = f.read()
                assert f"entry {i}" in content
            logger.stop()


class TestPropertyTimestampOrdering:
    """Property 1: Timestamp Ordering (property-based)."""

    @given(
        n=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=10)
    def test_property_timestamps_ordered(self, n: int):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()
            for i in range(n):
                logger.log("INFO", f"entry {i}")
            logger.stop()

            timestamps = []
            with open(path) as f:
                for line in f:
                    match = re.match(r"\[(.+?)\]", line)
                    if match:
                        timestamps.append(match.group(1))

            for i in range(1, len(timestamps)):
                assert timestamps[i] >= timestamps[i - 1]


class TestPropertyInputClassification:
    """Property 6: Input Classification.

    Inputs starting with '/' should be classified as COMMAND,
    all others as INPUT.
    """

    @given(
        text=st.text(min_size=1, max_size=100).filter(
            lambda s: s.strip() and "\n" not in s and "\r" not in s
        ),
    )
    @settings(max_examples=30)
    def test_property_classification(self, text: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(directory=tmpdir)
            path = logger.start()

            stripped = text.strip()
            if stripped.startswith("/"):
                logger.log("COMMAND", stripped)
            else:
                logger.log("INPUT", stripped)
            logger.stop()

            with open(path) as f:
                content = f.read()

            if stripped.startswith("/"):
                assert "[COMMAND]" in content
                assert "[INPUT]" not in content
            else:
                assert "[INPUT]" in content
                # COMMAND should not appear (except possibly in content)
                lines = content.strip().split("\n")
                non_system = [ln for ln in lines if "[SYSTEM]" not in ln]
                for line in non_system:
                    assert "[INPUT]" in line
