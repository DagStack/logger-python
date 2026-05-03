"""Unit tests for the canonical JSON serializer (RFC 8785 subset).

A sanity duplicate of config-python/test_canonical_json.py — to guarantee
byte-identical output between the config-python and logger-python canonical
JSON implementations (until they are merged into a Phase 2 dagstack-common
package).
"""

from __future__ import annotations

import pytest

from dagstack.logger.canonical_json import canonical_json_dumpb, canonical_json_dumps


class TestPrimitives:
    def test_null(self) -> None:
        assert canonical_json_dumps(None) == "null"

    def test_booleans(self) -> None:
        assert canonical_json_dumps(True) == "true"
        assert canonical_json_dumps(False) == "false"

    def test_strings(self) -> None:
        assert canonical_json_dumps("") == '""'
        assert canonical_json_dumps("hello") == '"hello"'
        assert canonical_json_dumps("привет") == '"привет"'

    def test_bytes_utf8(self) -> None:
        assert canonical_json_dumpb("hello") == b'"hello"'
        assert canonical_json_dumpb("привет") == '"привет"'.encode()


class TestNumbers:
    def test_int(self) -> None:
        assert canonical_json_dumps(42) == "42"
        assert canonical_json_dumps(-7) == "-7"
        assert canonical_json_dumps(0) == "0"

    def test_float(self) -> None:
        assert canonical_json_dumps(1.5) == "1.5"
        assert canonical_json_dumps(0.1) == "0.1"

    def test_negative_zero_normalized(self) -> None:
        # RFC 8785 §3.2.2.3: -0.0 → "0.0".
        assert canonical_json_dumps(-0.0) == "0.0"

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            canonical_json_dumps(float("nan"))

    def test_infinity_rejected(self) -> None:
        with pytest.raises(ValueError, match="Infinity"):
            canonical_json_dumps(float("inf"))
        with pytest.raises(ValueError, match="Infinity"):
            canonical_json_dumps(float("-inf"))


class TestContainers:
    def test_empty_array(self) -> None:
        assert canonical_json_dumps([]) == "[]"

    def test_empty_object(self) -> None:
        assert canonical_json_dumps({}) == "{}"

    def test_keys_sorted(self) -> None:
        assert canonical_json_dumps({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_keys_sorted_recursively(self) -> None:
        obj = {"outer": {"z": 1, "a": 2}}
        assert canonical_json_dumps(obj) == '{"outer":{"a":2,"z":1}}'

    def test_array_preserves_order(self) -> None:
        assert canonical_json_dumps([3, 1, 2]) == "[3,1,2]"

    def test_unicode_keys_sort_by_codepoint(self) -> None:
        # ASCII < Cyrillic in Unicode code points.
        result = canonical_json_dumps({"я": 1, "a": 2})
        assert result == '{"a":2,"я":1}'


class TestSeparators:
    def test_no_whitespace(self) -> None:
        result = canonical_json_dumps({"a": [1, 2, {"b": "c"}]})
        assert " " not in result
        assert "\n" not in result


class TestValidation:
    def test_non_string_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-string"):
            canonical_json_dumps({1: "v"})

    def test_nested_non_string_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-string"):
            canonical_json_dumps({"ok": {1: "bad"}})


class TestDeterminism:
    def test_permuted_input_same_output(self) -> None:
        a = {"x": 1, "y": 2, "z": 3}
        b = {"z": 3, "x": 1, "y": 2}
        assert canonical_json_dumps(a) == canonical_json_dumps(b)


class TestUTF16KeySort:
    """S3 regression: RFC 8785 §3.2.3 — keys sort by UTF-16 code units, not
    by Python's UTF-32 code-point natural order. On non-BMP characters
    (≥U+10000) the orders diverge.
    """

    def test_surrogate_pair_keys_match_rfc_8785(self) -> None:
        # 💎 is U+1F48E (UTF-16 surrogates D83D DC8E).
        # 🍕 is U+1F355 (UTF-16 surrogates D83C DF55).
        # In UTF-16 code-unit order: 🍕 (D83C ...) < 💎 (D83D ...).
        # Canonical wire matches logger-typescript and logger-go.
        got = canonical_json_dumps(
            {"aa": 1, "💎": 2, "ab": 3, "äz": 4, "🍕": 5},
        )
        assert got == '{"aa":1,"ab":3,"äz":4,"🍕":5,"💎":2}'

    def test_supplementary_plane_vs_bmp(self) -> None:
        # Non-BMP > BMP in both UTF-16 and code-point order, but the test
        # also pins the deterministic position relative to BMP characters
        # like 'z'.
        got = canonical_json_dumps({"z": 1, "🍕": 2})
        assert got == '{"z":1,"🍕":2}'
