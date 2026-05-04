"""Wire-format serialization for LogRecord.

Per spec ADR-0001 §1: three wire formats for different sinks:
- **dagstack JSON-lines** (default FileSink/ConsoleSink mode) — snake_case
  field names, trace_id/span_id as lowercase hex strings, timestamps as
  integer nanoseconds (raw JSON number). Implemented here.
- **OTel JSON** (`OTLPSink` HTTP+JSON protocol) — camelCase keys, timestamps
  stringified. Phase 2+ together with OTLPSink.
- **OTLP protobuf** — native OTel wire. Phase 2+.

Empty / None fields are **omitted** from the output — cleaner diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dagstack.logger.canonical_json import canonical_json_dumps
from dagstack.logger.trace_ids import span_id_to_hex, trace_id_to_hex

if TYPE_CHECKING:
    from dagstack.logger.records import (
        InstrumentationScope,
        LogRecord,
        Resource,
    )


def to_dagstack_jsonl_dict(record: LogRecord) -> dict[str, Any]:
    """Convert LogRecord → dict ready for a canonical JSON dump (snake_case).

    Empty/None values are skipped. trace_id/span_id are encoded as hex strings.
    Timestamps are kept as raw int (nanoseconds).
    """
    result: dict[str, Any] = {
        "time_unix_nano": record.time_unix_nano,
        "severity_number": record.severity_number,
        "severity_text": record.severity_text,
        "body": record.body,
    }

    if record.observed_time_unix_nano is not None:
        result["observed_time_unix_nano"] = record.observed_time_unix_nano

    if record.attributes:
        result["attributes"] = dict(record.attributes)

    if record.instrumentation_scope is not None:
        result["instrumentation_scope"] = _serialize_scope(record.instrumentation_scope)

    if record.resource is not None and record.resource.attributes:
        result["resource"] = _serialize_resource(record.resource)

    trace_id_hex = trace_id_to_hex(record.trace_id)
    if trace_id_hex is not None:
        result["trace_id"] = trace_id_hex
    span_id_hex = span_id_to_hex(record.span_id)
    if span_id_hex is not None:
        result["span_id"] = span_id_hex
    if record.trace_flags != 0:
        result["trace_flags"] = record.trace_flags

    return result


def to_dagstack_jsonl(record: LogRecord) -> str:
    """Convert LogRecord → canonical JSON string (one line, no trailing newline).

    Each sink adds the LF separator between records itself.
    """
    return canonical_json_dumps(to_dagstack_jsonl_dict(record))


def _serialize_scope(scope: InstrumentationScope) -> dict[str, Any]:
    """InstrumentationScope → dict (empty attrs omitted)."""
    out: dict[str, Any] = {"name": scope.name}
    if scope.version is not None:
        out["version"] = scope.version
    if scope.attributes:
        out["attributes"] = dict(scope.attributes)
    return out


def _serialize_resource(resource: Resource) -> dict[str, Any]:
    """Resource → dict (caller ensures non-empty attributes)."""
    return {"attributes": dict(resource.attributes)}
