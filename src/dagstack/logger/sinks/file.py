"""FileSink — write JSON-lines into a local file with native size-based rotation.

Per spec §7.2: FileSink Phase 1 MVP. Uses stdlib
`logging.handlers.RotatingFileHandler` under the hood — a battle-tested
rotation implementation. The format is our canonical JSON-lines (see
wire.to_dagstack_jsonl); the stdlib handler is used purely as a transport.

Rotation options:
    max_bytes: rotate when file size exceeds the limit (0 = disabled).
    keep: number of archived files (max_bytes.1, max_bytes.2, ...).
"""

from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from dagstack.logger.wire import to_dagstack_jsonl

if TYPE_CHECKING:
    from dagstack.logger.records import LogRecord


class FileSink:
    """Write LogRecords to a file as JSON-lines, with native rotation.

    .. warning:: ``path`` is opened verbatim (no path-traversal validation),
       and the open follows symlinks. The host must treat ``path`` as a
       **trusted** configuration value — never accept it directly from
       end-user input or a plugin manifest. If the application supports
       plugin-supplied logging configuration, enforce an allow-list of
       writable directories at the host layer, and consider symlink-resistant
       resolution (e.g., ``Path.resolve(strict=True)`` + prefix check, or
       ``os.open(path, O_NOFOLLOW)`` where the platform supports it)
       upstream of the FileSink.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = 0,
        keep: int = 0,
        min_severity: int = 1,
    ) -> None:
        self._path = Path(path)
        self._handler = RotatingFileHandler(
            filename=str(self._path),
            maxBytes=max_bytes,
            backupCount=keep,
            encoding="utf-8",
        )
        # The stdlib handler formats via Formatter — we pass an already-built
        # JSON line as the message and the formatter simply prints it.
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        self._lock = threading.Lock()
        self._closed = False
        self._min_severity = min_severity
        self.id = f"file:{self._path}"

    def emit(self, record: LogRecord) -> None:
        if self._closed:
            return
        if not self.supports_severity(record.severity_number):
            return
        line = to_dagstack_jsonl(record)
        py_record = _make_logging_record(line)
        with self._lock:
            # Thread-safety double-check (mypy narrowing false positive — see console.py).
            if self._closed:
                return  # type: ignore[unreachable]
            self._handler.emit(py_record)

    def flush(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self._closed:
                self._handler.flush()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._handler.close()

    def supports_severity(self, severity_number: int) -> bool:
        return severity_number >= self._min_severity


def _make_logging_record(message: str) -> logging.LogRecord:
    """Build a dummy logging.LogRecord with a pre-formatted message string.

    Stdlib RotatingFileHandler.emit() requires a `logging.LogRecord`, but the
    content is already a canonical JSON line. The name/level values are
    placeholders (not rendered when formatter = %(message)s).
    """
    return logging.LogRecord(
        name="dagstack.logger.file_sink",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=message,
        args=None,
        exc_info=None,
    )
