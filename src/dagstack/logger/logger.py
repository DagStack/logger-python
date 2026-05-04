"""Logger class — main public API.

Per spec §3: named loggers with dot-hierarchy, severity methods,
context-bound child loggers, scoped sink overrides, context propagation.

Python idioms (per spec §3.5):
- Sync primary API; async variants via future `ainfo`/`aerror` (Phase 2+).
- Methods accept `**attrs` kwargs OR an explicit `attributes` dict.
- `exception(err)` automatically captures active exception info.

Hierarchy (per spec §3.1): `Logger.get("dagstack.rag.retriever")` →
parent `"dagstack.rag"` → `"dagstack"` → root `""`. Sinks and min_level
inherit from the parent unless overridden on the child.
"""

from __future__ import annotations

import threading
import time
import traceback
from typing import TYPE_CHECKING

from dagstack.logger.context import get_active_trace_context, get_baggage_attributes
from dagstack.logger.records import InstrumentationScope, LogRecord, Resource
from dagstack.logger.redaction import DEFAULT_SECRET_SUFFIXES, redact_attributes
from dagstack.logger.severity import Severity, severity_text_for
from dagstack.logger.subscription import Subscription, emit_inactive_subscription_warning

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from dagstack.logger.records import Value
    from dagstack.logger.sinks import Sink


# RLock — `Logger.get` recurses into itself for the parent chain inside the
# lock. A plain Lock() would deadlock on recursive acquire by the same thread.
_registry_lock = threading.RLock()
_loggers: dict[str, Logger] = {}
_root_name = ""

#: Diagnostic channel for binding-internal warnings (sink failures,
#: configure-time disable-all redaction, etc.) per spec §7.4. This logger
#: MUST default to a stderr ConsoleSink so its output never silently merges
#: with application sinks — operators may opt in to merging by calling
#: ``set_sinks`` explicitly.
INTERNAL_LOGGER_NAME = "dagstack.logger.internal"

# Cross-binding parity flag per spec ADR-0001 v1.2 §3.4.2 (M2). The Python
# binding's idiomatic default is True (matches OTel's `opentelemetry.context`
# convention, which delegates to `contextvars`). Mutated only via
# `configure(auto_inject_trace_context=...)` and the test-only
# `_reset_registry_for_tests`.
_auto_inject_trace_context = True


def _get_auto_inject_trace_context() -> bool:
    """Internal accessor used by Logger._emit to read the current flag."""
    return _auto_inject_trace_context


def _set_auto_inject_trace_context(value: bool) -> None:
    """Internal mutator used by configure() to apply the flag."""
    global _auto_inject_trace_context
    _auto_inject_trace_context = value


