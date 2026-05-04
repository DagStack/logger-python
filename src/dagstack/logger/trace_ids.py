"""W3C Trace Context encoding helpers.

Per spec ADR-0001 §1: trace_id = 16 bytes, span_id = 8 bytes (OTel internal
model / OTLP protobuf wire). For JSON-lines / OTel JSON wire — lowercase hex
strings (32 / 16 hex chars respectively, zero-padded).

Helpers for encoding/decoding between bytes and hex-string forms.
"""

from __future__ import annotations

from typing import Final

_TRACE_ID_BYTES: Final[int] = 16
_SPAN_ID_BYTES: Final[int] = 8
_TRACE_ID_HEX_CHARS: Final[int] = _TRACE_ID_BYTES * 2
_SPAN_ID_HEX_CHARS: Final[int] = _SPAN_ID_BYTES * 2


def trace_id_to_hex(trace_id: bytes | None) -> str | None:
    """Encode a 16-byte trace_id → 32-char lowercase hex string, or None.

    Raises:
        ValueError: if `trace_id` is not None and not exactly 16 bytes.
    """
    if trace_id is None:
        return None
    if len(trace_id) != _TRACE_ID_BYTES:
        raise ValueError(f"trace_id must be {_TRACE_ID_BYTES} bytes, got {len(trace_id)}")
    return trace_id.hex()


def span_id_to_hex(span_id: bytes | None) -> str | None:
    """Encode an 8-byte span_id → 16-char lowercase hex string, or None.

    Raises:
        ValueError: if `span_id` is not None and not exactly 8 bytes.
    """
    if span_id is None:
        return None
    if len(span_id) != _SPAN_ID_BYTES:
        raise ValueError(f"span_id must be {_SPAN_ID_BYTES} bytes, got {len(span_id)}")
    return span_id.hex()


def hex_to_trace_id(hex_str: str | None) -> bytes | None:
    """Decode a 32-char hex string → 16-byte trace_id, or None.

    Raises:
        ValueError: if `hex_str` is not None and not 32 chars, or contains non-hex.
    """
    if hex_str is None:
        return None
    if len(hex_str) != _TRACE_ID_HEX_CHARS:
        raise ValueError(f"trace_id hex must be {_TRACE_ID_HEX_CHARS} chars, got {len(hex_str)}")
    try:
        return bytes.fromhex(hex_str)
    except ValueError as err:
        raise ValueError(f"trace_id hex {hex_str!r} contains invalid chars") from err


def hex_to_span_id(hex_str: str | None) -> bytes | None:
    """Decode a 16-char hex string → 8-byte span_id, or None.

    Raises:
        ValueError: if `hex_str` is not None and not 16 chars, or contains non-hex.
    """
    if hex_str is None:
        return None
    if len(hex_str) != _SPAN_ID_HEX_CHARS:
        raise ValueError(f"span_id hex must be {_SPAN_ID_HEX_CHARS} chars, got {len(hex_str)}")
    try:
        return bytes.fromhex(hex_str)
    except ValueError as err:
        raise ValueError(f"span_id hex {hex_str!r} contains invalid chars") from err
