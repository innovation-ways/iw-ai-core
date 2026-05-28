from __future__ import annotations

import math
import os
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import AgentRuntimeOption, ChatTab


@contextmanager
def _client(db_session, pi_runtime):
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    app.state.pi_runtime = pi_runtime
    app.state.opencode_runtime = MagicMock()
    app.state.opencode_runtime.health = AsyncMock(return_value=True)
    app.state.opencode_client = MagicMock()
    app.state.relay_manager = MagicMock()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def _seed_pi_runtime_option(db_session, model: str, context_window_tokens: int | None) -> None:
    row = AgentRuntimeOption(
        cli_tool="pi",
        model=model,
        cli_label="Pi",
        model_label=model,
        display_name=f"Pi {model}",
        context_window_tokens=context_window_tokens,
    )
    db_session.add(row)
    db_session.flush()


def _seed_pi_tab(db_session, project_id: str, model: str) -> ChatTab:
    tab = ChatTab(
        project_id=project_id,
        runtime="pi",
        model=f"pi/{model}",
        opencode_session_id="pi-sess-1",
        title="Pi tab",
    )
    db_session.add(tab)
    db_session.commit()
    return tab


def _pi_runtime(*, healthy: bool = True):
    rt = MagicMock()
    rt.health = AsyncMock(return_value=healthy)
    rt.get_session = AsyncMock(return_value={"id": "pi-sess-1"})
    rt.get_messages = AsyncMock(
        return_value=[
            {"role": "assistant", "usage": {"input": 30000, "output": 10000}},
            {"role": "assistant", "usage": {"input": 30000, "output": 30000}},
        ]
    )
    return rt


def test_get_tab_context_pct_known_for_pi_runtime(db_session, test_project) -> None:
    model = "Synthetic-Context-Model"
    _seed_pi_runtime_option(db_session, model=model, context_window_tokens=200000)
    tab = _seed_pi_tab(db_session, project_id=test_project.id, model=model)

    with _client(db_session, _pi_runtime(healthy=True)) as client:
        resp = client.get(f"/api/chat/tabs/{tab.id}")

    session = resp.json()["session"]
    assert session["context_pct_status"] == "known"
    assert session["used_tokens"] == 60000
    assert session["window_tokens"] == 200000
    assert session["context_pct"] == pytest.approx(30.0)
    assert math.isfinite(session["context_pct"])
    assert session["context_pct_status"] == "known"
    assert isinstance(session["used_tokens"], int)
    assert isinstance(session["window_tokens"], int)
    assert isinstance(session["context_pct"], float)


def test_get_tab_context_pct_unknown_window_for_pi_runtime(db_session, test_project) -> None:
    model = "Synthetic-Unknown-Window"
    _seed_pi_runtime_option(db_session, model=model, context_window_tokens=None)
    tab = _seed_pi_tab(db_session, project_id=test_project.id, model=model)

    with _client(db_session, _pi_runtime(healthy=True)) as client:
        resp = client.get(f"/api/chat/tabs/{tab.id}")

    session = resp.json()["session"]
    assert session["context_pct_status"] == "unknown_window"
    assert session["context_pct"] is None
    assert session["used_tokens"] is None
    assert session["window_tokens"] is None


def test_get_tab_context_pct_unknown_runtime_for_unhealthy_pi(db_session, test_project) -> None:
    model = "Synthetic-Unknown-Runtime"
    _seed_pi_runtime_option(db_session, model=model, context_window_tokens=200000)
    tab = _seed_pi_tab(db_session, project_id=test_project.id, model=model)

    with _client(db_session, _pi_runtime(healthy=False)) as client:
        resp = client.get(f"/api/chat/tabs/{tab.id}")

    assert resp.status_code == 200
    session = resp.json()["session"]
    assert session["context_pct_status"] == "unknown_runtime"
    assert session["context_pct"] is None
    assert session["used_tokens"] is None
    assert session["window_tokens"] is None
