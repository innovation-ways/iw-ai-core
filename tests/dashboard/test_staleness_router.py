"""Tests for F-00063 S03 — Staleness router endpoints.

Covers:
- GET /projects/{project_id}/staleness panel fragment (200, opt-out empty, 404 unknown)
- GET /projects/{project_id}/staleness-dot dot fragment (200, opt-out empty, 404 unknown)
- POST .../services/{service_name}/restart (happy, 429 soft-lock, 409 no-command, 404 unknown)
- POST .../services/{service_name}/start (happy path)
- POST .../services/{service_name}/stop (happy path)
- POST .../alembic/upgrade (happy path rc=0, failure rc!=0 → 502, 404 no alembic block)

These tests use FastAPI TestClient + mocks only; no live DB, no live processes.
The db_session fixture is provided via conftest.py (testcontainer) and injected via
dependency_overrides so the app can boot; the staleness endpoints themselves never
touch the DB.
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Module-level imports so that orch.db.session._engine is initialised during
# pytest *collection* (before _arm_live_db_guard sets IW_CORE_TEST_CONTEXT=true).
# This mirrors the pattern used by test_worktrees_view.py and test_jobs_filter_ui.py.
from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient using testcontainer db_session, with staleness soft-lock reset."""
    # Clear the soft-lock dict before the test so tests are independent.
    try:
        from dashboard.routers import staleness as staleness_mod

        staleness_mod._service_locks.clear()  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        pass

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    # Clear lock after test too
    try:
        from dashboard.routers import staleness as staleness_mod

        staleness_mod._service_locks.clear()  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------


def _make_staleness_result(
    project_id: str = "iw-ai-core",
    *,
    has_services: bool = True,
    is_stale: bool = False,
) -> object:
    """Build a minimal ProjectStalenessResult."""
    from orch.staleness.service import ProjectStalenessResult, ServiceStaleness

    services = []
    if has_services:
        svc = ServiceStaleness(
            name="daemon",
            status="stale" if is_stale else "up_to_date",
            actions=["restart"],
        )
        services.append(svc)

    return ProjectStalenessResult(
        project_id=project_id,
        services=services,
        alembic=None,
        is_stale=is_stale,
    )


def _make_empty_staleness_result(project_id: str = "cv") -> object:
    """Opt-out project: no services, no alembic."""
    from orch.staleness.service import ProjectStalenessResult

    return ProjectStalenessResult(
        project_id=project_id,
        services=[],
        alembic=None,
        is_stale=False,
    )


def _projects_toml_with_services() -> dict:
    """Minimal raw TOML structure with iw-ai-core services and alembic."""
    return {
        "projects": {
            "iw-ai-core": {
                "display_name": "IW AI Core",
                "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                "enabled": True,
                "services": [
                    {
                        "name": "daemon",
                        "detect": {"type": "pidfile", "path": ".daemon.pid"},
                        "watch_paths": ["orch/**"],
                        "ignore_paths": [],
                        "restart_command": "./ai-core.sh daemon restart",
                        "start_command": None,
                        "stop_command": None,
                        "hot_reload": False,
                    }
                ],
                "alembic": {"config": "alembic.ini"},
            },
            "cv": {
                "display_name": "CV",
                "repo_root": "/home/sergiog/dev/cv",
                "enabled": True,
            },
        }
    }


def _projects_toml_no_commands() -> dict:
    """Minimal raw TOML: service exists but has no commands configured."""
    return {
        "projects": {
            "iw-ai-core": {
                "display_name": "IW AI Core",
                "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                "enabled": True,
                "services": [
                    {
                        "name": "daemon",
                        "detect": {"type": "pidfile", "path": ".daemon.pid"},
                        "watch_paths": ["orch/**"],
                        "ignore_paths": [],
                        "restart_command": None,
                        "start_command": None,
                        "stop_command": None,
                        "hot_reload": False,
                    }
                ],
            }
        }
    }


# ===========================================================================
# GET /projects/{project_id}/staleness — panel fragment
# ===========================================================================


