from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.chat import tab_service as _tab_service
from orch.db.models import AgentRuntimeOption, Project


def _make_pi_runtime(messages_resp: list[dict[str, Any]]) -> Any:
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    rt.get_session = AsyncMock(return_value={"id": "pi-sess-1", "pi_session_path": None})
    rt.get_messages = AsyncMock(return_value=messages_resp)
    return rt


def _seed_pi_model(db: Any, context_window_tokens: int | None) -> None:
    row = db.query(AgentRuntimeOption).filter_by(cli_tool="pi", model="MiniMax-M2.7").one_or_none()
    if row is None:
        row = AgentRuntimeOption(
            cli_tool="pi",
            model="MiniMax-M2.7",
            cli_label="Pi",
            model_label="MiniMax",
            display_name="Pi MiniMax",
            context_window_tokens=context_window_tokens,
        )
        db.add(row)
    else:
        row.context_window_tokens = context_window_tokens
    db.commit()


def _create_pi_tab(db: Any, project_id: str) -> Any:
    tab, _ = _tab_service.create_tab(
        db,
        project_id=project_id,
        runtime="pi",
        model="pi/MiniMax-M2.7",
        opencode_session_id="pi-sess-1",
    )
    db.commit()
    return tab


@contextmanager
def _client(db_session: Any, pi_runtime: Any) -> Any:
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


def test_get_tab_payload_known_pi(db_session: Any, test_project: Project) -> None:
    _seed_pi_model(db_session, 100000)
    tab = _create_pi_tab(db_session, test_project.id)
    pi_runtime = _make_pi_runtime(
        [
            {
                "role": "assistant",
                "usage": {"input": 2000, "output": 3000, "cacheRead": 0, "cacheWrite": 0},
            }
        ]
    )

    with _client(db_session, pi_runtime) as tc:
        resp = tc.get(f"/api/chat/tabs/{tab.id}")

    body = resp.json()
    session = body["session"]
    assert resp.status_code == 200
    assert session["context_pct_status"] == "known"
    assert session["context_pct"] == 5.0
    assert session["used_tokens"] == 5000
    assert session["window_tokens"] == 100000
    assert session["context_pct_reason"] is None


def test_get_tab_payload_unknown_window_pi(db_session: Any, test_project: Project) -> None:
    _seed_pi_model(db_session, None)
    tab = _create_pi_tab(db_session, test_project.id)
    pi_runtime = _make_pi_runtime([{"role": "assistant", "usage": {"input": 2000, "output": 3000}}])

    with _client(db_session, pi_runtime) as tc:
        resp = tc.get(f"/api/chat/tabs/{tab.id}")

    body = resp.json()
    session = body["session"]
    assert resp.status_code == 200
    assert session["context_pct_status"] == "unknown_window"
    assert session["context_pct"] is None
    assert session["used_tokens"] is None
    assert session["window_tokens"] is None
    assert "set context_window_tokens" in (session["context_pct_reason"] or "")
