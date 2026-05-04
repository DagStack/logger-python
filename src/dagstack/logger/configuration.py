"""Bootstrap configuration for Logger — produced by the application from the config-spec section.

Per spec §9.1-§9.2: the logger reads its configuration via the
`dagstack-config` bindings. However, logger-python itself **does not depend**
on config-python — the application extracts the `logging:` section from
its Config, dumps it to a dict (via Pydantic) and passes it into the
module-level `configure(**section)` function.

This avoids circular / cross-package dependencies and preserves the
independence of the two libraries.

Usage (in app bootstrap):

    from dagstack.config import Config
    from dagstack.logger import ConsoleSink, FileSink, configure

    config = Config.load("app-config.yaml")
    log_cfg = config.get("logging", default={})

    configure(
        root_level=log_cfg.get("level", "INFO"),
        sinks=_build_sinks(log_cfg.get("sinks", [])),
        per_logger_levels=log_cfg.get("loggers", {}),
        resource_attributes=log_cfg.get("resource", {}),
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dagstack.logger.logger import (
    INTERNAL_LOGGER_NAME,
    Logger,
    _set_auto_inject_trace_context,
)
from dagstack.logger.records import Resource
from dagstack.logger.redaction import (
    RedactionConfig,  # noqa: TC001  # used at runtime via .validate() / .build_effective_suffixes()
)
from dagstack.logger.severity import (
    Severity,
    is_valid_severity_number,
)

if TYPE_CHECKING:
    from dagstack.logger.records import Value
    from dagstack.logger.sinks import Sink

_SEVERITY_NAME_TO_NUMBER: dict[str, int] = {
    "TRACE": int(Severity.TRACE),
    "DEBUG": int(Severity.DEBUG),
    "INFO": int(Severity.INFO),
    "WARN": int(Severity.WARN),
    "WARNING": int(Severity.WARN),
    "ERROR": int(Severity.ERROR),
    "FATAL": int(Severity.FATAL),
    "CRITICAL": int(Severity.FATAL),
}


def configure(
    *,
    root_level: str | int = "INFO",
    sinks: list[Sink] | None = None,
    per_logger_levels: dict[str, str | int] | None = None,
    resource_attributes: dict[str, Value] | None = None,
    redaction: RedactionConfig | None = None,
    auto_inject_trace_context: bool | None = None,
) -> None:
    """Bootstrap global logger state.

    Atomicity invariant: validation runs before any registry mutation. A
    malformed ``configure(...)`` call (e.g., bad severity name, invalid
    redaction suffix) raises before the apply phase, leaving the registry
    untouched.

    Args:
        root_level: default severity threshold for the root logger (a string
            name like "INFO" or numeric 9). Inherited by children without
            their own level.
        sinks: list of Sink instances attached to root. Inherited by children
            without their own sinks.
        per_logger_levels: map `logger_name → level` — override min_severity
            for specific loggers (e.g., `{"httpx": "WARN"}` silences a
            verbose HTTP client in dev).
        resource_attributes: process/service-level attrs for Resource;
            injected into every LogRecord.
        redaction: Phase 1 redaction policy per spec §10.4. Validated
            synchronously — invalid suffixes (empty / whitespace /
            non-lowercase-ASCII) raise ``ValueError``. Default behaviour
            (omitted) keeps the 6-element :data:`DEFAULT_SECRET_SUFFIXES`
            baseline.
        auto_inject_trace_context: cross-binding parity flag per spec
            ADR-0001 v1.2 §3.4.2 (M2). When True (the Python default —
            idiomatic, matches OTel's ``opentelemetry.context``
            convention), non-``*Ctx`` severity methods read ``trace_id`` /
            ``span_id`` / ``trace_flags`` from the active OTel context.
            When False, the ambient lookup is skipped — useful for
            cross-binding parity tests against ``go.dagstack.dev/logger``'s
            default explicit-ctx mode. Pass ``None`` (the default) to
            preserve the current value.
    """
    if redaction is not None:
        redaction.validate()

    root = Logger.get("")  # root logger (name = "")
    root.set_min_severity(_resolve_level(root_level))
    root.set_sinks(list(sinks) if sinks is not None else [])

    if resource_attributes:
        root.set_resource(Resource(attributes=dict(resource_attributes)))
    else:
        root.set_resource(None)

    if per_logger_levels:
        for name, level in per_logger_levels.items():
            logger = Logger.get(name)
            logger.set_min_severity(_resolve_level(level))

    if redaction is not None:
        effective = redaction.build_effective_suffixes()
        root.set_redaction_suffixes(effective)
        if redaction.replace_defaults and not redaction.extra_suffixes:
            Logger.get(INTERNAL_LOGGER_NAME).warn(
                "redaction disabled by configure: replace_defaults=True with "
                "empty extra_suffixes; all suffix-based masking is disabled "
                "(spec §10.4 disable-all warning)"
            )

    if auto_inject_trace_context is not None:
        _set_auto_inject_trace_context(auto_inject_trace_context)


def _resolve_level(level: str | int) -> int:
    """Convert a level name ("INFO") or numeric (9) into a severity_number (1-24)."""
    if isinstance(level, int):
        if not is_valid_severity_number(level):
            raise ValueError(f"severity_number {level} not in [1, 24]")
        return level
    upper = level.upper()
    if upper in _SEVERITY_NAME_TO_NUMBER:
        return _SEVERITY_NAME_TO_NUMBER[upper]
    raise ValueError(
        f"unknown severity name {level!r}; expected one of {sorted(_SEVERITY_NAME_TO_NUMBER)}"
    )
