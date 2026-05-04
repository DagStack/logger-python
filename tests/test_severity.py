"""Unit tests for the severity module."""

from __future__ import annotations

import pytest

from dagstack.logger.severity import (
    CANONICAL_SEVERITY_TEXTS,
    Severity,
    is_canonical_severity_text,
    is_valid_severity_number,
    severity_text_for,
)


class TestSeverityEnum:
    def test_baseline_values(self) -> None:
        # Spec §2: baseline per bucket — 1, 5, 9, 13, 17, 21.
        # The int(...) cast works around mypy comparison-overlap for Literal types.
        assert int(Severity.TRACE) == 1
        assert int(Severity.DEBUG) == 5
        assert int(Severity.INFO) == 9
        assert int(Severity.WARN) == 13
        assert int(Severity.ERROR) == 17
        assert int(Severity.FATAL) == 21

    def test_is_int(self) -> None:
        # IntEnum lets severity be used as int in comparisons.
        assert int(Severity.INFO) == 9
        assert Severity.ERROR > Severity.WARN


class TestCanonicalTexts:
    def test_exact_six_values(self) -> None:
        # Spec §2: exactly 6 canonical strings, no more.
        assert len(CANONICAL_SEVERITY_TEXTS) == 6
        assert set(CANONICAL_SEVERITY_TEXTS) == {
            "TRACE",
            "DEBUG",
            "INFO",
            "WARN",
            "ERROR",
            "FATAL",
        }

    def test_is_canonical_truthy(self) -> None:
        for text in CANONICAL_SEVERITY_TEXTS:
            assert is_canonical_severity_text(text)

    @pytest.mark.parametrize(
        "bad_text",
        ["trace", "info2", "Warning", "FATAL2", "CRITICAL", ""],
    )
    def test_non_canonical_falsy(self, bad_text: str) -> None:
        assert not is_canonical_severity_text(bad_text)


class TestSeverityTextFor:
    @pytest.mark.parametrize(
        ("number", "expected"),
        [
            (1, "TRACE"),
            (2, "TRACE"),
            (4, "TRACE"),
            (5, "DEBUG"),
            (8, "DEBUG"),
            (9, "INFO"),
            (12, "INFO"),
            (13, "WARN"),
            (16, "WARN"),
            (17, "ERROR"),
            (20, "ERROR"),
            (21, "FATAL"),
            (24, "FATAL"),
        ],
    )
    def test_bucket_boundaries(self, number: int, expected: str) -> None:
        assert severity_text_for(number) == expected

    def test_below_range_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[1, 24\]"):
            severity_text_for(0)

    def test_above_range_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[1, 24\]"):
            severity_text_for(25)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[1, 24\]"):
            severity_text_for(-1)


class TestIsValidSeverityNumber:
    @pytest.mark.parametrize("n", [1, 9, 24])
    def test_in_range(self, n: int) -> None:
        assert is_valid_severity_number(n)

    @pytest.mark.parametrize("n", [0, 25, -1])
    def test_out_of_range(self, n: int) -> None:
        assert not is_valid_severity_number(n)
