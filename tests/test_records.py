"""Unit tests for the LogRecord / Resource / InstrumentationScope dataclasses."""

from __future__ import annotations

from dagstack.logger.records import InstrumentationScope, LogRecord, Resource


class TestInstrumentationScope:
    def test_name_only(self) -> None:
        s = InstrumentationScope(name="dagstack.rag")
        assert s.name == "dagstack.rag"
        assert s.version is None
        assert s.attributes == {}

    def test_with_version_and_attrs(self) -> None:
        s = InstrumentationScope(
            name="dagstack.rag.retriever",
            version="1.4.2",
            attributes={"foo": "bar"},
        )
        assert s.version == "1.4.2"
        assert s.attributes == {"foo": "bar"}

    def test_defaults_are_not_shared(self) -> None:
        # slots=True + field(default_factory=dict) — each instance gets fresh dict.
        a = InstrumentationScope(name="a")
        b = InstrumentationScope(name="b")
        a.attributes["shared"] = 1
        assert "shared" not in b.attributes


class TestResource:
    def test_empty(self) -> None:
        r = Resource()
        assert r.attributes == {}

    def test_with_attrs(self) -> None:
        r = Resource(attributes={"service.name": "order-service"})
        assert r.attributes["service.name"] == "order-service"


class TestLogRecord:
    def test_minimal(self) -> None:
        rec = LogRecord(
            time_unix_nano=1_700_000_000_000_000_000,
            severity_number=9,
            severity_text="INFO",
            body="hello world",
        )
        assert rec.time_unix_nano == 1_700_000_000_000_000_000
        assert rec.severity_number == 9
        assert rec.severity_text == "INFO"
        assert rec.body == "hello world"
        assert rec.attributes == {}
        assert rec.instrumentation_scope is None
        assert rec.resource is None
        assert rec.trace_id is None
        assert rec.span_id is None
        assert rec.trace_flags == 0
        assert rec.observed_time_unix_nano is None

    def test_full_fields(self) -> None:
        scope = InstrumentationScope(name="dagstack.rag", version="1.0")
        resource = Resource(attributes={"service.name": "order-service"})
        rec = LogRecord(
            time_unix_nano=1_700_000_000_000_000_000,
            severity_number=17,
            severity_text="ERROR",
            body={"msg": "failure", "code": 500},
            attributes={"user.id": 42, "request.id": "req-abc"},
            instrumentation_scope=scope,
            resource=resource,
            trace_id=bytes.fromhex("0af7651916cd43dd8448eb211c80319c"),
            span_id=bytes.fromhex("b7ad6b7169203331"),
            trace_flags=1,
            observed_time_unix_nano=1_700_000_000_000_000_123,
        )
        assert rec.severity_text == "ERROR"
        assert rec.attributes["user.id"] == 42
        assert rec.instrumentation_scope is scope
        assert rec.resource is resource
        assert len(rec.trace_id or b"") == 16
        assert len(rec.span_id or b"") == 8

    def test_body_can_be_structured(self) -> None:
        # Body is a Value type; allows dict / list / scalar.
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body={"nested": [1, 2, {"deep": True}]},
        )
        assert isinstance(rec.body, dict)
