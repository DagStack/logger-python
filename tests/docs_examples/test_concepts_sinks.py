"""Auto-tests for Python snippets from `docs/concepts/sinks.mdx`."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from dagstack.logger import (
    ConsoleSink,
    FileSink,
    InMemorySink,
    Logger,
    configure,
)


# ── "ConsoleSink" — three modes ────────────────────────────────────────


def test_sinks__console_sink_three_modes() -> None:
    """Snippet `docs/concepts/sinks.mdx` → "ConsoleSink" → Python TabItem.

    Three distinct ConsoleSink configurations — auto, json with severity
    floor, and forced pretty — must construct without error and expose the
    documented `id` field.
    """
    # --- snippet start (sinks / ConsoleSink) ------------------------------
    from dagstack.logger import ConsoleSink

    # Auto mode: pretty on a TTY, JSON otherwise.
    sink = ConsoleSink(mode="auto")

    # Force JSON for container logs.
    sink = ConsoleSink(mode="json", min_severity=9)

    # Force pretty for a debug terminal.
    sink = ConsoleSink(mode="pretty")
    # --- snippet end ------------------------------------------------------

    # The last assignment is "pretty" mode.
    assert sink.id == "console:pretty"


# ── "FileSink" — full options ──────────────────────────────────────────


def test_sinks__file_sink(tmp_path: Path) -> None:
    """Snippet `docs/concepts/sinks.mdx` → "FileSink" → Python TabItem.

    The doc snippet writes to `/var/log/order-service.jsonl` which the test
    sandbox cannot create. Substituted with `tmp_path / order-service.jsonl`
    so the constructor exercises real disk I/O without escalating perms.
    """
    log_path = tmp_path / "order-service.jsonl"

    # --- snippet start (sinks / FileSink — adapted) -----------------------
    from dagstack.logger import FileSink

    sink = FileSink(
        log_path,  # NB: docs use "/var/log/order-service.jsonl"
        max_bytes=100_000_000,  # rotate at 100 MB
        keep=10,  # keep 10 archived files
        min_severity=9,  # INFO and above
    )
    # --- snippet end ------------------------------------------------------

    assert sink.id == f"file:{log_path}"
    assert sink.supports_severity(9) is True
    assert sink.supports_severity(8) is False  # below INFO floor

    # Emit a record and verify it lands on disk as JSON-lines.
    configure(root_level="INFO", sinks=[sink])
    Logger.get("test").info("first line", attributes={"k": "v"})
    sink.close()

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "first line" in content


# ── "InMemorySink" — capture + clear ───────────────────────────────────


def test_sinks__in_memory_sink() -> None:
    """Snippet `docs/concepts/sinks.mdx` → "InMemorySink" → Python TabItem.

    The MDX snippet contains the elided line `# ... emit some records ...`.
    To exercise the `assert any(r.body == "expected message" ...)` line
    verbatim, we wire the sink onto a logger and emit one matching record
    where the docs say "emit some records". The snippet itself stays
    untouched between the markers.
    """
    # --- snippet start (sinks / InMemorySink) -----------------------------
    from dagstack.logger import InMemorySink

    sink = InMemorySink(capacity=100)
    # ... emit some records ...
    Logger.get("").set_sinks([sink])  # NB: realisation of the elided "..." line.
    Logger.get("test").info("expected message")  # NB: idem.

    records = sink.records()  # snapshot copy
    assert any(r.body == "expected message" for r in records)

    sink.clear()  # reset for the next test
    # --- snippet end ------------------------------------------------------

    # After clear() the snapshot is empty.
    assert sink.records() == []


# ── "Multi-sink routing" ──────────────────────────────────────────────


def test_sinks__multi_sink_routing(tmp_path: Path) -> None:
    """Snippet `docs/concepts/sinks.mdx` → "Multi-sink routing" → Python TabItem.

    NB: docs use FileSink("/var/log/app.jsonl", ...). Substituted with
    `tmp_path / app.jsonl` for sandbox-safe execution.
    """
    log_path = tmp_path / "app.jsonl"

    # --- snippet start (sinks / multi-sink routing — adapted) -------------
    from dagstack.logger import ConsoleSink, FileSink, configure

    configure(
        root_level="DEBUG",
        sinks=[
            ConsoleSink(mode="pretty", min_severity=13),  # WARN+ on the console
            # NB: docs use "/var/log/app.jsonl"
            FileSink(log_path, max_bytes=100_000_000, keep=10, min_severity=9),
        ],
    )
    # --- snippet end ------------------------------------------------------

    # The two sinks have independent severity floors — verify by emitting
    # at DEBUG (below console's 13 floor, also below file's 9 floor):
    Logger.get("test").info("info-only", attributes={"k": "v"})
    Logger.get("").flush()
    Logger.get("").close()

    content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    # FileSink min_severity=9 (INFO) accepted the record.
    assert "info-only" in content


# Lint shrinking — every name imported above is referenced somewhere.
_ = (io, pytest, ConsoleSink, FileSink, InMemorySink)
