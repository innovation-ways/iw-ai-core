"""Unit tests for ``orch.chat.tab_service`` (F-00086).

These tests assert the runtime-agnostic ``chat_tabs`` CRUD layer behaviour:

* ``create_tab`` happy path + runtime allowlist + soft-cap warning flag
* ``close_tab`` / ``reopen_tab`` idempotency + soft-delete preserves session id
* empty-body PATCH does not bump ``updated_at`` (invariant #8)
* ``bootstrap_default_tab`` idempotency under concurrent calls (invariant #6)

The tests use the testcontainer-backed ``db_session`` fixture from
``tests/integration/conftest.py`` (loaded via the root ``tests/conftest.py``
``pytest_plugins``). Per ``tests/CLAUDE.md`` the template DB has already
applied ``Base.metadata.create_all()`` AND ``FTS_FUNCTION_SQL`` /
``FTS_TRIGGER_SQL`` AND ``alembic upgrade head``, so the ``chat_tabs`` table
shipped by S01's migration is available.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from orch.chat import tab_service
from orch.chat.migration_helpers import bootstrap_default_tab
from orch.db.models import ChatTab

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Happy path + persistence
# ---------------------------------------------------------------------------


def test_create_tab_persists_row_with_defaults(
    db_session: Session,
    test_project: Any,
) -> None:
    tab, soft_cap_exceeded = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="anthropic/claude-sonnet-4-7",
    )
    db_session.flush()

    assert tab.id is not None
    assert tab.project_id == test_project.id
    assert tab.runtime == "opencode"
    assert tab.model == "anthropic/claude-sonnet-4-7"
    assert tab.status == "active"
    assert tab.title == "New chat"
    assert tab.opencode_session_id is None
    assert tab.closed_at is None
    assert soft_cap_exceeded is False


# ---------------------------------------------------------------------------
# Runtime allowlist (invariant #3 — tested at the service layer)
# ---------------------------------------------------------------------------


def test_create_tab_rejects_unknown_runtime(
    db_session: Session,
    test_project: Any,
) -> None:
    with pytest.raises(ValueError, match=r"runtime 'pi' not in allowlist"):
        tab_service.create_tab(
            db_session,
            project_id=test_project.id,
            runtime="pi",
            model="any/model",
        )
    # No row written
    db_session.flush()
    rows = db_session.query(ChatTab).filter(ChatTab.project_id == test_project.id).all()
    assert rows == []


# ---------------------------------------------------------------------------
# Soft cap (invariant #4) — PRIMARY TDD-RED EVIDENCE TARGET
# ---------------------------------------------------------------------------


def test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten(
    db_session: Session,
    test_project: Any,
) -> None:
    flags: list[bool] = []
    for i in range(11):
        _tab, exceeded = tab_service.create_tab(
            db_session,
            project_id=test_project.id,
            model=f"anthropic/claude-sonnet-4-{i}",
            title=f"Tab {i}",
        )
        flags.append(exceeded)
        db_session.flush()

    # The first 10 inserts must NOT trigger the soft-cap flag (count after
    # insert is 1..10 — within the cap). The 11th must.
    assert flags[:10] == [False] * 10
    assert flags[10] is True


# ---------------------------------------------------------------------------
# Soft-delete + reopen (invariant #5)
# ---------------------------------------------------------------------------


def test_close_tab_is_idempotent(
    db_session: Session,
    test_project: Any,
) -> None:
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        opencode_session_id="oc-sess-abc",
    )
    db_session.flush()

    closed = tab_service.close_tab(db_session, str(tab.id))
    db_session.flush()
    assert closed.status == "closed"
    assert closed.closed_at is not None
    assert closed.opencode_session_id == "oc-sess-abc"
    first_closed_at = closed.closed_at

    # Second close: no-op; closed_at unchanged.
    closed_again = tab_service.close_tab(db_session, str(tab.id))
    db_session.flush()
    assert closed_again.status == "closed"
    assert closed_again.closed_at == first_closed_at
    assert closed_again.opencode_session_id == "oc-sess-abc"


def test_reopen_tab_restores_active_status(
    db_session: Session,
    test_project: Any,
) -> None:
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        opencode_session_id="oc-sess-xyz",
    )
    db_session.flush()

    tab_service.close_tab(db_session, str(tab.id))
    db_session.flush()

    reopened = tab_service.reopen_tab(db_session, str(tab.id))
    db_session.flush()
    assert reopened.status == "active"
    assert reopened.closed_at is None
    assert reopened.opencode_session_id == "oc-sess-xyz"


# ---------------------------------------------------------------------------
# Empty-body PATCH (invariant #8)
# ---------------------------------------------------------------------------


def test_empty_patch_does_not_bump_updated_at(
    db_session: Session,
    test_project: Any,
) -> None:
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        title="orig",
    )
    db_session.flush()
    original_updated_at = tab.updated_at

    # Wait long enough that any rebump would be detectable at TIMESTAMPTZ μs resolution.
    time.sleep(0.01)

    updated = tab_service.update_tab(db_session, str(tab.id))
    db_session.flush()
    assert updated.updated_at == original_updated_at
    assert updated.title == "orig"
    assert updated.model == "m"


# ---------------------------------------------------------------------------
# Bootstrap default tab (invariant #6)
# ---------------------------------------------------------------------------


def _make_runtime_with_sessions(sessions: list[dict[str, Any]]) -> Any:
    """Build a ChatRuntime-shaped AsyncMock returning the given sessions."""
    runtime = AsyncMock()
    runtime.list_sessions = AsyncMock(return_value=sessions)
    runtime.health = AsyncMock(return_value=True)
    return runtime


def test_bootstrap_creates_default_tab_when_empty_and_session_exists(
    db_session: Session,
    test_project: Any,
) -> None:
    runtime = _make_runtime_with_sessions(
        [
            {"id": "oc-sess-1", "directory": "/repos/test", "createdAt": 1700000000},
            {"id": "oc-sess-2", "directory": "/repos/test", "createdAt": 1700000010},
            {"id": "oc-sess-other", "directory": "/repos/other", "createdAt": 1700000020},
        ]
    )

    tab = asyncio.run(
        bootstrap_default_tab(
            db_session,
            project_id=test_project.id,
            runtime=runtime,
            project_repo_root="/repos/test",
            default_model="anthropic/claude-sonnet-4-7",
        )
    )
    db_session.flush()

    assert tab is not None
    assert tab.title == "Default"
    assert tab.opencode_session_id == "oc-sess-2"  # most recent matching session
    assert tab.model == "anthropic/claude-sonnet-4-7"
    assert tab.runtime == "opencode"
    assert tab.status == "active"

    # Idempotent: re-running with the same state returns None.
    second = asyncio.run(
        bootstrap_default_tab(
            db_session,
            project_id=test_project.id,
            runtime=runtime,
            project_repo_root="/repos/test",
            default_model="anthropic/claude-sonnet-4-7",
        )
    )
    db_session.flush()
    assert second is None
    rows = db_session.query(ChatTab).filter(ChatTab.project_id == test_project.id).all()
    assert len(rows) == 1


def test_bootstrap_does_not_fire_when_only_closed_tabs_exist(
    db_session: Session,
    test_project: Any,
) -> None:
    """Invariant #6: once any row exists for the project (even closed-only),
    bootstrap MUST NOT resurrect a prior OpenCode session."""
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        opencode_session_id="oc-pre-existing",
    )
    db_session.flush()
    tab_service.close_tab(db_session, str(tab.id))
    db_session.flush()

    runtime = _make_runtime_with_sessions(
        [{"id": "oc-fresh", "directory": "/repos/test", "createdAt": 1800000000}]
    )

    result = asyncio.run(
        bootstrap_default_tab(
            db_session,
            project_id=test_project.id,
            runtime=runtime,
            project_repo_root="/repos/test",
            default_model="m",
        )
    )
    db_session.flush()
    assert result is None
    rows = db_session.query(ChatTab).filter(ChatTab.project_id == test_project.id).all()
    assert len(rows) == 1
    assert rows[0].status == "closed"


# ---------------------------------------------------------------------------
# recent_closed_tabs ordering and limit (AC8 / §Scope)
# ---------------------------------------------------------------------------


def test_recent_closed_tabs_orders_by_closed_at_desc(
    db_session: Session,
    test_project: Any,
) -> None:
    """``recent_closed_tabs`` returns closed tabs in ``closed_at DESC`` order."""
    tab_a, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        title="A",
        opencode_session_id="oc-a",
    )
    tab_b, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        title="B",
        opencode_session_id="oc-b",
    )
    tab_c, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
        title="C",
        opencode_session_id="oc-c",
    )
    db_session.flush()

    # Close in order A, C, B with a small delay so closed_at values are
    # strictly ordered at TIMESTAMPTZ μs resolution.
    tab_service.close_tab(db_session, str(tab_a.id))
    db_session.flush()
    time.sleep(0.01)
    tab_service.close_tab(db_session, str(tab_c.id))
    db_session.flush()
    time.sleep(0.01)
    tab_service.close_tab(db_session, str(tab_b.id))
    db_session.flush()

    closed = tab_service.recent_closed_tabs(db_session, project_id=test_project.id)
    titles = [t.title for t in closed]
    # Last closed first: B, then C, then A.
    assert titles == ["B", "C", "A"], f"unexpected order: {titles}"


def test_recent_closed_tabs_respects_limit(
    db_session: Session,
    test_project: Any,
) -> None:
    """``limit`` parameter caps the result count."""
    created: list[Any] = []
    for i in range(5):
        tab, _ = tab_service.create_tab(
            db_session,
            project_id=test_project.id,
            model="m",
            title=f"T{i}",
        )
        db_session.flush()
        created.append(tab)
    for tab in created:
        tab_service.close_tab(db_session, str(tab.id))
        db_session.flush()
        time.sleep(0.005)

    capped = tab_service.recent_closed_tabs(db_session, project_id=test_project.id, limit=3)
    assert len(capped) == 3
    # The three most-recently closed are the last three we created (T2..T4)
    # because the test closed them in creation order.
    titles = [t.title for t in capped]
    assert titles == ["T4", "T3", "T2"], f"unexpected order: {titles}"


# ---------------------------------------------------------------------------
# touch_last_active bumps the column (used by /prompt forwarder)
# ---------------------------------------------------------------------------


def test_touch_last_active_bumps_field(
    db_session: Session,
    test_project: Any,
) -> None:
    """``touch_last_active`` advances ``last_active_at`` to a fresh now()."""
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="m",
    )
    db_session.flush()
    before = tab.last_active_at
    assert before is not None

    # Pause long enough that TIMESTAMPTZ μs resolution detects the bump.
    time.sleep(0.01)

    tab_service.touch_last_active(db_session, str(tab.id))
    db_session.flush()
    db_session.refresh(tab)
    after = tab.last_active_at
    assert after is not None
    assert after > before, (
        f"touch_last_active did not advance last_active_at (before={before}, after={after})"
    )


def test_touch_last_active_is_no_op_for_missing_tab(
    db_session: Session,
    test_project: Any,  # noqa: ARG001 — fixture forces table to exist
) -> None:
    """``touch_last_active`` swallows missing tabs (background pump safety)."""
    # No exception, no DB write — function is a defensive no-op when the
    # tab vanished between the dispatch and the bump.
    tab_service.touch_last_active(db_session, "00000000-0000-0000-0000-000000000000")
    db_session.flush()


def test_bootstrap_is_idempotent_under_concurrent_calls(
    db_engine: Any,
    db_session: Session,
    test_project: Any,
) -> None:
    """Concurrent bootstrap calls must not produce two default tabs.

    Races are guarded by the ``uq_chat_tabs_default_per_project`` partial
    unique index (S01 migration). The loser of the race catches
    ``IntegrityError`` and re-fetches the existing default tab.

    Implementation: this test drives true concurrency by opening two
    fully independent connections from the per-test ``db_engine`` clone,
    which gives each thread its own transaction (the standard
    ``db_session_factory`` fixture pins all sessions to one connection
    and therefore cannot model the race). We also commit
    ``test_project`` into the per-test clone first so both worker
    transactions can see the FK target.
    """
    from sqlalchemy.orm import sessionmaker as _sessionmaker

    # Persist the project row so independent connections can satisfy the FK.
    db_session.commit()

    make_session = _sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    runtime = _make_runtime_with_sessions(
        [{"id": "oc-shared", "directory": "/repos/test", "createdAt": 1700000000}]
    )

    results: list[ChatTab | None] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(parties=2)

    def _worker() -> None:
        sess = make_session()
        try:
            barrier.wait(timeout=5.0)
            tab = asyncio.run(
                bootstrap_default_tab(
                    sess,
                    project_id=test_project.id,
                    runtime=runtime,
                    project_repo_root="/repos/test",
                    default_model="m",
                )
            )
            sess.commit()
            results.append(tab)
        except BaseException as exc:  # noqa: BLE001 — surface every race outcome
            errors.append(exc)
            sess.rollback()
        finally:
            sess.close()

    threads = [threading.Thread(target=_worker, name=f"bootstrap-{i}") for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert not errors, f"unexpected exceptions: {errors!r}"

    check = make_session()
    try:
        rows = (
            check.query(ChatTab)
            .filter(ChatTab.project_id == test_project.id, ChatTab.title == "Default")
            .all()
        )
    finally:
        check.close()
    assert len(rows) == 1, f"expected exactly one default tab, found {len(rows)}"
