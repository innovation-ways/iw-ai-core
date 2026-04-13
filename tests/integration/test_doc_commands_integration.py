"""Integration tests for doc CLI commands using a real PostgreSQL testcontainer.

These tests supplement the unit tests in tests/unit/test_doc_commands.py
and the existing integration tests in tests/integration/test_doc_commands.py.

Key gaps filled here:
- Oversized content via --content (not just --content-file)
- E2E: CLI write to dashboard read roundtrip
- CLI exit code 2 for content >= 10 MB
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.cli.doc_commands import doc_update
from orch.cli.main import cli
from orch.db.models import Project, ProjectDoc

if TYPE_CHECKING:
    from collections.abc import Generator

    from click.testing import Result
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client for the dashboard app."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


def invoke(args: list[str], get_session: Any, project_id: str = "test-proj") -> Result:
    runner = CliRunner()
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def invoke_direct(args: list[str], get_session: Any, project_id: str = "test-proj") -> Result:
    runner = CliRunner()
    return runner.invoke(
        doc_update,
        args,
        obj={"get_session": get_session, "project_id": project_id},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Oversized Content
# ---------------------------------------------------------------------------


class TestDocUpdateContentSizeLimitIntegration:
    """Content >= 10 MB is rejected with exit code 2 without touching DB."""

    def test_doc_update_oversized_content_exits_2(
        self, cli_get_session: Any, test_project: Project, db_session: Any
    ) -> None:
        """Oversized content via --content flag triggers exit code 2."""
        large_content = "x" * (10 * 1024 * 1024 + 1)

        result = invoke(
            [
                "doc-update",
                "module-large",
                "--title",
                "Large Doc",
                "--doc-type",
                "module",
                "--tier",
                "human_authored",
                "--editorial-category",
                "technical",
                "--content",
                large_content,
            ],
            cli_get_session,
        )

        assert result.exit_code == 2
        assert "exceeds maximum size" in result.stderr

        doc = db_session.get(ProjectDoc, "test-proj:module-large")
        assert doc is None, "Oversized content should not be written to DB"


# ---------------------------------------------------------------------------
# End-to-End: CLI Write -> Dashboard Read
# ---------------------------------------------------------------------------


class TestE2ECliWriteDashboardRead:
    """Full roundtrip: CLI write a doc, then read it via dashboard routes."""

    def test_e2e_cli_write_dashboard_read(
        self,
        cli_get_session: Any,
        test_project: Project,
        db_session: Any,
        client: TestClient,
    ) -> None:
        """CLI doc-update -> GET /docs -> GET /docs/{id} -> GET /versions -> update."""
        result = invoke(
            [
                "doc-update",
                "module-auth",
                "--title",
                "Auth Module",
                "--doc-type",
                "module",
                "--tier",
                "semi_automated",
                "--editorial-category",
                "technical",
                "--status",
                "draft",
                "--content",
                "# Auth Module\n\nThis is the auth module content.",
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["doc_id"] == "test-proj:module-auth"
        assert output["version"] == 1
        assert output["snapshot_created"] is True

        resp = client.get("/project/test-proj/docs")
        assert resp.status_code == 200
        assert "Auth Module" in resp.text

        resp = client.get("/project/test-proj/docs/module-auth")
        assert resp.status_code == 200
        assert "<h1>" in resp.text
        assert "Auth Module" in resp.text

        resp = client.get("/project/test-proj/api/docs/module-auth/versions")
        assert resp.status_code == 200
        assert "v1" in resp.text

        result2 = invoke(
            [
                "doc-update",
                "module-auth",
                "--content",
                "# Auth Module\n\nUpdated content with new information.",
            ],
            cli_get_session,
        )
        assert result2.exit_code == 0, result2.stderr
        output2 = json.loads(result2.output)
        assert output2["version"] == 2

        resp = client.get("/project/test-proj/api/docs/module-auth/versions")
        assert resp.status_code == 200
        assert "v1" in resp.text
        assert "v2" in resp.text


# ---------------------------------------------------------------------------
# Boundary: Unknown Project Exit Code 1
# ---------------------------------------------------------------------------


class TestDocUpdateUnknownProject:
    """Error handling for unknown project."""

    def test_doc_update_unknown_project_exit_code_1(self, cli_get_session: Any) -> None:
        """Unknown project exits with code 1 and error message."""
        result = invoke(
            [
                "doc-update",
                "doc1",
                "--title",
                "Title",
                "--doc-type",
                "module",
                "--tier",
                "human_authored",
                "--editorial-category",
                "technical",
            ],
            cli_get_session,
            project_id="nonexistent",
        )

        assert result.exit_code == 1
        assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# Boundary: Idempotency — Unchanged Content
# ---------------------------------------------------------------------------


class TestDocUpdateUnchangedContent:
    """Idempotency: unchanged content does not create new snapshot."""

    def test_doc_update_unchanged_content_no_new_version(
        self, cli_get_session: Any, test_project: Project, db_session: Any
    ) -> None:
        """Second update with identical content does not create new version."""
        result1 = invoke(
            [
                "doc-update",
                "module-auth",
                "--title",
                "Auth Module",
                "--doc-type",
                "module",
                "--tier",
                "semi_automated",
                "--editorial-category",
                "technical",
                "--content",
                "# Same Content",
            ],
            cli_get_session,
        )
        assert result1.exit_code == 0, result1.stderr
        output1 = json.loads(result1.output)
        assert output1["version"] == 1
        assert output1["snapshot_created"] is True

        result2 = invoke(
            [
                "doc-update",
                "module-auth",
                "--title",
                "Auth Module Updated Title",
                "--content",
                "# Same Content",
            ],
            cli_get_session,
        )
        assert result2.exit_code == 0, result2.stderr
        output2 = json.loads(result2.output)
        assert output2["version"] == 1
        assert output2["snapshot_created"] is False

        doc = db_session.get(ProjectDoc, "test-proj:module-auth")
        assert doc is not None
        assert doc.title == "Auth Module Updated Title"
        assert doc.version == 1

        from orch.db.models import ProjectDocVersion

        versions = db_session.query(ProjectDocVersion).filter_by(doc_id=doc.id).all()
        assert len(versions) == 1
