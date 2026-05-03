"""Unit tests for ConsoleSink."""

from __future__ import annotations

import io
import json
from typing import Any

from dagstack.logger.records import InstrumentationScope, LogRecord
from dagstack.logger.sinks import ConsoleSink, Sink


def _record(
    body: Any = "hello",
    severity_number: int = 9,
    severity_text: str = "INFO",
    attributes: dict[str, Any] | None = None,
    scope_name: str = "dagstack.rag",
) -> LogRecord:
    return LogRecord(
        time_unix_nano=1_700_000_000_000_000_000,
        severity_number=severity_number,
        severity_text=severity_text,
        body=body,
        attributes=dict(attributes or {}),
        instrumentation_scope=InstrumentationScope(name=scope_name),
    )


class TestConsoleSinkJson:
    def test_json_mode_writes_canonical_json_line(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="json", stream=stream)
        sink.emit(_record("hello"))
        output = stream.getvalue()
        assert output.endswith("\n")
        parsed = json.loads(output.strip())
        assert parsed["body"] == "hello"
        assert parsed["severity_text"] == "INFO"

    def test_json_mode_sorted_keys(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="json", stream=stream)
        sink.emit(_record("msg"))
        line = stream.getvalue().strip()
        # Canonical JSON — sorted keys. `body` < `instrumentation_scope` < ...
        assert line.startswith('{"body":')

    def test_multiple_records_separated_by_newlines(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="json", stream=stream)
        sink.emit(_record("one"))
        sink.emit(_record("two"))
        lines = stream.getvalue().strip().split("\n")
        assert len(lines) == 2


class TestConsoleSinkAutoMode:
    def test_non_tty_stream_uses_json(self) -> None:
        # StringIO is not a TTY → auto picks json.
        stream = io.StringIO()
        sink = ConsoleSink(mode="auto", stream=stream)
        sink.emit(_record())
        # Must parse as JSON.
        assert json.loads(stream.getvalue().strip())

    def test_tty_stream_uses_pretty(self) -> None:
        # Simulate a TTY stream (isatty returns True).
        class _TtyStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        stream = _TtyStream()
        sink = ConsoleSink(mode="auto", stream=stream)
        sink.emit(_record("msg"))
        # ANSI escape present in pretty mode.
        assert "\033[" in stream.getvalue()


class TestConsoleSinkPretty:
    def test_pretty_includes_severity(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(_record("x", severity_text="WARN"))
        output = stream.getvalue()
        assert "WARN" in output

    def test_pretty_includes_logger_name(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(_record(scope_name="dagstack.test"))
        assert "dagstack.test" in stream.getvalue()

    def test_pretty_root_logger_fallback(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        record = LogRecord(
            time_unix_nano=1_700_000_000_000_000_000,
            severity_number=9,
            severity_text="INFO",
            body="x",
            # No instrumentation_scope.
        )
        sink.emit(record)
        assert "root" in stream.getvalue()

    def test_pretty_attributes_rendered(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(_record(attributes={"user.id": 42, "request.id": "abc"}))
        output = stream.getvalue()
        assert "user.id=42" in output
        assert "request.id=abc" in output

    def test_pretty_string_with_space_quoted(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(_record(attributes={"msg": "hello world"}))
        assert '"hello world"' in stream.getvalue()

    def test_pretty_timestamp_iso_utc(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(_record())
        output = stream.getvalue()
        # Unix nano 1700000000 seconds → 2023-11-14T22:13:20Z
        assert "2023-11-14T22:13:20" in output
        assert "Z" in output

    def test_pretty_structured_body_as_json(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(_record(body={"nested": [1, 2]}))
        output = stream.getvalue()
        assert '{"nested":[1,2]}' in output

    def test_pretty_scalar_types_in_attributes(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="pretty", stream=stream)
        sink.emit(
            _record(
                attributes={
                    "is_production": True,
                    "debug_mode": False,
                    "optional_value": None,
                }
            )
        )
        output = stream.getvalue()
        assert "is_production=true" in output
        assert "debug_mode=false" in output
        assert "optional_value=null" in output


class TestConsoleSinkFilter:
    def test_min_severity_drops_below(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="json", stream=stream, min_severity=9)
        sink.emit(_record("debug", severity_number=5))
        sink.emit(_record("info", severity_number=9))
        assert stream.getvalue().count("\n") == 1

    def test_supports_severity_reflects_threshold(self) -> None:
        sink = ConsoleSink(min_severity=13)
        assert not sink.supports_severity(9)
        assert sink.supports_severity(13)


class TestConsoleSinkLifecycle:
    def test_close_prevents_further_writes(self) -> None:
        stream = io.StringIO()
        sink = ConsoleSink(mode="json", stream=stream)
        sink.emit(_record("before"))
        sink.close()
        sink.emit(_record("after"))
        assert stream.getvalue().count("\n") == 1

    def test_close_idempotent(self) -> None:
        sink = ConsoleSink(mode="json", stream=io.StringIO())
        sink.close()
        sink.close()  # no exception

    def test_flush_does_not_raise(self) -> None:
        sink = ConsoleSink(mode="json", stream=io.StringIO())
        sink.flush()
        sink.flush(timeout=0.1)

    def test_flush_after_close_noop(self) -> None:
        sink = ConsoleSink(mode="json", stream=io.StringIO())
        sink.close()
        sink.flush()  # no exception

    def test_id_reflects_mode(self) -> None:
        assert ConsoleSink(mode="json", stream=io.StringIO()).id == "console:json"
        assert ConsoleSink(mode="pretty", stream=io.StringIO()).id == "console:pretty"
        assert ConsoleSink(mode="auto", stream=io.StringIO()).id == "console:auto"

    def test_protocol_compliance(self) -> None:
        sink = ConsoleSink(stream=io.StringIO())
        assert isinstance(sink, Sink)
