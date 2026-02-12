"""Audit trail logger for recording session activity to a log file."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TextIO

logger = logging.getLogger(__name__)


class AuditLogger:
    """Writes timestamped audit entries to a plain-text log file.

    Entry format: [ISO8601_timestamp] [TYPE] content
    """

    def __init__(self, directory: str = ".af") -> None:
        self._directory = directory
        self._file: TextIO | None = None
        self._file_path: str | None = None
        self._active: bool = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def file_path(self) -> str | None:
        return self._file_path

    def _generate_filename(self) -> str:
        """Generate audit_YYYYMMDD_HHMMSS.log filename."""
        now = datetime.now()
        return f"audit_{now.strftime('%Y%m%d_%H%M%S')}.log"

    def start(self) -> str:
        """Create a new audit file and start logging.

        Returns the file path. Raises OSError on failure.
        """
        os.makedirs(self._directory, exist_ok=True)
        filename = self._generate_filename()
        self._file_path = os.path.join(self._directory, filename)
        self._file = open(self._file_path, "a")  # noqa: SIM115
        self._active = True
        self._write_entry("SYSTEM", "Audit started")
        return self._file_path

    def stop(self) -> None:
        """Write final entry, close file, deactivate."""
        if not self._active or self._file is None:
            return
        self._write_entry("SYSTEM", "Audit stopped")
        self._file.flush()
        self._file.close()
        self._active = False

    def log(self, entry_type: str, content: str) -> None:
        """Write a timestamped entry. No-op if not active."""
        if not self._active:
            return
        try:
            self._write_entry(entry_type, content)
        except (OSError, ValueError) as e:
            logger.warning("Audit write failed, disabling auditing: %s", e)
            self._active = False
            if self._file is not None:
                try:
                    self._file.close()
                except OSError:
                    pass

    def _write_entry(self, entry_type: str, content: str) -> None:
        """Format and write a single entry, flush immediately."""
        if self._file is None:
            return
        timestamp = datetime.now().isoformat(timespec="milliseconds")
        entry = f"[{timestamp}] [{entry_type}] {content}\n"
        self._file.write(entry)
        self._file.flush()
