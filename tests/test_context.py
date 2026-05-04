"""Unit tests for the OTel context propagation helpers."""

from __future__ import annotations

from opentelemetry import baggage, context, trace

from dagstack.logger.context import (
    DEFAULT_BAGGAGE_KEYS,
    get_active_trace_context,
    get_baggage_attributes,
)


class TestGetActiveTraceContext:
    def test_no_active_span_returns_none(self) -> None:
        # Default OTel API without SDK → no-op span → invalid context.
        trace_id, span_id, flags = get_active_trace_context()
        assert trace_id is None
        assert span_id is None
        assert flags == 0

    def test_with_recording_span_returns_bytes(self) -> None:
        # Manually construct a valid span context — a simple case without the full SDK.
        span_ctx = trace.SpanContext(
            trace_id=0x0AF7651916CD43DD8448EB211C80319C,
            span_id=0xB7AD6B7169203331,
            is_remote=False,
            trace_flags=trace.TraceFlags(1),
        )
        fake_span = trace.NonRecordingSpan(span_ctx)
        token = context.attach(trace.set_span_in_context(fake_span))
        try:
            trace_id, span_id, flags = get_active_trace_context()
            assert trace_id == bytes.fromhex("0af7651916cd43dd8448eb211c80319c")
            assert span_id == bytes.fromhex("b7ad6b7169203331")
            assert flags == 1
        finally:
            context.detach(token)


class TestGetBaggageAttributes:
    def test_no_baggage_returns_empty(self) -> None:
        assert get_baggage_attributes() == {}

    def test_whitelist_keys_injected(self) -> None:
        ctx = baggage.set_baggage("tenant.id", "tenant-42")
        ctx = baggage.set_baggage("request.id", "req-abc", ctx)
        token = context.attach(ctx)
        try:
            attrs = get_baggage_attributes()
            assert attrs.get("tenant.id") == "tenant-42"
            assert attrs.get("request.id") == "req-abc"
        finally:
            context.detach(token)

    def test_non_whitelisted_keys_skipped(self) -> None:
        ctx = baggage.set_baggage("custom.key", "value")
        token = context.attach(ctx)
        try:
            attrs = get_baggage_attributes()
            assert "custom.key" not in attrs
        finally:
            context.detach(token)

    def test_default_whitelist_has_expected_keys(self) -> None:
        assert "tenant.id" in DEFAULT_BAGGAGE_KEYS
        assert "request.id" in DEFAULT_BAGGAGE_KEYS
        assert "user.id" in DEFAULT_BAGGAGE_KEYS
