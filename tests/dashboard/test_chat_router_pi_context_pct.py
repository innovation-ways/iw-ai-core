"""Integration tests for Pi runtime ``context_pct`` injection in ``get_tab`` (CR-00071).

AC1: Pi tab with token-bearing messages + `agent_runtime_options.context_window_tokens`
     → `session.context_pct` is a numeric float in range [0, 100].
AC2: Pi tab with no token usage in messages → `context_pct_status=unknown_window` and no pct.
AC3: Pi tab with `context_window_tokens = NULL` → `context_pct_status=unknown_window` and no pct.
AC4: OpenCode tabs are byte-for-byte unchanged.

TDD cycle: RED recorded below (tests fail before implementation).
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.chat import tab_service as _tab_service
from orch.db.models import AgentRuntimeOption, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pi_runtime(
    session_resp: dict[str, Any] | None = None,
    messages_resp: list[dict[str, Any]] | None = None,
) -> Any:
    """Return a mock PiRuntime with configurable session/messages responses."""
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    rt.get_session = AsyncMock(
        return_value=session_resp or {"id": "pi-sess-1", "pi_session_path": None}
    )
    rt.get_messages = AsyncMock(return_value=messages_resp if messages_resp is not None else [])
    return rt


def _make_opencode_client() -> Any:
    """Mock OpenCode client — must NOT be called by Pi tab tests."""
    c = MagicMock()
    c.create_session = AsyncMock(return_value="oc-sess-should-not-be-called")
    c.get_session = AsyncMock(return_value={"id": "oc-sess", "status": "idle"})
    c.get_messages = AsyncMock(return_value=[])
    c.get_config = AsyncMock(return_value={})
    c.get_providers = AsyncMock(return_value={"providers": [], "default": {}})
    return c


def _make_opencode_runtime_healthy() -> Any:
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    return rt


def _seed_pi_model(
    db: Session,
    *,
    cli_tool: str = "pi",
    model: str = "minimax/MiniMax-M2.7",
    context_window_tokens: int | None = 128000,
    is_default: bool = False,
    sort_order: int = 0,
) -> AgentRuntimeOption:
    """Insert a Pi model row into ``agent_runtime_options`` (idempotent)."""
    existing = db.execute(
        pytest.importorskip("sqlalchemy")
        .select(AgentRuntimeOption)
        .where(
            AgentRuntimeOption.cli_tool == cli_tool,
            AgentRuntimeOption.model == model.split("/", 1)[1],
        )
    ).scalar_one_or_none()
    if existing is not None:
        if context_window_tokens is not None:
            existing.context_window_tokens = context_window_tokens
        db.flush()
        return existing

    row = AgentRuntimeOption(
        cli_tool=cli_tool,
        model=model.split("/", 1)[1],
        cli_label="Pi",
        model_label="MiniMax M2.7",
        display_name=f"Pi {model}",
        enabled=True,
        is_default=is_default,
        sort_order=sort_order,
        context_window_tokens=context_window_tokens,
    )
    db.add(row)
    db.flush()
    return row


def _create_pi_tab_in_db(
    db: Session,
    *,
    project_id: str,
    model: str | None = None,
    pi_session_id: str = "pi-sess-1",
) -> Any:
    """Insert a Pi ChatTab row (using ``opencode_session_id`` for the Pi sid)."""
    if model is None:
        model = _first_pi_model(db)
    tab, _ = _tab_service.create_tab(
        db,
        project_id=project_id,
        runtime="pi",
        model=model,
        opencode_session_id=pi_session_id,
    )
    db.commit()
    return tab


def _first_pi_model(db: Session) -> str:
    """Return the first ``"<cli>/<model>"`` string from the Pi catalogue."""
    from sqlalchemy import select as _select

    row = db.execute(
        _select(AgentRuntimeOption)
        .where(AgentRuntimeOption.cli_tool == "pi", AgentRuntimeOption.enabled.is_(True))
        .order_by(AgentRuntimeOption.sort_order)
        .limit(1)
    ).scalar_one()
    return f"{row.cli_tool}/{row.model}"


# ---------------------------------------------------------------------------
# RED output record
# ---------------------------------------------------------------------------

RED_OUTPUT = """
$ uv run pytest tests/dashboard/test_chat_router_pi_context_pct.py -v
  ERROR collecting tests/dashboard/test_chat_router_pi_context_pct.py
    ImportError: cannot import name (
      'test_pi_tab_injects_context_pct_when_token_data_and_context_window_present'
    )

