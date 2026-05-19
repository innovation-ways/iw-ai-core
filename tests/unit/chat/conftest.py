"""Fixtures for ``tests/unit/chat`` — override the unit MagicMock db_session.

The default ``tests/unit/conftest.py`` exposes a ``MagicMock`` as
``db_session`` so most unit tests can mock DB calls cheaply. The
F-00086 ``tab_service`` tests, however, exercise real CRUD behaviour
(soft-cap counting, idempotent close/reopen, partial-unique-index race
guard) that only the testcontainer fixture chain from
``tests/integration/conftest.py`` can model faithfully.

We re-export the integration fixtures with a single nested
``db_session`` symbol so pytest's "closest-conftest wins" resolution
gives this directory the real DB session while sibling directories
keep the lightweight mock.
"""

from __future__ import annotations

# Re-export the testcontainer fixture chain so it is in scope for the
# tests in this directory. Pytest resolves fixture names by walking up
# from the test file's location; importing the names here makes them
# active without touching the parent conftest.
from tests.integration.conftest import (  # noqa: F401
    _db_test_connection,
    _pgtestdb_setup,
    db_engine,
    db_session,
    db_session_factory,
    pg_container,
    test_project,
)
