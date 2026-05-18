"""Integration tests for GET /api/chat/config project allowlist intersection.

Uses a real DB session (testcontainer clone) plus a mocked opencode client on
app.state to avoid launching subprocesses in CI.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers import chat as chat_mod
from orch.db.models import Project


def _healthy_runtime() -> Any:
    runtime = MagicMock()
    runtime.health = AsyncMock(return_value=True)
    return runtime


def _mock_client(
    *, providers: dict[str, Any], default_model: str = "anthropic/claude-opus-4-7"
) -> Any:
    client = MagicMock()
    client.get_config = AsyncMock(return_value={"model": default_model, "default_agent": "default"})
    client.get_providers = AsyncMock(return_value=providers)
    return client


@pytest.fixture(autouse=True)
def _clear_chat_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_mod, "_CONFIG_TTL", 0)
    chat_mod._config_cache.clear()


@pytest.fixture
def chat_client(db_session) -> Generator[TestClient, None, None]:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    app.state.opencode_runtime = _healthy_runtime()
    app.state.opencode_client = _mock_client(
        providers={
            "providers": [
                {
                    "id": "anthropic",
                    "models": {"claude-opus-4-7": {}, "claude-sonnet-4-6": {}},
                },
                {
                    "id": "openai",
                    "models": {"gpt-5.3-codex": {}, "gpt-5.2-mini": {}},
                },
            ],
            "default": {"anthropic": "claude-opus-4-7"},
        }
    )
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def test_chat_config_returns_allowlist_intersection_in_allowlist_order(
    chat_client: TestClient,
    db_session,
) -> None:
    db_session.add(
        Project(
            id="iw-ai-core",
            display_name="IW AI Core",
            repo_root="/repos/iw-ai-core",
            config={
                "ai_assistant": {
                    "models": [
                        "openai/gpt-5.3-codex",
                        "anthropic/claude-opus-4-7",
                        "ollama/gemma4:26b",
                    ],
                    "default_model": "anthropic/claude-opus-4-7",
                }
            },
        )
    )
    db_session.commit()

    resp = chat_client.get("/api/chat/config", params={"project_id": "iw-ai-core"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["models"] == ["openai/gpt-5.3-codex", "anthropic/claude-opus-4-7"]
    assert payload["default_model"] == "anthropic/claude-opus-4-7"


def test_chat_config_fail_open_when_ai_assistant_missing(
    chat_client: TestClient, db_session
) -> None:
    db_session.add(
        Project(
            id="iw-ai-core",
            display_name="IW AI Core",
            repo_root="/repos/iw-ai-core",
            config={},
        )
    )
    db_session.commit()

    resp = chat_client.get("/api/chat/config", params={"project_id": "iw-ai-core"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["models"] == [
        "anthropic/claude-opus-4-7",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-5.2-mini",
        "openai/gpt-5.3-codex",
    ]
    assert payload["default_model"] == "anthropic/claude-opus-4-7"


def test_chat_config_fail_open_for_unknown_project(chat_client: TestClient) -> None:
    resp = chat_client.get("/api/chat/config", params={"project_id": "does-not-exist"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["models"] == [
        "anthropic/claude-opus-4-7",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-5.2-mini",
        "openai/gpt-5.3-codex",
    ]
    assert payload["default_model"] == "anthropic/claude-opus-4-7"


def test_chat_config_warns_and_drops_unreachable_allowlist_entries(
    chat_client: TestClient,
    db_session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_session.add(
        Project(
            id="iw-ai-core",
            display_name="IW AI Core",
            repo_root="/repos/iw-ai-core",
            config={
                "ai_assistant": {
                    "models": [
                        "ollama/gemma4:26b",
                        "anthropic/claude-sonnet-4-6",
                    ],
                    "default_model": "ollama/gemma4:26b",
                }
            },
        )
    )
    db_session.commit()
    caplog.set_level(logging.WARNING)

    resp = chat_client.get("/api/chat/config", params={"project_id": "iw-ai-core"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["models"] == ["anthropic/claude-sonnet-4-6"]
    assert payload["default_model"] == "anthropic/claude-sonnet-4-6"
    assert any(
        "dropped unreachable models" in record.message and "ollama/gemma4:26b" in record.message
        for record in caplog.records
    ), f"Expected unreachable-model warning, got: {[r.message for r in caplog.records]}"
