"""Unit tests for InMemorySink."""

from __future__ import annotations

from dagstack.logger.records import LogRecord
from dagstack.logger.sinks import InMemorySink, Sink


def _record(body: str = "x", severity: int = 9) -> LogRecord:
    return LogRecord(
        time_unix_nano=0,
        severity_number=severity,
        severity_text="INFO",
        body=body,
    )


class TestInMemorySink:
    def test_emit_captures_record(self) -> None:
        sink = InMemorySink(capacity=10)
        sink.emit(_record("hello"))
        records = sink.records()
        assert len(records) == 1
        assert records[0].body == "hello"

    def test_capacity_bounded_drops_oldest(self) -> None:
        sink = InMemorySink(capacity=3)
        for i in range(5):
            sink.emit(_record(f"msg-{i}"))
        records = sink.records()
        assert len(records) == 3
        # Oldest dropped, last 3 retained.
        assert [r.body for r in records] == ["msg-2", "msg-3", "msg-4"]

    def test_records_returns_copy(self) -> None:
        sink = InMemorySink()
        sink.emit(_record())
        snapshot = sink.records()
        snapshot.clear()
        # Clearing the snapshot does not affect internal storage.
        assert len(sink.records()) == 1

    def test_clear_empties(self) -> None:
        sink = InMemorySink()
        sink.emit(_record())
        sink.emit(_record())
        sink.clear()
        assert sink.records() == []

    def test_close_stops_further_emits(self) -> None:
        sink = InMemorySink()
        sink.emit(_record("before"))
        sink.close()
        sink.emit(_record("after"))
        records = sink.records()
        assert len(records) == 1
        assert records[0].body == "before"

    def test_flush_is_noop(self) -> None:
        sink = InMemorySink()
        sink.flush()
        sink.flush(timeout=0.1)

    def test_id_format(self) -> None:
        sink = InMemorySink(capacity=42)
        assert sink.id.startswith("in-memory:cap=42#")

    def test_id_per_instance_unique(self) -> None:
        a = InMemorySink(capacity=10)
        b = InMemorySink(capacity=10)
        assert a.id != b.id

    def test_capacity_property(self) -> None:
        sink = InMemorySink(capacity=77)
        assert sink.capacity == 77

    def test_min_severity_drops_below_threshold(self) -> None:
        sink = InMemorySink(min_severity=9)  # INFO and above
        sink.emit(_record("debug", severity=5))
        sink.emit(_record("info", severity=9))
        sink.emit(_record("error", severity=17))
        records = sink.records()
        assert [r.body for r in records] == ["info", "error"]

    def test_supports_severity(self) -> None:
        sink = InMemorySink(min_severity=9)
        assert not sink.supports_severity(5)
        assert sink.supports_severity(9)
        assert sink.supports_severity(17)

    def test_protocol_compliance(self) -> None:
        sink = InMemorySink()
        assert isinstance(sink, Sink)
