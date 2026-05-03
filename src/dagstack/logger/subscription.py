"""Subscription handle for logger runtime-reconfigure callbacks.

Per spec §7.2: `Subscription { unsubscribe, active, inactive_reason, path }`.
In Phase 1 `active=False` — watch-based reload is not implemented.
The module-level `configure()` replaces state wholesale; the subscription
API is a placeholder for Phase 2 file-watcher / admin-API reload.

Diagnostic channel — the named logger `dagstack.logger.internal` (§7.4).
The warning here is emitted via stdlib `logging` rather than the binding's
own `Logger` to keep this module free of any import-time dependency on
`logger.py` (which itself imports from `subscription.py`), and to avoid the
chicken-and-egg problem of the logger warning about itself through itself.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_INTERNAL_LOGGER = logging.getLogger("dagstack.logger.internal")


class Subscription:
    """Handle returned by `Logger.on_reconfigure()` (Phase 2+).

    In Phase 1 subscriptions are always `active=False` and emit a warning.
    Placeholder API for forward compatibility.
    """

    __slots__ = ("_unsubscribe_impl", "_unsubscribed", "active", "inactive_reason", "path")

    def __init__(
        self,
        *,
        path: str,
        active: bool,
        inactive_reason: str | None = None,
        unsubscribe: Callable[[], None] | None = None,
    ) -> None:
        self.path = path
        self.active = active
        self.inactive_reason = inactive_reason
        self._unsubscribe_impl = unsubscribe if unsubscribe is not None else _noop
        self._unsubscribed = False

    def unsubscribe(self) -> None:
        if self._unsubscribed:
            return
        self._unsubscribed = True
        self._unsubscribe_impl()

    def __repr__(self) -> str:
        return (
            f"Subscription(path={self.path!r}, active={self.active}, "
            f"inactive_reason={self.inactive_reason!r})"
        )


def _noop() -> None:
    """Default unsubscribe for inactive subscriptions."""


def emit_inactive_subscription_warning(*, path: str) -> None:
    """Warn on `dagstack.logger.internal` about a subscription without watch support."""
    _INTERNAL_LOGGER.warning(
        "subscription_without_watch: path=%r — callback will never fire "
        "(Phase 1 logger does not support watch-based reconfiguration)",
        path,
    )
