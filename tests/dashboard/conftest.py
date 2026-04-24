"""Dashboard integration tests — depends on integration db_session fixture.

This file acts as a conftest entry point so that tests/dashboard/ test files
can use the db_session fixture defined in tests/integration/conftest.py.
"""

from __future__ import annotations

# Re-export the integration conftest fixtures so they are visible to pytest
# when collecting tests under tests/dashboard/.
# pytest automatically loads conftest.py from the parent directories,
# but since tests/dashboard/ is not under tests/integration/ we need
# this file to ensure the integration conftest is visible.
# Import fixtures from integration conftest so pytest can discover them
from tests.integration.conftest import (  # noqa: F401
    db_engine,
    db_session,
    pg_container,
    test_project,
)
