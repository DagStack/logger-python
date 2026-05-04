"""Shared fixtures for `tests/docs_examples/`.

Each docs-example test mutates the global Logger registry (via `Logger.get`,
`configure`, `scope_sinks`, etc.). The registry is a process-wide cache, so
tests must reset it before AND after each test to avoid bleeding state into
other tests in the suite.

The reset happens via the package-private helper
`dagstack.logger.logger._reset_registry_for_tests`, which is the same hook
the unit-test suite uses (see `tests/test_logger.py`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from dagstack.logger.logger import _reset_registry_for_tests


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    """Ensure each docs-example test runs against a clean Logger registry."""
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()
