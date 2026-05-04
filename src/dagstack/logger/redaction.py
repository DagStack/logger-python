"""Attribute redaction — mask secret-like values per spec §10.

Default patterns — suffix matching on keys (case-insensitive):
    `*_key`, `*_secret`, `*_token`, `*_password`, `*_passphrase`, `*_credentials`

Per spec §10.1: mask rendering — literal `"***"`. The raw value **never**
crosses the logger API boundary in an attribute value flagged as secret.
For nested attributes redaction is recursive (§10.2).

The body (LogRecord.body) is **not** redacted — developers must format the
body without secrets (§10.1 rationale).

Phase 1 public API for tuning the suffix list lives in :class:`RedactionConfig`
(spec ADR-0001 v1.1 §10.4) — applications register additional suffixes via
``configure(redaction=RedactionConfig(...))`` without waiting for the Phase 2
processor pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dagstack.logger.records import Value


# Default secret patterns per spec ADR-0001 §10.1 / §10.4 v1.1. Opinionated
# 6-element subset of `config-spec/_meta/secret_patterns.yaml`. The list is
# fixed at v1.1 to preserve API stability; richer matchers ship via the Phase 2
# processor pipeline (§10.3).
DEFAULT_SECRET_SUFFIXES: frozenset[str] = frozenset(
    {
        "_key",
        "_secret",
        "_token",
        "_password",
        "_passphrase",
        "_credentials",
    }
)

REDACTED_PLACEHOLDER: str = "***"


_LOWERCASE_ASCII = re.compile(r"^[\x00-\x7f]*$")


@dataclass(frozen=True, slots=True)
class RedactionConfig:
    """Phase 1 redaction policy per spec §10.4.

    Applications register extra suffixes via
    ``configure(redaction=RedactionConfig(extra_suffixes=("_apikey",)))``.

    Default behaviour (omitted or default-constructed) keeps the 6-element
    :data:`DEFAULT_SECRET_SUFFIXES` baseline.

    Attributes:
        extra_suffixes: Additional secret suffixes registered by the
            application. Each entry MUST be lowercase ASCII, contain no
            whitespace, and be non-empty (validated at configure time).
        replace_defaults: When ``True``, swaps the base set for
            ``extra_suffixes`` instead of unioning. Combined with an empty
            ``extra_suffixes``, all suffix-based redaction is disabled —
            the binding emits a WARN diagnostic on
            ``dagstack.logger.internal`` in that case (spec §10.4
            disable-all warning).
    """

    extra_suffixes: tuple[str, ...] = ()
    replace_defaults: bool = False

    def validate(self) -> None:
        """Reject malformed entries per spec §10.4. Raises ValueError on the first violation."""
        for i, s in enumerate(self.extra_suffixes):
            if s == "":
                msg = f"redaction.extra_suffixes[{i}] contains an empty string"
                raise ValueError(msg)
            if any(ch.isspace() for ch in s):
                msg = f"redaction.extra_suffixes[{i}] contains whitespace: {s!r}"
                raise ValueError(msg)
            if s.lower() != s or not _LOWERCASE_ASCII.match(s):
                msg = f"redaction.extra_suffixes[{i}] must be lowercase ASCII: {s!r}"
                raise ValueError(msg)

    def build_effective_suffixes(self) -> frozenset[str]:
        """Build the post-configure suffix set applied during emit.

        When ``replace_defaults`` is False, returns the union of
        :data:`DEFAULT_SECRET_SUFFIXES` and ``extra_suffixes`` (lowercased).
        When ``replace_defaults`` is True, returns only ``extra_suffixes`` —
        an empty frozenset signals "no suffix-based masking" (disable-all).

        Does NOT validate; pair with :meth:`validate` when the input is
        untrusted, or use the ``configure(redaction=...)`` surface which
        validates synchronously.
        """
        out: set[str] = set()
        if not self.replace_defaults:
            out.update(DEFAULT_SECRET_SUFFIXES)
        for s in self.extra_suffixes:
            out.add(s.lower())
        return frozenset(out)


# Sentinel preserved for the disable-all case: distinguishable from None
# (= "no override / inherit") at the resolver. We use frozenset() (an
# explicit non-None empty set) to mean "explicit empty / disable-all"
# alongside the redaction_explicit flag on Logger.
_EMPTY_SUFFIXES: frozenset[str] = frozenset()


def is_secret_key(key: str, suffixes: frozenset[str] = DEFAULT_SECRET_SUFFIXES) -> bool:
    """Return True if key matches any of the suffix patterns (case-insensitive)."""
    lowered = key.lower()
    return any(lowered.endswith(s) for s in suffixes)


def _redact_value(
    value: Value,
    suffixes: frozenset[str],
) -> Value:
    """Recurse into containers without inspecting the carrier key (private)."""
    if isinstance(value, dict):
        return redact_attributes(value, suffixes)
    if isinstance(value, list):
        return [_redact_value(item, suffixes) for item in value]
    return value


def redact_attributes(
    attrs: dict[str, Value],
    suffixes: frozenset[str] = DEFAULT_SECRET_SUFFIXES,
) -> dict[str, Value]:
    """Return a new dict with masked secret values (recursive for nested containers).

    Args:
        attrs: original attributes dict.
        suffixes: suffix patterns for secret-key detection.

    Returns:
        A copy with `"***"` on keys matching the secrets pattern.
        Non-secret values are passed through; nested dicts AND nested
        lists-of-dicts (e.g. event arrays in structured payloads) are
        recursed so that a `password` key buried inside `events[0].body`
        still gets masked.
    """
    result: dict[str, Value] = {}
    for key, value in attrs.items():
        if is_secret_key(key, suffixes):
            result[key] = REDACTED_PLACEHOLDER
        else:
            result[key] = _redact_value(value, suffixes)
    return result
