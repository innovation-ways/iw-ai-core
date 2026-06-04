"""Integration tests for register command + functional doc auto-detect."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import Project, WorkItem

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    """Invoke the CLI with a pre-injected session factory."""
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


class TestRegisterFunctionalDoc:
    """Parameterised cases for AC4 / boundary-behaviour scenarios."""

    def test_sibling_functional_doc_exists_both_columns_populated(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """Sibling <ID>_Functional.md exists next to technical doc -> both columns populated."""
        # Set up: design doc and functional doc in same directory
        tech_doc = tmp_path / "F-00001_Design.md"
        tech_doc.write_text("# F-00001 Technical Design")
        func_doc = tmp_path / "F-00001_Functional.md"
        func_doc.write_text("# F-00001 Functional Design\n\n## Why\nTest.")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = invoke(
            runner,
            [
                "register",
                "F-00001",
                "Test Item",
                "--type",
                "feature",
                "--design-doc",
                "F-00001_Design.md",
            ],
            cli_get_session,
        )
        assert result.exit_code == 0, result.output

        item = db_session.get(WorkItem, ("test-proj", "F-00001"))
        assert item is not None
        assert item.functional_doc_path == "F-00001_Functional.md"
        assert item.functional_doc_content is not None
        assert "Functional Design" in item.functional_doc_content

    def test_sibling_functional_doc_absent_both_columns_none(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """Sibling file absent -> INSERT succeeds; both columns NULL."""
        tech_doc = tmp_path / "F-00002_Design.md"
        tech_doc.write_text("# F-00002 Technical Design")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = invoke(
            runner,
            [
                "register",
                "F-00002",
                "Test Item 2",
                "--type",
                "feature",
                "--design-doc",
                "F-00002_Design.md",
            ],
            cli_get_session,
        )
        assert result.exit_code == 0, result.output

        item = db_session.get(WorkItem, ("test-proj", "F-00002"))
        assert item is not None
        assert item.functional_doc_path is None
        assert item.functional_doc_content is None

    def test_functional_doc_override_with_existing_file(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """--functional-doc PATH override with existing file -> columns populated from that path."""
        tech_doc = tmp_path / "F-00003_Design.md"
        tech_doc.write_text("# F-00003 Technical Design")
        alt_func_doc = tmp_path / "alt-func.md"
        alt_func_doc.write_text("# Alternate Functional\n\n## Why\nDifferent.")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = invoke(
            runner,
            [
                "register",
                "F-00003",
                "Test Item 3",
                "--type",
                "feature",
                "--design-doc",
                "F-00003_Design.md",
                "--functional-doc",
                "alt-func.md",
            ],
            cli_get_session,
        )
        assert result.exit_code == 0, result.output

        item = db_session.get(WorkItem, ("test-proj", "F-00003"))
        assert item is not None
        assert item.functional_doc_path == "alt-func.md"
        assert item.functional_doc_content is not None
        assert "Alternate Functional" in item.functional_doc_content

    def test_functional_doc_override_with_missing_file_fails(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """--functional-doc PATH pointing to missing file -> command fails, no row inserted."""
        tech_doc = tmp_path / "F-00004_Design.md"
        tech_doc.write_text("# F-00004 Technical Design")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = invoke(
            runner,
            [
                "register",
                "F-00004",
                "Test Item 4",
                "--type",
                "feature",
                "--design-doc",
                "F-00004_Design.md",
                "--functional-doc",
                "does-not-exist.md",
            ],
            cli_get_session,
        )
        assert result.exit_code == 2, result.output
        assert "does-not-exist" in result.output or "not found" in result.output

        item = db_session.get(WorkItem, ("test-proj", "F-00004"))
        assert item is None

    def test_functional_doc_empty_file_treated_as_absent(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """Empty sibling file -> file reads as empty string; columns set to None
        (consistent with design doc convention where absent/missing -> NULL,
        empty reads as empty string but treated as absent for prompt-building).
        We treat it as absent for DB purposes."""
        tech_doc = tmp_path / "F-00005_Design.md"
        tech_doc.write_text("# F-00005 Technical Design")
        func_doc = tmp_path / "F-00005_Functional.md"
        func_doc.write_text("")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = invoke(
            runner,
            [
                "register",
                "F-00005",
                "Test Item 5",
                "--type",
                "feature",
                "--design-doc",
                "F-00005_Design.md",
            ],
            cli_get_session,
        )
        assert result.exit_code == 0, result.output

        item = db_session.get(WorkItem, ("test-proj", "F-00005"))
        assert item is not None
        # Empty string is falsy but not NULL — treat as absent for functional doc
        assert item.functional_doc_path is None
        assert item.functional_doc_content is None

    def test_register_with_sibling_fts_returns_row_on_content_term(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """With sibling functional doc, FTS query on content-specific term returns the row."""
        tech_doc = tmp_path / "F-00006_Design.md"
        tech_doc.write_text("# F-00006 Technical Design")
        func_doc = tmp_path / "F-00006_Functional.md"
        func_doc.write_text("# F-00006 Functional Design\n\n## Why\nUniqueXYZKeyword test.")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = invoke(
            runner,
            [
                "register",
                "F-00006",
                "Test Item 6",
                "--type",
                "feature",
                "--design-doc",
                "F-00006_Design.md",
            ],
            cli_get_session,
        )
        assert result.exit_code == 0, result.output

        from sqlalchemy import text

        rows = db_session.execute(
            text(
                "SELECT id FROM work_items "
                "WHERE functional_doc_search @@ to_tsquery('english', 'UniqueXYZKeyword')"
            )
        ).fetchall()
        assert any(r[0] == "F-00006" for r in rows), (
            "FTS query on content-specific term did not return F-00006"
        )

    def test_register_twice_second_is_idempotent(
        self,
        db_session: SASession,
        test_project: Project,
        cli_get_session: Any,
        tmp_path: Any,
        monkeypatch: Any,
    ) -> None:
        """First register succeeds; second register with same ID is idempotent (no new row)."""
        tech_doc = tmp_path / "F-00007_Design.md"
        tech_doc.write_text("# F-00007 Technical Design")
        func_doc = tmp_path / "F-00007_Functional.md"
        func_doc.write_text("# F-00007 Functional Design\n\n## Why\nTest.")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result1 = invoke(
            runner,
            [
                "register",
                "F-00007",
                "First Register",
                "--type",
                "feature",
                "--design-doc",
                "F-00007_Design.md",
            ],
            cli_get_session,
        )
        assert result1.exit_code == 0, result1.output

        item1 = db_session.get(WorkItem, ("test-proj", "F-00007"))
        assert item1 is not None
        assert item1.title == "First Register"

        result2 = invoke(
            runner,
            [
                "register",
                "F-00007",
                "Second Register",
                "--type",
                "feature",
                "--design-doc",
                "F-00007_Design.md",
            ],
            cli_get_session,
        )
        # Idempotent behaviour: succeeds but doesn't create a duplicate
        assert result2.exit_code == 0, result2.output

        item2 = db_session.get(WorkItem, ("test-proj", "F-00007"))
        assert item2 is not None
        # Title is unchanged (first register's title persists)
        assert item2.title == "First Register"
