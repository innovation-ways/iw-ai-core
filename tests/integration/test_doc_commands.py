"""Integration tests for doc CLI commands using a real PostgreSQL testcontainer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from click.testing import CliRunner

from orch.cli.doc_commands import doc_update
from orch.cli.main import cli
from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, Project, ProjectDoc
from orch.doc_service import DocService

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


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


class TestDocUpdateCreatesNewDoc:
    """iw doc-update creates a new doc and version snapshot."""

    def test_doc_update_creates_new_doc(self, cli_get_session: Any, test_project: Project) -> None:
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
                "# Auth Module\n\nContent here.",
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["doc_id"] == "test-proj:module-auth"
        assert output["project_id"] == "test-proj"
        assert output["version"] == 1
        assert output["status"] == "draft"
        assert output["snapshot_created"] is True

    def test_doc_update_unknown_project_exits_1(self, cli_get_session: Any) -> None:
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


class TestDocUpdateUpdatesExistingDoc:
    """Second call with different content increments version."""

    def test_doc_update_updates_existing_doc(
        self, cli_get_session: Any, test_project: Project, db_session: Any
    ) -> None:
        svc = DocService(db_session)
        svc.create_doc(
            project_id="test-proj",
            doc_id="module-auth",
            title="Auth Module",
            doc_type=DocType.module,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.draft,
            content="# Version 1",
            trigger_reason="initial",
        )
        db_session.commit()

        result = invoke(
            [
                "doc-update",
                "module-auth",
                "--content",
                "# Version 2",
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["version"] == 2
        assert output["snapshot_created"] is True

    def test_doc_update_idempotent_same_content(
        self, cli_get_session: Any, test_project: Project, db_session: Any
    ) -> None:
        svc = DocService(db_session)
        svc.create_doc(
            project_id="test-proj",
            doc_id="module-auth",
            title="Auth Module",
            doc_type=DocType.module,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            content="# Same Content",
            trigger_reason="initial",
        )
        db_session.commit()

        result = invoke(
            [
                "doc-update",
                "module-auth",
                "--content",
                "# Same Content",
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["version"] == 1
        assert output["snapshot_created"] is False


class TestDocUpdateAudience:
    """--audience is parsed as comma-separated list."""

    def test_doc_update_audience_parsed(
        self, cli_get_session: Any, test_project: Project, db_session: Any
    ) -> None:
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
                "--audience",
                "architects,senior-developers",
                "--content",
                "# Auth",
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["doc_id"] == "test-proj:module-auth"

        doc = db_session.get(ProjectDoc, "test-proj:module-auth")
        assert doc is not None
        assert doc.audience == ["architects", "senior-developers"]


class TestDocUpdateSourcePaths:
    """--source-paths is parsed as comma-separated list."""

    def test_doc_update_source_paths_parsed(
        self, cli_get_session: Any, test_project: Project, db_session: Any
    ) -> None:
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
                "--source-paths",
                "docs/arch.md,docs/api.md",
                "--content",
                "# Auth",
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["doc_id"] == "test-proj:module-auth"

        doc = db_session.get(ProjectDoc, "test-proj:module-auth")
        assert doc is not None
        assert doc.source_paths == ["docs/arch.md", "docs/api.md"]


class TestDocUpdateContentFromStdin:
    """--content-file - reads from stdin."""

    def test_doc_update_content_from_stdin(
        self, cli_get_session: Any, test_project: Project
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            doc_update,
            [
                "module-auth",
                "--title",
                "Auth",
                "--doc-type",
                "module",
                "--tier",
                "human_authored",
                "--editorial-category",
                "technical",
                "--content-file",
                "-",
            ],
            input="# Content from stdin",
            obj={"get_session": cli_get_session, "project_id": "test-proj"},
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["snapshot_created"] is True


class TestDocUpdateContentFromFile:
    """--content-file with a real file path."""

    def test_doc_update_content_from_file(
        self,
        cli_get_session: Any,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        content_file = tmp_path / "doc.md"
        content_file.write_text("# Content from file", encoding="utf-8")

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
                "--content-file",
                str(content_file),
            ],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["doc_id"] == "test-proj:module-auth"
        assert output["snapshot_created"] is True
