"""Smoke tests for the skeleton: package importable, version, spec submodule, OTel API."""

from __future__ import annotations


def test_package_importable() -> None:
    import dagstack.logger

    assert dagstack.logger is not None


def test_version_is_string() -> None:
    from dagstack.logger import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_spec_submodule_present() -> None:
    """spec/ must contain the logger-spec ADR — it is a git submodule."""
    from pathlib import Path

    repo_root = Path(__file__).parent.parent
    adr = repo_root / "spec" / "adr" / "0001-logger-contract.md"
    assert adr.exists(), f"spec submodule not initialised: {adr} missing"


def test_otel_api_importable() -> None:
    """opentelemetry-api — mandatory dependency (context propagation)."""
    from opentelemetry import context, trace

    assert context is not None
    assert trace is not None
