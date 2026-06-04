"""Integration tests for bootstrap-default-tab behaviour (AC5, AC9, invariant #6).

Covers:
- AC5: bootstrap creates a Default tab when no rows exist + prior session found
- AC5 idempotency: second GET returns the same tab (no duplicate)
- AC9: bootstrap does NOT fire when only closed tabs exist
- Boundary "Bootstrap called twice concurrently": race safety via partial unique index
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.chat import tab_service
from orch.chat.migration_helpers import bootstrap_default_tab
from orch.db.models import ChatTab, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime_with_sessions(sessions: list[dict[str, Any]]) -> Any:
    rt = MagicMock()
    rt.list_sessions = AsyncMock(return_value=sessions)
    rt.health = AsyncMock(return_value=True)
    return rt


def _client_mock(*, models: list[str] | None = None, default_model: str = "prov-a/model-a") -> Any:
    c = MagicMock()
    c.create_session = AsyncMock(return_value="oc-sess-new")
    c.get_session = AsyncMock(return_value={"id": "oc-sess-new", "status": "idle"})
    c.get_messages = AsyncMock(return_value=[])
    c.list_sessions = AsyncMock(return_value=[])
    c.prompt = AsyncMock(return_value=None)
    c.abort = AsyncMock(return_value=None)
    c.reply_permission = AsyncMock(return_value=None)
    c.get_config = AsyncMock(return_value={"model": default_model})
    if models is None:
        models = ["prov-a/model-a", "prov-a/model-b"]
    providers: dict[str, dict[str, Any]] = {}
    for combo in models:
        if "/" not in combo:
            continue
        pid, mid = combo.split("/", 1)
        providers.setdefault(pid, {"id": pid, "models": {}})
        providers[pid]["models"][mid] = {}
    c.get_providers = AsyncMock(
        return_value={
            "providers": list(providers.values()),
            "default": {default_model.split("/", 1)[0]: default_model.split("/", 1)[1]},
        }
    )
    return c


# ---------------------------------------------------------------------------
# Bootstrap via HTTP (AC5 / AC9 integration)
# ---------------------------------------------------------------------------


def _make_test_client(
    db_session: Session,
    runtime: Any,
    *,
    project_id: str = "test-proj",
) -> TestClient:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.state.opencode_runtime = runtime
        app.state.opencode_client = _client_mock()
        app.state.relay_manager = MagicMock()
        app.dependency_overrides[get_db] = lambda: db_session
        return app, original
    except Exception:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        raise


def test_bootstrap_seeds_default_when_chat_tabs_empty(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC5: first GET /api/chat/tabs creates exactly one Default tab from prior session."""
    runtime = _make_runtime_with_sessions(
        [
            {"id": "oc-sess-1", "directory": "/repos/test", "createdAt": 1700000000},
            {"id": "oc-sess-2", "directory": "/repos/test", "createdAt": 1700000010},
        ]
    )

    app, original_eii = _make_test_client(db_session, runtime, project_id=test_project.id)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(f"/api/chat/tabs?project_id={test_project.id}")
            assert resp.status_code == 200
            tabs = resp.json()["tabs"]
            assert len(tabs) == 1, f"Expected exactly one Default tab, got {len(tabs)}: {tabs}"
            assert tabs[0]["title"] == "Default"
            assert tabs[0]["opencode_session_id"] == "oc-sess-2"  # most recent
            assert tabs[0]["model"] == "prov-a/model-a"
            assert tabs[0]["runtime"] == "opencode"
            assert tabs[0]["status"] == "active"
    finally:
        app.dependency_overrides.clear()
        if original_eii is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_eii


