"""Sink implementations for dagstack-logger.

Public re-exports:
    from dagstack.logger.sinks import Sink, ConsoleSink, FileSink, InMemorySink

See spec ADR-0001 §7 (sink contract + adapter roadmap). Phase 1 ships three
sinks: console (JSON / pretty dev-mode), file (native rotation), in-memory
(ring buffer, tests).
"""

from dagstack.logger.sinks.base import Sink
from dagstack.logger.sinks.console import ConsoleSink
from dagstack.logger.sinks.file import FileSink
from dagstack.logger.sinks.in_memory import InMemorySink

__all__ = [
    "ConsoleSink",
    "FileSink",
    "InMemorySink",
    "Sink",
]
