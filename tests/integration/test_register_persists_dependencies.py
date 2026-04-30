"""Integration test for I-00053 — `iw register` persists declared dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import WorkItem

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from sqlalchemy.orm import Session as SASession

    from orch.db.models import Project


def _invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def test_register_persists_declared_depends_on(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """A design doc with declared `Depends on:` results in WorkItem.depends_on populated."""
    design_doc = tmp_path / "F-99001_Feature_Design.md"
    design_doc.write_text(
        "# F-99001: Test\n\n"
        "## Description\nx\n\n"
        "## Dependencies\n\n"
        "- **Depends on**: F-99000\n"
        "- **Blocks**: None\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99001",
            "Test item",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99001"))
    assert wi is not None
    assert wi.depends_on == ["F-99000"], f"Expected depends_on=['F-99000'], got {wi.depends_on}"
    assert wi.blocks == []


def test_register_inverts_blocks_into_other_items_depends_on(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """When F-A declares `Blocks: F-B`, F-B's depends_on must gain F-A."""
    # Pre-register F-B with empty deps
    runner = CliRunner()
    f_b_doc = tmp_path / "F-99002_Feature_Design.md"
    f_b_doc.write_text(
        "# F-99002: Blocked item\n\n## Description\ny\n",
        encoding="utf-8",
    )
    reg_b = _invoke(
        runner,
        [
            "register",
            "F-99002",
            "Blocked item",
            "--type",
            "feature",
            "--design-doc",
            str(f_b_doc),
        ],
        cli_get_session,
    )
    assert reg_b.exit_code == 0, reg_b.output

    # Verify F-B starts with empty depends_on
    f_b_before = db_session.get(WorkItem, ("test-proj", "F-99002"))
    assert f_b_before is not None
    assert f_b_before.depends_on == [], f"B before: {f_b_before.depends_on}"

    # Register F-A whose design doc says "Blocks: F-B"
    f_a_doc = tmp_path / "F-99003_Feature_Design.md"
    f_a_doc.write_text(
        "# F-99003: Blocker\n\n## Description\nz\n\n## Dependencies\n\n- **Blocks**: F-99002\n",
        encoding="utf-8",
    )
    reg_a = _invoke(
        runner,
        [
            "register",
            "F-99003",
            "Blocker",
            "--type",
            "feature",
            "--design-doc",
            str(f_a_doc),
        ],
        cli_get_session,
    )
    assert reg_a.exit_code == 0, reg_a.output

    # F-B's depends_on must now contain F-99003
    db_session.expire_all()
    f_b_after = db_session.get(WorkItem, ("test-proj", "F-99002"))
    assert f_b_after is not None
    assert "F-99003" in f_b_after.depends_on, (
        f"F-99002.depends_on should contain 'F-99003', got {f_b_after.depends_on}"
    )
    # F-A's blocks list must contain F-99002
    f_a_after = db_session.get(WorkItem, ("test-proj", "F-99003"))
    assert f_a_after is not None
    assert "F-99002" in f_a_after.blocks


def test_register_blocks_missing_target_logs_warning(
    caplog: pytest.LogCaptureFixture,
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """Declaring `Blocks: F-99999` (unregistered) logs a WARNING and does not raise."""
    design_doc = tmp_path / "F-99004_Feature_Design.md"
    design_doc.write_text(
        "# F-99004: Block missing\n\n"
        "## Description\nw\n\n"
        "## Dependencies\n\n"
        "- **Blocks**: F-99999\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99004",
            "Block missing",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    # Should not raise — missing target is skipped with a warning
    output = result.output + (result.stderr or "")
    # The warning is printed to stderr via click.echo(..., err=True)
    assert "F-99999" in output or "not registered" in output.lower() or "skipping" in output.lower()


def test_register_self_dependency_filtered(
    caplog: pytest.LogCaptureFixture,
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """A design doc declaring `Depends on: <self>` filters it out and logs a WARNING."""
    design_doc = tmp_path / "F-99005_Feature_Design.md"
    design_doc.write_text(
        "# F-99005: Self dep\n\n"
        "## Description\nv\n\n"
        "## Dependencies\n\n"
        "- **Depends on**: F-99005\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99005",
            "Self dep",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99005"))
    assert wi is not None
    assert "F-99005" not in wi.depends_on, (
        f"Self-dependency should be filtered, got {wi.depends_on}"
    )
    output = result.output + (result.stderr or "")
    assert "self" in output.lower() or "F-99005" in output


def test_register_no_dependencies_section_persists_empty(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """A design doc with no `## Dependencies` section results in empty depends_on."""
    design_doc = tmp_path / "F-99006_Feature_Design.md"
    design_doc.write_text(
        "# F-99006: No deps\n\n"
        "## Description\nno deps section here\n\n"
        "## Scope\n\n"
        "- `orch/foo.py`\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99006",
            "No deps",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99006"))
    assert wi is not None
    assert wi.depends_on == [], f"Expected [], got {wi.depends_on}"
    assert wi.blocks == []
