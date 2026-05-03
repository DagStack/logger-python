"""Canonical JSON serializer — RFC 8785 subset (config-spec §9.1.1).

Duplicates the logic from `dagstack-config/canonical_json.py` to avoid a
circular dependency in Phase 1 (config-python is not published to Nexus).
In Phase 2 this can be extracted into a shared `dagstack-common` package —
for now the implementations live side-by-side, and a cross-binding
conformance test guarantees identical output.
"""

from __future__ import annotations

import json
import math
from typing import Any


def canonical_json_dumps(obj: Any) -> str:
    """Serialize obj into a canonical JSON string.

    Rules:
    - Sorted object keys (lexicographic UTF-16 code-unit order per RFC 8785
      §3.2.3 — matches the cross-binding canonical sort applied by
      `@dagstack/logger` (TypeScript native `Object.keys().sort()`) and
      `go.dagstack.dev/logger`).
    - No whitespace except inside strings.
    - Integers without a decimal point (`1`); floats use shortest round-trip.
    - `-0.0` → `0.0` (RFC 8785 §3.2.2.3).
    - NaN / ±Infinity → ValueError.
    - Non-string dict keys → ValueError.
    - UTF-8 ensure_ascii=False (Unicode characters pass through).

    Raises:
        ValueError: NaN/Infinity floats, non-string keys.
    """
    normalized = _normalize(obj)
    # `sort_keys=False` is intentional: `_normalize` already inserted dict
    # entries in UTF-16 code-unit sorted order. `json.dumps`'s built-in
    # `sort_keys=True` would re-sort using Python's UTF-32 code-point
    # comparison, which diverges from RFC 8785 on surrogate pairs (S3).
    return json.dumps(
        normalized,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    )


def canonical_json_dumpb(obj: Any) -> bytes:
    """Serialize obj into canonical JSON UTF-8 bytes."""
    return canonical_json_dumps(obj).encode("utf-8")


def _utf16_sort_key(s: str) -> bytes:
    """RFC 8785 §3.2.3 sort key: encode the string as UTF-16-BE bytes.

    Bytewise tuple comparison on UTF-16-BE bytes is equivalent to
    lexicographic comparison of the underlying UTF-16 code-unit sequence,
    which matches both the RFC and the native JavaScript / Go behaviour.
    """
    return s.encode("utf-16-be")


def _normalize(obj: Any) -> Any:
    """Recursively normalize edge cases before json.dumps.

    Dict keys are inserted in UTF-16 code-unit sorted order (per
    `_utf16_sort_key`), so the downstream `json.dumps` with
    `sort_keys=False` preserves the canonical sort.
    """
    if isinstance(obj, dict):
        items = []
        for key, value in obj.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string dict key not allowed in canonical JSON: {key!r}")
            items.append((key, value))
        items.sort(key=lambda kv: _utf16_sort_key(kv[0]))
        result: dict[str, Any] = {}
        for key, value in items:
            result[key] = _normalize(value)
        return result
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"NaN / Infinity not allowed in canonical JSON: {obj!r}")
        if obj == 0.0:
            return 0.0
        return obj
    return obj
