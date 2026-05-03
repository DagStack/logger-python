"""Context propagation helpers — OTel Context API integration.

Per spec §3.4: loggers MUST auto-inject into LogRecord:
- trace_id, span_id, trace_flags — from the active OTel span (W3C Trace Context).
- W3C Baggage entries → attributes (e.g., `tenant.id`, `request.id`).

Uses `opentelemetry-api` as a mandatory dependency. The OTel no-op
implementation is active by default (when the SDK is not installed) — the
functions return empty values but the API stays compatible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import baggage as otel_baggage
from opentelemetry import trace as otel_trace

if TYPE_CHECKING:
    from dagstack.logger.records import Value


# Default baggage keys auto-injected as attributes (per spec §3.4). Other
# baggage entries are skipped.
DEFAULT_BAGGAGE_KEYS: frozenset[str] = frozenset({"tenant.id", "request.id", "user.id"})


def get_active_trace_context() -> tuple[bytes | None, bytes | None, int]:
    """Return (trace_id, span_id, trace_flags) from the active OTel span, or (None, None, 0).

    No active span → all None + trace_flags=0. This is a legitimate state —
    not every record is emitted inside a span (background tasks, startup).
    """
    span = otel_trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return (None, None, 0)
    # OTel stores trace_id/span_id as int (128/64 bit). Our wire format is bytes.
    trace_id_bytes = span_context.trace_id.to_bytes(16, byteorder="big")
    span_id_bytes = span_context.span_id.to_bytes(8, byteorder="big")
    return (trace_id_bytes, span_id_bytes, span_context.trace_flags)


def get_baggage_attributes(
    allowed_keys: frozenset[str] = DEFAULT_BAGGAGE_KEYS,
) -> dict[str, Value]:
    """Return W3C Baggage entries matching `allowed_keys` as a dict of attributes.

    Baggage is cross-service context propagation; the logger extracts the
    allow-listed keys and injects them into attributes.
    """
    result: dict[str, Value] = {}
    all_baggage = otel_baggage.get_all()
    for key, value in all_baggage.items():
        if key in allowed_keys:
            # Baggage values are always str per W3C spec.
            result[key] = str(value) if not isinstance(value, str) else value
    return result
