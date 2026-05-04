"""dagstack.logger — OTel-compatible structured logging.

Public API (Phase 1 — Phase D complete):

    from dagstack.logger import (
        Logger,
        LogRecord,
        Severity,
        Subscription,
        # Sinks
        Sink,
        ConsoleSink,
        FileSink,
        InMemorySink,
        # Configuration bootstrap
        configure,
    )

Usage:

    from dagstack.logger import Logger, ConsoleSink, configure

    configure(
        root_level="INFO",
        sinks=[ConsoleSink(mode="auto")],
        resource_attributes={"service.name": "order-service"},
    )
    logger = Logger.get("order_service.checkout", version="1.4.2")
    logger.info("query received", attributes={"user.id": 42})

    try:
        ...
    except Exception as err:
        logger.exception(err, attributes={"request.id": "req-abc"})

Scoped sink overrides:

    from dagstack.logger import InMemorySink

    test_sink = InMemorySink()
    with logger.scope_sinks([test_sink]):
        logger.info("captured only here")
    assert len(test_sink.records()) == 1
"""

from dagstack.logger._version import __version__
from dagstack.logger.configuration import configure
from dagstack.logger.logger import INTERNAL_LOGGER_NAME, Logger
from dagstack.logger.records import InstrumentationScope, LogRecord, Resource
from dagstack.logger.redaction import (
    DEFAULT_SECRET_SUFFIXES,
    REDACTED_PLACEHOLDER,
    RedactionConfig,
)
from dagstack.logger.severity import Severity
from dagstack.logger.sinks import ConsoleSink, FileSink, InMemorySink, Sink
from dagstack.logger.subscription import Subscription

__all__ = [
    "DEFAULT_SECRET_SUFFIXES",
    "INTERNAL_LOGGER_NAME",
    "REDACTED_PLACEHOLDER",
    "ConsoleSink",
    "FileSink",
    "InMemorySink",
    "InstrumentationScope",
    "LogRecord",
    "Logger",
    "RedactionConfig",
    "Resource",
    "Severity",
    "Sink",
    "Subscription",
    "__version__",
    "configure",
]
