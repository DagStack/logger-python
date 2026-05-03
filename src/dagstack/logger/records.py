"""LogRecord + Resource + InstrumentationScope dataclasses.

Per spec ADR-0001 §1: LogRecord is structurally identical to the OTel Log
Data Model v1.24. Field names = OTel normative spec (`time_unix_nano`,
`trace_id` bytes, etc.). Serialization into wire-format (OTLP protobuf /
OTel JSON / dagstack JSON-lines) lives in separate functions (see wire.py).

The Value type alias describes the allowed shapes inside body/attributes:
- Scalars: str, int, float, bool, None.
- Map: dict[str, Value].
- Sequence: list[Value].
A recursive structure matching config-spec §1 `Value`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Recursive Value type — PEP 604 `X | Y` syntax. Python's type system does
# not model recursion directly; we use string forward-references.
#
# Accepted values: str, int, float, bool, None, nested dict/list.
Value = str | int | float | bool | None | dict[str, "Value"] | list["Value"]


@dataclass(slots=True)
class InstrumentationScope:
    """Per spec §4.1: logger's self-descriptor — name + version + optional attrs.

    Name matches the logger name (`dagstack.rag.retriever`); version is the
    semantic version of the package / plugin.
    """

    name: str
    version: str | None = None
    attributes: dict[str, Value] = field(default_factory=dict)


@dataclass(slots=True)
class Resource:
    """Per spec §4.2: process-/service-/host-level attributes (OTel Resource).

    Shared across all logger instances of a single process. Typical keys:
    `service.name`, `service.version`, `service.instance.id`,
    `deployment.environment`, `host.name`, `process.pid`,
    `telemetry.sdk.{name,version,language}`.
    """

    attributes: dict[str, Value] = field(default_factory=dict)


@dataclass(slots=True)
class LogRecord:
    """OTel Log Data Model v1.24-compatible LogRecord.

    Per spec §1: internal field names = OTel normative (time_unix_nano,
    observed_time_unix_nano, severity_number, severity_text, body, attributes,
    resource, instrumentation_scope, trace_id as bytes(16), span_id as
    bytes(8), trace_flags).

    Wire serialization (OTLP / JSON) lives in separate functions, see wire.py:
    - OTLP protobuf: trace_id/span_id as bytes, timestamps as fixed64.
    - OTel JSON: trace_id/span_id as lowercase hex, timestamps as stringified int.
    - dagstack JSON-lines: snake_case keys, hex ids, raw int timestamps.

    `observed_time_unix_nano` — the sink sets it on ingestion if null
    (per spec §1 ownership).
    """

    time_unix_nano: int
    """Emit time, nanoseconds since Unix epoch."""

    severity_number: int
    """OTel severity 1-24."""

    severity_text: str
    """One of 6 canonical strings (see severity.SEVERITY_TEXTS)."""

    body: Value
    """Primary message — string or structured (map/array/scalar)."""

    attributes: dict[str, Value] = field(default_factory=dict)
    """Per-record key-value context."""

    instrumentation_scope: InstrumentationScope | None = None
    """Logger self-descriptor (§4.1)."""

    resource: Resource | None = None
    """Process/service/host attributes (§4.2)."""

    trace_id: bytes | None = None
    """W3C Trace Context — 16 random bytes, if an active span is present."""

    span_id: bytes | None = None
    """W3C Trace Context — 8 random bytes, if an active span is present."""

    trace_flags: int = 0
    """W3C flags (sampled bit etc.). Default 0 = not-sampled."""

    observed_time_unix_nano: int | None = None
    """Ingest time at sink. Producer leaves None; sink fills it in."""
