"""InMemorySink — ring-buffer LogRecord accumulator for tests and debugging.

Per spec §7.2: Phase 1 MVP, a capacity-bounded ring. The oldest records are
dropped automatically via collections.deque(maxlen=...).

Usage in tests:
    sink = InMemorySink(capacity=100)
    logger = Logger.get("test").with_sinks([sink])
    logger.info("x")
    assert sink.records[0].body == "x"
"""

from __future__ import annotations

import itertools
import threading
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dagstack.logger.records import LogRecord

_instance_counter = itertools.count(1)


class InMemorySink:
    """Ring-buffer sink for assertions in tests.

    Thread-safe (deque.append + list() snapshot under lock). Does not support
    wire serialization — it stores LogRecord dataclasses directly, and
    assertions access record.body/attributes.
    """

    def __init__(
        self,
        *,
        capacity: int = 1000,
        min_severity: int = 1,
    ) -> None:
        self._records: deque[LogRecord] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._closed = False
        self._capacity = capacity
        self._min_severity = min_severity
        # Per-instance suffix avoids ID collisions when several InMemorySinks
        # share the same capacity (common in tests).
        self.id = f"in-memory:cap={capacity}#{next(_instance_counter)}"

    def emit(self, record: LogRecord) -> None:
        if self._closed:
            return
        if not self.supports_severity(record.severity_number):
            return
        with self._lock:
            if not self._closed:
                self._records.append(record)

    def flush(self, timeout: float = 5.0) -> None:
        # In-memory → nothing to drain.
        return

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def supports_severity(self, severity_number: int) -> bool:
        return severity_number >= self._min_severity

    # ─── Test-specific helpers ───────────────────────────────────────────────

    def records(self) -> list[LogRecord]:
        """Snapshot captured records (copy). Not part of Sink Protocol."""
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        """Drop all captured records. Test cleanup."""
        with self._lock:
            self._records.clear()

    @property
    def capacity(self) -> int:
        return self._capacity
