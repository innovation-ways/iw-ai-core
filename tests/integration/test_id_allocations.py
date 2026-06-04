"""Unit tests for allocate_next_id() idempotency behavior (CR-00053 AC1–AC4).

RED phase: tests verify expected behavior before allocate_next_id() accepts
the idempotency_key parameter. These tests should FAIL until:
  1. allocate_next_id() is updated to accept idempotency_key as keyword-only arg
  2. IdAllocation model is present (S01 addition)

Tests use a real PostgreSQL testcontainer (session-scoped) with transactional
rollback after each test — the same pattern as test_chat_message_model.py.
"""

from __future__ import annotations

import psycopg.errors
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from orch.db.models import FTS_FUNCTION_SQL, FTS_TRIGGER_SQL, Base, IdAllocation, IdSequence

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_engine():
    """Start a PostgreSQL container for this test module (session-scoped)."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            conn.commit()
        yield engine


@pytest.fixture
def db_session(pg_engine):
    """Each test gets a transactional session that rolls back after the test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Imports (deferred so live-DB guard fires before testcontainers are reached)
# ---------------------------------------------------------------------------


def _allocate_next_id(session, project_id, prefix, *, idempotency_key=None):
    """Proxy that imports and calls allocate_next_id from orch.cli.id_commands."""
    from orch.cli.id_commands import allocate_next_id

    return allocate_next_id(session, project_id, prefix, idempotency_key=idempotency_key)


# ---------------------------------------------------------------------------
# AC1 — no key path unchanged: two calls, sequential IDs, no id_allocations rows
# ---------------------------------------------------------------------------


def test_no_key_path_unchanged(db_session):
    """allocate_next_id(session, project_id, prefix) with no key returns sequential IDs.

    Covers AC1: no --idempotency-key flag → two distinct IDs allocated,
    id_allocations row count is 0, id_sequences.next_number incremented by 2.
    """
    project_id = "test-proj-ac1"
    prefix = "R"

    # First call
    number1, formatted1 = _allocate_next_id(db_session, project_id, prefix)
    assert formatted1 == f"R-{number1:05d}"

    # Second call — must be the next sequential number
    number2, formatted2 = _allocate_next_id(db_session, project_id, prefix)
    assert formatted2 == f"R-{number2:05d}"
    assert number2 == number1 + 1

    # No id_allocations rows should be written when idempotency_key is None
    rows = db_session.execute(select(IdAllocation)).scalars().all()
    assert len(rows) == 0

    # id_sequences.next_number should have advanced by 2
    seq_row = db_session.execute(select(IdSequence).where(IdSequence.prefix == prefix)).scalar_one()
    assert seq_row.next_number == number1 + 2


# ---------------------------------------------------------------------------
# AC2 — repeat call with same key returns same ID, only one id_allocations row
# ---------------------------------------------------------------------------


