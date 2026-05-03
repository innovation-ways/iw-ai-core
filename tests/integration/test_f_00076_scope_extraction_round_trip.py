"""Integration test for F-00076 — scope extraction provenance round-trip.

Verifies AC3/AC4: For each combination of (declared / regex_fallback / none),
the value stored in WorkItem.config["scope_extraction"] matches the design contract.

AC3: Declared section → source == "declared", no "warned_at"
AC4: Missing section with file paths → source == "regex_fallback", "warned_at" present
AC4 variant: Missing section with no paths → source == "none"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    get_session: object,
    project_id: str = "test-proj",
):
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# AC3: Declared section — source=declared
# ---------------------------------------------------------------------------


def test_declared_scope_source_is_declared(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """AC3: Design doc with ## Impacted Paths section → source == 'declared'."""
    design_doc = tmp_path / "F-99020_Feature_Design.md"
    design_doc.write_text(
        "# F-99020: Declared Scope Test\n\n"
        "## Description\nAdd feature.\n\n"
        "## Impacted Paths\n\n"
        "- orch/foo.py\n"
        "- orch/bar/**\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99020",
            "Declared Scope Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99020"))
    assert wi is not None
    assert wi.impacted_paths == ["orch/foo.py", "orch/bar/**"]
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "declared"
    assert "warned_at" not in scope_extraction


def test_declared_empty_paths_source_is_declared(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """AC3 variant: Declared section present but empty list → source == 'declared'."""
    design_doc = tmp_path / "F-99021_Feature_Design.md"
    design_doc.write_text(
        "# F-99021: Empty Paths Test\n\n"
        "## Description\nNo concrete files.\n\n"
        "## Impacted Paths\n\n"
        "(empty — designer intentionally declared none)\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99021",
            "Empty Paths Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99021"))
    assert wi is not None
    assert wi.impacted_paths == []
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "declared"


# ---------------------------------------------------------------------------
# AC4: Missing section — regex_fallback
# ---------------------------------------------------------------------------


def test_missing_section_with_file_paths_source_is_regex_fallback(
    caplog: pytest.LogCaptureFixture,
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """AC4: No ## Impacted Paths section but prose mentions files → source == 'regex_fallback'."""
    design_doc = tmp_path / "F-99022_Feature_Design.md"
    design_doc.write_text(
        "# F-99022: Regex Fallback Test\n\n"
        "## Description\nModify orch/foo.py and dashboard/bar.ts.\n\n"
        "## Scope\n\n- Add the feature to orch/foo.py\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99022",
            "Regex Fallback Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99022"))
    assert wi is not None
    assert len(wi.impacted_paths) > 0, "Expected auto-extracted paths"
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "regex_fallback"
    assert "warned_at" in scope_extraction

    # stderr warning must be present
    output = result.output + (result.stderr or "")
    assert "scope auto-extracted" in output.lower() or "please verify" in output.lower()


# ---------------------------------------------------------------------------
# AC4 variant: No paths anywhere — source=none
# ---------------------------------------------------------------------------


def test_no_paths_anywhere_source_is_none(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """Design doc with no ## Impacted Paths section and no file paths → source == 'none'."""
    design_doc = tmp_path / "F-99023_Feature_Design.md"
    design_doc.write_text(
        "# F-99023: No Paths At All\n\n## Description\nJust a placeholder.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99023",
            "No Paths At All",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99023"))
    assert wi is not None
    assert wi.impacted_paths == []
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "none"


# ---------------------------------------------------------------------------
# Research items may keep "none" even if empty
# ---------------------------------------------------------------------------


def test_research_item_keeps_none_source(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """Research items may keep source=='none' even with empty impacted_paths.

    Invariant 2: "Research items may keep 'none' even if impacted_paths is empty."
    """
    design_doc = tmp_path / "R-99024_Research_Design.md"
    design_doc.write_text(
        "# R-99024: Research Item Test\n\n## Description\nInvestigate options.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "R-99024",
            "Research Item Test",
            "--type",
            "research",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "R-99024"))
    assert wi is not None
    assert wi.impacted_paths == []
    scope_extraction = wi.config.get("scope_extraction")
    # Research may keep "none"
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "none"
