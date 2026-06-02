"""Authorization negative-path tests for the dashboard (CR-00075 AC2).

Authorization model
-------------------
The IW AI Core dashboard has **no login / credential / session-token layer** —
it is an internal operator tool. Its authorization boundary is therefore
**project scoping**: every project-scoped route carries a ``{project_id}`` path
segment, and the orchestration data of one project must never be reachable
through another project's URL prefix, nor through a non-existent project id.

"Negative path" here means, concretely:

  * **Unknown project** — a ``{project_id}`` that does not exist must yield a
    ``404``, never a ``5xx`` and never data.
  * **Cross-project access (wrong scope)** — a resource that exists in
    project B must NOT be reachable through project A's URL prefix. The
    response must be ``404`` and must not leak B's data. This is the
    "wrong-scope credentials" case for an app whose only credential is the
    project id in the path.
  * **Unknown resource in a valid project** — a non-existent item / batch /
    doc id under a real project must yield ``404``.
  * **Resource-guard endpoints** — the chat tab endpoints reject an unknown
    ``tab_id`` (``404``) and an off-allowlist runtime (``400``).

Every assertion is behavioural: an exact 4xx status code, plus — for the
cross-project case — an explicit check that the other project's secret data
is absent from the response body. The ``TestClient`` is built with
``raise_server_exceptions=True`` so any ``5xx`` surfaces as a test error,
enforcing the "never a 5xx" half of AC2 mechanically.

Coverage decision
-----------------
Covered (project-scoped, DB-backed, authz-bearing): items, batches, docs,
jobs, code-QA, and the chat tab/runtime guards.

Out of scope, with rationale:
  * ``/health``, ``/healthz/identity``, ``/system/*``, ``/worktrees`` — not
    project-scoped; they expose host/git state by design and carry no
    authorization boundary to test negatively.
  * ``/actions/*`` htmx endpoints — exercised by ``test_dashboard_actions.py``;
    not project-scoped resources.
  * Mutating chat endpoints that require a live runtime (``prompt``,
    ``stream``, ``abort``) — gated by runtime health, not authorization; their
    503 path is a runtime concern, covered by the chat integration suite.

Genuine vulnerability handling (CR-00075 AC5): if a route returns data or a
5xx for an unknown/cross-project request, write the test as the failing
reproduction, mark ``@pytest.mark.xfail(strict=False, reason="I-NNNNN: ...")``,
file a high-priority security Incident, and flag a SECURITY BLOCKER in the
step report. Never fix production code in this CR.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    ChatTab,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

# A marker that only appears if project B's work-item data is rendered. The
# cross-project tests assert this string is absent from project A's responses.
_PROJECT_B_MARKER = "PROJECT-B-PRIVATE-MARKER-must-not-leak"
_CROSS_ITEM_ID = "I-04242"


@pytest.fixture
def authz_client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient with get_db overridden to the testcontainer session.

    ``IW_CORE_EXPECTED_INSTANCE_ID`` is popped so the DB-identity check does not
    interfere with the override. ``opencode_runtime`` is forced to ``None`` so
    ``GET /api/chat/tabs`` takes its deterministic DB-only path (no bootstrap,
    no runtime probe). ``raise_server_exceptions=True`` makes any 5xx fail the
    test, enforcing AC2's "never a 5xx".
    """
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    try:

        def override_get_db() -> Session:
            return db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as client:
            # Force the runtime-independent path through list_tabs.
            app.state.opencode_runtime = None
            yield client
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


