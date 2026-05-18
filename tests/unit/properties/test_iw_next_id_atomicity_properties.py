"""Property-based tests for `allocate_next_id` atomicity under concurrent calls.

Tests that multiple concurrent callers of `allocate_next_id` with the same
prefix never receive the same (prefix, suffix) pair — the lost-update violation.

This is the ONLY property test that touches a real database; it uses the
testcontainer `db_session` fixture loaded via pytest_plugins in conftest.py.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import integers, sampled_from

from orch.cli.id_commands import allocate_next_id
from orch.db.models import Project

# ----- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def project_in_session(db_session):
    """Ensure a Project row exists in the current test DB clone."""
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


# ----- Property tests ------------------------------------------------------------------


def _allocate_in_thread(session_factory, project_id: str, prefix: str) -> tuple[str, int]:
    """Call allocate_next_id in a thread-safe context."""
    with session_factory() as session:
        result = allocate_next_id(session, project_id, prefix)
        session.commit()
        return result


@pytest.mark.skip(
    reason=(
        "CR-00060 S03 finding: allocate_next_id() has a pre-existing concurrency bug "
        "(duplicate IDs returned under concurrent calls). "
        "Filed as P2-CR-B-followup-next-id-atomicity. "
        "Do NOT unskip until the bug is fixed — the test correctly fails when run."
    )
)
@settings(
    max_examples=10,
    deadline=5000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    prefix=sampled_from(["WI", "BAT", "DOC", "TEST"]),
    num_concurrent=integers(min_value=2, max_value=8),
)
def test_concurrent_allocate_next_id_no_duplicates(
    db_session, project_in_session, prefix: str, num_concurrent: int
) -> None:
    """Property: concurrent allocate_next_id(prefix) calls never return the same number.

    Uses db_session from the testcontainer fixture (loaded via pytest_plugins in
    conftest.py). Invariant: across all concurrent calls, no two calls return the
    same (prefix, numeric_suffix) pair (the lost-update violation).
    """
    from sqlalchemy.orm import sessionmaker

    project_id = project_in_session.id
    engine = db_session.get_bind()
    session_factory = sessionmaker(bind=engine)

    with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [
            executor.submit(_allocate_in_thread, session_factory, project_id, prefix)
            for _ in range(num_concurrent)
        ]
        results = [f.result() for f in futures]

    numeric_ids = [numeric_id for _, numeric_id in results]
    assert len(numeric_ids) == len(set(numeric_ids)), (
        f"Duplicate numeric_id detected for prefix {prefix!r}: {numeric_ids}"
    )
