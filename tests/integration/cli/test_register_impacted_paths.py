"""Integration tests for F-00076 — `iw register` populates `WorkItem.impacted_paths`."""

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
) -> object:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Declared section — source=declared
# ---------------------------------------------------------------------------


def test_register_declared_impacted_paths(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """Design doc with ## Impacted Paths populates impacted_paths with source='declared'."""
    design_doc = tmp_path / "F-99010_Feature_Design.md"
    design_doc.write_text(
        "# F-99010: Declared Paths Test\n\n"
        "## Description\nfoo\n\n"
        "## Scope\n\n### In Scope\n\n- Feature A\n\n"
        "## Impacted Paths\n\n"
        "- orch/foo.py\n"
        "- orch/bar/**\n"
        "- dashboard/templates/components/**\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99010",
            "Declared Paths Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99010"))
    assert wi is not None
    assert wi.impacted_paths == [
        "orch/foo.py",
        "orch/bar/**",
        "dashboard/templates/components/**",
    ], f"Expected impacted_paths with declared values, got {wi.impacted_paths}"
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "declared"
    assert "warned_at" not in scope_extraction


def test_register_declared_impacted_paths_code_block(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """Impacted Paths in a fenced code block is also parsed and source='declared'."""
    design_doc = tmp_path / "F-99011_Feature_Design.md"
    design_doc.write_text(
        "# F-99011: Code Block Paths Test\n\n"
        "## Description\nfoo\n\n"
        "## Impacted Paths\n\n"
        "```\n"
        "orch/foo.py\n"
        "orch/bar/**\n"
        "```\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99011",
            "Code Block Paths Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99011"))
    assert wi is not None
    assert wi.impacted_paths == ["orch/foo.py", "orch/bar/**"]
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "declared"


# ---------------------------------------------------------------------------
# Regex fallback — source=regex_fallback, warned_at present
# ---------------------------------------------------------------------------


def test_register_no_impacted_paths_section_falls_back_to_regex(
    caplog: pytest.LogCaptureFixture,
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """No ## Impacted Paths section falls back to regex with source='regex_fallback'."""
    design_doc = tmp_path / "F-99012_Feature_Design.md"
    design_doc.write_text(
        "# F-99012: No Section Test\n\n"
        "## Description\nfoo\n\n"
        "## Scope\n\n### In Scope\n\n"
        "- Add `orch/foo.py` and `dashboard/bar.ts` files.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99012",
            "No Section Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99012"))
    assert wi is not None
    assert set(wi.impacted_paths) == {"orch/foo.py", "dashboard/bar.ts"}
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "regex_fallback"
    assert "warned_at" in scope_extraction
    # stderr must contain the warning
    output = result.output + (result.stderr or "")
    assert "scope auto-extracted" in output.lower() or "please verify" in output.lower()


# ---------------------------------------------------------------------------
# No file paths anywhere — source=none
# ---------------------------------------------------------------------------


def test_register_no_paths_anywhere_source_none(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """A design doc with no ## Impacted Paths section and no file paths -> source='none'."""
    design_doc = tmp_path / "F-99013_Feature_Design.md"
    design_doc.write_text(
        "# F-99013: No Paths At All\n\n## Description\nNothing concrete here.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99013",
            "No Paths At All",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99013"))
    assert wi is not None
    assert wi.impacted_paths == []
    scope_extraction = wi.config.get("scope_extraction")
    assert scope_extraction is not None
    assert scope_extraction.get("source") == "none"
    output = result.output + (result.stderr or "")
    assert "auto-extracted" not in output.lower()


# ---------------------------------------------------------------------------
# Parser validation error — exit non-zero
# ---------------------------------------------------------------------------


def test_register_invalid_glob_absolute_path_exits_nonzero(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """A design doc containing /etc/passwd in ## Impacted Paths exits non-zero, no row created."""
    design_doc = tmp_path / "F-99014_Feature_Design.md"
    design_doc.write_text(
        "# F-99014: Invalid Paths Test\n\n"
        "## Description\nfoo\n\n"
        "## Impacted Paths\n\n"
        "- /etc/passwd\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99014",
            "Invalid Paths Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
    output = result.output + (result.stderr or "")
    assert "absolute paths are not allowed" in output.lower() or "/etc/passwd" in output

    # No WorkItem row should be created
    wi = db_session.get(WorkItem, ("test-proj", "F-99014"))
    assert wi is None


def test_register_invalid_glob_double_dot_exits_nonzero(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """A design doc containing ../ in ## Impacted Paths exits non-zero, no row created."""
    design_doc = tmp_path / "F-99015_Feature_Design.md"
    design_doc.write_text(
        "# F-99015: Double Dot Test\n\n"
        "## Description\nfoo\n\n"
        "## Impacted Paths\n\n"
        "- orch/../etc/passwd\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99015",
            "Double Dot Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
    output = result.output + (result.stderr or "")
    assert ".." in output or "not allowed" in output.lower()

    wi = db_session.get(WorkItem, ("test-proj", "F-99015"))
    assert wi is None


# ---------------------------------------------------------------------------
# Impacted paths in config is preserved alongside other config keys
# ---------------------------------------------------------------------------


def test_register_impacted_paths_does_not_clobber_existing_config(
    db_session: SASession,
    test_project: Project,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """impacted_paths is added to config, not replacing existing config keys."""
    design_doc = tmp_path / "F-99016_Feature_Design.md"
    design_doc.write_text(
        "# F-99016: Config Preservation Test\n\n"
        "## Description\nfoo\n\n"
        "## Impacted Paths\n\n"
        "- orch/foo.py\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "F-99016",
            "Config Preservation Test",
            "--type",
            "feature",
            "--design-doc",
            str(design_doc),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "F-99016"))
    assert wi is not None
    # config must have scope_extraction
    assert "scope_extraction" in wi.config
