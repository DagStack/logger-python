"""Unit tests for Subscription + the inactive warning."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dagstack.logger.subscription import (
    Subscription,
    emit_inactive_subscription_warning,
)

if TYPE_CHECKING:
    import pytest


class TestSubscription:
    def test_active_false_default(self) -> None:
        sub = Subscription(path="x", active=False, inactive_reason="noop")
        assert sub.active is False
        assert sub.inactive_reason == "noop"

    def test_unsubscribe_calls_impl(self) -> None:
        calls = []
        sub = Subscription(path="x", active=True, unsubscribe=lambda: calls.append("x"))
        sub.unsubscribe()
        assert calls == ["x"]

    def test_unsubscribe_idempotent(self) -> None:
        calls = []
        sub = Subscription(path="x", active=True, unsubscribe=lambda: calls.append("x"))
        sub.unsubscribe()
        sub.unsubscribe()
        assert calls == ["x"]

    def test_repr_readable(self) -> None:
        sub = Subscription(path="logger:root", active=False, inactive_reason="foo")
        r = repr(sub)
        assert "logger:root" in r
        assert "False" in r


class TestWarningEmission:
    def test_warning_to_internal_logger(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="dagstack.logger.internal"):
            emit_inactive_subscription_warning(path="logger:dagstack.rag")
        assert any("subscription_without_watch" in record.message for record in caplog.records)
        assert any("logger:dagstack.rag" in record.message for record in caplog.records)
