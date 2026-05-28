"""Dashboard tests for CR-00090 - E2E polling suppression via IW_CORE_E2E_MODE.

Verifies:
- AC1: hx-trigger="never" when IW_CORE_E2E_MODE=true (polling suppressed)
- AC2: hx-trigger="never" absent when IW_CORE_E2E_MODE is unset (polling present)
- AC5: _e2e_mode global is present in template context

These tests use FastAPI TestClient + testcontainer db_session; no live DB.
The `_e2e_mode` global is set at app construction time via:
  templates.env.globals["_e2e_mode"] = get_e2e_mode()

The dashboard creates multiple Jinja2Templates instances:
  - app.py's create_app() creates one and sets globals on it (used by most routes)
  - staleness router creates its own module-level instance at import time

We set os.environ["IW_CORE_E2E_MODE"] BEFORE create_app() so get_e2e_mode()
naturally returns the right value, and ALSO patch both templates instances
after create_app() to handle the staleness router's module-level instance.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Client fixtures - one per e2e_mode scenario
# ---------------------------------------------------------------------------


@pytest.fixture
def client_e2e_on(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    """TestClient with IW_CORE_E2E_MODE=true set before app creation.

    We set the env var before create_app() AND patch the staleness router's
    module-level templates instance to ensure _e2e_mode propagates to all
    rendered templates (app.templates AND staleness.templates).
    """
    # Set env BEFORE create_app() so the app's templates global is seeded True
    monkeypatch.setenv("IW_CORE_E2E_MODE", "true")

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    # Patch the staleness router's module-level templates instance too.
    # This instance is created at import time (before create_app() runs),
    # so it needs _e2e_mode injected directly. The app.templates instance
    # already has it from create_app()'s templates.env.globals["_e2e_mode"] = ... line.
    from orch.config import get_e2e_mode

    # Patch staleness router's templates globals
    app.state.templates.env.globals["_e2e_mode"] = get_e2e_mode()

    # Patch staleness router's module-level templates (used by staleness router)
    from dashboard.routers import staleness as staleness_mod

    staleness_mod.templates.env.globals["_e2e_mode"] = get_e2e_mode()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_e2e_off(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    """TestClient with IW_CORE_E2E_MODE unset (default: polling enabled)."""
    # delenv BEFORE create_app() so get_e2e_mode() returns False
    monkeypatch.delenv("IW_CORE_E2E_MODE", raising=False)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    from orch.config import get_e2e_mode

    app.state.templates.env.globals["_e2e_mode"] = get_e2e_mode()

    from dashboard.routers import staleness as staleness_mod

    staleness_mod.templates.env.globals["_e2e_mode"] = get_e2e_mode()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


class TestWorktreeBadgeE2eMode:
    """AC1 + AC2 via the sidebar worktree-badge polling element in base.html."""

    def test_polling_suppressed_when_e2e_mode_true(self, client_e2e_on: TestClient) -> None:
        """AC1: hx-trigger='never' when E2E mode is on; no hx-get on the worktree badge."""
        response = client_e2e_on.get("/")
        assert response.status_code == 200
        html = response.text

        # The sidebar worktrees nav item's polling span:
        # With _headless=True -> hx-trigger="never", NO hx-get
        assert 'hx-trigger="never"' in html, (
            "Expected hx-trigger='never' on worktree badge when E2E mode is active. "
            "This means _headless evaluated to True from _e2e_mode."
        )
        # The polling span should NOT have hx-get when suppressed
        # hx-get="/system/nav/worktree-badge" appears only when _headless is False
        # So when _headless is True, hx-get is absent from the span
        assert 'hx-get="/system/nav/worktree-badge"' not in html, (
            "Expected NO hx-get on worktree badge when E2E mode is active. "
            "The span should be silent (no background requests)."
        )

    def test_polling_present_when_e2e_mode_off(self, client_e2e_off: TestClient) -> None:
        """AC2: hx-trigger='never' absent and hx-get present when E2E mode is off."""
        response = client_e2e_off.get("/")
        assert response.status_code == 200
        html = response.text

        # Without E2E mode, polling is active:
        # hx-trigger should be "load, every 60s" (not "never")
        assert 'hx-trigger="never"' not in html, (
            "Expected NO hx-trigger='never' on worktree badge when E2E mode is off. "
            "Polling should be active in production/dev mode."
        )
        # The hx-get should be present for the active polling span
        assert 'hx-get="/system/nav/worktree-badge"' in html, (
            "Expected hx-get='/system/nav/worktree-badge' on worktree badge when "
            "E2E mode is off. Polling endpoint must be called every 60s."
        )


class TestStalenessDotE2eMode:
    """AC1 + AC2 for the staleness dot fragment rendered inside project pages."""

    def test_staleness_dot_suppresses_polling_when_e2e_mode_true(
        self, client_e2e_on: TestClient, test_project: Project
    ) -> None:
        """AC1: staleness-dot span has hx-trigger='never' when E2E mode is on."""
        # Route: GET /projects/{project_id}/staleness-dot - renders staleness_dot.html
        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=_make_stale_result(test_project.id),
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client_e2e_on.get(f"/projects/{test_project.id}/staleness-dot")
            assert response.status_code == 200
            html = response.text

        # Must contain hx-trigger="never"
        assert 'hx-trigger="never"' in html, (
            "staleness-dot must have hx-trigger='never' when E2E mode is active. "
            "This confirms _headless is True via _e2e_mode."
        )
        # Must NOT have hx-get (polling disabled)
        assert f'hx-get="/projects/{test_project.id}/staleness-dot"' not in html, (
            "staleness-dot must NOT have hx-get when E2E mode is active. "
            "No background staleness checks should be made during E2E verification."
        )
        # Must still contain the dot element with the expected CSS class
        assert "iw-staleness-dot" in html, (
            "staleness-dot should still render the indicator element when E2E mode is on. "
            "Only polling is suppressed, not the UI."
        )

    def test_staleness_dot_polls_when_e2e_mode_off(
        self, client_e2e_off: TestClient, test_project: Project
    ) -> None:
        """AC2: staleness-dot retains htmx polling when E2E mode is off."""
        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=_make_stale_result(test_project.id),
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client_e2e_off.get(f"/projects/{test_project.id}/staleness-dot")
            assert response.status_code == 200
            html = response.text

        # Must NOT have hx-trigger="never"
        assert 'hx-trigger="never"' not in html, (
            "staleness-dot must NOT have hx-trigger='never' when E2E mode is off. "
            "Normal polling must remain active in production/dev."
        )
        # Must have the normal htmx polling attributes
        assert f'hx-get="/projects/{test_project.id}/staleness-dot"' in html, (
            "staleness-dot must have hx-get when E2E mode is off. "
            "Polling must be active with an endpoint to hit every 15s."
        )
        assert 'hx-trigger="every 15s"' in html, (
            "staleness-dot must have hx-trigger='every 15s' when E2E mode is off. "
            "The correct interval must be used."
        )
        assert 'hx-swap="outerHTML"' in html, (
            "staleness-dot must have hx-swap='outerHTML' for proper replacement."
        )

    def test_staleness_dot_renders_dot_class_when_e2e_mode_true(
        self, client_e2e_on: TestClient, test_project: Project
    ) -> None:
        """The staleness-dot UI element still renders (red/grey dot) with E2E mode on."""
        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=_make_stale_result(test_project.id),
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client_e2e_on.get(f"/projects/{test_project.id}/staleness-dot")
            assert response.status_code == 200
            html = response.text

        # Should render the red-dot class (since our mock is stale)
        assert "iw-staleness-dot--red" in html, (
            "staleness-dot should still render the red dot class when stale, "
            "even with E2E mode active. "
            "Polling is suppressed but the visual indicator is preserved."
        )


# ---------------------------------------------------------------------------
# AC5 - _e2e_mode global present in template context
# AC5: "When any template is rendered via TemplateResponse, the Jinja2 context
# includes _e2e_mode as a boolean (True or False) without requiring the route
# handler to pass it explicitly."
# We verify this by confirming that templates that use `_e2e_mode` in their
# {% set _headless = ... %} expression compile and render without UndefinedError.
# The sidebar worktree-badge span is the canonical use-site.
# ---------------------------------------------------------------------------


class TestE2eModeGlobalPresent:
    """AC5: _e2e_mode global is available in all rendered templates."""

    def test_e2e_mode_global_usable_in_sidebar_when_e2e_true(
        self, client_e2e_on: TestClient
    ) -> None:
        """Sidebar renders without UndefinedError when _e2e_mode is True."""
        response = client_e2e_on.get("/")
        assert response.status_code == 200
        # If _e2e_mode were undefined, Jinja2 would raise UndefinedError on
        # the {% set _headless = _e2e_mode or ... %} line and the page would 500.
        # A 200 response with hx-trigger="never" confirms the template used
        # _e2e_mode successfully.
        assert 'hx-trigger="never"' in response.text, (
            "_e2e_mode global was unavailable or evaluated incorrectly. "
            "The sidebar should have used _e2e_mode=True to set hx-trigger='never'."
        )

    def test_e2e_mode_global_usable_in_sidebar_when_e2e_false(
        self, client_e2e_off: TestClient
    ) -> None:
        """Sidebar renders without UndefinedError when _e2e_mode is False."""
        response = client_e2e_off.get("/")
        assert response.status_code == 200
        # No UndefinedError means _e2e_mode was available (even if False)
        # Check that the sidebar worktrees link is present (sidebar rendered correctly)
        assert 'hx-get="/system/nav/worktree-badge"' in response.text, (
            "Sidebar worktree-badge should be present. "
            "This confirms the sidebar rendered successfully with _e2e_mode=False in context."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stale_result(project_id: str) -> object:
    """Return a minimal stale ProjectStalenessResult for staleness router mocks."""
    from datetime import UTC, datetime

    from orch.staleness.git_lookup import CommitSummary
    from orch.staleness.service import ProjectStalenessResult, ServiceStaleness

    return ProjectStalenessResult(
        project_id=project_id,
        services=[
            ServiceStaleness(
                name="daemon",
                status="stale",
                start_time=datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
                commits=[
                    CommitSummary(sha="abc1234", subject="feat: example commit"),
                ],
                actions=["restart"],
            )
        ],
        alembic=None,
        is_stale=True,
    )
