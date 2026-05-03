"""Unit tests for FileSink."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from dagstack.logger.records import LogRecord
from dagstack.logger.sinks import FileSink, Sink

if TYPE_CHECKING:
    from pathlib import Path


def _record(body: str = "msg", severity_number: int = 9) -> LogRecord:
    return LogRecord(
        time_unix_nano=0,
        severity_number=severity_number,
        severity_text="INFO",
        body=body,
    )


class TestFileSinkBasic:
    def test_writes_jsonl_to_file(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        sink = FileSink(target)
        sink.emit(_record("hello"))
        sink.close()
        content = target.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["body"] == "hello"

    def test_multiple_records_multiple_lines(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        sink = FileSink(target)
        for i in range(3):
            sink.emit(_record(f"msg-{i}"))
        sink.close()
        lines = target.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["body"] == "msg-0"
        assert json.loads(lines[2])["body"] == "msg-2"

    def test_id_includes_path(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        sink = FileSink(target)
        assert sink.id == f"file:{target}"
        sink.close()


class TestFileSinkRotation:
    def test_rotation_by_size(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        # A small max_bytes → rotation after several records.
        sink = FileSink(target, max_bytes=200, keep=2)
        for i in range(20):
            sink.emit(_record(f"record-{i:03d}"))
        sink.close()
        # Main file + at least 1 backup.
        backups = list(tmp_path.glob("log.jsonl.*"))
        assert len(backups) >= 1
        assert len(backups) <= 2  # keep=2 — no more.


class TestFileSinkFilter:
    def test_min_severity_drops_below(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        sink = FileSink(target, min_severity=13)  # WARN+
        sink.emit(_record("debug", severity_number=5))
        sink.emit(_record("info", severity_number=9))
        sink.emit(_record("warn", severity_number=13))
        sink.close()
        lines = target.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["body"] == "warn"


class TestFileSinkLifecycle:
    def test_close_prevents_further_writes(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        sink = FileSink(target)
        sink.emit(_record("before"))
        sink.close()
        sink.emit(_record("after"))
        content = target.read_text(encoding="utf-8").strip()
        assert "before" in content
        assert "after" not in content

    def test_close_idempotent(self, tmp_path: Path) -> None:
        sink = FileSink(tmp_path / "log.jsonl")
        sink.close()
        sink.close()

    def test_flush_noop_basically(self, tmp_path: Path) -> None:
        sink = FileSink(tmp_path / "log.jsonl")
        sink.emit(_record())
        sink.flush()
        sink.close()


class TestFileSinkProtocol:
    def test_is_sink(self, tmp_path: Path) -> None:
        sink = FileSink(tmp_path / "log.jsonl")
        assert isinstance(sink, Sink)
        sink.close()
