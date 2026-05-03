"""Auto-tests for Python snippets from `dagstack-logger-docs/site/docs/intro.mdx`.

Each test mirrors one `<TabItem value="python">` block from the page and
asserts the behaviour described by the surrounding prose. Snippets between
`# --- snippet start (...) ---` / `# --- snippet end ---` are copied
verbatim from MDX. Adjustments outside the markers (in-memory stream
substitution, capture sink so we can inspect records) are kept minimal —
the docs-grade snippet itself is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dagstack.logger import (
    ConsoleSink,
    InMemorySink,
    Logger,
    configure,
)


# ── "Your first log line" — bootstrap + named logger ──────────────────


def test_intro__your_first_log_line() -> None:
    """Snippet `docs/intro.mdx` → section "Your first log line" → Python TabItem.

    The console sink in `auto` mode picks JSON when stderr is not a TTY
    (pytest captures stderr), so we attach an `InMemorySink` next to it
    to inspect the structured record without having to parse JSON output.
    """
    capture_sink = InMemorySink()

    # --- snippet start (intro / your first log line) ----------------------
    from dagstack.logger import Logger, ConsoleSink, configure

    configure(
        root_level="INFO",
        sinks=[ConsoleSink(mode="auto")],
        resource_attributes={"service.name": "order-service"},
    )

    logger = Logger.get("order_service.api", version="1.0.0")
    logger.info("request received", attributes={"request.id": "req-abc", "user.id": 42})
    # --- snippet end ------------------------------------------------------

    # Add the capture sink AFTER the snippet so we can verify a fresh emit
    # carries the configured resource + bound version.
    Logger.get("").set_sinks([ConsoleSink(mode="auto"), capture_sink])
    logger.info("request received", attributes={"request.id": "req-abc", "user.id": 42})

    records = capture_sink.records()
    assert len(records) == 1
    rec = records[0]
    assert rec.body == "request received"
    assert rec.severity_text == "INFO"
    assert rec.attributes["request.id"] == "req-abc"
    assert rec.attributes["user.id"] == 42
    assert rec.resource is not None
    assert rec.resource.attributes["service.name"] == "order-service"
    assert rec.instrumentation_scope.name == "order_service.api"
    assert rec.instrumentation_scope.version == "1.0.0"


# ── "Adding sinks" — multi-sink configure ─────────────────────────────


def test_intro__adding_sinks(tmp_path: Path) -> None:
    """Snippet `docs/intro.mdx` → section "Adding sinks" → Python TabItem.

    The doc snippet uses `FileSink("/var/log/order-service.jsonl", ...)`
    which the test sandbox cannot write to. We substitute a `tmp_path /
    order-service.jsonl` path so `FileSink` can actually open the file;
    everything else is verbatim from the docs.
    """
    log_path = tmp_path / "order-service.jsonl"

    # --- snippet start (intro / adding sinks — adapted) -------------------
    from dagstack.logger import ConsoleSink, FileSink, InMemorySink, configure

    configure(
        root_level="INFO",
        sinks=[
            ConsoleSink(mode="json"),
            # NB: docs: FileSink("/var/log/order-service.jsonl", ...).
            FileSink(log_path, max_bytes=100_000_000, keep=10),
        ],
        resource_attributes={
            "service.name": "order-service",
            "service.version": "1.0.0",
            "deployment.environment": "production",
        },
    )
    # --- snippet end ------------------------------------------------------

    # Reference imported names so linting does not flag them as unused.
    # The InMemorySink import in the docs snippet is for context — the
    # snippet itself does not instantiate it.
    assert InMemorySink is not None

    # The Resource attached by configure(...) is preserved on the root
    # logger and inherited by every child — verify it via effective_resource.
    root = Logger.get("")
    resource = root.effective_resource()
    assert resource is not None
    assert resource.attributes["service.name"] == "order-service"
    assert resource.attributes["service.version"] == "1.0.0"
    assert resource.attributes["deployment.environment"] == "production"

    # Close the file sink to avoid leaking an open fd into other tests.
    root.close()


# ── "Logging exceptions" ──────────────────────────────────────────────


class OrderValidationError(Exception):
    """Stand-in for the user-defined error in the docs snippet."""


def test_intro__logging_exceptions() -> None:
    """Snippet `docs/intro.mdx` → section "Logging exceptions" → Python TabItem."""
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])
    logger = Logger.get("order_service")
    order_id = 1234

    def process_order(_oid: int) -> None:
        raise OrderValidationError("invalid order")

    # --- snippet start (intro / logging exceptions) -----------------------
    try:
        process_order(order_id)
    except OrderValidationError as err:
        logger.exception(err, attributes={"order.id": order_id})
    # --- snippet end ------------------------------------------------------

    rec = sink.records()[0]
    assert rec.severity_text == "ERROR"
    assert rec.attributes["exception.type"] == "OrderValidationError"
    assert rec.attributes["exception.message"] == "invalid order"
    assert isinstance(rec.attributes["exception.stacktrace"], str)
    assert rec.attributes["order.id"] == 1234


# ── "Capturing logs in tests" — InMemorySink + scope_sinks ────────────


def test_intro__capturing_logs_in_tests() -> None:
    """Snippet `docs/intro.mdx` → section "Capturing logs in tests" → Python TabItem."""
    # Bootstrap the global logger with a no-op base sink so the scoped
    # override in the snippet has a known parent to swap from.
    _bootstrap_capture_test()

    def run_business_logic() -> None:
        Logger.get("test_module").info("operation completed")

    # --- snippet start (intro / capturing logs in tests) ------------------
    from dagstack.logger import InMemorySink, Logger

    sink = InMemorySink(capacity=100)
    logger = Logger.get("test_module")

    with logger.scope_sinks([sink]):
        run_business_logic()

    records = sink.records()
    assert any(r.body == "operation completed" for r in records)
    # --- snippet end ------------------------------------------------------


def _bootstrap_capture_test() -> None:
    """Helper: configure root with a single InMemorySink baseline.

    Extracted so the test function can rely on `from dagstack.logger import
    InMemorySink` inside the snippet without triggering Python's local-
    scoping rule on the symbol.
    """
    from dagstack.logger import InMemorySink as _InMemorySink

    configure(root_level="INFO", sinks=[_InMemorySink()])


# Explicit references so linters do not flag the convenience imports.
_ = (pytest,)