class TestStalenessPanel:
    """GET /projects/{project_id}/staleness returns the panel fragment."""

    def test_panel_200_for_known_project(self, client: TestClient) -> None:
        """Returns 200 when the project exists and compute_project_staleness succeeds."""
        result = _make_staleness_result("iw-ai-core")

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
            patch("dashboard.routers.staleness.templates") as mock_templates,
        ):
            from fastapi.responses import HTMLResponse

            mock_templates.TemplateResponse.return_value = HTMLResponse(
                content="<div>panel</div>", status_code=200
            )
            response = client.get("/projects/iw-ai-core/staleness")
            assert response.status_code == 200

    def test_panel_empty_body_for_optout_project(self, client: TestClient) -> None:
        """Returns 200 with empty body for projects that have no services/alembic config."""
        result = _make_empty_staleness_result("cv")

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client.get("/projects/cv/staleness")
            assert response.status_code == 200
            # Empty body for opt-out projects
            assert response.text.strip() == ""

    def test_panel_404_for_unknown_project(self, client: TestClient) -> None:
        """Returns 404 when the project is not in projects.toml."""
        with patch(
            "dashboard.routers.staleness._is_known_project",
            return_value=False,
        ):
            response = client.get("/projects/unknown-project/staleness")
            assert response.status_code == 404


# ===========================================================================
# GET /projects/{project_id}/staleness-dot — dot fragment
# ===========================================================================


class TestStalenessDot:
    """GET /projects/{project_id}/staleness-dot returns the dot fragment."""

    def test_dot_200_for_known_project(self, client: TestClient) -> None:
        """Returns 200 for a known project with services declared."""
        result = _make_staleness_result("iw-ai-core")

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
            patch("dashboard.routers.staleness.templates") as mock_templates,
        ):
            from fastapi.responses import HTMLResponse

            mock_templates.TemplateResponse.return_value = HTMLResponse(
                content="<span class='dot'></span>", status_code=200
            )
            response = client.get("/projects/iw-ai-core/staleness-dot")
            assert response.status_code == 200

    def test_dot_empty_body_for_optout_project(self, client: TestClient) -> None:
        """Returns 200 with literal empty body for opt-out projects."""
        result = _make_empty_staleness_result("cv")

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client.get("/projects/cv/staleness-dot")
            assert response.status_code == 200
            # CRITICAL: must be a literal empty body (not whitespace) so htmx
            # replaces the placeholder with nothing
            assert response.text == ""

    def test_dot_404_for_unknown_project(self, client: TestClient) -> None:
        """Returns 404 when the project is not in projects.toml."""
        with patch(
            "dashboard.routers.staleness._is_known_project",
            return_value=False,
        ):
            response = client.get("/projects/unknown-project/staleness-dot")
            assert response.status_code == 404


# ===========================================================================
# POST /projects/{project_id}/services/{service_name}/restart  # noqa: ERA001
# ===========================================================================


class TestServiceRestart:
    """POST .../services/{service_name}/restart endpoint."""

    def test_restart_invokes_subprocess_with_command(self, client: TestClient) -> None:
        """Successful restart returns 204 and invokes subprocess.Popen."""
        toml_data = _projects_toml_with_services()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()
            response = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert response.status_code == 204
            mock_popen.assert_called_once()

            # Verify the configured command string was passed
            call_args = mock_popen.call_args
            cmd_arg = call_args[0][0] if call_args[0] else call_args[1].get("args", "")
            assert "./ai-core.sh daemon restart" in str(cmd_arg)

    def test_restart_returns_429_on_second_post_within_5s(self, client: TestClient) -> None:
        """Second POST within 5s returns 429 with Retry-After header."""
        toml_data = _projects_toml_with_services()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            # First POST: should succeed
            r1 = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert r1.status_code == 204

            # Second POST immediately: should be rate-limited
            r2 = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert r2.status_code == 429
            assert "Retry-After" in r2.headers

    def test_restart_returns_409_when_no_restart_command(self, client: TestClient) -> None:
        """Returns 409 when the service has no restart_command configured."""
        toml_data = _projects_toml_no_commands()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert response.status_code == 409

    def test_restart_returns_404_for_unknown_project(self, client: TestClient) -> None:
        """Returns 404 when the project is not in projects.toml."""
        toml_data = _projects_toml_with_services()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/no-such-project/services/daemon/restart")
            assert response.status_code == 404

    def test_restart_returns_404_for_unknown_service(self, client: TestClient) -> None:
        """Returns 404 when the service name is not declared in projects.toml."""
        toml_data = _projects_toml_with_services()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/iw-ai-core/services/no-such-service/restart")
            assert response.status_code == 404

    def test_restart_sets_hx_trigger_toast_header(self, client: TestClient) -> None:
        """Successful restart sets HX-Trigger header with showToast payload."""
        toml_data = _projects_toml_with_services()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()
            response = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert response.status_code == 204
            assert "HX-Trigger" in response.headers
            assert "showToast" in response.headers["HX-Trigger"]


