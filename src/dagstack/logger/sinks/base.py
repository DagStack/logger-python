"""Sink Protocol + contract per spec §7.1.

Phase 1 sinks use synchronous writes (console/file/in-memory are local I/O;
the non-blocking caller-side property is guaranteed by OS buffering). Phase
2 OTLPSink will add true async with batching + an internal queue — at that
point the spec §7.1 non-blocking emit contract becomes materially relevant.

All sinks are thread-safe (threading.Lock around I/O).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dagstack.logger.records import LogRecord


@runtime_checkable
class Sink(Protocol):
    """Sink contract per spec §7.1.

    Implementations MUST expose:
        id: URI-style identifier for diagnostics (`"console:dev"`, `"file:/var/log/app.jsonl"`).
        emit(record): non-blocking (Phase 1 — synchronous local I/O; Phase 2 — batch worker).
        flush(timeout): best-effort drain of the internal buffer. Phase 1
            sinks are synchronous, so the ``timeout`` argument is accepted
            for forward compatibility but **not enforced** — TimeoutError
            never fires here. Phase 2 (OTLPSink and friends) MUST raise
            TimeoutError if the drain cannot complete in time.
        close(): flush + release resources (file handles, sockets). Idempotent.
        supports_severity(n): optional filter hint — the sink may reject
            before buffering (early drop).

    Implementations MAY expose (Phase 2+):
        - buffer depth metric
        - async queue
        - retry policy
    """

    id: str

    def emit(self, record: LogRecord) -> None:
        """Deliver a record to the sink. Phase 1: synchronous; Phase 2: enqueue for a worker."""
        ...

    def flush(self, timeout: float = 5.0) -> None:
        """Block until buffered records are delivered, or raise TimeoutError.

        Phase 1: synchronous sinks; ``timeout`` is accepted for forward
        compatibility but not enforced (TimeoutError is never raised
        here). Phase 2: waits for the background worker and MUST raise
        TimeoutError when the deadline elapses.
        """
        ...

    def close(self) -> None:
        """Flush + release resources. Idempotent."""
        ...

    def supports_severity(self, severity_number: int) -> bool:
        """Early-drop hint: return False if the sink will not emit this level."""
        ...
