"""Auto-tests for Python snippets from `docs/concepts/severity.mdx`."""

from __future__ import annotations

from dagstack.logger import InMemorySink, Logger, Severity, configure


# ── "Calling the severity methods" ────────────────────────────────────


def test_severity__calling_the_severity_methods() -> None:
    """Snippet `docs/concepts/severity.mdx` → "Calling the severity methods" → Python TabItem.

    All six severity methods emit one record each at the documented
    severity_number (1, 5, 9, 13, 17, 21) → severity_text bucket.
    """
    sink = InMemorySink()
    # Lower the floor so TRACE/DEBUG records are not dropped by the root
    # min_severity. configure(root_level="TRACE") is the canonical way to
    # observe the full numeric range.
    configure(root_level="TRACE", sinks=[sink])

    # --- snippet start (severity / calling the severity methods) ----------
    from dagstack.logger import Logger

    logger = Logger.get("order_service.checkout")

    logger.trace("entering function", attributes={"args.order_id": 1234})
    logger.debug("cache miss", attributes={"cache.key": "user:42"})
    logger.info("order placed", attributes={"order.id": 1234})
    logger.warn("retry triggered", attributes={"retry.attempt": 2})
    logger.error("payment declined", attributes={"order.id": 1234})
    logger.fatal("config invariant violated", attributes={"reason": "missing service.name"})
    # --- snippet end ------------------------------------------------------

    records = sink.records()
    assert len(records) == 6

    expected = [
        ("entering function", 1, "TRACE"),
        ("cache miss", 5, "DEBUG"),
        ("order placed", 9, "INFO"),
        ("retry triggered", 13, "WARN"),
        ("payment declined", 17, "ERROR"),
        ("config invariant violated", 21, "FATAL"),
    ]
    for rec, (body, num, text) in zip(records, expected, strict=True):
        assert rec.body == body
        assert rec.severity_number == num
        assert rec.severity_text == text


# ── "Intermediate severity_number via .log(...)" ──────────────────────


def test_severity__intermediate_via_log_method() -> None:
    """Snippet `docs/concepts/severity.mdx` → "Intermediate" Python TabItem.

    severity_number=11 is in the 9-12 INFO bucket → severity_text="INFO".
    """
    sink = InMemorySink()
    configure(root_level="TRACE", sinks=[sink])
    logger = Logger.get("order_service.checkout")

    # --- snippet start (severity / intermediate via log method) -----------
    logger.log(11, "intermediate level", attributes={"phase": "warmup"})
    # severity_number=11 → severity_text="INFO" (still in 9-12 bucket).
    # --- snippet end ------------------------------------------------------

    rec = sink.records()[0]
    assert rec.severity_number == 11
    assert rec.severity_text == "INFO"
    assert rec.attributes["phase"] == "warmup"


# ── "The constants" — Severity enum ───────────────────────────────────


def test_severity__constants() -> None:
    """Snippet `docs/concepts/severity.mdx` → "The constants" → Python TabItem.

    The six bucket boundaries are exposed as `Severity` IntEnum members.
    """
    # --- snippet start (severity / the constants) -------------------------
    from dagstack.logger import Severity

    assert int(Severity.TRACE) == 1
    assert int(Severity.DEBUG) == 5
    assert int(Severity.INFO) == 9
    assert int(Severity.WARN) == 13
    assert int(Severity.ERROR) == 17
    assert int(Severity.FATAL) == 21
    # --- snippet end ------------------------------------------------------


_ = Severity  # appease lint when the snippet's local Severity import shadows
