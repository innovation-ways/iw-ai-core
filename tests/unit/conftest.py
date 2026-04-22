"""Unit test fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def db_session() -> MagicMock:
    """Provide a mock ORM session for unit tests that need to stub DB calls."""
    return MagicMock(spec=["get"])