def test_bootstrap_is_no_op_on_second_call(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC5 idempotency: second GET returns the same tab; no duplicate in DB."""
    runtime = _make_runtime_with_sessions(
        [{"id": "oc-sess-1", "directory": "/repos/test", "createdAt": 1700000000}]
    )

    app, original_eii = _make_test_client(db_session, runtime, project_id=test_project.id)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            # First call — creates the default tab
            resp1 = client.get(f"/api/chat/tabs?project_id={test_project.id}")
            assert resp1.status_code == 200
            first_tab_id = resp1.json()["tabs"][0]["id"]

            # Second call — same tab, no duplicate
            resp2 = client.get(f"/api/chat/tabs?project_id={test_project.id}")
            assert resp2.status_code == 200
            tabs2 = resp2.json()["tabs"]
            assert len(tabs2) == 1, f"Expected exactly one tab on second call, got {len(tabs2)}"
            assert tabs2[0]["id"] == first_tab_id

            # DB confirms exactly one row
            db_session.expire_all()
            rows = db_session.query(ChatTab).filter(ChatTab.project_id == test_project.id).all()
            assert len(rows) == 1
    finally:
        app.dependency_overrides.clear()
        if original_eii is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_eii


def test_bootstrap_is_no_op_when_only_closed_tabs_exist(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC9 / Boundary: project with only closed tabs does NOT trigger bootstrap."""
    # Pre-create a closed tab (simulates user who opened then closed all tabs)
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        model="prov-a/model-a",
        opencode_session_id="oc-pre-existing",
    )
    db_session.flush()
    tab_service.close_tab(db_session, str(tab.id))
    db_session.flush()

    runtime = _make_runtime_with_sessions(
        [{"id": "oc-fresh", "directory": "/repos/test", "createdAt": 1800000000}]
    )

    app, original_eii = _make_test_client(db_session, runtime, project_id=test_project.id)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(f"/api/chat/tabs?project_id={test_project.id}")
            assert resp.status_code == 200
            tabs = resp.json()["tabs"]
            # include_closed=False → empty list (user closed all tabs)
            assert tabs == [], f"Expected empty list when only closed tab exists; got {tabs}"
    finally:
        app.dependency_overrides.clear()
        if original_eii is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_eii

    # DB still has exactly ONE row (the pre-existing closed tab)
    db_session.expire_all()
    rows = db_session.query(ChatTab).filter(ChatTab.project_id == test_project.id).all()
    assert len(rows) == 1
    assert rows[0].status == "closed"
    assert rows[0].opencode_session_id == "oc-pre-existing"


# ---------------------------------------------------------------------------
# Bootstrap concurrent-call race safety (Boundary "Bootstrap called twice concurrently")
# ---------------------------------------------------------------------------


def test_bootstrap_concurrent_calls_create_exactly_one_tab(
    db_engine: Any,
    db_session: Session,
    test_project: Project,
) -> None:
    """Two racing GET calls on empty chat_tabs produce exactly one Default tab.

    The ``uq_chat_tabs_default_per_project`` partial unique index from S01
    ('UNIQUE (project_id) WHERE title='Default' AND status='active'')
    enforces this. The loser catches IntegrityError, rolls back, and
    re-fetches the winner's row.
    """
    # Commit the project row so independent connections can FK to it.
    # Keep a plain scalar copy of the ID before commit; ORM instances are
    # session-bound and may require refresh after commit, which is unsafe
    # from worker threads.
    project_id = test_project.id
    db_session.commit()

    from sqlalchemy.orm import sessionmaker as _sessionmaker

    make_session = _sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    runtime = _make_runtime_with_sessions(
        [{"id": "oc-shared", "directory": "/repos/test", "createdAt": 1700000000}]
    )

    # Capture id (UUID) instead of the ORM instance — instances are detached
    # after sess.close() and any attribute access raises DetachedInstanceError.
    result_ids: list[Any] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(parties=2)

    def _worker() -> None:
        sess = make_session()
        try:
            # Wait for both threads to be ready
            barrier.wait(timeout=5.0)
            # Call bootstrap directly on the independent session.
            # bootstrap_default_tab is async (chat router awaits it); each
            # worker drives it via asyncio.run so the thread is sync but
            # the helper itself can await runtime.list_sessions().
            tab = asyncio.run(
                bootstrap_default_tab(
                    sess,
                    project_id=project_id,
                    runtime=runtime,
                    project_repo_root="/repos/test",
                    default_model="prov-a/model-a",
                )
            )
            sess.commit()
            # Read attribute while session is still open so the resulting
            # value survives past sess.close().
            result_ids.append(tab.id if tab is not None else None)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            sess.rollback()
        finally:
            sess.close()

    threads = [threading.Thread(target=_worker, name=f"bootstrap-{i}") for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert not errors, f"Unexpected exceptions during concurrent bootstrap: {errors!r}"

    # Exactly one tab in DB
    check = make_session()
    try:
        rows = (
            check.query(ChatTab)
            .filter(ChatTab.project_id == project_id, ChatTab.title == "Default")
            .all()
        )
    finally:
        check.close()
    assert len(rows) == 1, f"Expected exactly one Default tab after race, found {len(rows)}"

    # Both callers got a non-None result (loser re-fetched winner's row)
    non_none = [tid for tid in result_ids if tid is not None]
    assert len(non_none) == 2, f"Expected both callers to receive a tab; got {len(non_none)}"
    # Same tab ID for both
    tab_ids = set(non_none)
    assert len(tab_ids) == 1, f"Expected same tab ID for both callers; got {tab_ids}"