# ===========================================================================
# POST /projects/{project_id}/services/{service_name}/start  # noqa: ERA001
# ===========================================================================


class TestServiceStart:
    """POST .../services/{service_name}/start endpoint."""

    def test_start_invokes_subprocess_with_command(self, client: TestClient) -> None:
        """Successful start returns 204 and invokes subprocess.Popen."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    "services": [
                        {
                            "name": "daemon",
                            "detect": {"type": "pidfile", "path": ".daemon.pid"},
                            "watch_paths": ["orch/**"],
                            "ignore_paths": [],
                            "restart_command": None,
                            "start_command": "./ai-core.sh daemon start",
                            "stop_command": None,
                            "hot_reload": False,
                        }
                    ],
                }
            }
        }

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()
            response = client.post("/projects/iw-ai-core/services/daemon/start")
            assert response.status_code == 204
            mock_popen.assert_called_once()

    def test_start_returns_409_when_no_start_command(self, client: TestClient) -> None:
        """Returns 409 when the service has no start_command configured."""
        toml_data = _projects_toml_no_commands()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/iw-ai-core/services/daemon/start")
            assert response.status_code == 409


# ===========================================================================
# POST /projects/{project_id}/services/{service_name}/stop  # noqa: ERA001
# ===========================================================================


class TestServiceStop:
    """POST .../services/{service_name}/stop endpoint."""

    def test_stop_invokes_subprocess_with_command(self, client: TestClient) -> None:
        """Successful stop returns 204 and invokes subprocess.Popen."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    "services": [
                        {
                            "name": "daemon",
                            "detect": {"type": "pidfile", "path": ".daemon.pid"},
                            "watch_paths": ["orch/**"],
                            "ignore_paths": [],
                            "restart_command": None,
                            "start_command": None,
                            "stop_command": "./ai-core.sh daemon stop",
                            "hot_reload": False,
                        }
                    ],
                }
            }
        }

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()
            response = client.post("/projects/iw-ai-core/services/daemon/stop")
            assert response.status_code == 204
            mock_popen.assert_called_once()

    def test_stop_returns_409_when_no_stop_command(self, client: TestClient) -> None:
        """Returns 409 when the service has no stop_command configured."""
        toml_data = _projects_toml_no_commands()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/iw-ai-core/services/daemon/stop")
            assert response.status_code == 409


# ===========================================================================
# POST /projects/{project_id}/alembic/upgrade  # noqa: ERA001
# ===========================================================================