class Logger:
    """Named logger with dot-hierarchy.

    Do NOT construct directly — use `Logger.get(name, version)`:

        >>> logger = Logger.get("dagstack.rag.retriever", version="1.4.2")
        >>> logger.info("query received", attributes={"user.id": 42})
        >>> logger.exception(err)  # auto stack trace

    Scoped overrides:

        >>> with logger.scope_sinks([InMemorySink()]):
        ...     logger.info("captured in scope")
    """

    __slots__ = (
        "_attributes",
        "_lock",
        "_min_severity",
        "_name",
        "_parent",
        "_redaction_explicit",
        "_redaction_suffixes",
        "_resource",
        "_scope",
        "_sinks",
        "_sinks_explicit",
        "_version",
    )

    _name: str
    _version: str | None
    _parent: Logger | None
    _sinks: list[Sink]
    _sinks_explicit: bool
    _min_severity: int
    _attributes: dict[str, Value]
    _resource: Resource | None
    _scope: InstrumentationScope
    _redaction_suffixes: frozenset[str]
    _redaction_explicit: bool
    _lock: threading.Lock

    # ─── Constructor / registry ───────────────────────────────────────────────

    @classmethod
    def get(cls, name: str = "", version: str | None = None) -> Logger:
        """Return (or create) a named logger. Cached in the registry.

        Args:
            name: dot-notation path. `""` = root. Parent is derived by
                splitting on the last dot.
            version: instrumentation scope version; updated on the existing
                logger if it differs.
        """
        with _registry_lock:
            if name in _loggers:
                existing = _loggers[name]
                # Update version if newly provided.
                if version is not None and existing._version != version:
                    existing._version = version
                    existing._scope = InstrumentationScope(name=name or "root", version=version)
                return existing
            parent: Logger | None = None
            if name != _root_name:
                parent_name = _parent_name_of(name)
                parent = cls.get(parent_name)
            instance = cls.__new__(cls)
            instance._init_state(name=name, version=version, parent=parent)
            _loggers[name] = instance
            return instance

    def _init_state(
        self,
        *,
        name: str,
        version: str | None,
        parent: Logger | None,
    ) -> None:
        self._name = name
        self._version = version
        self._parent = parent
        self._sinks = []
        self._sinks_explicit = False
        self._min_severity = 1  # inherit resolution via effective_min_severity
        self._attributes = {}
        self._resource = None
        self._scope = InstrumentationScope(name=name or "root", version=version)
        # `_redaction_explicit=False` means inherit from parent (root falls back
        # to DEFAULT_SECRET_SUFFIXES). When True, `_redaction_suffixes` is the
        # active set — including the empty frozenset for disable-all per spec
        # §10.4. The boolean flag avoids a `None`-vs-empty quirk.
        self._redaction_suffixes = DEFAULT_SECRET_SUFFIXES
        self._redaction_explicit = False
        self._lock = threading.Lock()
        if name == INTERNAL_LOGGER_NAME:
            # Default the diagnostic channel to its own stderr ConsoleSink so
            # internal warnings don't silently merge with application sinks
            # (spec §7.4). Operators may override via `.set_sinks(...)`.
            from dagstack.logger.severity import Severity  # local import — avoid cycle
            from dagstack.logger.sinks import ConsoleSink

            self._sinks = [ConsoleSink(mode="json", min_severity=int(Severity.WARN))]
            self._sinks_explicit = True

    # ─── Introspection ───────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str | None:
        return self._version

    def effective_sinks(self) -> list[Sink]:
        """Resolved sinks list — explicit on this logger or inherited from the parent."""
        if self._sinks_explicit:
            return list(self._sinks)
        if self._parent is not None:
            return self._parent.effective_sinks()
        return []

    def effective_min_severity(self) -> int:
        """Resolved min_severity — explicit or inherited."""
        if self._min_severity > 1:
            return self._min_severity
        if self._parent is not None:
            return self._parent.effective_min_severity()
        return 1

    def effective_resource(self) -> Resource | None:
        """Resolved resource — explicit or inherited."""
        if self._resource is not None:
            return self._resource
        if self._parent is not None:
            return self._parent.effective_resource()
        return None

    # ─── Configuration mutators ─────────────────────────────────────────────
    #
    # WARNING: these methods mutate the *shared* registry node for this
    # logger name (per spec §3.1). `Logger.get(name)` is a singleton per
    # name, so any other code that holds the same handle — or that calls
    # `Logger.get(name)` again — sees the updated state immediately. This
    # is intentional for bootstrap (`Logger.get("").set_min_severity(int(Severity.DEBUG))`
    # propagates through the whole tree via parent inheritance) but it
    # breaks naive test isolation: a test that overrides sinks on a
    # well-known name leaks the override into the next test.
    #
    # For test isolation, call `Logger.reset()` between tests, or use the
    # scoped variants (§6) — `with_sinks` / `append_sinks` /
    # `scope_sinks` — which return a fresh handle with overrides instead
    # of mutating the shared state.

    def set_sinks(self, sinks: list[Sink]) -> None:
        """Replace explicit sinks on this logger.

        Mutates the shared registry node (visible to all consumers of the
        same name). Children inherit the new list unless they have their
        own explicit sinks.
        """
        with self._lock:
            self._sinks = list(sinks)
            self._sinks_explicit = True

    def set_min_severity(self, severity_number: int) -> None:
        """Replace min_severity — early-drop threshold.

        Mutates the shared registry node (visible to all consumers of the
        same name). Children inherit unless they set their own threshold.
        """
        with self._lock:
            self._min_severity = severity_number

    def set_resource(self, resource: Resource | None) -> None:
        """Replace the Resource (or clear it with None).

        Mutates the shared registry node (visible to all consumers of the
        same name). Children inherit unless they set their own Resource.
        """
        with self._lock:
            self._resource = resource

    def set_redaction_suffixes(self, suffixes: frozenset[str] | None) -> None:
        """Install the effective secret-suffix set on this logger (spec §10.4).

        Mutates the shared registry node. The set MUST already be lowercased
        and validated — use :meth:`RedactionConfig.build_effective_suffixes` to
        derive it.

        Pass ``None`` to fall back to inherited behaviour (parent's suffixes or
        :data:`DEFAULT_SECRET_SUFFIXES` at the root). Pass an empty frozenset
        for the explicit disable-all case (per spec §10.4) — the resolver
        preserves it via the ``_redaction_explicit`` flag.
        """
        with self._lock:
            if suffixes is None:
                self._redaction_suffixes = DEFAULT_SECRET_SUFFIXES
                self._redaction_explicit = False
                return
            self._redaction_suffixes = suffixes
            self._redaction_explicit = True

    def effective_secret_suffixes(self) -> frozenset[str]:
        """Resolve the redaction-suffix set applied by this logger.

        Explicit on this node or inherited from the parent chain. Returns
        :data:`DEFAULT_SECRET_SUFFIXES` when no override is registered anywhere
        up the chain. An explicit empty frozenset (disable-all per spec §10.4)
        is preserved through inheritance via the ``_redaction_explicit`` flag.
        """
        # Internal: the four chain-walks (sinks / min-severity / resource /
        # suffixes) are tracked for collapse into a single upward traversal
        # in issue #105.
        if self._redaction_explicit:
            return self._redaction_suffixes
        if self._parent is not None:
            return self._parent.effective_secret_suffixes()
        return DEFAULT_SECRET_SUFFIXES

    @classmethod
    def reset(cls) -> None:
        """Clear the global Logger registry — restore root defaults.

        For test isolation: call between tests that mutate logger state
        via `set_sinks` / `set_min_severity` / `set_resource` or via the
        module-level `configure(...)`. After `reset()`, a subsequent
        `Logger.get(name)` creates a fresh node with no inherited
        overrides.

        SAFETY: this is a coarse instrument — it invalidates **all**
        logger handles still held elsewhere. Production code MUST NOT
        call this; it is reserved for test fixtures and the binding's
        own teardown.
        """
        with _registry_lock:
            _loggers.clear()

    # ─── Severity methods ────────────────────────────────────────────────────

    def trace(self, body: Value, *, attributes: Mapping[str, Value] | None = None) -> None:
        self._emit(int(Severity.TRACE), body, attributes)

    def debug(self, body: Value, *, attributes: Mapping[str, Value] | None = None) -> None:
        self._emit(int(Severity.DEBUG), body, attributes)

    def info(self, body: Value, *, attributes: Mapping[str, Value] | None = None) -> None:
        self._emit(int(Severity.INFO), body, attributes)

    def warn(self, body: Value, *, attributes: Mapping[str, Value] | None = None) -> None:
        self._emit(int(Severity.WARN), body, attributes)

    def error(self, body: Value, *, attributes: Mapping[str, Value] | None = None) -> None:
        self._emit(int(Severity.ERROR), body, attributes)

    def fatal(self, body: Value, *, attributes: Mapping[str, Value] | None = None) -> None:
        self._emit(int(Severity.FATAL), body, attributes)

    def log(
        self,
        severity_number: int,
        body: Value,
        *,
        attributes: Mapping[str, Value] | None = None,
    ) -> None:
        """Generic emit with explicit severity_number (1-24). For intermediate levels."""
        self._emit(severity_number, body, attributes)

    def exception(
        self,
        err: BaseException,
        *,
        body: Value | None = None,
        attributes: Mapping[str, Value] | None = None,
    ) -> None:
        """Log an exception with OTel semconv-compatible attributes.

        Adds `exception.type`, `exception.message`, `exception.stacktrace` to
        attributes (spec §3.2 contract).
        """
        exc_attrs: dict[str, Value] = {
            "exception.type": type(err).__qualname__,
            "exception.message": str(err),
            "exception.stacktrace": "".join(
                traceback.format_exception(type(err), err, err.__traceback__)
            ),
        }
        if attributes is not None:
            exc_attrs.update(attributes)
        final_body: Value = body if body is not None else str(err)
        self._emit(int(Severity.ERROR), final_body, exc_attrs)

    # ─── Scoped overrides (§6 spec) ─────────────────────────────────────────

    def with_sinks(self, sinks: list[Sink]) -> Logger:
        """Return a non-cached child logger with replaced sinks (§6.1)."""
        child = self._make_detached_child()
        child._sinks = list(sinks)
        child._sinks_explicit = True
        return child

    def append_sinks(self, extra_sinks: list[Sink]) -> Logger:
        """Return a non-cached child with parent's sinks + extras."""
        child = self._make_detached_child()
        child._sinks = self.effective_sinks() + list(extra_sinks)
        child._sinks_explicit = True
        return child

    def without_sinks(self) -> Logger:
        """Return a non-cached child with an empty sinks list — emits are discarded."""
        child = self._make_detached_child()
        child._sinks = []
        child._sinks_explicit = True
        return child

    def scope_sinks(self, sinks: list[Sink]) -> _SinkScope:
        """Context manager — temporarily replace THIS logger's sinks.

        Unlike `with_sinks` (which creates a separate child), `scope_sinks`
        swaps sinks on `self` for the duration of the `with` block. Handy for
        tests against a globally-accessed logger.
        """
        return _SinkScope(self, sinks)

    def child(self, attributes: Mapping[str, Value]) -> Logger:
        """Return a non-cached child with pre-bound attributes (§3.3)."""
        new_logger = self._make_detached_child()
        new_logger._attributes = {**self._attributes, **attributes}
        return new_logger

    def _make_detached_child(self) -> Logger:
        """Create a new Logger outside the registry — inherits from self as its parent."""
        child = Logger.__new__(Logger)
        child._init_state(name=self._name, version=self._version, parent=self)
        child._attributes = dict(self._attributes)
        child._redaction_suffixes = self._redaction_suffixes
        child._redaction_explicit = self._redaction_explicit
        return child

    # ─── Subscriptions (§7.2, Phase 1 inactive) ─────────────────────────────

    def on_reconfigure(self, callback: Callable[[], None]) -> Subscription:
        """Subscribe to reconfigure events. Phase 1 — inactive + warning."""
        emit_inactive_subscription_warning(path=f"logger:{self._name}")
        return Subscription(
            path=f"logger:{self._name}",
            active=False,
            inactive_reason="Phase 1 logger does not support watch-based reconfigure",
        )

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def flush(self, timeout: float = 5.0) -> None:
        """Flush all effective sinks (best-effort; timeout per-sink).

        Phase 1: all built-in sinks (Console, File, InMemory) are synchronous,
        so ``timeout`` is accepted but **not enforced** — TimeoutError will
        not be raised by any built-in sink. Phase 2 (OTLPSink) MUST honour
        the deadline; refer to the spec ADR-0001 §7.1.
        """
        for sink in self.effective_sinks():
            try:
                sink.flush(timeout)
            except Exception:
                # Flush failures must not break shutdown — swallow.
                continue

    def close(self) -> None:
        """Close all sinks — idempotent."""
        for sink in self.effective_sinks():
            try:
                sink.close()
            except Exception:
                continue

    # ─── Internal emit ───────────────────────────────────────────────────────

    def _emit(
        self,
        severity_number: int,
        body: Value,
        attributes: Mapping[str, Value] | None,
    ) -> None:
        """Build LogRecord + fan-out to sinks."""
        # Early drop by severity (the §7.1 supports_severity hint applies later
        # per-sink, but logger-level drop saves building a record for
        # non-emitting severities).
        if severity_number < self.effective_min_severity():
            return

        # Merge attributes: child bound < call-site. Context auto-injection.
        record_attrs: dict[str, Value] = {}
        record_attrs.update(self._attributes)
        if attributes is not None:
            record_attrs.update(attributes)

        # Context propagation (§3.4).
        baggage_attrs = get_baggage_attributes()
        for key, value in baggage_attrs.items():
            record_attrs.setdefault(key, value)

        # Redaction (§10.1-10.2).
        record_attrs = redact_attributes(record_attrs, self.effective_secret_suffixes())

        # Active trace/span context (§3.4). When the cross-binding parity
        # flag (§3.4.2) is False, skip the ambient lookup — wire output
        # then matches `auto_inject_trace_context = false` bindings.
        if _auto_inject_trace_context:
            trace_id, span_id, trace_flags = get_active_trace_context()
        else:
            trace_id, span_id, trace_flags = None, None, 0

        record = LogRecord(
            time_unix_nano=time.time_ns(),
            severity_number=severity_number,
            severity_text=severity_text_for(severity_number),
            body=body,
            attributes=record_attrs,
            instrumentation_scope=self._scope,
            resource=self.effective_resource(),
            trace_id=trace_id,
            span_id=span_id,
            trace_flags=trace_flags,
        )

        for sink in self.effective_sinks():
            try:
                sink.emit(record)
            except Exception:
                # Sink failure is isolated — the remaining sinks keep emitting.
                # Phase 2+: report on the dagstack.logger.internal channel.
                continue


