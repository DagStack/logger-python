"""Auto-tests for Python snippets from `docs/concepts/operations.mdx`.

Phase 1 status — `logger.operation(...)` and `logger.emit_event(...)` are
normative in spec §5.1/§5.2 but have not yet shipped in the v0.1.x
binding. The MDX page documents the manual workaround via
`logger.child(attributes={...})`; we exercise that workaround here.
"""

from __future__ import annotations

from dagstack.logger import InMemorySink, Logger, configure


# ── "Operations — manual workaround" ──────────────────────────────────


def test_operations__manual_workaround_via_child() -> None:
    """Snippet `docs/concepts/operations.mdx` → "manual workaround" → Python TabItem.

    The snippet shows the Phase 1 pattern: build a child logger with
    pre-bound `operation.*` attributes, then emit through it. Every emit
    inherits the bound attributes.
    """
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])

    # --- snippet start (operations / manual workaround) -------------------
    import uuid
    from dagstack.logger import Logger

    logger = Logger.get("order_service")

    op_logger = logger.child(
        attributes={
            "operation.name": "process_order",
            "operation.id": str(uuid.uuid4()),
            "operation.kind": "lifecycle",
        }
    )
    op_logger.info("started", attributes={"order.id": 1234})
    op_logger.info(
        "completed",
        attributes={
            "operation.status": "ok",
            "operation.duration_ms": 142,
        },
    )
    # --- snippet end ------------------------------------------------------

    records = sink.records()
    assert len(records) == 2

    started, completed = records
    # Bound attributes inherited on every emit.
    assert started.attributes["operation.name"] == "process_order"
    assert started.attributes["operation.kind"] == "lifecycle"
    assert isinstance(started.attributes["operation.id"], str)
    assert started.attributes["order.id"] == 1234

    assert completed.attributes["operation.name"] == "process_order"
    assert completed.attributes["operation.id"] == started.attributes["operation.id"]
    assert completed.attributes["operation.status"] == "ok"
    assert completed.attributes["operation.duration_ms"] == 142
