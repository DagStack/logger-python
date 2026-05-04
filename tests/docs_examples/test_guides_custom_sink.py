"""Auto-tests for Python snippets from `docs/guides/custom-sink.mdx`."""

from __future__ import annotations

from typing import Any

import pytest

from dagstack.logger import (
    ConsoleSink,
    InMemorySink,
    Logger,
    LogRecord,
    Sink,
    configure,
)


# ── Step 2. "Implement the protocol" — CallbackSink ───────────────────


def test_custom_sink__callback_sink_protocol() -> None:
    """Snippet `docs/guides/custom-sink.mdx` → "Step 2. Implement the protocol" → Python TabItem.

    The CallbackSink class is defined verbatim from the docs. We then
    verify that:
    1. It satisfies the `Sink` Protocol (`isinstance(..., Sink)`).
    2. Severity filtering rejects records below `min_severity`.
    3. `close()` is idempotent.
    4. After close, further emits are no-ops.
    """
    received: list[LogRecord] = []

    # --- snippet start (custom-sink / step 2 CallbackSink) ----------------
    import threading
    from typing import Callable

    from dagstack.logger import LogRecord, Sink

    class CallbackSink:
        """Forward each LogRecord to a user-supplied callable."""

        def __init__(
            self,
            callback: Callable[[LogRecord], None],
            *,
            min_severity: int = 1,
        ) -> None:
            self._callback = callback
            self._min_severity = min_severity
            self._lock = threading.Lock()
            self._closed = False
            self.id = f"callback:{callback.__name__}"

        def emit(self, record: LogRecord) -> None:
            if self._closed:
                return
            if not self.supports_severity(record.severity_number):
                return
            with self._lock:
                if self._closed:
                    return
                self._callback(record)

        def flush(self, timeout: float = 5.0) -> None:
            # Synchronous — nothing buffered.
            return

        def close(self) -> None:
            with self._lock:
                self._closed = True

        def supports_severity(self, severity_number: int) -> bool:
            return severity_number >= self._min_severity

    # --- snippet end ------------------------------------------------------

    def collect(record: LogRecord) -> None:
        received.append(record)

    sink = CallbackSink(collect, min_severity=9)  # INFO floor

    # Structural conformance — the Sink Protocol is runtime-checkable.
    assert isinstance(sink, Sink)

    # ID built from callback __name__.
    assert sink.id == "callback:collect"

    # Severity floor — DEBUG (5) rejected, INFO (9) accepted.
    assert sink.supports_severity(5) is False
    assert sink.supports_severity(9) is True

    # Use the sink in a real configure() / emit pipeline.
    configure(root_level="TRACE", sinks=[sink])
    Logger.get("test").debug("dropped")  # below floor
    Logger.get("test").info("captured", attributes={"k": "v"})

    assert len(received) == 1
    assert received[0].body == "captured"

    # close() is idempotent.
    sink.close()
    sink.close()  # second call — must not raise.

    # After close, emits become no-ops.
    Logger.get("test").info("after-close")
    assert len(received) == 1


# ── Step 2 (cont). "Wire it up alongside the built-in sinks" ──────────


def test_custom_sink__wire_callback_sink_into_configure() -> None:
    """Snippet `docs/guides/custom-sink.mdx` → "wire it up" → Python TabItem.

    The doc snippet imports `sentry_sdk` and routes ERROR+ records into
    Sentry. Real Sentry SDK is not a test dependency — we substitute a
    capturing fake whose API matches `sentry_sdk.capture_message(...)`.
    """
    # NB: docs snippet imports `sentry_sdk` and calls
    # `sentry_sdk.capture_message(...)`. Replaced with `fake_sentry_sdk`
    # so the test is hermetic. Drift would be: the binding API contract
    # for record.body/severity_number/attributes — covered below.
    captured: list[dict[str, Any]] = []

    class _FakeSentrySDK:
        @staticmethod
        def capture_message(message: str, level: str, extras: dict[str, Any]) -> None:
            captured.append({"message": message, "level": level, "extras": extras})

    sentry_sdk = _FakeSentrySDK()

    # Re-define CallbackSink locally — the snippet's `wire it up` block is
    # written assuming CallbackSink is in scope. We import the same
    # implementation from the previous snippet's body inline; the structure
    # exercised below is the configure() call itself.
    import threading

    class CallbackSink:
        def __init__(self, callback: Any, *, min_severity: int = 1) -> None:
            self._callback = callback
            self._min_severity = min_severity
            self._lock = threading.Lock()
            self._closed = False
            self.id = f"callback:{getattr(callback, '__name__', 'anon')}"

        def emit(self, record: LogRecord) -> None:
            if self._closed:
                return
            if not self.supports_severity(record.severity_number):
                return
            with self._lock:
                if self._closed:
                    return
                self._callback(record)

        def flush(self, timeout: float = 5.0) -> None:
            return

        def close(self) -> None:
            with self._lock:
                self._closed = True

        def supports_severity(self, severity_number: int) -> bool:
            return severity_number >= self._min_severity

    # --- snippet start (custom-sink / wire-it-up — adapted) ---------------
    # NB: docs: `import sentry_sdk` (real SDK).
    from dagstack.logger import ConsoleSink, configure

    def forward_to_sentry(record):
        if record.severity_number >= 17:  # ERROR and above
            sentry_sdk.capture_message(
                str(record.body),
                level="error",
                extras=record.attributes,
            )

    configure(
        root_level="INFO",
        sinks=[
            ConsoleSink(mode="auto"),
            CallbackSink(forward_to_sentry, min_severity=17),
        ],
    )
    # --- snippet end ------------------------------------------------------

    # INFO record → does NOT reach Sentry (below severity floor).
    Logger.get("svc").info("informational", attributes={"k": "v"})
    assert captured == []

    # ERROR record → reaches Sentry forwarder with the documented shape.
    Logger.get("svc").error("payment failed", attributes={"order.id": 42})
    assert len(captured) == 1
    assert captured[0]["message"] == "payment failed"
    assert captured[0]["level"] == "error"
    assert captured[0]["extras"]["order.id"] == 42


# Lint anchors.
_ = (pytest, ConsoleSink, InMemorySink, configure)
