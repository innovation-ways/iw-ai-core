"""Unit tests for project initialization.

Tests cover file system operations only — no DB required.
A mock session is used to verify DB calls without a live database.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from orch.skills.init_project import ProjectsTomlError, init_project

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


def _make_platform_root(tmp_path: Path) -> Path:
    """Create a minimal platform root with templates and skills dirs."""
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
# .iw-orch.json creation
# ---------------------------------------------------------------------------


def test_creates_iw_orch_json(tmp_path: Path) -> None:
    repo_path = tmp_path / "my-project"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    init_project("my-proj", repo_path, "My Project", session, platform_root=platform_root)

    config_file = repo_path / ".iw-orch.json"
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data["project_id"] == "my-proj"
    assert "max_parallel" in data


def test_iw_orch_json_contains_project_id(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    init_project("my-cool-proj", repo_path, "Cool", session, platform_root=platform_root)

    data = json.loads((repo_path / ".iw-orch.json").read_text())
    assert data["project_id"] == "my-cool-proj"


# ---------------------------------------------------------------------------
# ai-dev directory structure
# ---------------------------------------------------------------------------


def test_creates_ai_dev_directories(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    init_project("proj", repo_path, "Proj", session, platform_root=platform_root)

    assert (repo_path / "ai-dev" / "design" / "active").is_dir()


# ---------------------------------------------------------------------------
# workflow.md from template
# ---------------------------------------------------------------------------


def test_creates_workflow_md_from_template(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    init_project("proj", repo_path, "Proj", session, platform_root=platform_root)

    workflow_md = repo_path / "ai-dev" / "workflow.md"
    assert workflow_md.exists()
    content = workflow_md.read_text()
    assert "Workflow Definition" in content
    assert "Implementation" in content


def test_creates_workflow_md_without_template(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    # Remove template
    (platform_root / "templates" / "default_workflow.md").unlink()
    session = _make_mock_session()

    init_project("proj", repo_path, "Proj", session, platform_root=platform_root)

    workflow_md = repo_path / "ai-dev" / "workflow.md"
    assert workflow_md.exists()


# ---------------------------------------------------------------------------
# projects.toml updated
# ---------------------------------------------------------------------------


def test_appends_to_projects_toml(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    init_project("my-proj", repo_path, "My Project", session, platform_root=platform_root)

    toml_content = (platform_root / "projects.toml").read_text()
    assert "my-proj" in toml_content
    assert "My Project" in toml_content
    assert str(repo_path) in toml_content


# ---------------------------------------------------------------------------
# Result summary
# ---------------------------------------------------------------------------


def test_result_contains_created_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    result = init_project("proj", repo_path, "Proj", session, platform_root=platform_root)

    assert ".iw-orch.json" in result.created_files
    assert "ai-dev/workflow.md" in result.created_files
    assert result.projects_toml_updated is True


def test_result_db_rows_created(tmp_path: Path) -> None:
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    result = init_project("proj", repo_path, "Proj", session, platform_root=platform_root)

    # Should have created project + 4 sequences + migration lock
    assert any("projects" in row for row in result.db_rows_created)
    assert any("id_sequences" in row for row in result.db_rows_created)
    assert any("migration_locks" in row for row in result.db_rows_created)


# ---------------------------------------------------------------------------
# projects.toml idempotency — regression for the duplicate-table corruption
# ---------------------------------------------------------------------------


def test_projects_toml_append_is_idempotent(tmp_path: Path) -> None:
    """Registering the same project twice must not duplicate the TOML table.

    Duplicate [projects.x] tables make tomllib refuse to parse the file,
    which silently clears the daemon's in-memory project registry and
    halts all work items.
    """
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    session = _make_mock_session()

    init_project("my-proj", repo_path, "My Project", session, platform_root=platform_root)
    result2 = init_project("my-proj", repo_path, "My Project", session, platform_root=platform_root)

    toml_content = (platform_root / "projects.toml").read_text()
    assert toml_content.count("[projects.my-proj]") == 1
    assert result2.projects_toml_updated is False

    import tomllib

    # Must still parse cleanly after the second init_project call
    parsed = tomllib.loads(toml_content)
    assert "my-proj" in parsed["projects"]


def test_init_project_refuses_corrupt_projects_toml(tmp_path: Path) -> None:
    """If projects.toml is already unparseable, init_project must fail loudly.

    Appending to a broken file would compound the corruption and keep the
    daemon stuck on its next reload.
    """
    import pytest

    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    platform_root = _make_platform_root(tmp_path)
    # Corrupt the file with a duplicate table
    (platform_root / "projects.toml").write_text(
        "[projects.dup]\nrepo_root='/tmp/a'\n[projects.dup]\nrepo_root='/tmp/b'\n"
    )
    session = _make_mock_session()

    with pytest.raises(ProjectsTomlError):
        init_project("new-proj", repo_path, "New Proj", session, platform_root=platform_root)