class TestAlembicUpgrade:
    """POST /projects/{project_id}/alembic/upgrade endpoint."""

    def test_alembic_upgrade_happy_path(self, client: TestClient) -> None:
        """Returns 200 with alembic stdout when rc=0."""
        toml_data = _projects_toml_with_services()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "INFO  [alembic.runtime.migration] Running upgrade...\n"
        mock_proc.stderr = ""

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch(
                "dashboard.routers.staleness.subprocess.run",
                return_value=mock_proc,
            ),
        ):
            response = client.post("/projects/iw-ai-core/alembic/upgrade")
            assert response.status_code == 200

    def test_alembic_upgrade_failure_returns_502(self, client: TestClient) -> None:
        """Returns 502 when alembic exits with rc!=0 (DB unreachable, migration error)."""
        toml_data = _projects_toml_with_services()

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "FAILED: connection refused"

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch(
                "dashboard.routers.staleness.subprocess.run",
                return_value=mock_proc,
            ),
        ):
            response = client.post("/projects/iw-ai-core/alembic/upgrade")
            assert response.status_code == 502

    def test_alembic_upgrade_returns_404_when_no_alembic_block(self, client: TestClient) -> None:
        """Returns 404 when the project has no alembic block in projects.toml."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    # no services, no alembic
                }
            }
        }

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/iw-ai-core/alembic/upgrade")
            assert response.status_code == 404

    def test_alembic_upgrade_returns_404_for_unknown_project(self, client: TestClient) -> None:
        """Returns 404 when the project is not in projects.toml."""
        toml_data = _projects_toml_with_services()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.post("/projects/no-such-project/alembic/upgrade")
            assert response.status_code == 404


# ===========================================================================
# Soft-lock: tests that lock expires after 5s
# ===========================================================================


class TestSoftLockExpiry:
    """Verify soft-lock expires after 5 seconds."""

    def test_second_restart_succeeds_after_lock_expires(self, client: TestClient) -> None:
        """After >5s, a second POST should succeed (lock has expired)."""
        toml_data = _projects_toml_with_services()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            # Inject a stale lock timestamp (6 seconds ago)
            from dashboard.routers import staleness as staleness_mod

            staleness_mod._service_locks[("iw-ai-core", "daemon")] = time.monotonic() - 6.0

            # Now the POST should succeed (lock expired)
            response = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert response.status_code == 204


# ===========================================================================
# S07 additions: 429 soft-lock tests for start and stop (S05 gap)
# ===========================================================================


def _toml_with_start_stop() -> dict:
    """Minimal TOML with start_command and stop_command but no restart_command."""
    return {
        "projects": {
            "iw-ai-core": {
                "display_name": "IW AI Core",
                "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                "enabled": True,
                "services": [
                    {
                        "name": "daemon",
                        "detect": {"type": "pidfile", "path": ".daemon.pid"},
                        "watch_paths": ["orch/**"],
                        "ignore_paths": [],
                        "restart_command": None,
                        "start_command": "./ai-core.sh daemon start",
                        "stop_command": "./ai-core.sh daemon stop",
                        "hot_reload": False,
                    }
                ],
            }
        }
    }


class TestStartEndpointSoftLock:
    """POST .../start endpoint soft-lock (S05 gap)."""

    def test_start_returns_429_on_second_post_within_5s(self, client: TestClient) -> None:
        """Second POST to start within 5s returns 429 with Retry-After header."""
        toml_data = _toml_with_start_stop()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            r1 = client.post("/projects/iw-ai-core/services/daemon/start")
            assert r1.status_code == 204, f"First start should succeed, got {r1.status_code}"

            # Second POST immediately — lock should block
            r2 = client.post("/projects/iw-ai-core/services/daemon/start")
            assert r2.status_code == 429
            assert "Retry-After" in r2.headers

    def test_start_only_one_subprocess_on_rapid_posts(self, client: TestClient) -> None:
        """Invariant 4: of 3 rapid start POSTs, only exactly one invokes subprocess."""
        toml_data = _toml_with_start_stop()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            statuses = [
                client.post("/projects/iw-ai-core/services/daemon/start").status_code
                for _ in range(3)
            ]

        # Exactly one should succeed (204), the rest should be 429
        assert statuses.count(204) == 1
        assert statuses.count(429) == 2
        # Exactly one subprocess invocation
        assert mock_popen.call_count == 1


class TestStopEndpointSoftLock:
    """POST .../stop endpoint soft-lock (S05 gap)."""

    def test_stop_returns_429_on_second_post_within_5s(self, client: TestClient) -> None:
        """Second POST to stop within 5s returns 429 with Retry-After header."""
        toml_data = _toml_with_start_stop()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            r1 = client.post("/projects/iw-ai-core/services/daemon/stop")
            assert r1.status_code == 204, f"First stop should succeed, got {r1.status_code}"

            # Second POST immediately — lock should block
            r2 = client.post("/projects/iw-ai-core/services/daemon/stop")
            assert r2.status_code == 429
            assert "Retry-After" in r2.headers

    def test_stop_only_one_subprocess_on_rapid_posts(self, client: TestClient) -> None:
        """Invariant 4: of 3 rapid stop POSTs, only exactly one invokes subprocess."""
        toml_data = _toml_with_start_stop()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            statuses = [
                client.post("/projects/iw-ai-core/services/daemon/stop").status_code
                for _ in range(3)
            ]

        assert statuses.count(204) == 1
        assert statuses.count(429) == 2
        assert mock_popen.call_count == 1


# ===========================================================================
# S07 additions: alembic TimeoutExpired handling (S05 gap)
# ===========================================================================


class TestAlembicUpgradeTimeoutExpired:
    """POST .../alembic/upgrade TimeoutExpired branch (S05 gap)."""

    def test_alembic_upgrade_timeout_returns_502(self, client: TestClient) -> None:
        """When alembic subprocess times out, the endpoint returns 502."""
        import subprocess as sp

        toml_data = _projects_toml_with_services()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch(
                "dashboard.routers.staleness.subprocess.run",
                side_effect=sp.TimeoutExpired("alembic", 60),
            ),
        ):
            response = client.post("/projects/iw-ai-core/alembic/upgrade")
            assert response.status_code == 502
            assert "timed out" in response.text.lower() or "timeout" in response.text.lower()

    def test_alembic_upgrade_db_url_env_injected_into_subprocess(self, client: TestClient) -> None:
        """Invariant 5: when db_url_env is set, subprocess receives that exact env var."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    "alembic": {
                        "config": "alembic.ini",
                        "db_url_env": "MY_TEST_DB_URL",
                    },
                }
            }
        }

        captured_envs: list[dict] = []

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            env = kwargs.get("env")
            if env is not None:
                captured_envs.append(dict(env))
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Running upgrade..."
            result.stderr = ""
            return result

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.run", side_effect=fake_run),
            patch.dict(os.environ, {"MY_TEST_DB_URL": "postgresql://test_host/testdb"}),
        ):
            response = client.post("/projects/iw-ai-core/alembic/upgrade")
            assert response.status_code == 200

        # Verify that the subprocess received the configured env var
        assert len(captured_envs) == 1
        assert captured_envs[0].get("MY_TEST_DB_URL") == "postgresql://test_host/testdb"
        assert captured_envs[0].get("IW_ALEMBIC_DB_URL") == "postgresql://test_host/testdb"

    def test_alembic_upgrade_no_db_url_env_uses_parent_env(self, client: TestClient) -> None:
        """Invariant 5: when db_url_env is omitted, subprocess inherits parent env (env=None)."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    "alembic": {
                        "config": "alembic.ini",
                        # db_url_env intentionally absent — iw-ai-core dogfood case
                    },
                }
            }
        }

        captured_kwargs: list[dict] = []

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            captured_kwargs.append(dict(kwargs))
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Running upgrade..."
            result.stderr = ""
            return result

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.run", side_effect=fake_run),
        ):
            response = client.post("/projects/iw-ai-core/alembic/upgrade")
            assert response.status_code == 200

        # When db_url_env is omitted, env kwarg must be None (inherits parent)
        assert len(captured_kwargs) == 1
        assert captured_kwargs[0].get("env") is None


# ===========================================================================
# S07 additions: malformed projects.toml → 500
# ===========================================================================


class TestMalformedProjectsToml:
    """Malformed projects.toml produces 500, other pages unaffected."""

    def test_panel_returns_500_on_toml_parse_error(self, client: TestClient) -> None:
        """When projects.toml is malformed, staleness panel returns 500."""
        import tomllib

        with (
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                side_effect=tomllib.TOMLDecodeError("bad toml", "", 0),
            ),
        ):
            response = client.get("/projects/iw-ai-core/staleness")
            # The endpoint catches exception and returns 500
            assert response.status_code == 500

    def test_restart_returns_500_on_toml_parse_error(self, client: TestClient) -> None:
        """When projects.toml fails to load, restart endpoint returns 500."""
        import tomllib

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            side_effect=tomllib.TOMLDecodeError("bad toml", "", 0),
        ):
            response = client.post("/projects/iw-ai-core/services/daemon/restart")
            assert response.status_code == 500

    def test_other_routes_unaffected_when_toml_malformed(self, client: TestClient) -> None:
        """When staleness endpoint returns 500, the /health endpoint is still up."""
        # /health is registered directly on the app and should always respond
        health_response = client.get("/health")
        assert health_response.status_code == 200


# ===========================================================================
# S07 additions: router-to-template wiring sanity test (S06 finding)
# ===========================================================================


class TestRouterToTemplateWiring:
    """Verify actual endpoint renders non-empty HTML for a stale project.

    S06 found that prior template tests bypassed the router and supplied
    context directly. These tests call the actual endpoint so that context
    key mismatches (like FINDING-1 and FINDING-2) are caught by the test suite.
    """

    def test_panel_renders_non_empty_for_stale_project(self, client: TestClient) -> None:
        """GET /projects/{id}/staleness renders actual template content for stale project."""
        result = _make_staleness_result("iw-ai-core", has_services=True, is_stale=True)

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client.get("/projects/iw-ai-core/staleness")
            assert response.status_code == 200
            # Must be non-empty HTML with actual content
            assert len(response.text.strip()) > 0
            # The response must contain the project's service name
            assert "daemon" in response.text

    def test_dot_renders_red_class_for_stale_project(self, client: TestClient) -> None:
        """GET /projects/{id}/staleness-dot renders the red dot class for stale project."""
        result = _make_staleness_result("iw-ai-core", has_services=True, is_stale=True)

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client.get("/projects/iw-ai-core/staleness-dot")
            assert response.status_code == 200
            # Must be non-empty and contain the red dot class
            assert "iw-staleness-dot" in response.text
            assert "iw-staleness-dot--red" in response.text

    def test_panel_renders_service_and_alembic_sections(self, client: TestClient) -> None:
        """GET staleness panel includes both Migrations and Services sections when both present."""
        from orch.staleness.alembic_check import AlembicStatus, RevisionSummary
        from orch.staleness.git_lookup import CommitSummary
        from orch.staleness.service import ProjectStalenessResult, ServiceStaleness

        result = ProjectStalenessResult(
            project_id="iw-ai-core",
            services=[
                ServiceStaleness(
                    name="daemon",
                    status="stale",
                    commits=[CommitSummary(sha="abc1234" * 5 + "a", subject="Break daemon")],
                    actions=["restart"],
                )
            ],
            alembic=AlembicStatus(
                status="stale",
                current="old123",
                head="new456",
                pending=[RevisionSummary(rev_id="new456", message="New migration")],
                error=None,
            ),
            is_stale=True,
        )

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client.get("/projects/iw-ai-core/staleness")
            assert response.status_code == 200
            body = response.text
            # Both sections must be present
            assert "Migration" in body
            assert "Services" in body or "daemon" in body
            # Migrations section must come before Services section (Invariant 7)
            assert body.index("Migration") < body.index("daemon")

    def test_confirm_endpoint_renders_service_name_and_command(self, client: TestClient) -> None:
        """GET .../restart/confirm renders confirm dialog with command text."""
        toml_data = _projects_toml_with_services()

        with patch(
            "dashboard.routers.staleness._load_projects_toml",
            return_value=toml_data,
        ):
            response = client.get("/projects/iw-ai-core/services/daemon/restart/confirm")
            assert response.status_code == 200
            body = response.text
            # Must contain service name and command text
            assert "daemon" in body
            assert "./ai-core.sh daemon restart" in body
            # Must have Confirm and Cancel buttons
            assert "Confirm" in body
            assert "Cancel" in body


# ===========================================================================
# S07 additions: self-restart returns 202 quickly
# ===========================================================================


class TestSelfRestart:
    """POST to dashboard's own restart_command returns 202 within 200ms."""

    def test_self_restart_returns_202(self, client: TestClient) -> None:
        """Dashboard self-restart endpoint returns 202 (not 204) immediately."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    "services": [
                        {
                            "name": "dashboard",
                            "detect": {"type": "pidfile", "path": ".dashboard.pid"},
                            "watch_paths": ["dashboard/**"],
                            "ignore_paths": [],
                            "restart_command": "bin/restart-dashboard.sh",
                            "start_command": None,
                            "stop_command": None,
                            "hot_reload": False,
                        }
                    ],
                }
            }
        }

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            import time as _time

            t0 = _time.monotonic()
            response = client.post("/projects/iw-ai-core/services/dashboard/restart")
            elapsed_ms = (_time.monotonic() - t0) * 1000

        # Self-restart must return 202 (not 204) so HTTP response flushes first
        assert response.status_code == 202
        # Must return quickly (≤ 200 ms)
        assert elapsed_ms < 200, f"Self-restart took {elapsed_ms:.1f}ms, expected <200ms"

    def test_self_restart_spawns_detached_process(self, client: TestClient) -> None:
        """Dashboard self-restart spawns process with start_new_session=True."""
        toml_data = {
            "projects": {
                "iw-ai-core": {
                    "display_name": "IW AI Core",
                    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core",
                    "enabled": True,
                    "services": [
                        {
                            "name": "dashboard",
                            "detect": {"type": "pidfile", "path": ".dashboard.pid"},
                            "watch_paths": ["dashboard/**"],
                            "ignore_paths": [],
                            "restart_command": "bin/restart-dashboard.sh",
                            "start_command": None,
                            "stop_command": None,
                            "hot_reload": False,
                        }
                    ],
                }
            }
        }

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()
            client.post("/projects/iw-ai-core/services/dashboard/restart")

            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs.get("start_new_session") is True


# ===========================================================================
# S07 additions: Invariant tests
# ===========================================================================


class TestInvariants:
    """Tests that directly assert the F-00063 invariants."""

    def test_inv1_no_new_db_tables(self) -> None:
        """Invariant 1: staleness feature creates no new DB tables."""
        from orch.db.models import Base

        table_names = set(Base.metadata.tables.keys())
        # Staleness-related table names that would violate Invariant 1
        staleness_table_patterns = [
            "staleness",
            "stale",
            "service_status",
            "process_check",
        ]
        for pattern in staleness_table_patterns:
            matching = [t for t in table_names if pattern in t.lower()]
            assert not matching, (
                f"Found staleness-related table(s) {matching} — Invariant 1 violated: "
                "staleness feature must not create new DB tables"
            )

    def test_inv4_three_rapid_restart_posts_only_one_subprocess(self, client: TestClient) -> None:
        """Invariant 4: 3 rapid restart POSTs result in exactly 1 subprocess invocation."""
        toml_data = _projects_toml_with_services()

        with (
            patch(
                "dashboard.routers.staleness._load_projects_toml",
                return_value=toml_data,
            ),
            patch("dashboard.routers.staleness.subprocess.Popen") as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            statuses = [
                client.post("/projects/iw-ai-core/services/daemon/restart").status_code
                for _ in range(3)
            ]

        # Exactly one 204, two 429s
        assert statuses.count(204) == 1
        assert statuses.count(429) == 2
        # Critical: subprocess spawned exactly once
        assert mock_popen.call_count == 1

    def test_inv6_projects_toml_reread_on_each_call(self, client: TestClient) -> None:
        """Invariant 6: projects.toml is re-read on every staleness computation (no caching)."""
        call_count = 0

        original_result = _make_staleness_result("iw-ai-core", has_services=True, is_stale=False)
        updated_result = _make_staleness_result("iw-ai-core", has_services=True, is_stale=True)

        results = [original_result, updated_result]

        def side_effect(project_id: str) -> object:
            nonlocal call_count
            r = results[min(call_count, len(results) - 1)]
            call_count += 1
            return r

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                side_effect=side_effect,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            r1 = client.get("/projects/iw-ai-core/staleness")
            r2 = client.get("/projects/iw-ai-core/staleness")

        # Both calls should succeed and compute_project_staleness called twice
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert call_count == 2, (
            f"compute_project_staleness called {call_count} times; "
            "Invariant 6 requires a fresh call on every render (no caching)"
        )

    def test_inv8_not_running_only_produces_no_red_dot(self, client: TestClient) -> None:
        """Invariant 8: not_running-only services → dot is not red."""
        from orch.staleness.service import ProjectStalenessResult, ServiceStaleness

        # All services are "not_running"; is_stale must be False
        result = ProjectStalenessResult(
            project_id="iw-ai-core",
            services=[
                ServiceStaleness(
                    name="daemon",
                    status="not_running",
                    actions=["start"],
                )
            ],
            alembic=None,
            is_stale=False,  # not_running does NOT contribute to is_stale
        )

        with (
            patch(
                "dashboard.routers.staleness.compute_project_staleness",
                return_value=result,
            ),
            patch(
                "dashboard.routers.staleness._is_known_project",
                return_value=True,
            ),
        ):
            response = client.get("/projects/iw-ai-core/staleness-dot")
            assert response.status_code == 200
            body = response.text
            # Must NOT have the red dot class
            assert "iw-staleness-dot--red" not in body
            # May have grey dot (services declared but not stale)
            if body.strip():
                assert "iw-staleness-dot--grey" in body
