"""Auto-tests for Python snippets from `docs/guides/testing.mdx`.

The MDX page documents an end-user pytest pattern. To exercise the
snippets verbatim we supply tiny stand-ins for the business-logic
functions referenced by the snippets (`place_order`, `run_business_logic`,
`run_phase_one`, `run_phase_two`, `index_repository`) — each emits the
records the snippet then asserts on.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from dagstack.logger import InMemorySink, Logger, configure


# ── Stand-ins for the user code referenced by the snippets ────────────


def place_order(order_id: int, user_id: int) -> None:
    """Stand-in: emit one INFO record matching what the docs assert on.

    Step 1 in the docs scopes sinks on `Logger.get("order_service.checkout")`,
    Step 2 scopes on `Logger.get("order_service")`. To make the same helper
    work for both, emit through `order_service.checkout` — its emits are
    captured both when the parent (`order_service`) and the same name are
    scoped, because:
      - parent scope: child inherits sinks via effective_sinks() chain.
      - same-name scope: direct hit on the swapped logger.
    """
    Logger.get("order_service.checkout").info(
        "order placed",
        attributes={"order.id": order_id, "user.id": user_id},
    )


def run_phase_one() -> None:
    Logger.get("order_service.checkout").info("phase 1 complete", attributes={"phase": "one"})


def run_phase_two() -> None:
    Logger.get("order_service.checkout").info("phase 2 step", attributes={"phase": "two"})


def index_repository() -> None:
    log = Logger.get("indexer")
    for i in range(5):
        log.info("file indexed", attributes={"i": i})
    log.info("indexing finished", attributes={"event.name": "completed"})


# ── Step 1. "Capture records for one test" ────────────────────────────


def test_testing__capture_records_for_one_test() -> None:
    """Snippet `docs/guides/testing.mdx` → "Step 1. Capture records for one test" → Python TabItem."""
    # Floor low enough so INFO records emitted by business logic land in sink.
    configure(root_level="INFO", sinks=[])

    # --- snippet start (testing / step 1) ---------------------------------
    from dagstack.logger import InMemorySink, Logger

    def test_order_placement_logs_audit_event():
        sink = InMemorySink(capacity=100)
        logger = Logger.get("order_service.checkout")

        with logger.scope_sinks([sink]):
            place_order(order_id=1234, user_id=42)

        records = sink.records()
        audit = next(r for r in records if r.body == "order placed")
        assert audit.severity_text == "INFO"
        assert audit.attributes["order.id"] == 1234
        assert audit.attributes["user.id"] == 42

    # --- snippet end ------------------------------------------------------

    # The snippet is a `def test_...(): ...` — pytest, given a nested
    # function, would not invoke it. We invoke it here so the snippet's
    # asserts actually fire.
    #
    # NB: scope on `order_service.checkout` captures emits via the parent
    # `order_service` logger because place_order() calls
    # `Logger.get("order_service")` whose effective_sinks resolves up the
    # chain. To keep the snippet verbatim, we adapt place_order to emit
    # via the documented logger name. See helper at top of file.
    test_order_placement_logs_audit_event()


# Reconcile: the docs snippet captures via `order_service.checkout`, but
# the helper `place_order` emits via `order_service` (its parent). To
# preserve the docs example verbatim, override the helper just for this
# call so the emit goes through `order_service.checkout`.
def test_testing__capture_records_for_one_test_via_child_logger() -> None:
    """Variant covering the exact `Logger.get("order_service.checkout")` path
    referenced by the docs prose ("the scope on the child captures...").
    """
    sink = InMemorySink(capacity=100)
    logger = Logger.get("order_service.checkout")

    with logger.scope_sinks([sink]):
        Logger.get("order_service.checkout").info(
            "order placed",
            attributes={"order.id": 1234, "user.id": 42},
        )

    records = sink.records()
    audit = next(r for r in records if r.body == "order placed")
    assert audit.severity_text == "INFO"
    assert audit.attributes["order.id"] == 1234


# ── Step 2. "Reusable test fixture" ───────────────────────────────────


@pytest.fixture
def captured_logs() -> Iterator[InMemorySink]:
    """Capture records emitted by the `order_service` logger during the test.

    Verbatim from the docs except `Iterator` typing on the return.
    """
    # --- snippet start (testing / step 2 fixture body) --------------------
    sink = InMemorySink(capacity=1000)
    logger = Logger.get("order_service")
    with logger.scope_sinks([sink]):
        yield sink
    # --- snippet end ------------------------------------------------------


def test_testing__step2_audit_trail(captured_logs: InMemorySink) -> None:
    """Snippet `docs/guides/testing.mdx` → "Step 2. Reusable test fixture" → Python TabItem."""
    # --- snippet start (testing / step 2 audit trail) ---------------------
    place_order(order_id=1234, user_id=42)
    records = captured_logs.records()
    assert len(records) == 1
    assert records[0].attributes["order.id"] == 1234
    # --- snippet end ------------------------------------------------------


# ── Step 3. "Asserting on attributes" — redaction subset ──────────────


def test_testing__step3_redaction_masks_api_keys(captured_logs: InMemorySink) -> None:
    """Snippet `docs/guides/testing.mdx` → "Step 3. Asserting on attributes" → Python TabItem.

    Only the redaction sub-snippet is exercised; the trace-context and
    "only one error" sub-snippets reference user-defined helpers
    (`open_otel_span`, `run_business_logic`) that the docs do not define
    inline. Mirrored the redaction case verbatim.
    """
    # --- snippet start (testing / step 3 redaction) -----------------------
    Logger.get("order_service").info(
        "authenticated",
        attributes={
            "user.id": 42,
            "api_key": "sk-supersecret",
        },
    )

    record = captured_logs.records()[0]
    assert record.attributes["user.id"] == 42
    assert record.attributes["api_key"] == "***"
    # --- snippet end ------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "trace_context_propagated snippet uses `open_otel_span(name=..., trace_id=...)` "
        "and `expected_trace_id`, which are user-defined helpers not exposed by the "
        "binding. Covered by tests/test_context.py against the underlying OTel API. "
        "TODO: revisit when docs add a self-contained snippet using `opentelemetry.trace`."
    )
)
def test_testing__step3_trace_context_propagated() -> None:
    """Snippet `docs/guides/testing.mdx` → "Step 3" trace-context block.

    Skipped — the snippet relies on user-defined `open_otel_span(...)` and
    `expected_trace_id` symbols. Documented as drift; revisit on docs update.
    """


# ── Step 4. "Resetting between assertions" ────────────────────────────


def test_testing__step4_phase_separation(captured_logs: InMemorySink) -> None:
    """Snippet `docs/guides/testing.mdx` → "Step 4. Resetting between assertions" → Python TabItem."""
    # --- snippet start (testing / step 4 phase separation) ----------------
    run_phase_one()
    assert any(r.body == "phase 1 complete" for r in captured_logs.records())

    captured_logs.clear()

    run_phase_two()
    assert all(r.attributes.get("phase") == "two" for r in captured_logs.records())
    # --- snippet end ------------------------------------------------------


# ── Step 5. "Avoiding capacity overflow" ──────────────────────────────


def test_testing__step5_high_volume() -> None:
    """Snippet `docs/guides/testing.mdx` → "Step 5. Avoiding capacity overflow" → Python TabItem."""
    # --- snippet start (testing / step 5 high volume) ---------------------
    sink = InMemorySink(capacity=10_000)
    with Logger.get("indexer").scope_sinks([sink]):
        index_repository()

    assert len(sink.records()) <= sink.capacity
    assert any(r.attributes.get("event.name") == "completed" for r in sink.records())
    # --- snippet end ------------------------------------------------------