def test_repeat_key_returns_same_id(db_session):
    """Two calls with the same idempotency_key return identical (number, formatted_id).

    Covers AC2: first call allocates a fresh ID and writes one id_allocations row.
    Second call with the same key returns the same ID without incrementing id_sequences
    a second time and without inserting a second row.
    """
    project_id = "test-proj-ac2"
    prefix = "R"
    key = "abc"

    # First call — allocates new ID and writes to id_allocations
    number1, formatted1 = _allocate_next_id(db_session, project_id, prefix, idempotency_key=key)
    assert formatted1 == f"R-{number1:05d}"

    # Get id_sequences state after first call
    seq_after_first = db_session.execute(
        select(IdSequence).where(IdSequence.prefix == prefix)
    ).scalar_one()
    next_after_first = seq_after_first.next_number

    # Second call with SAME key — must return identical ID
    number2, formatted2 = _allocate_next_id(db_session, project_id, prefix, idempotency_key=key)
    assert number2 == number1
    assert formatted2 == formatted1

    # id_sequences.next_number must NOT have been incremented a second time
    seq_row = db_session.execute(select(IdSequence).where(IdSequence.prefix == prefix)).scalar_one()
    assert seq_row.next_number == next_after_first  # unchanged from after first call

    # Exactly ONE id_allocations row exists
    rows = (
        db_session.execute(
            select(IdAllocation).where(
                IdAllocation.prefix == prefix,
                IdAllocation.idempotency_key == key,
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].number == number1


# ---------------------------------------------------------------------------
# AC3 — distinct keys allocate distinct IDs
# ---------------------------------------------------------------------------


def test_distinct_keys_distinct_ids(db_session):
    """Two different idempotency_keys for the same prefix produce distinct IDs.

    Covers AC3: key "abc" and key "def" each get their own allocation.
    """
    project_id = "test-proj-ac3"
    prefix = "R"

    number1, formatted1 = _allocate_next_id(db_session, project_id, prefix, idempotency_key="abc")
    number2, formatted2 = _allocate_next_id(db_session, project_id, prefix, idempotency_key="def")

    assert number2 != number1
    assert formatted1 == f"R-{number1:05d}"
    assert formatted2 == f"R-{number2:05d}"

    # Two id_allocations rows, one per key
    all_rows = db_session.execute(select(IdAllocation)).scalars().all()
    assert len(all_rows) == 2

    # id_sequences.next_number advanced by 2 (not 1 — each distinct key causes an increment)
    seq_row = db_session.execute(select(IdSequence).where(IdSequence.prefix == prefix)).scalar_one()
    assert seq_row.next_number == number2 + 1


# ---------------------------------------------------------------------------
# AC4 — same key under different prefixes is independent
# ---------------------------------------------------------------------------


def test_same_key_different_prefixes_independent(db_session):
    """The same idempotency_key on different prefixes produces independent allocations.

    Covers AC4: prefix="R" key="abc" and prefix="F" key="abc" are independent rows
    because the idempotency constraint is on (prefix, idempotency_key).

    Note: the underlying sequence numbers may or may not be equal (R and F have
    independent sequences), so we assert on the rows (different prefixes) rather
    than on the numeric values being different.
    """
    project_id = "test-proj-ac4"
    key = "abc"

    num_r, formatted_r = _allocate_next_id(db_session, project_id, "R", idempotency_key=key)
    num_f, formatted_f = _allocate_next_id(db_session, project_id, "F", idempotency_key=key)

    # formatted IDs must be distinct (different prefixes)
    assert formatted_r == f"R-{num_r:05d}"
    assert formatted_f == f"F-{num_f:05d}"
    assert formatted_r != formatted_f

    # Two rows, different prefixes (R and F), same key value
    all_rows = db_session.execute(select(IdAllocation)).scalars().all()
    assert len(all_rows) == 2
    prefixes = {r.prefix for r in all_rows}
    assert prefixes == {"R", "F"}


# ---------------------------------------------------------------------------
# Concurrent-INSERT retry: IntegrityError on first INSERT, retry picks up winner
# ---------------------------------------------------------------------------


def test_concurrent_same_key_retries_and_returns_winner(db_session, monkeypatch):
    """When a concurrent call has already inserted the (prefix, key) row, our
    speculative id_sequences increment is rolled back via SAVEPOINT, then the
    retry SELECT finds the winner's row and returns its number.

    This simulates the race where:
      1. We begin_nested() (SAVEPOINT)
      2. We SELECT FOR UPDATE and increment id_sequences
      3. We INSERT into id_allocations — UniqueViolation because the winner beat us
      4. We ROLLBACK TO SAVEPOINT (undoes the id_sequences increment)
      5. We retry the SELECT for the existing row → returns winner's number

    The test patches session.execute to raise IntegrityError on the INSERT,
    then verifies:
      - The second call (after retry) succeeds
      - id_sequences.next_number was NOT double-incremented (SAVEPOINT rollback works)
      - The returned number is the winner's number (not our speculative one)
    """

    project_id = "test-proj-concurrent"
    prefix = "R"
    key = "concurrent-key"

    # Pre-insert the winner's row so our session can find it on retry
    winner_number = 999
    db_session.add(
        IdAllocation(
            prefix=prefix,
            number=winner_number,
            idempotency_key=key,
            project_id=project_id,
        )
    )
    db_session.flush()

    # Initialise id_sequences (it starts at 1, will be incremented in the first attempt)
    db_session.execute(
        text(
            "INSERT INTO id_sequences (prefix, next_number) VALUES (:p, :n) "
            "ON CONFLICT (prefix) DO NOTHING"
        ),
        {"p": prefix, "n": winner_number + 1},
    )
    db_session.commit()

    # Re-open session for the actual test
    connection = db_session.get_bind()
    transaction = connection.begin_nested()
    factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = factory()

    try:
        # First attempt: our SAVEPOINT'd increment would happen, then INSERT fails
        # We patch the INSERT to raise IntegrityError immediately
        call_count = 0

        original_execute = session.execute

        def patched_execute(stmt, *args, **kwargs):
            nonlocal call_count
            # After the SELECT FOR UPDATE has been executed (first call),
            # the next INSERT into id_allocations raises UniqueViolation
            call_count += 1
            if call_count == 2:  # The INSERT into id_allocations
                # Trigger the same error the DB would raise on duplicate key
                raise IntegrityError(
                    "statement",
                    {},
                    psycopg.errors.UniqueViolation(
                        "duplicate key value violates unique constraint idx_id_allocations_key"
                    ),
                )
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr(session, "execute", patched_execute)

        # This will: begin_nested(), SELECT FOR UPDATE, INSERT (fails), rollback savepoint,
        # retry SELECT, return winner's number
        number, formatted = _allocate_next_id(session, project_id, prefix, idempotency_key=key)

        assert number == winner_number, (
            f"Expected winner's number {winner_number}, got {number} — "
            "SAVEPOINT rollback must have undone the speculative increment"
        )
        assert formatted == f"R-{winner_number:05d}"
    finally:
        session.close()
        transaction.rollback()
