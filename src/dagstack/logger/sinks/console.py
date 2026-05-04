"""ConsoleSink — stdout/stderr writer with JSON or pretty dev-mode.

Per spec §7.2: ConsoleSink — Phase 1 MVP, auto-detects TTY for the default
mode. Non-TTY (piped into jq / fluent / container stdout capture) → JSON
wire format. TTY (interactive terminal) → pretty colored output for
developer UX.
"""

from __future__ import annotations

import contextlib
import sys
import threading
from datetime import UTC
from typing import TYPE_CHECKING, Literal, TextIO

from dagstack.logger.severity import (
    SEVERITY_TEXT_DEBUG,
    SEVERITY_TEXT_ERROR,
    SEVERITY_TEXT_FATAL,
    SEVERITY_TEXT_INFO,
    SEVERITY_TEXT_TRACE,
    SEVERITY_TEXT_WARN,
)
from dagstack.logger.wire import to_dagstack_jsonl

if TYPE_CHECKING:
    from dagstack.logger.records import LogRecord


ConsoleMode = Literal["auto", "json", "pretty"]


# ANSI escape codes. Used only in pretty mode when the stream is a TTY.
_ANSI_RESET = "\033[0m"
_ANSI_DIM = "\033[2m"
_ANSI_SEVERITY_COLOR: dict[str, str] = {
    SEVERITY_TEXT_TRACE: "\033[2;37m",  # dim gray
    SEVERITY_TEXT_DEBUG: "\033[36m",  # cyan
    SEVERITY_TEXT_INFO: "\033[32m",  # green
    SEVERITY_TEXT_WARN: "\033[33m",  # yellow
    SEVERITY_TEXT_ERROR: "\033[31m",  # red
    SEVERITY_TEXT_FATAL: "\033[1;31m",  # bold red
}


class ConsoleSink:
    """Write LogRecords to stdout/stderr as JSON-lines or pretty colored text.

    Args:
        mode: "auto" (TTY → pretty, non-TTY → json), "json" forces JSON, "pretty" forces pretty.
        stream: destination stream, default `sys.stderr`.
        min_severity: early-drop threshold (records with severity_number < min_severity are skipped).
    """

    def __init__(
        self,
        *,
        mode: ConsoleMode = "auto",
        stream: TextIO | None = None,
        min_severity: int = 1,
    ) -> None:
        self._stream: TextIO = stream if stream is not None else sys.stderr
        self._mode: ConsoleMode = mode
        self._min_severity = min_severity
        self._lock = threading.Lock()
        self._closed = False
        self.id = f"console:{mode}"

    def emit(self, record: LogRecord) -> None:
        if self._closed:
            return
        if not self.supports_severity(record.severity_number):
            return
        line = self._format(record)
        with self._lock:
            # Second close check inside the lock — race with concurrent close()
            # from another thread. Mypy narrowing sees self._closed=False after
            # the first check, but the value may change between checks; the
            # `# type: ignore[unreachable]` below covers this thread-safety branch.
            if self._closed:
                return  # type: ignore[unreachable]
            self._stream.write(line + "\n")
            self._stream.flush()

    def flush(self, timeout: float = 5.0) -> None:
        # Phase 1: stream.write + flush is synchronous; nothing to drain.
        with self._lock:
            if not self._closed:
                self._stream.flush()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            # Do NOT close stdout/stderr (they are shared with the process);
            # only flush. ValueError — when the stream has already been closed
            # externally (ignored).
            with contextlib.suppress(ValueError):
                self._stream.flush()

    def supports_severity(self, severity_number: int) -> bool:
        return severity_number >= self._min_severity

    # ─── Formatting ──────────────────────────────────────────────────────────

    def _format(self, record: LogRecord) -> str:
        if self._effective_mode() == "json":
            return to_dagstack_jsonl(record)
        return self._format_pretty(record)

    def _effective_mode(self) -> ConsoleMode:
        if self._mode != "auto":
            return self._mode
        # TTY check — streams without isatty (StringIO in tests) → JSON.
        isatty = getattr(self._stream, "isatty", None)
        if isatty is not None and isatty():
            return "pretty"
        return "json"

    def _format_pretty(self, record: LogRecord) -> str:
        """Single-line colored format for an interactive TTY."""
        color = _ANSI_SEVERITY_COLOR.get(record.severity_text, "")
        reset = _ANSI_RESET if color else ""
        # Timestamp (UTC ISO-8601 with microsecond precision).
        timestamp = _format_timestamp(record.time_unix_nano)
        name = record.instrumentation_scope.name if record.instrumentation_scope else "root"
        parts = [
            f"{_ANSI_DIM}{timestamp}{_ANSI_RESET}",
            f"[{color}{record.severity_text}{reset}]",
            f"{_ANSI_DIM}{name}{_ANSI_RESET}:",
            _format_body(record.body),
        ]
        if record.attributes:
            attrs = " ".join(
                f"{k}={_format_scalar(v)}" for k, v in sorted(record.attributes.items())
            )
            parts.append(f"{_ANSI_DIM}|{_ANSI_RESET} {attrs}")
        return " ".join(parts)


def _format_timestamp(nano: int) -> str:
    """unix_nano → ISO-8601 UTC with ms precision."""
    from datetime import datetime

    seconds = nano // 1_000_000_000
    micros = (nano % 1_000_000_000) // 1_000
    dt = datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=micros)
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _format_body(body: object) -> str:
    if isinstance(body, str):
        return body
    # Structured body (dict/list/scalar non-str) → compact JSON.
    from dagstack.logger.canonical_json import canonical_json_dumps

    return canonical_json_dumps(body)


def _format_scalar(value: object) -> str:
    if isinstance(value, str):
        # Quote if it contains spaces.
        if " " in value or "=" in value:
            return f'"{value}"'
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)
