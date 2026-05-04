"""Unit tests for attribute redaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from dagstack.logger.redaction import (
    DEFAULT_SECRET_SUFFIXES,
    REDACTED_PLACEHOLDER,
    is_secret_key,
    redact_attributes,
)

if TYPE_CHECKING:
    from dagstack.logger.records import Value


class TestIsSecretKey:
    def test_api_key_matches(self) -> None:
        assert is_secret_key("api_key")
        assert is_secret_key("OPENAI_API_KEY")

    def test_secret_suffix(self) -> None:
        assert is_secret_key("client_secret")
        assert is_secret_key("CLIENT_SECRET")

    def test_token_suffix(self) -> None:
        assert is_secret_key("access_token")

    def test_password_suffix(self) -> None:
        assert is_secret_key("db_password")

    def test_non_secret_keys(self) -> None:
        assert not is_secret_key("user.id")
        assert not is_secret_key("request.id")
        assert not is_secret_key("model")
        assert not is_secret_key("temperature")

    def test_custom_suffixes(self) -> None:
        assert is_secret_key("app_hash", suffixes=frozenset({"_hash"}))
        assert not is_secret_key("app_hash", suffixes=frozenset({"_secret"}))


def _attrs(value: Any) -> dict[str, Value]:
    """Cast Python dict → ConfigTree for mypy happiness in tests."""
    return cast("dict[str, Value]", value)


class TestRedactAttributes:
    def test_masks_secret_values(self) -> None:
        result = redact_attributes(_attrs({"api_key": "sk-123", "model": "gpt-4"}))
        assert result["api_key"] == REDACTED_PLACEHOLDER
        assert result["model"] == "gpt-4"

    def test_returns_copy_not_mutating(self) -> None:
        original = _attrs({"api_key": "sk-123"})
        result = redact_attributes(original)
        assert original == {"api_key": "sk-123"}
        assert result != original

    def test_recursive_nested_maps(self) -> None:
        # Suffix patterns — `_password` (prefix required), not standalone `password`.
        attrs = _attrs({"outer": "fine", "nested": {"db_password": "hunter2", "safe": "ok"}})
        result = redact_attributes(attrs)
        assert result["outer"] == "fine"
        nested = result["nested"]
        assert isinstance(nested, dict)
        assert nested["db_password"] == REDACTED_PLACEHOLDER
        assert nested["safe"] == "ok"

    def test_deep_nesting(self) -> None:
        attrs = _attrs({"a": {"b": {"c": {"my_token": "secret"}}}})
        result = redact_attributes(attrs)
        a = result["a"]
        assert isinstance(a, dict)
        b = a["b"]
        assert isinstance(b, dict)
        c = b["c"]
        assert isinstance(c, dict)
        assert c["my_token"] == REDACTED_PLACEHOLDER

    def test_default_suffixes_complete_set(self) -> None:
        expected = {"_key", "_secret", "_token", "_password", "_passphrase", "_credentials"}
        assert set(DEFAULT_SECRET_SUFFIXES) == expected

    def test_case_insensitive_matching(self) -> None:
        result = redact_attributes(_attrs({"API_KEY": "sk-123"}))
        assert result["API_KEY"] == REDACTED_PLACEHOLDER

    def test_recursive_into_lists_of_dicts(self) -> None:
        # S8 fix: secrets buried inside list items must be masked.
        attrs = _attrs(
            {
                "events": [
                    {"type": "login", "user_password": "hunter2"},
                    {"type": "exchange", "api_key": "sk-secret"},
                ]
            }
        )
        result = redact_attributes(attrs)
        events = result["events"]
        assert isinstance(events, list)
        assert events[0]["user_password"] == REDACTED_PLACEHOLDER
        assert events[0]["type"] == "login"
        assert events[1]["api_key"] == REDACTED_PLACEHOLDER

    def test_recursive_into_mixed_lists(self) -> None:
        # Lists of primitives stay untouched; dict items get redacted.
        attrs = _attrs(
            {
                "tags": ["alpha", "beta"],
                "samples": [{"my_token": "x"}, {"safe": "ok"}],
            }
        )
        result = redact_attributes(attrs)
        assert result["tags"] == ["alpha", "beta"]
        samples = result["samples"]
        assert isinstance(samples, list)
        assert samples[0]["my_token"] == REDACTED_PLACEHOLDER
        assert samples[1]["safe"] == "ok"


class TestRedactionConfig:
    def test_build_effective_additive(self) -> None:
        from dagstack.logger import DEFAULT_SECRET_SUFFIXES, RedactionConfig

        cfg = RedactionConfig(extra_suffixes=("_apikey", "_x_internal_token"))
        got = cfg.build_effective_suffixes()
        assert "_apikey" in got
        assert "_x_internal_token" in got
        assert DEFAULT_SECRET_SUFFIXES.issubset(got)

    def test_build_effective_replace(self) -> None:
        from dagstack.logger import RedactionConfig

        cfg = RedactionConfig(extra_suffixes=("_password",), replace_defaults=True)
        got = cfg.build_effective_suffixes()
        assert got == frozenset({"_password"})

    def test_build_effective_disable_all(self) -> None:
        from dagstack.logger import RedactionConfig

        cfg = RedactionConfig(replace_defaults=True)
        got = cfg.build_effective_suffixes()
        assert got == frozenset()

    def test_build_effective_lowercases_extras(self) -> None:
        from dagstack.logger import RedactionConfig

        cfg = RedactionConfig(extra_suffixes=("_KEY",), replace_defaults=True)
        # build doesn't validate; lowercasing here is defensive.
        got = cfg.build_effective_suffixes()
        assert got == frozenset({"_key"})

    def test_validate_accepts_well_formed(self) -> None:
        from dagstack.logger import RedactionConfig

        RedactionConfig(extra_suffixes=("_apikey",)).validate()  # no raise

    def test_validate_rejects_empty(self) -> None:
        import pytest

        from dagstack.logger import RedactionConfig

        with pytest.raises(ValueError, match="empty string"):
            RedactionConfig(extra_suffixes=("",)).validate()

    def test_validate_rejects_whitespace(self) -> None:
        import pytest

        from dagstack.logger import RedactionConfig

        with pytest.raises(ValueError, match="whitespace"):
            RedactionConfig(extra_suffixes=("_my secret",)).validate()

    def test_validate_rejects_non_lowercase_ascii(self) -> None:
        import pytest

        from dagstack.logger import RedactionConfig

        with pytest.raises(ValueError, match="lowercase ASCII"):
            RedactionConfig(extra_suffixes=("_APIKEY",)).validate()
        with pytest.raises(ValueError, match="lowercase ASCII"):
            RedactionConfig(extra_suffixes=("_кей",)).validate()


class TestEffectiveSecretSuffixesInheritance:
    """Regression for architect review M-1 (M3 impl): explicit-flag
    propagation, not nil-vs-empty quirk.
    """

    def test_disable_all_inherited_by_child(self) -> None:
        from dagstack.logger import Logger
        from dagstack.logger.logger import _reset_registry_for_tests

        _reset_registry_for_tests()
        root = Logger.get("")
        root.set_redaction_suffixes(frozenset())  # explicit empty, disable-all
        child = Logger.get("dagstack.rag")
        assert len(child.effective_secret_suffixes()) == 0

    def test_no_override_falls_back_to_default(self) -> None:
        from dagstack.logger import DEFAULT_SECRET_SUFFIXES, Logger
        from dagstack.logger.logger import _reset_registry_for_tests

        _reset_registry_for_tests()
        child = Logger.get("dagstack.rag")
        assert child.effective_secret_suffixes() == DEFAULT_SECRET_SUFFIXES
