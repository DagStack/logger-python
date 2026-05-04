"""Auto-tests for Python snippets from `docs/concepts/scoped-overrides.mdx`."""

from __future__ import annotations

from pathlib import Path

from dagstack.logger import (
    FileSink,
    InMemorySink,
    Logger,
    configure,
)


# ── "Three operations" — with_sinks / append_sinks / without_sinks ────


def test_scoped_overrides__three_operations(tmp_path: Path) -> None:
    """Snippet `docs/concepts/scoped-overrides.mdx` → "Three operations" → Python TabItem.

    NB: docs use FileSink("/var/log/audit.jsonl"). Substituted with
    `tmp_path / audit.jsonl` for sandbox-safe execution.
    """
    audit_path = tmp_path / "audit.jsonl"

    # Ensure the parent logger has a baseline sink so `append_sinks` has
    # something to extend (otherwise effective_sinks() = [] and the
    # "both parent's and the extra" assertion below would degrade).
    # Helper avoids shadowing `InMemorySink` (which the snippet imports).
    parent_capture = _make_parent_capture()

    # --- snippet start (scoped-overrides / three operations — adapted) ----
    from dagstack.logger import Logger, InMemorySink, FileSink

    logger = Logger.get("order_service")

    # Replace sinks — only InMemorySink receives emits.
    test_logger = logger.with_sinks([InMemorySink(capacity=100)])
    test_logger.info("captured here")

    # Append a sink — both the parent's and the extra receive emits.
    # NB: docs: FileSink("/var/log/audit.jsonl")
    audit_logger = logger.append_sinks([FileSink(audit_path)])
    audit_logger.info("audit event")

    # Discard — emits go to /dev/null.
    silent_logger = logger.without_sinks()
    silent_logger.info("never seen")
    # --- snippet end ------------------------------------------------------

    # `with_sinks` replaced sinks — `parent_capture` did NOT receive
    # "captured here" via test_logger (test_logger has its own InMemorySink).
    bodies = [r.body for r in parent_capture.records()]
    assert "captured here" not in bodies

    # `append_sinks` extended — parent_capture DID receive "audit event"
    # and the file ALSO got "audit event".
    assert "audit event" in bodies
    assert audit_path.exists()
    assert "audit event" in audit_path.read_text(encoding="utf-8")

    # `without_sinks` discards — "never seen" reached neither.
    assert "never seen" not in bodies
    assert "never seen" not in audit_path.read_text(encoding="utf-8")


# ── "Lexically bounded scope" — scope_sinks context manager ───────────


def test_scoped_overrides__scope_sinks_context_manager() -> None:
    """Snippet `docs/concepts/scoped-overrides.mdx` → "Lexically bounded scope" → Python TabItem."""
    # Bootstrap with a baseline sink — extracted to a helper so the snippet
    # below can `from dagstack.logger import InMemorySink, ...` without
    # Python's local-scoping rule shadowing the symbol used here.
    _bootstrap_scope_sinks_test()

    def run_business_logic() -> None:
        Logger.get("order_service").info("inside scope")

    # --- snippet start (scoped-overrides / scope_sinks) -------------------
    from dagstack.logger import Logger, InMemorySink

    logger = Logger.get("order_service")
    sink = InMemorySink(capacity=100)

    with logger.scope_sinks([sink]):
        run_business_logic()  # emits via Logger.get("order_service") land in sink
        # other modules calling Logger.get("order_service") inside this block
        # also emit into sink

    # Outside the block, emits go to the global sinks again.
    assert len(sink.records()) > 0
    # --- snippet end ------------------------------------------------------


def _make_parent_capture() -> InMemorySink:
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])
    return sink


def _bootstrap_scope_sinks_test() -> None:
    configure(root_level="INFO", sinks=[InMemorySink()])