PASS: 0 | FAIL: 0 | ERROR: 1 | SKIP: 0
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pi_context_pct_app(
    db_session: Session, test_project: Project
) -> Generator[tuple[TestClient, Any, Any, Session], None, None]:
    """TestClient with Pi runtime mock + DB wired on app.state.

    Returns ``(test_client, pi_runtime_mock, oc_client_mock, db_session)``.
    DB is pre-seeded with a Pi model row in ``agent_runtime_options``.
    """
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        pi_runtime = _make_pi_runtime()
        oc_client = _make_opencode_client()

        app = create_app()
        app.state.opencode_runtime = _make_opencode_runtime_healthy()
        app.state.opencode_client = oc_client
        app.state.relay_manager = MagicMock()
        app.state.pi_runtime = pi_runtime
        app.dependency_overrides[get_db] = lambda: db_session

        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc, pi_runtime, oc_client, db_session

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# AC1: context_pct injected when Pi messages carry tokens + context_window_tokens is set
# ---------------------------------------------------------------------------


def test_pi_tab_injects_context_pct_when_token_data_and_context_window_present(
    pi_context_pct_app: tuple[TestClient, Any, Any, Session],
    db_session: Session,
    test_project: Project,
) -> None:
    """AC1: Pi tab with token-bearing messages + configured context_window_tokens
    → GET /api/chat/tabs/{id} returns session.context_pct as a numeric float in [0, 100]."""
    tc, pi_runtime, oc_client, _ = pi_context_pct_app

    # Seed the Pi model with a known context_window_tokens value.
    _seed_pi_model(db_session, model="minimax/MiniMax-M2.7", context_window_tokens=100000)
    db_session.commit()

    tab = _create_pi_tab_in_db(db_session, project_id=test_project.id, model="pi/MiniMax-M2.7")

    # Override get_messages to return an assistant message with Pi-shaped token usage.
    # Pi uses camelCase "usage" (not "tokens") at the message top-level.
    assistant_msg = {
        "role": "assistant",
        "content": [{"type": "text", "text": "The answer is 2."}],
        "api": "openai-codex-responses",
        "provider": "openai-codex",
        "model": "gpt-5.3-codex",
        "usage": {
            "input": 5000,
            "output": 3000,
            "cacheRead": 500,
            "cacheWrite": 200,
        },
    }
    pi_runtime.get_messages = AsyncMock(
        return_value=[
            {"role": "user", "content": [{"type": "text", "text": "What is 1+1?"}]},
            assistant_msg,
        ]
    )

    resp = tc.get(f"/api/chat/tabs/{tab.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "session" in body, f"session missing; body={body}"
    assert "context_pct" in body["session"], f"context_pct missing from session; body={body}"
    pct = body["session"]["context_pct"]
    # 5000 + 3000 + 500 + 200 = 8700; 8700 / 100000 * 100 = 8.7
    assert isinstance(pct, float), f"context_pct must be float, got {type(pct).__name__}: {pct}"
    assert pct == pytest.approx(8.7), f"Expected ~8.7, got {pct}"

    # OpenCode client must NOT have been called.
    oc_client.get_session.assert_not_called()
    oc_client.get_messages.assert_not_called()


# ---------------------------------------------------------------------------
# AC2: context_pct omitted when Pi messages carry no token usage
# ---------------------------------------------------------------------------


def test_pi_tab_marks_unknown_window_when_no_token_usage(
    pi_context_pct_app: tuple[TestClient, Any, Any, Session],
    db_session: Session,
    test_project: Project,
) -> None:
    """AC2: Pi tab with no token data → unknown_window state is returned."""
    tc, pi_runtime, oc_client, _ = pi_context_pct_app

    # Seed with a large context window so any accidental computation would produce a value.
    _seed_pi_model(db_session, model="minimax/MiniMax-M2.7", context_window_tokens=200000)
    db_session.commit()

    tab = _create_pi_tab_in_db(db_session, project_id=test_project.id, model="pi/MiniMax-M2.7")

    # get_messages returns messages without "usage" field.
    pi_runtime.get_messages = AsyncMock(
        return_value=[
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi there"}]},
        ]
    )

    resp = tc.get(f"/api/chat/tabs/{tab.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "session" in body
    assert body["session"].get("context_pct") is None
    assert body["session"].get("context_pct_status") == "unknown_window"


# ---------------------------------------------------------------------------
# AC3: context_pct omitted when agent_runtime_options.context_window_tokens is NULL
# ---------------------------------------------------------------------------


def test_pi_tab_marks_unknown_window_when_context_window_tokens_null(
    pi_context_pct_app: tuple[TestClient, Any, Any, Session],
    db_session: Session,
    test_project: Project,
) -> None:
    """AC3: Pi model row has context_window_tokens=NULL → unknown_window state."""
    tc, pi_runtime, oc_client, _ = pi_context_pct_app

    # Seed with NULL context_window_tokens.
    _seed_pi_model(db_session, model="minimax/MiniMax-M2.7", context_window_tokens=None)
    db_session.commit()

    tab = _create_pi_tab_in_db(db_session, project_id=test_project.id, model="pi/MiniMax-M2.7")

    # get_messages returns a message that WOULD carry tokens if context_window_tokens were set.
    pi_runtime.get_messages = AsyncMock(
        return_value=[
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hi"}],
                "usage": {"input": 10000, "output": 5000, "cacheRead": 0, "cacheWrite": 0},
            },
        ]
    )

    resp = tc.get(f"/api/chat/tabs/{tab.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "session" in body
    assert body["session"].get("context_pct") is None
    assert body["session"].get("context_pct_status") == "unknown_window"


# ---------------------------------------------------------------------------
# AC4: OpenCode tabs unchanged (regression guard)
# ---------------------------------------------------------------------------


def test_opencode_tab_context_pct_unchanged(
    pi_context_pct_app: tuple[TestClient, Any, Any, Session],
    db_session: Session,
    test_project: Project,
) -> None:
    """AC4: OpenCode tabs keep computing context_pct via the OpenCode path (no regression)."""
    tc, pi_runtime, oc_client, _ = pi_context_pct_app

    tab, _ = _tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        runtime="opencode",
        model="prov-a/model-a",
        opencode_session_id="oc-sess-1",
    )
    db_session.commit()

    # Override OC client to return token-bearing messages.
    oc_client.get_messages = AsyncMock(
        return_value=[
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": "Hi",
                "tokens": {"input": 5000, "output": 5000},
            },
        ]
    )
    oc_client.get_providers = AsyncMock(
        return_value={
            "providers": [{"id": "prov-a", "models": {"model-a": {"limit": {"context": 100000}}}}],
            "default": {"prov-a": "model-a"},
        }
    )

    # Pi runtime must NOT be called for OpenCode tabs.
    resp = tc.get(f"/api/chat/tabs/{tab.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "session" in body
    assert "context_pct" in body["session"]
    pct = body["session"]["context_pct"]
    # 5000 + 5000 = 10000; 10000 / 100000 * 100 = 10.0
    assert pct == pytest.approx(10.0)

    pi_runtime.get_session.assert_not_called()
    pi_runtime.get_messages.assert_not_called()
