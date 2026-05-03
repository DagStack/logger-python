"""Unit tests for wire-format serialization (dagstack JSON-lines)."""

from __future__ import annotations

import json

from dagstack.logger.records import InstrumentationScope, LogRecord, Resource
from dagstack.logger.wire import to_dagstack_jsonl, to_dagstack_jsonl_dict


class TestMinimalRecord:
    def test_required_fields_only(self) -> None:
        rec = LogRecord(
            time_unix_nano=1700000000000000000,
            severity_number=9,
            severity_text="INFO",
            body="hello",
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d == {
            "time_unix_nano": 1700000000000000000,
            "severity_number": 9,
            "severity_text": "INFO",
            "body": "hello",
        }

    def test_none_fields_omitted(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
        )
        d = to_dagstack_jsonl_dict(rec)
        assert "trace_id" not in d
        assert "span_id" not in d
        assert "instrumentation_scope" not in d
        assert "resource" not in d
        assert "attributes" not in d
        assert "observed_time_unix_nano" not in d
        assert "trace_flags" not in d


class TestWithOptionals:
    def test_trace_span_emitted_as_hex(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            trace_id=bytes.fromhex("0af7651916cd43dd8448eb211c80319c"),
            span_id=bytes.fromhex("b7ad6b7169203331"),
            trace_flags=1,
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert d["span_id"] == "b7ad6b7169203331"
        assert d["trace_flags"] == 1

    def test_trace_flags_zero_omitted(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
        )
        d = to_dagstack_jsonl_dict(rec)
        assert "trace_flags" not in d

    def test_attributes_populated(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            attributes={"user.id": 42, "request.id": "req-abc"},
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["attributes"] == {"user.id": 42, "request.id": "req-abc"}

    def test_empty_attributes_omitted(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            attributes={},
        )
        d = to_dagstack_jsonl_dict(rec)
        assert "attributes" not in d

    def test_instrumentation_scope_emitted(self) -> None:
        scope = InstrumentationScope(name="dagstack.rag", version="1.0.0")
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            instrumentation_scope=scope,
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["instrumentation_scope"] == {"name": "dagstack.rag", "version": "1.0.0"}

    def test_scope_without_version(self) -> None:
        scope = InstrumentationScope(name="root")
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            instrumentation_scope=scope,
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["instrumentation_scope"] == {"name": "root"}

    def test_scope_with_attributes(self) -> None:
        scope = InstrumentationScope(name="rag", attributes={"build": "prod"})
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            instrumentation_scope=scope,
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["instrumentation_scope"]["attributes"] == {"build": "prod"}

    def test_resource_emitted(self) -> None:
        resource = Resource(attributes={"service.name": "order-service"})
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            resource=resource,
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["resource"] == {"attributes": {"service.name": "order-service"}}

    def test_empty_resource_omitted(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
            resource=Resource(),
        )
        d = to_dagstack_jsonl_dict(rec)
        assert "resource" not in d

    def test_observed_time_emitted_when_set(self) -> None:
        rec = LogRecord(
            time_unix_nano=100,
            severity_number=9,
            severity_text="INFO",
            body="x",
            observed_time_unix_nano=200,
        )
        d = to_dagstack_jsonl_dict(rec)
        assert d["observed_time_unix_nano"] == 200


class TestCanonicalSerialization:
    def test_output_is_canonical_json(self) -> None:
        rec = LogRecord(
            time_unix_nano=100,
            severity_number=9,
            severity_text="INFO",
            body="hi",
        )
        s = to_dagstack_jsonl(rec)
        # Keys are sorted alphabetically:
        assert s == '{"body":"hi","severity_number":9,"severity_text":"INFO","time_unix_nano":100}'

    def test_output_round_trips_via_json_parse(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body={"nested": [1, 2, 3]},
            attributes={"k": "v"},
        )
        s = to_dagstack_jsonl(rec)
        parsed = json.loads(s)
        assert parsed["body"]["nested"] == [1, 2, 3]
        assert parsed["attributes"]["k"] == "v"

    def test_no_trailing_newline(self) -> None:
        rec = LogRecord(
            time_unix_nano=0,
            severity_number=9,
            severity_text="INFO",
            body="x",
        )
        s = to_dagstack_jsonl(rec)
        assert not s.endswith("\n")

    def test_deterministic_output(self) -> None:
        rec = LogRecord(
            time_unix_nano=100,
            severity_number=17,
            severity_text="ERROR",
            body="x",
            attributes={"z": 1, "a": 2},
        )
        assert to_dagstack_jsonl(rec) == to_dagstack_jsonl(rec)