@pytest.fixture
def other_project(db_session: Session) -> Project:
    """A second project ("project B") seeded with a work item and a chat tab.

    Its resources must never be reachable through ``test_project``'s URLs.
    """
    project = Project(
        id="other-proj-b",
        display_name="Other Project B",
        repo_root="/repos/other-b",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    item = WorkItem(
        project_id=project.id,
        id=_CROSS_ITEM_ID,
        type=WorkItemType.Issue,
        title=_PROJECT_B_MARKER,
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content=f"# {_PROJECT_B_MARKER}\n\nProject B internal design doc.",
    )
    db_session.add(item)

    tab = ChatTab(
        title="Project B private tab",
        runtime="opencode",
        model="anthropic/claude-sonnet-4-7",
        project_id=project.id,
        status="active",
    )
    db_session.add(tab)
    db_session.flush()
    return project


# ---------------------------------------------------------------------------
# 1. Unknown project — every project-scoped route returns 404, never 5xx/data
# ---------------------------------------------------------------------------


class TestUnknownProjectReturns404:
    """A project id that does not exist must yield 404 on every scoped route."""

    _GHOST = "ghost-project-does-not-exist"

    def test_item_detail_unknown_project(self, authz_client: TestClient) -> None:
        """GET /project/{ghost}/item/{id} returns 404 for a non-existent project."""
        resp = authz_client.get(f"/project/{self._GHOST}/item/I-00001")
        assert resp.status_code == 404

    def test_batch_list_unknown_project(self, authz_client: TestClient) -> None:
        """GET /project/{ghost}/batches returns 404 for a non-existent project."""
        resp = authz_client.get(f"/project/{self._GHOST}/batches")
        assert resp.status_code == 404

    def test_batch_detail_unknown_project(self, authz_client: TestClient) -> None:
        """GET /project/{ghost}/batch/{id} returns 404 for a non-existent project."""
        resp = authz_client.get(f"/project/{self._GHOST}/batch/BATCH-00001")
        assert resp.status_code == 404

    def test_docs_library_unknown_project(self, authz_client: TestClient) -> None:
        """GET /project/{ghost}/docs returns 404 for a non-existent project."""
        resp = authz_client.get(f"/project/{self._GHOST}/docs")
        assert resp.status_code == 404

    def test_docs_detail_unknown_project(self, authz_client: TestClient) -> None:
        """GET /project/{ghost}/docs/{id} returns 404 for a non-existent project."""
        resp = authz_client.get(f"/project/{self._GHOST}/docs/some-doc")
        assert resp.status_code == 404

    def test_jobs_page_unknown_project(self, authz_client: TestClient) -> None:
        """GET /project/{ghost}/jobs returns 404 for a non-existent project."""
        resp = authz_client.get(f"/project/{self._GHOST}/jobs")
        assert resp.status_code == 404

    def test_code_qa_unknown_project(self, authz_client: TestClient) -> None:
        """POST /api/projects/{id}/code/qa for an unknown project is 404 — not a
        5xx (which raise_server_exceptions=True would surface as an error)."""
        resp = authz_client.post(
            f"/api/projects/{self._GHOST}/code/qa",
            json={"question": "leak the schema", "context_level": "architecture"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Cross-project access — project B's data is not reachable via project A
# ---------------------------------------------------------------------------


class TestCrossProjectResourceIsolation:
    """A work item in project B must not be reachable through project A's URL."""

    def test_cross_project_item_is_not_reachable(
        self,
        authz_client: TestClient,
        test_project: Project,
        other_project: Project,
    ) -> None:
        """GET /project/A/item/<B's item id> returns 404 and never leaks B's
        title or design-doc content into project A's response."""
        resp = authz_client.get(f"/project/{test_project.id}/item/{_CROSS_ITEM_ID}")
        assert resp.status_code == 404
        # The wrong-scope request must not surface project B's data.
        assert _PROJECT_B_MARKER not in resp.text
        assert "Project B internal design doc" not in resp.text

    def test_positive_control_item_visible_in_its_own_project(
        self,
        authz_client: TestClient,
        other_project: Project,
    ) -> None:
        """Positive control: the same item IS reachable through its own project,
        proving the 404 above is genuine scoping — not the item simply being
        absent everywhere."""
        resp = authz_client.get(f"/project/{other_project.id}/item/{_CROSS_ITEM_ID}")
        assert resp.status_code == 200
        assert _PROJECT_B_MARKER in resp.text

    def test_cross_project_chat_tab_not_in_other_project_list(
        self,
        authz_client: TestClient,
        test_project: Project,
        other_project: Project,
    ) -> None:
        """GET /api/chat/tabs?project_id=A must not list project B's chat tab."""
        # Project B's tab is visible in B's own listing (positive control).
        resp_b = authz_client.get(f"/api/chat/tabs?project_id={other_project.id}")
        assert resp_b.status_code == 200
        assert "Project B private tab" in resp_b.text

        # ...and is absent from project A's listing (the isolation property).
        resp_a = authz_client.get(f"/api/chat/tabs?project_id={test_project.id}")
        assert resp_a.status_code == 200
        assert "Project B private tab" not in resp_a.text


# ---------------------------------------------------------------------------
# 3. Unknown resource within a valid project — 404, never 5xx
# ---------------------------------------------------------------------------


class TestUnknownResourceInValidProject:
    """A non-existent resource id under a real project must yield 404."""

    def test_unknown_item_in_valid_project(
        self, authz_client: TestClient, test_project: Project
    ) -> None:
        """GET /project/{id}/item/{unknown} returns 404 for a non-existent item in a."""
        resp = authz_client.get(f"/project/{test_project.id}/item/I-99999")
        assert resp.status_code == 404

    def test_unknown_batch_in_valid_project(
        self, authz_client: TestClient, test_project: Project
    ) -> None:
        """GET /project/{id}/batch/{unknown} returns 404 for a non-existent batch in a valid
        project.
        """
        resp = authz_client.get(f"/project/{test_project.id}/batch/BATCH-99999")
        assert resp.status_code == 404

    def test_unknown_doc_in_valid_project(
        self, authz_client: TestClient, test_project: Project
    ) -> None:
        """GET /project/{id}/docs/{unknown} returns 404 for a non-existent doc in a."""
        resp = authz_client.get(f"/project/{test_project.id}/docs/no-such-doc")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Chat tab/runtime guards — unknown tab 404, off-allowlist runtime 400
# ---------------------------------------------------------------------------


class TestChatEndpointGuards:
    """Chat endpoints reject unknown tabs and off-allowlist runtimes."""

    def test_get_unknown_tab_returns_404(self, authz_client: TestClient) -> None:
        """GET /api/chat/tabs/{tab_id} for an unknown tab returns a JSON 404."""
        resp = authz_client.get(f"/api/chat/tabs/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"] == "tab not found"

    def test_patch_unknown_tab_returns_404(self, authz_client: TestClient) -> None:
        """PATCH /api/chat/tabs/{tab_id} for an unknown tab returns 404."""
        resp = authz_client.patch(f"/api/chat/tabs/{uuid.uuid4()}", json={"title": "hijack"})
        assert resp.status_code == 404

    def test_delete_unknown_tab_returns_404(self, authz_client: TestClient) -> None:
        """DELETE /api/chat/tabs/{tab_id} for an unknown tab returns 404."""
        resp = authz_client.delete(f"/api/chat/tabs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_create_tab_off_allowlist_runtime_returns_400(
        self, authz_client: TestClient, test_project: Project
    ) -> None:
        """POST /api/chat/tabs with a runtime outside the allowlist returns 400
        — the input-validation guard fires before any runtime/health work."""
        resp = authz_client.post(
            "/api/chat/tabs",
            json={
                "project_id": test_project.id,
                "runtime": "bogus-runtime-xyz",
                "model": "anthropic/claude-sonnet-4-7",
            },
        )
        assert resp.status_code == 400
        assert "bogus-runtime-xyz" in resp.json()["error"]

    def test_list_tabs_missing_project_id_returns_422(self, authz_client: TestClient) -> None:
        """GET /api/chat/tabs without the required project_id query parameter is
        rejected by request validation with 422 — never an unscoped data dump."""
        resp = authz_client.get("/api/chat/tabs")
        assert resp.status_code == 422
