"""Integration tests for iw init-project against a real PostgreSQL testcontainer."""

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from orch.cli.main import cli
from orch.db.models import IdSequence, MigrationLock, Project

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_platform_root(tmp_path: Path) -> Path:
    """Create a minimal iw-ai-core platform root for tests."""
    platform_root = tmp_path / "platform"
    (platform_root / "templates").mkdir(parents=True)
    (platform_root / "skills").mkdir(parents=True)
    (platform_root / "projects.toml").write_text(
        "# IW AI Core — Project Registry\n", encoding="utf-8"
    )
    (platform_root / "templates" / "default_workflow.md").write_text(
        "# Workflow Definition\n## Steps\n1. Implementation\n", encoding="utf-8"
    )
    return platform_root


# ---------------------------------------------------------------------------
# Full init creates correct DB records
# ---------------------------------------------------------------------------


def test_full_init_creates_db_records(
    db_session: SASession,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "my-project"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)

    # Patch platform root so init_project uses tmp dirs, not the real repo
    import orch.skills.init_project as init_mod

    original_root = init_mod._PLATFORM_ROOT
    init_mod._PLATFORM_ROOT = platform_root
    try:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["init-project", "--id", "new-proj", "--path", str(repo_path), "--name", "New Project"],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
    finally:
        init_mod._PLATFORM_ROOT = original_root

    assert result.exit_code == 0, result.output

    # Project row exists
    project = db_session.execute(
        select(Project).where(Project.id == "new-proj")
    ).scalar_one_or_none()
    assert project is not None
    assert project.display_name == "New Project"
    assert project.repo_root == str(repo_path)

    # ID sequences exist for all prefixes
    sequences = (
        db_session.execute(select(IdSequence).where(IdSequence.project_id == "new-proj"))
        .scalars()
        .all()
    )
    prefixes = {seq.prefix for seq in sequences}
    assert prefixes == {"F", "I", "CR", "BATCH"}
    for seq in sequences:
        assert seq.next_number == 1

    # Migration lock exists
    lock = db_session.execute(
        select(MigrationLock).where(MigrationLock.project_id == "new-proj")
    ).scalar_one_or_none()
    assert lock is not None
    assert lock.current_holder is None


# ---------------------------------------------------------------------------
# iw projects list shows newly initialized project
# ---------------------------------------------------------------------------


def test_init_project_appears_in_projects_list(
    db_session: SASession,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "listed-project"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)

    import orch.skills.init_project as init_mod

    original_root = init_mod._PLATFORM_ROOT
    init_mod._PLATFORM_ROOT = platform_root
    try:
        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "init-project",
                "--id",
                "listed-proj",
                "--path",
                str(repo_path),
                "--name",
                "Listed Project",
            ],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
    finally:
        init_mod._PLATFORM_ROOT = original_root

    result = runner.invoke(
        cli,
        ["--json", "projects", "list"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    projects = json.loads(result.output)
    ids = [p["id"] for p in projects]
    assert "listed-proj" in ids


# ---------------------------------------------------------------------------
# iw next-id works for the new project (starts at 1)
# ---------------------------------------------------------------------------


def test_next_id_works_for_new_project(
    db_session: SASession,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "id-project"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)

    import orch.skills.init_project as init_mod

    original_root = init_mod._PLATFORM_ROOT
    init_mod._PLATFORM_ROOT = platform_root
    try:
        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "init-project",
                "--id",
                "id-proj",
                "--path",
                str(repo_path),
                "--name",
                "ID Project",
            ],
            obj={"get_session": cli_get_session},
            catch_exceptions=False,
        )
    finally:
        init_mod._PLATFORM_ROOT = original_root

    result = runner.invoke(
        cli,
        ["--project", "id-proj", "next-id", "--type", "incident"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "I001"

    result2 = runner.invoke(
        cli,
        ["--project", "id-proj", "next-id", "--type", "feature"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result2.exit_code == 0
    assert result2.output.strip() == "F001"