class _SinkScope:
    """Context manager returned by `Logger.scope_sinks(...)`."""

    __slots__ = ("_logger", "_new_sinks", "_prev_explicit", "_prev_sinks")

    def __init__(self, logger: Logger, new_sinks: list[Sink]) -> None:
        self._logger = logger
        self._new_sinks = list(new_sinks)
        self._prev_sinks: list[Sink] = []
        self._prev_explicit = False

    def __enter__(self) -> Logger:
        with self._logger._lock:
            self._prev_sinks = self._logger._sinks
            self._prev_explicit = self._logger._sinks_explicit
            self._logger._sinks = self._new_sinks
            self._logger._sinks_explicit = True
        return self._logger

    def __exit__(self, *_exc: object) -> None:
        with self._logger._lock:
            self._logger._sinks = self._prev_sinks
            self._logger._sinks_explicit = self._prev_explicit


def _parent_name_of(name: str) -> str:
    """`dagstack.rag.retriever` → `dagstack.rag`; root → root."""
    if "." not in name:
        return _root_name
    return name.rsplit(".", 1)[0]


def _reset_registry_for_tests() -> None:
    """Clear cached loggers — test-only helper.

    Tests mutate global state (sinks, severity); the reset ensures isolation
    between tests. NOT a public API.
    """
    global _auto_inject_trace_context
    with _registry_lock:
        _loggers.clear()
    _auto_inject_trace_context = True
