"""Unit tests for the trace_ids encoding helpers."""

from __future__ import annotations

import pytest

from dagstack.logger.trace_ids import (
    hex_to_span_id,
    hex_to_trace_id,
    span_id_to_hex,
    trace_id_to_hex,
)


class TestTraceIdEncoding:
    def test_bytes_to_hex_known_value(self) -> None:
        # 16 bytes — 32 hex chars (lowercase).
        tid = bytes.fromhex("0af7651916cd43dd8448eb211c80319c")
        assert trace_id_to_hex(tid) == "0af7651916cd43dd8448eb211c80319c"

    def test_all_zeros(self) -> None:
        assert trace_id_to_hex(b"\x00" * 16) == "00000000000000000000000000000000"

    def test_none_returns_none(self) -> None:
        assert trace_id_to_hex(None) is None

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="16 bytes"):
            trace_id_to_hex(b"\x00" * 8)  # span_id size, not trace_id

    def test_roundtrip(self) -> None:
        original = bytes(range(16))
        hex_form = trace_id_to_hex(original)
        assert hex_form is not None
        assert hex_to_trace_id(hex_form) == original


class TestSpanIdEncoding:
    def test_bytes_to_hex_known_value(self) -> None:
        sid = bytes.fromhex("b7ad6b7169203331")
        assert span_id_to_hex(sid) == "b7ad6b7169203331"

    def test_none_returns_none(self) -> None:
        assert span_id_to_hex(None) is None

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="8 bytes"):
            span_id_to_hex(b"\x00" * 16)

    def test_roundtrip(self) -> None:
        original = bytes(range(8))
        hex_form = span_id_to_hex(original)
        assert hex_form is not None
        assert hex_to_span_id(hex_form) == original


class TestHexToTraceId:
    def test_valid_hex(self) -> None:
        result = hex_to_trace_id("0af7651916cd43dd8448eb211c80319c")
        assert result == bytes.fromhex("0af7651916cd43dd8448eb211c80319c")

    def test_none_passes_through(self) -> None:
        assert hex_to_trace_id(None) is None

    def test_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="32 chars"):
            hex_to_trace_id("deadbeef")

    def test_invalid_chars(self) -> None:
        bad = "g" * 32
        with pytest.raises(ValueError, match="invalid chars"):
            hex_to_trace_id(bad)


class TestHexToSpanId:
    def test_valid_hex(self) -> None:
        assert hex_to_span_id("0123456789abcdef") == bytes.fromhex("0123456789abcdef")

    def test_none_passes_through(self) -> None:
        assert hex_to_span_id(None) is None

    def test_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="16 chars"):
            hex_to_span_id("deadbeef")

    def test_invalid_chars(self) -> None:
        with pytest.raises(ValueError, match="invalid chars"):
            hex_to_span_id("z" * 16)
