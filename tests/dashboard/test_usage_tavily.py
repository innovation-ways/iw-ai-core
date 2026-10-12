"""Tavily usage parsing and Homepage embed regression tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch import llm_usage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def tavily_usage_cache_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Keep Tavily last-good cache writes inside each test tmpdir."""
    monkeypatch.setenv("IW_CORE_TAVILY_USAGE_CACHE", str(tmp_path / "tavily-usage.json"))


@pytest.fixture
def client(db_session: Session) -> TestClient:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_tavily_usage_prefers_key_usage_and_free_tier_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_headers: dict[str, str] = {}

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> _FakeResponse:
        assert url == "https://api.tavily.com/usage"
        assert timeout == 10.0
        seen_headers.update(headers)
        return _FakeResponse({"key": {"usage": 123, "limit": 1000}})

    monkeypatch.setattr(llm_usage.httpx, "get", fake_get)
    result = llm_usage._tavily_usage_remote("secret-token")

    assert result == {"block_pct": 12, "used": 123, "total": 1000}
    assert seen_headers["Authorization"] == "Bearer secret-token"
    assert "X-Project-ID" not in seen_headers


def test_tavily_usage_falls_back_to_account_and_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, headers: dict[str, str], timeout: float) -> _FakeResponse:
        return _FakeResponse(
            {
                "key": {"usage": None, "limit": None},
                "account": {"plan_usage": 1400, "plan_limit": None},
            },
        )

    monkeypatch.setattr(llm_usage.httpx, "get", fake_get)
    assert llm_usage._tavily_usage_remote("secret-token") == {
        "block_pct": 100,
        "used": 1400,
        "total": 1000,
    }


def test_tavily_usage_uses_stale_cache_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cache_path = tmp_path / "tavily-usage.json"
    cache_path.write_text(
        '{"usage": {"block_pct": 3, "used": 30, "total": 1000}}',
    )
    monkeypatch.setenv("IW_CORE_TAVILY_USAGE_CACHE", str(cache_path))

    request = llm_usage.httpx.Request("GET", "https://api.tavily.com/usage")
    response = llm_usage.httpx.Response(429, request=request)

    def fake_get(url: str, headers: dict[str, str], timeout: float):
        raise llm_usage.httpx.HTTPStatusError(
            "rate limited",
            request=request,
            response=response,
        )

    monkeypatch.setattr(llm_usage.httpx, "get", fake_get)
    assert llm_usage._tavily_usage() == {
        "block_pct": 3,
        "used": 30,
        "total": 1000,
        "stale": True,
    }


def test_tavily_embed_renders_credit_label_and_bar(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_llm_usage() -> dict[str, object]:
        return {
            "claude": {"block_pct": 0, "week_pct": 0, "block_reset": "5h", "week_reset": "7d"},
            "minimax": {"block_pct": 0, "block_reset": "5h", "used": None, "total": None},
            "codex": {"block_pct": 0, "week_pct": 0, "status": "ok"},
            "tavily": {"block_pct": 12, "used": 123, "total": 1000},
        }

    monkeypatch.setattr("dashboard.routers.usage.get_llm_usage", fake_get_llm_usage)
    response = client.get("/api/usage/llm/embed?provider=tavily")

    assert response.status_code == 200, response.text
    assert "123 / 1000 credits" in response.text
    assert "width: 12%" in response.text
    assert 'PROVIDER = "tavily"' in response.text
