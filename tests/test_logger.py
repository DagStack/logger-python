"""Unit tests for the Logger class."""

from __future__ import annotations

from typing import Any

import pytest

from dagstack.logger import (
    ConsoleSink,
    InMemorySink,
    Logger,
    Severity,
    configure,
)
from dagstack.logger.logger import _reset_registry_for_tests


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Isolate tests — clear the Logger registry between each."""
    _reset_registry_for_tests()


def _capture_sink() -> InMemorySink:
    return InMemorySink()


class TestLoggerGet:
    def test_root_logger_cached(self) -> None:
        a = Logger.get("")
        b = Logger.get("")
        assert a is b

    def test_named_logger_cached(self) -> None:
        a = Logger.get("dagstack.rag")
        b = Logger.get("dagstack.rag")
        assert a is b

    def test_child_has_parent(self) -> None:
        parent = Logger.get("dagstack")
        child = Logger.get("dagstack.rag")
        # Parent should be cached reference — child points to it.
        assert child._parent is parent

    def test_root_has_no_parent(self) -> None:
        root = Logger.get("")
        assert root._parent is None

    def test_version_updated_on_existing(self) -> None:
        a = Logger.get("x")
        b = Logger.get("x", version="1.0")
        assert a is b
        assert b.version == "1.0"


class TestLoggerReset:
    def test_reset_clears_registry(self) -> None:
        a = Logger.get("dagstack.reset_test")
        a.set_min_severity(99)
        Logger.reset()
        b = Logger.get("dagstack.reset_test")
        # New registry node — a no longer reflects shared state.
        assert b._min_severity == 1
        # And a fresh handle is not the previous singleton.
        assert b is not a

    def test_reset_is_idempotent(self) -> None:
        Logger.reset()
        Logger.reset()
        # Should not raise and the next get works.
        Logger.get("dagstack.reset_idempotent")


class TestSeverityMethods:
    def test_info_emits_with_correct_severity(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        Logger.get("test").info("msg")
        rec = sink.records()[0]
        assert rec.severity_number == int(Severity.INFO)
        assert rec.severity_text == "INFO"
        assert rec.body == "msg"

    def test_all_severity_methods(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        log = Logger.get("x")
        log.trace("t")
        log.debug("d")
        log.info("i")
        log.warn("w")
        log.error("e")
        log.fatal("f")
        severities = [r.severity_text for r in sink.records()]
        assert severities == ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]

    def test_log_with_explicit_severity_number(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        Logger.get("x").log(10, "inter")  # INFO2 range
        rec = sink.records()[0]
        assert rec.severity_number == 10
        assert rec.severity_text == "INFO"  # bucket canonical


class TestExceptionLogging:
    def test_exception_adds_otel_attributes(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        try:
            raise ValueError("boom")
        except ValueError as err:
            Logger.get("x").exception(err)
        rec = sink.records()[0]
        assert rec.severity_text == "ERROR"
        assert rec.attributes["exception.type"] == "ValueError"
        assert rec.attributes["exception.message"] == "boom"
        trace_str = rec.attributes["exception.stacktrace"]
        assert isinstance(trace_str, str)
        assert "ValueError: boom" in trace_str
        assert "raise ValueError" in trace_str

    def test_exception_custom_body_and_attrs(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        try:
            raise RuntimeError("oops")
        except RuntimeError as err:
            Logger.get("x").exception(
                err, body="failed to process", attributes={"request.id": "req-42"}
            )
        rec = sink.records()[0]
        assert rec.body == "failed to process"
        assert rec.attributes["request.id"] == "req-42"
        assert rec.attributes["exception.type"] == "RuntimeError"


class TestAttributes:
    def test_call_site_attributes_merged(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        Logger.get("x").info("msg", attributes={"user.id": 42})
        assert sink.records()[0].attributes["user.id"] == 42

    def test_child_logger_binds_attributes(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        base = Logger.get("x")
        scoped = base.child({"session.id": "sess-1"})
        scoped.info("in scope")
        rec = sink.records()[0]
        assert rec.attributes["session.id"] == "sess-1"

    def test_child_attributes_overridden_by_callsite(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        log = Logger.get("x").child({"k": "parent"})
        log.info("msg", attributes={"k": "call-site"})
        assert sink.records()[0].attributes["k"] == "call-site"

    def test_redaction_masks_secrets(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        Logger.get("x").info("msg", attributes={"api_key": "sk-secret", "user.id": 42})
        attrs = sink.records()[0].attributes
        assert attrs["api_key"] == "***"
        assert attrs["user.id"] == 42


class TestHierarchy:
    def test_child_inherits_sinks(self) -> None:
        sink = _capture_sink()
        configure(root_level="TRACE", sinks=[sink])
        Logger.get("dagstack.rag.retriever").info("from deep logger")
        assert len(sink.records()) == 1

    def test_child_inherits_min_severity(self) -> None:
        sink = _capture_sink()
        configure(
            root_level="TRACE",
            sinks=[sink],
            per_logger_levels={"dagstack.rag": "WARN"},
        )
        child = Logger.get("dagstack.rag.retriever")
        child.debug("below threshold")
        child.error("above threshold")
        records = sink.records()
        assert len(records) == 1
        assert records[0].body == "above threshold"

    def test_per_logger_level_override(self) -> None:
        sink = _capture_sink()
        configure(
            root_level="INFO",
            sinks=[sink],
            per_logger_levels={"noisy": "WARN"},
        )
        Logger.get("noisy").info("should be dropped")
        Logger.get("quiet").info("should pass")
        bodies = [r.body for r in sink.records()]
        assert "should be dropped" not in bodies
        assert "should pass" in bodies


class TestScopedOverrides:
    def test_with_sinks_creates_detached_child(self) -> None:
        sink_base = _capture_sink()
        sink_scoped = _capture_sink()
        configure(root_level="TRACE", sinks=[sink_base])
        base = Logger.get("x")
        scoped = base.with_sinks([sink_scoped])
        scoped.info("only scoped")
        assert len(sink_scoped.records()) == 1
        assert len(sink_base.records()) == 0  # no leak

    def test_append_sinks_includes_both(self) -> None:
        sink_base = _capture_sink()
        sink_extra = _capture_sink()
        configure(root_level="TRACE", sinks=[sink_base])
        scoped = Logger.get("x").append_sinks([sink_extra])
        scoped.info("both")
        assert len(sink_base.records()) == 1
        assert len(sink_extra.records()) == 1

    def test_without_sinks_discards(self) -> None:
        sink_base = _capture_sink()
        configure(root_level="TRACE", sinks=[sink_base])
        scoped = Logger.get("x").without_sinks()
        scoped.info("discarded")
        assert len(sink_base.records()) == 0

    def test_scope_sinks_context_manager(self) -> None:
        sink_base = _capture_sink()
        sink_scoped = _capture_sink()
        configure(root_level="TRACE", sinks=[sink_base])
        log = Logger.get("x")
        log.info("before")
        with log.scope_sinks([sink_scoped]):
            log.info("during")
        log.info("after")
        assert [r.body for r in sink_base.records()] == ["before", "after"]
        assert [r.body for r in sink_scoped.records()] == ["during"]


class TestConfigure:
    def test_resource_attributes_attached(self) -> None:
        sink = _capture_sink()
        configure(
            root_level="INFO",
            sinks=[sink],
            resource_attributes={"service.name": "order-service"},
        )
        Logger.get("x").info("msg")
        rec = sink.records()[0]
        assert rec.resource is not None
        assert rec.resource.attributes["service.name"] == "order-service"

    def test_level_resolves_string(self) -> None:
        sink = _capture_sink()
        configure(root_level="warn", sinks=[sink])  # case-insensitive
        Logger.get("x").info("below")
        Logger.get("x").error("above")
        assert len(sink.records()) == 1

    def test_level_resolves_numeric(self) -> None:
        sink = _capture_sink()
        configure(root_level=17, sinks=[sink])  # ERROR baseline
        Logger.get("x").warn("below")
        Logger.get("x").error("above")
        assert len(sink.records()) == 1

    def test_unknown_level_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown severity"):
            configure(root_level="BOGUS")

    def test_invalid_numeric_level_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[1, 24\]"):
            configure(root_level=100)


class TestSubscriptionInactive:
    def test_on_reconfigure_returns_inactive(self) -> None:
        configure(root_level="INFO", sinks=[_capture_sink()])
        sub = Logger.get("x").on_reconfigure(callback=lambda: None)
        assert sub.active is False


class TestLifecycle:
    def test_flush_no_exception(self) -> None:
        configure(root_level="INFO", sinks=[_capture_sink()])
        Logger.get("x").flush()

    def test_close_no_exception(self) -> None:
        configure(root_level="INFO", sinks=[_capture_sink()])
        Logger.get("x").close()

    def test_flush_isolates_failing_sink(self) -> None:
        class _FailingSink:
            id = "fail"

            def emit(self, _: Any) -> None:
                pass

            def flush(self, _: float = 5.0) -> None:
                raise RuntimeError("boom")

            def close(self) -> None:
                pass

            def supports_severity(self, _: int) -> bool:
                return True

        sink = _capture_sink()
        configure(root_level="INFO", sinks=[_FailingSink(), sink])
        # Does not crash despite the exception in the first sink's flush.
        Logger.get("x").flush()

    def test_sink_emit_failure_isolated(self) -> None:
        class _FailingSink:
            id = "fail"

            def emit(self, _: Any) -> None:
                raise RuntimeError("emit boom")

            def flush(self, _: float = 5.0) -> None:
                pass

            def close(self) -> None:
                pass

            def supports_severity(self, _: int) -> bool:
                return True

        good = _capture_sink()
        configure(root_level="INFO", sinks=[_FailingSink(), good])
        Logger.get("x").info("msg")
        # The good sink still received the record despite the failing sibling.
        assert len(good.records()) == 1


class TestIntegrationWithConsoleSink:
    def test_records_traverse_console_and_memory(self) -> None:
        import io

        stream = io.StringIO()
        mem_sink = _capture_sink()
        configure(
            root_level="INFO",
            sinks=[ConsoleSink(mode="json", stream=stream), mem_sink],
        )
        Logger.get("x").info("hello")
        assert "hello" in stream.getvalue()
        assert mem_sink.records()[0].body == "hello"


class TestConfigureRedaction:
    def test_extra_suffixes_additive(self) -> None:
        from dagstack.logger import InMemorySink, Logger, RedactionConfig, configure

        sink = InMemorySink()
        configure(
            root_level="INFO",
            sinks=[sink],
            redaction=RedactionConfig(extra_suffixes=("_apikey",)),
        )
        Logger.get("x").info(
            "event",
            attributes={
                "openai_api_key": "sk-base",  # base — masked
                "stripe_apikey": "sk-extra",  # extra — masked
                "user.id": 17,  # safe
            },
        )
        rec = sink.records()[0]
        assert rec.attributes["openai_api_key"] == "***"
        assert rec.attributes["stripe_apikey"] == "***"
        assert rec.attributes["user.id"] == 17

    def test_replace_defaults(self) -> None:
        from dagstack.logger import InMemorySink, Logger, RedactionConfig, configure

        sink = InMemorySink()
        configure(
            root_level="INFO",
            sinks=[sink],
            redaction=RedactionConfig(extra_suffixes=("_password",), replace_defaults=True),
        )
        Logger.get("x").info(
            "event",
            attributes={
                "openai_api_key": "sk-base",  # base — NOT masked under replace
                "db_password": "real-password",  # extra — masked
            },
        )
        rec = sink.records()[0]
        assert rec.attributes["openai_api_key"] != "***"
        assert rec.attributes["db_password"] == "***"

    def test_disable_all_does_not_leak_warn_to_app_sinks(self) -> None:
        from dagstack.logger import InMemorySink, Logger, RedactionConfig, configure

        sink = InMemorySink()
        configure(
            root_level="INFO",
            sinks=[sink],
            redaction=RedactionConfig(replace_defaults=True),
        )
        Logger.get("x").info(
            "event",
            attributes={
                "openai_api_key": "sk-base",
                "db_password": "real-password",
            },
        )
        rec = sink.records()[0]
        assert rec.attributes["openai_api_key"] != "***"
        assert rec.attributes["db_password"] != "***"
        # Internal WARN MUST NOT route to application sinks (spec §7.4).
        for r in sink.records():
            body = r.body if isinstance(r.body, str) else ""
            assert "disable-all" not in body

    def test_invalid_suffix_raises_synchronously(self) -> None:
        import pytest

        from dagstack.logger import InMemorySink, Logger, RedactionConfig, configure

        sink = InMemorySink()
        with pytest.raises(ValueError, match="lowercase ASCII"):
            configure(
                root_level="INFO",
                sinks=[sink],
                redaction=RedactionConfig(extra_suffixes=("_APIKEY",)),
            )
        # No partial reconfigure: sinks list never installed.
        Logger.get("x").info("post-throw", attributes={})
        assert sink.records() == []

    def test_internal_logger_defaults_to_own_sink(self) -> None:
        from dagstack.logger import (
            INTERNAL_LOGGER_NAME,
            ConsoleSink,
            InMemorySink,
            Logger,
            configure,
        )

        sink = InMemorySink()
        configure(root_level="INFO", sinks=[sink])
        internal = Logger.get(INTERNAL_LOGGER_NAME)
        sinks = internal.effective_sinks()
        assert len(sinks) == 1
        assert isinstance(sinks[0], ConsoleSink)

    def test_internal_logger_operator_override(self) -> None:
        from dagstack.logger import INTERNAL_LOGGER_NAME, InMemorySink, Logger

        custom = InMemorySink()
        Logger.get(INTERNAL_LOGGER_NAME).set_sinks([custom])
        sinks = Logger.get(INTERNAL_LOGGER_NAME).effective_sinks()
        assert len(sinks) == 1
        assert sinks[0].id == custom.id


class TestAutoInjectTraceContext:
    """M2 cross-binding parity flag per spec ADR-0001 v1.2 §3.4.2."""

    def test_default_is_true(self) -> None:
        """Python idiomatic default: auto-inject ON (matches OTel context API)."""
        from dagstack.logger.logger import (
            _get_auto_inject_trace_context,
            _reset_registry_for_tests,
        )

        _reset_registry_for_tests()
        assert _get_auto_inject_trace_context() is True

    def test_configure_disables_ambient_lookup(self) -> None:
        """When False, emit skips get_active_trace_context — wire output without trace_id."""
        from dagstack.logger import InMemorySink, Logger, configure

        sink = InMemorySink()
        configure(
            root_level="INFO",
            sinks=[sink],
            auto_inject_trace_context=False,
        )
        Logger.get("x").info("event")
        rec = sink.records()[0]
        assert rec.trace_id is None
        assert rec.span_id is None
        assert rec.trace_flags == 0

    def test_configure_omitted_preserves_current(self) -> None:
        """When auto_inject_trace_context is None (omitted), current value persists."""
        from dagstack.logger import InMemorySink, configure
        from dagstack.logger.logger import (
            _get_auto_inject_trace_context,
            _reset_registry_for_tests,
        )

        _reset_registry_for_tests()
        # Start true (default), flip to false, then call configure() without
        # the flag — must remain false.
        configure(root_level="INFO", sinks=[InMemorySink()], auto_inject_trace_context=False)
        assert _get_auto_inject_trace_context() is False
        configure(root_level="INFO", sinks=[InMemorySink()])
        assert _get_auto_inject_trace_context() is False
        # Flip back explicitly.
        configure(root_level="INFO", sinks=[InMemorySink()], auto_inject_trace_context=True)
        assert _get_auto_inject_trace_context() is True

    def test_reset_registry_restores_default(self) -> None:
        """_reset_registry_for_tests must restore default True for test isolation."""
        from dagstack.logger.logger import (
            _get_auto_inject_trace_context,
            _reset_registry_for_tests,
            _set_auto_inject_trace_context,
        )

        _set_auto_inject_trace_context(False)
        assert _get_auto_inject_trace_context() is False
        _reset_registry_for_tests()
        assert _get_auto_inject_trace_context() is True
