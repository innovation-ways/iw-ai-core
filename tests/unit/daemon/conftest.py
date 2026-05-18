"""Fixtures for daemon-unit tests.

Some daemon unit tests exercise predicates and helpers that issue real
SQL against PostgreSQL JSONB operators (e.g. the scope-violation budget
predicate from I-00101). These need the testcontainer-backed
``db_session`` instead of the MagicMock declared in ``tests/unit/conftest.py``.

Importing the fixture here scopes it to ``tests/unit/daemon/`` only;
tests under ``tests/unit/`` (outside ``daemon/``) still get the MagicMock
``db_session`` from the parent ``unit/conftest.py``.
"""

from __future__ import annotations

from tests.integration.conftest import db_session  # noqa: F401

__all__ = ["db_session"]
