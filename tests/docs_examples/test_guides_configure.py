"""Auto-tests for Python snippets from `docs/guides/configure.mdx`."""

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


# ── Step 2. "Build sinks from the config" — build_sinks factory ───────


def test_configure__build_sinks_factory(tmp_path: Path) -> None:
    """Snippet `docs/guides/configure.mdx` → "Step 2. Build sinks from the config" → Python TabItem.

    The factory function `build_sinks` is defined verbatim from the docs.
    We run it against two synthetic sink specs (console + file) and
    verify the returned list contains the expected sink kinds.
    """
    log_path = tmp_path / "order-service.jsonl"

    # --- snippet start (configure / build_sinks factory) ------------------
    from dagstack.logger import ConsoleSink, FileSink, configure

    def build_sinks(sink_specs: list[dict]) -> list:
        sinks = []
        for spec in sink_specs:
            kind = spec["type"]
            if kind == "console":
                sinks.append(
                    ConsoleSink(
                        mode=spec.get("mode", "auto"),
                        min_severity=_resolve_severity(spec.get("min_severity", "INFO")),
                    )
                )
            elif kind == "file":
                sinks.append(
                    FileSink(
                        path=spec["path"],
                        max_bytes=spec.get("max_bytes", 0),
                        keep=spec.get("keep", 0),
                        min_severity=_resolve_severity(spec.get("min_severity", "INFO")),
                    )
                )
            else:
                raise ValueError(f"unsupported sink type: {kind!r}")
        return sinks

    def _resolve_severity(value):
        # configure() also accepts these strings directly; this helper is
        # for sinks where the constructor expects an int.
        return {"TRACE": 1, "DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17, "FATAL": 21}[
            value.upper()
        ]

    # --- snippet end ------------------------------------------------------

    sinks = build_sinks(
        [
            {"type": "console", "mode": "json", "min_severity": "WARN"},
            {
                "type": "file",
                "path": str(log_path),
                "max_bytes": 1_000_000,
                "keep": 3,
                "min_severity": "INFO",
            },
        ]
    )

    assert len(sinks) == 2
    assert isinstance(sinks[0], ConsoleSink)
    assert sinks[0].id == "console:json"
    assert isinstance(sinks[1], FileSink)
    assert sinks[1].id == f"file:{log_path}"
    # Severity floor for console is WARN (13).
    assert sinks[0].supports_severity(12) is False
    assert sinks[0].supports_severity(13) is True
    # Severity floor for file is INFO (9).
    assert sinks[1].supports_severity(8) is False
    assert sinks[1].supports_severity(9) is True

    # Unknown kind raises.
    with pytest.raises(ValueError, match="unsupported sink type"):
        build_sinks([{"type": "kafka"}])

    # Reference `configure` so the snippet's import is exercised.
    assert configure is not None


# ── Step 4. "Per-logger overrides" ────────────────────────────────────


def test_configure__per_logger_overrides() -> None:
    """Snippet `docs/guides/configure.mdx` → "Step 4. Per-logger overrides" → Python TabItem.

    `per_logger_levels` overrides min_severity for individual named loggers.
    """
    capture = InMemorySink()

    # --- snippet start (configure / per-logger overrides) -----------------
    from dagstack.logger import ConsoleSink, configure

    configure(
        root_level="INFO",
        # NB: docs ConsoleSink(mode="auto"); we add a capture sink for asserts.
        sinks=[ConsoleSink(mode="auto"), capture],
        per_logger_levels={
            "httpx": "WARN",
            "urllib3": "WARN",
            "order_service.checkout": "DEBUG",
        },
        resource_attributes={"service.name": "order-service"},
    )
    # --- snippet end ------------------------------------------------------

    # `order_service.checkout` accepts DEBUG records (5 ≥ 5).
    Logger.get("order_service.checkout").debug("debug-from-checkout")
    # `httpx` rejects INFO records (9 < 13).
    Logger.get("httpx").info("info-from-httpx")
    # Default INFO logger accepts INFO records.
    Logger.get("other.module").info("info-from-other")

    bodies = [r.body for r in capture.records()]
    assert "debug-from-checkout" in bodies, (
        "DEBUG override on order_service.checkout was not applied"
    )
    assert "info-from-httpx" not in bodies, "WARN override on httpx did not silence INFO"
    assert "info-from-other" in bodies


# ── Step 5. "Graceful shutdown" — atexit + flush + close ──────────────


def test_configure__graceful_shutdown() -> None:
    """Snippet `docs/guides/configure.mdx` → "Step 5. Graceful shutdown" → Python TabItem.

    The `@atexit.register` decorator side-effects the global atexit list,
    so we run only the body of the registered function (not the registration
    itself) to keep the test isolated. The registration line is preserved
    inside the snippet block; the asserts below cover its behaviour.
    """
    capture = _seed_pre_shutdown_capture()

    # --- snippet start (configure / graceful shutdown) --------------------
    import atexit
    from dagstack.logger import Logger

    @atexit.register
    def shutdown_logger():
        Logger.get("").flush(timeout=5.0)
        Logger.get("").close()

    # --- snippet end ------------------------------------------------------

    # Invoke the registered hook synchronously to verify it does not raise.
    shutdown_logger()

    # Records emitted before close are visible; flush/close are idempotent.
    assert any(r.body == "pre-shutdown" for r in capture.records())
    # Calling again is a no-op (per docs the call is idempotent).
    shutdown_logger()


def _seed_pre_shutdown_capture() -> InMemorySink:
    """Helper: configure root with one InMemorySink and emit a pre-shutdown record.

    Extracted so the snippet body below can `from dagstack.logger import
    Logger` without Python's local-scoping rule shadowing the symbol.
    """
    capture = InMemorySink()
    configure(root_level="INFO", sinks=[capture])
    Logger.get("test").info("pre-shutdown")
    return capture


# Lint anchors.
_ = (io, ConsoleSink, FileSink, InMemorySink, configure)
