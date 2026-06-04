"""Unit test fixtures.

Unit tests that need a db_session mock get it here without touching the
integration testcontainer infrastructure.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def db_session() -> MagicMock:
    """Provide a MagicMock session for unit tests that need to mock DB calls."""
    return MagicMock()


__all__ = ["db_session"]
