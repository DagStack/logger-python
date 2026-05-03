"""Severity numbering + canonical text mapping.

Per spec ADR-0001 §2: OTel severity numbering 1-24 via `severity_number`.
`severity_text` MUST be exactly one of the 6 canonical OTel-recommended strings
(`TRACE`/`DEBUG`/`INFO`/`WARN`/`ERROR`/`FATAL`). Numeric granularity is carried
in `severity_number`; backends filter by `severity_text` exact match.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class Severity(IntEnum):
    """Primary severity levels matching the public API methods.

    Values = baseline per severity bucket (1=TRACE, 5=DEBUG, 9=INFO, ...).
    Intermediate levels (TRACE2/TRACE3/TRACE4, etc.) are emitted via
    `Logger.log(severity_number, ...)` with a numeric value.
    """

    TRACE = 1
    DEBUG = 5
    INFO = 9
    WARN = 13
    ERROR = 17
    FATAL = 21


# Canonical 6-value string set — OTel-recommended (spec §2).
# Backends filter by exact match — do not add "TRACE2" / "INFO3" / etc.
SEVERITY_TEXT_TRACE: Final[str] = "TRACE"
SEVERITY_TEXT_DEBUG: Final[str] = "DEBUG"
SEVERITY_TEXT_INFO: Final[str] = "INFO"
SEVERITY_TEXT_WARN: Final[str] = "WARN"
SEVERITY_TEXT_ERROR: Final[str] = "ERROR"
SEVERITY_TEXT_FATAL: Final[str] = "FATAL"

CANONICAL_SEVERITY_TEXTS: Final[tuple[str, ...]] = (
    SEVERITY_TEXT_TRACE,
    SEVERITY_TEXT_DEBUG,
    SEVERITY_TEXT_INFO,
    SEVERITY_TEXT_WARN,
    SEVERITY_TEXT_ERROR,
    SEVERITY_TEXT_FATAL,
)


# Bucket boundaries — inclusive ranges per OTel semconv:
#   1-4   → TRACE
#   5-8   → DEBUG
#   9-12  → INFO
#   13-16 → WARN
#   17-20 → ERROR
#   21-24 → FATAL
_BUCKET_BOUNDARIES: Final[tuple[tuple[int, int, str], ...]] = (
    (1, 4, SEVERITY_TEXT_TRACE),
    (5, 8, SEVERITY_TEXT_DEBUG),
    (9, 12, SEVERITY_TEXT_INFO),
    (13, 16, SEVERITY_TEXT_WARN),
    (17, 20, SEVERITY_TEXT_ERROR),
    (21, 24, SEVERITY_TEXT_FATAL),
)

_MIN_SEVERITY_NUMBER: Final[int] = 1
_MAX_SEVERITY_NUMBER: Final[int] = 24


def severity_text_for(severity_number: int) -> str:
    """Map severity_number (1-24) → canonical severity_text (one of 6).

    Raises:
        ValueError: if severity_number is outside [1, 24].
    """
    if severity_number < _MIN_SEVERITY_NUMBER or severity_number > _MAX_SEVERITY_NUMBER:
        raise ValueError(
            f"severity_number must be in [{_MIN_SEVERITY_NUMBER}, {_MAX_SEVERITY_NUMBER}], "
            f"got {severity_number}"
        )
    for low, high, text in _BUCKET_BOUNDARIES:
        if low <= severity_number <= high:
            return text
    raise AssertionError(f"unreachable: bucket not found for {severity_number}")  # pragma: no cover


def is_valid_severity_number(severity_number: int) -> bool:
    """Return True if severity_number is in [1, 24]."""
    return _MIN_SEVERITY_NUMBER <= severity_number <= _MAX_SEVERITY_NUMBER


def is_canonical_severity_text(text: str) -> bool:
    """Return True if text is one of the 6 canonical OTel-recommended strings."""
    return text in CANONICAL_SEVERITY_TEXTS
