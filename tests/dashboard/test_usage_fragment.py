"""Rendering regression tests for I-00120 — Codex usage footer warning states.

Drives GET /api/usage/llm/fragment via TestClient and asserts the rendered HTML
contains specific warning phrases and CSS classes per codex status, and that the
normal bars are absent in warning states.

Uses attribute-scoped / specific-phrase assertions (not bare ambiguous substrings).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture — file-local, copied from existing dashboard test patterns
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _codex_spans(soup: BeautifulSoup) -> list[str]:
    """Return all text spans inside the Codex section (ignoring plan_type label)."""
    codex_parts: list[str] = []
    for el in soup.find_all("span"):
        txt = el.get_text().strip()
        if txt:
            codex_parts.append(txt)
    return codex_parts


def _codex_section_html(soup: BeautifulSoup) -> str:
    """Return the substring of the HTML that belongs to the Codex section."""
    all_text = str(soup)
    # Find the Codex label span and grab everything from there to the next · separator
    idx = all_text.find("Codex")
    if idx == -1:
        return ""
    # Grab up to 1500 chars from the Codex label — enough to cover the bars + warning
    return all_text[idx : idx + 1500]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCodexFragmentExpired:
    """Fragment renders correct warning for codex status == 'expired'."""

    def test_expired_status_shows_warning_and_bars_absent(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """status=expired → warning phrase in text-amber-600; Codex bars absent."""
        codex_data = {
            "block_pct": 0,
            "week_pct": 0,
            "block_reset": None,
            "week_reset": None,
            "plan_type": None,
            "status": "expired",
        }

        def fake_get_llm_usage() -> dict[str, object]:
            """Return fake LLM usage data for testing."""
            return {
                "claude": {"block_pct": 0, "week_pct": 0, "block_reset": "5h", "week_reset": "7d"},
                "minimax": {"block_pct": 0, "block_reset": "5h", "used": None, "total": None},
                "codex": codex_data,
            }

        monkeypatch.setattr("dashboard.routers.usage.get_llm_usage", fake_get_llm_usage)
        response = client.get("/api/usage/llm/fragment")
        assert response.status_code == 200, response.text
        html = response.text
        soup = _soup(html)

        # 1. Warning phrase contains the specific expired message
        assert "token expired" in html, (
            f"HTML does not contain warning phrase 'token expired'. HTML snippet:\n{html[:800]}"
        )
        assert "re-authenticate" in html, (
            f"HTML does not contain 're-authenticate'. HTML snippet:\n{html[:800]}"
        )

        # 2. Warning uses text-amber-600 (the designated warning colour)
        assert "text-amber-600" in html, (
            f"'text-amber-600' not found in HTML. HTML snippet:\n{html[:800]}"
        )

        # 3. Codex bars are NOT rendered in the expired state (warning replaces them)
        codex_html_str = str(soup)
        idx = codex_html_str.find("Codex")
        assert idx != -1
        codex_section = codex_html_str[idx : idx + 600]
        # In the warning state the ⚠ span replaces both bar divs — strip the
        # warning span before checking that no bar-with-w-20 class appears.
        import re

        codex_bars_only = re.sub(
            r'<span class="hidden sm:flex items-center gap-1 text-amber[^"]*">[\s\S]*?</span>',
            "",
            codex_section,
        )
        # The two bar divs (w-20) for block + week pct → absent in expired/error/unauthenticated
        assert "w-20" not in codex_bars_only, (
            "Progress-bar containers (w-20) must not appear in expired state."
        )


class TestCodexFragmentUnauthenticated:
    """Fragment renders correct warning for codex status == 'unauthenticated'."""

    def test_unauthenticated_status_shows_not_configured_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """status=unauthenticated → 'not configured' phrase in HTML."""
        codex_data = {
            "block_pct": 0,
            "week_pct": 0,
            "block_reset": None,
            "week_reset": None,
            "plan_type": None,
            "status": "unauthenticated",
        }

        def fake_get_llm_usage() -> dict[str, object]:
            """Return fake LLM usage data for testing."""
            return {
                "claude": {"block_pct": 0, "week_pct": 0, "block_reset": "5h", "week_reset": "7d"},
                "minimax": {"block_pct": 0, "block_reset": "5h", "used": None, "total": None},
                "codex": codex_data,
            }

        monkeypatch.setattr("dashboard.routers.usage.get_llm_usage", fake_get_llm_usage)
        response = client.get("/api/usage/llm/fragment")
        assert response.status_code == 200, response.text
        html = response.text
        assert "not configured" in html, (
            f"Expected 'not configured' warning for unauthenticated. HTML snippet:\n{html[:600]}"
        )
        # Must also include the opencode auth instruction phrase
        assert "opencode auth login" in html, (
            f"Expected 'opencode auth login' instruction. HTML snippet:\n{html[:600]}"
        )
        # And it must be in the amber warning colour
        assert "text-amber-600" in html


class TestCodexFragmentError:
    """Fragment renders correct warning for codex status == 'error'."""

    def test_error_status_shows_usage_unavailable_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """status=error → 'usage unavailable' phrase in HTML."""
        codex_data = {
            "block_pct": 0,
            "week_pct": 0,
            "block_reset": None,
            "week_reset": None,
            "plan_type": None,
            "status": "error",
        }

        def fake_get_llm_usage() -> dict[str, object]:
            """Return fake LLM usage data for testing."""
            return {
                "claude": {"block_pct": 0, "week_pct": 0, "block_reset": "5h", "week_reset": "7d"},
                "minimax": {"block_pct": 0, "block_reset": "5h", "used": None, "total": None},
                "codex": codex_data,
            }

        monkeypatch.setattr("dashboard.routers.usage.get_llm_usage", fake_get_llm_usage)
        response = client.get("/api/usage/llm/fragment")
        assert response.status_code == 200, response.text
        html = response.text
        assert "usage unavailable" in html, (
            f"Expected 'usage unavailable' warning for error status. HTML snippet:\n{html[:600]}"
        )
        # Must be in amber warning colour
        assert "text-amber-600" in html


class TestCodexFragmentOk:
    """Fragment renders normal bars (no warning) for codex status == 'ok'."""

    def test_ok_status_shows_bars_and_no_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """status=ok → percentage bars rendered; no ⚠ or warning phrases."""
        codex_data = {
            "block_pct": 47,
            "week_pct": 12,
            "block_reset": "5h 0m",
            "week_reset": "7d 0m",
            "plan_type": "plus",
            "status": "ok",
        }

        def fake_get_llm_usage() -> dict[str, object]:
            """Return fake LLM usage data for testing."""
            return {
                "claude": {"block_pct": 0, "week_pct": 0, "block_reset": "5h", "week_reset": "7d"},
                "minimax": {"block_pct": 0, "block_reset": "5h", "used": None, "total": None},
                "codex": codex_data,
            }

        monkeypatch.setattr("dashboard.routers.usage.get_llm_usage", fake_get_llm_usage)
        response = client.get("/api/usage/llm/fragment")
        assert response.status_code == 200, response.text
        html = response.text
        soup = _soup(html)

        # 1. Codex bars ARE present (at least one style=width:N% div in the Codex section)
        codex_html_str = str(soup)
        idx = codex_html_str.find("Codex")
        assert idx != -1, "Codex label not found in HTML"
        codex_section = codex_html_str[idx : idx + 600]
        snippet = codex_section[:300]
        assert "width:" in codex_section, (
            f"No percentage bar found in Codex section for ok status. Snippet:\n{snippet}"
        )

        # 2. No ⚠ in the OK state (warning must be absent)
        assert "⚠" not in codex_section, (
            f"Warning icon ⚠ must not appear in ok status. Codex section:\n{codex_section[:300]}"
        )

        # 3. No amber warning class in the OK state
        assert "text-amber-600" not in codex_section, (
            f"'text-amber-600' must not appear in ok status. Codex section:\n{codex_section[:300]}"
        )

        # 4. No warning phrases in the Codex section for ok status
        assert "token expired" not in codex_section
        assert "not configured" not in codex_section
        assert "usage unavailable" not in codex_section

    def test_ok_zero_pct_still_shows_bars_no_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """status=ok but block_pct=0 (genuine zero usage) → bars at 0% but no warning."""
        codex_data = {
            "block_pct": 0,
            "week_pct": 0,
            "block_reset": "5h 0m",
            "week_reset": "7d 0m",
            "plan_type": "free",
            "status": "ok",
        }

        def fake_get_llm_usage() -> dict[str, object]:
            """Return fake LLM usage data for testing."""
            return {
                "claude": {"block_pct": 0, "week_pct": 0, "block_reset": "5h", "week_reset": "7d"},
                "minimax": {"block_pct": 0, "block_reset": "5h", "used": None, "total": None},
                "codex": codex_data,
            }

        monkeypatch.setattr("dashboard.routers.usage.get_llm_usage", fake_get_llm_usage)
        response = client.get("/api/usage/llm/fragment")
        assert response.status_code == 200, response.text
        html = response.text

        # Even with 0% usage (genuine), bars are shown (width:0%) — no warning
        assert "width: 0%" in html, (
            f"0% bars must appear for genuine zero-usage ok state. HTML snippet:\n{html[:500]}"
        )
        # Warning phrases are absent
        assert "⚠" not in html
        assert "token expired" not in html
        assert "not configured" not in html
        assert "usage unavailable" not in html
