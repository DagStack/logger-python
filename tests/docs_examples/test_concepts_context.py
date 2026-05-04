"""Auto-tests for Python snippets from `docs/concepts/context.mdx`."""

from __future__ import annotations

from dagstack.logger import InMemorySink, Logger, configure


# ── "Setting baggage entries" — W3C Baggage propagation ──────────────


def test_context__setting_baggage_entries() -> None:
    """Snippet `docs/concepts/context.mdx` → "Setting baggage entries" → Python TabItem.

    The whitelisted baggage key `tenant.id` is auto-injected into the
    record's attributes when an OTel context with that baggage entry is
    active during the emit.
    """
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])
    logger = Logger.get("order_service")

    # --- snippet start (context / setting baggage entries) ----------------
    from opentelemetry import baggage, context

    ctx = baggage.set_baggage("tenant.id", "acme-corp")
    token = context.attach(ctx)
    try:
        logger.info("processing request")
        # The emitted record carries attributes={"tenant.id": "acme-corp", ...}
        # plus trace_id / span_id from the active span (if any).
    finally:
        context.detach(token)
    # --- snippet end ------------------------------------------------------

    rec = sink.records()[0]
    assert rec.body == "processing request"
    assert rec.attributes["tenant.id"] == "acme-corp"


# ── Negative: outside the context, `tenant.id` is not injected ────────


def test_context__outside_context_no_baggage() -> None:
    """Per the spec §3.4 narration in context.mdx — outside any active
    OTel context, no baggage attributes are injected. This test pins down
    that side of the contract so a regression that always-injects would
    surface immediately.
    """
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])
    logger = Logger.get("order_service")

    logger.info("no baggage active")
    rec = sink.records()[0]
    assert "tenant.id" not in rec.attributes
