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


from tests.integration.conftest import db_engine, pg_container, test_project

__all__ = ["db_engine", "db_session", "pg_container", "test_project"]
