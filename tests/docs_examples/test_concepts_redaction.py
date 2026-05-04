"""Auto-tests for Python snippets from `docs/concepts/redaction.mdx`."""

from __future__ import annotations

from dagstack.logger import InMemorySink, Logger, configure


# ── "Behaviour" — flat attribute masking ──────────────────────────────


def test_redaction__flat_attributes() -> None:
    """Snippet `docs/concepts/redaction.mdx` → "Behaviour" → Python TabItem.

    Keys ending in `_key` and `_token` are masked; non-secret keys pass
    through unchanged.
    """
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])

    # --- snippet start (redaction / behaviour) ----------------------------
    from dagstack.logger import Logger

    logger = Logger.get("auth")

    logger.info(
        "user authenticated",
        attributes={
            "user.id": 42,
            "api_key": "sk-very-secret-value",  # → "***"
            "session_token": "ey...",  # → "***"
            "request.id": "req-abc",
        },
    )
    # Emitted record:
    # attributes = {
    #   "user.id": 42,
    #   "api_key": "***",
    #   "session_token": "***",
    #   "request.id": "req-abc",
    # }
    # --- snippet end ------------------------------------------------------

    rec = sink.records()[0]
    assert rec.attributes["user.id"] == 42
    assert rec.attributes["api_key"] == "***"
    assert rec.attributes["session_token"] == "***"
    assert rec.attributes["request.id"] == "req-abc"


# ── "Nested attributes" — recursive masking ───────────────────────────


def test_redaction__nested_attributes() -> None:
    """Snippet `docs/concepts/redaction.mdx` → "Nested attributes" → Python TabItem.

    Redaction recurses through dict-typed values; `client_secret` nested
    two levels deep is still masked.
    """
    sink = InMemorySink()
    configure(root_level="INFO", sinks=[sink])
    logger = Logger.get("auth")

    # --- snippet start (redaction / nested attributes) --------------------
    logger.info(
        "config snapshot",
        attributes={
            "config": {
                "service.name": "order-service",
                "auth": {
                    "client_secret": "shh",  # → "***"
                    "redirect_url": "https://...",
                },
            },
        },
    )
    # Result:
    # attributes = {
    #   "config": {
    #     "service.name": "order-service",
    #     "auth": {
    #       "client_secret": "***",
    #       "redirect_url": "https://...",
    #     },
    #   },
    # }
    # --- snippet end ------------------------------------------------------

    rec = sink.records()[0]
    config = rec.attributes["config"]
    assert isinstance(config, dict)
    assert config["service.name"] == "order-service"
    auth = config["auth"]
    assert isinstance(auth, dict)
    assert auth["client_secret"] == "***"
    assert auth["redirect_url"] == "https://..."
