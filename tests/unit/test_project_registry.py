"""Unit tests for the project registry.

Uses tmp_path to create real files; no database involved.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from orch.daemon.project_registry import (
    ProjectRegistry,
    load_projects_toml,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_toml(path: Path, content: str) -> None:
    path.write_text(content)


def make_project_dir(tmp_path: Path, project_id: str, iw_config: dict | None = None) -> Path:
    """Create a fake project directory with an optional .iw-orch.json."""
    repo = tmp_path / project_id
    repo.mkdir(parents=True, exist_ok=True)
    if iw_config is not None:
        (repo / ".iw-orch.json").write_text(json.dumps(iw_config))
    return repo


def make_toml_file(tmp_path: Path, projects: dict[str, dict]) -> Path:
    """Write a projects.toml with the given project entries."""
    lines: list[str] = []
    for pid, cfg in projects.items():
        lines.append(f"[projects.{pid}]")
        for key, value in cfg.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, int):
                lines.append(f"{key} = {value}")
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text("\n".join(lines) + "\n")
    return toml_file


# ---------------------------------------------------------------------------
# load_projects_toml — parsing
# ---------------------------------------------------------------------------


def test_load_valid_single_project(tmp_path: Path) -> None:
    """A minimal valid projects.toml produces one ProjectConfig."""
    repo = make_project_dir(tmp_path, "alpha")
    toml_file = make_toml_file(tmp_path, {"alpha": {"repo_root": str(repo)}})

    projects = load_projects_toml(toml_file)

    assert "alpha" in projects
    cfg = projects["alpha"]
    assert cfg.id == "alpha"
    assert cfg.repo_root == str(repo)
    assert cfg.enabled is True  # default


def test_load_enabled_false(tmp_path: Path) -> None:
    """enabled = false is respected."""
    repo = make_project_dir(tmp_path, "beta")
    toml_file = make_toml_file(tmp_path, {"beta": {"repo_root": str(repo), "enabled": False}})

    projects = load_projects_toml(toml_file)

    assert projects["beta"].enabled is False


def test_load_display_name_from_toml(tmp_path: Path) -> None:
    """display_name in projects.toml takes precedence over .iw-orch.json."""
    repo = make_project_dir(tmp_path, "gamma", iw_config={"display_name": "From JSON"})
    toml_file = make_toml_file(
        tmp_path,
        {"gamma": {"repo_root": str(repo), "display_name": "From TOML"}},
    )

    projects = load_projects_toml(toml_file)

    assert projects["gamma"].display_name == "From TOML"


def test_load_display_name_fallback_to_iw_orch_json(tmp_path: Path) -> None:
    """If display_name is absent from toml, falls back to .iw-orch.json."""
    repo = make_project_dir(tmp_path, "delta", iw_config={"display_name": "Delta Project"})
    toml_file = make_toml_file(tmp_path, {"delta": {"repo_root": str(repo)}})

    projects = load_projects_toml(toml_file)

    assert projects["delta"].display_name == "Delta Project"


def test_load_display_name_fallback_to_project_id(tmp_path: Path) -> None:
    """If display_name is absent from both toml and .iw-orch.json, uses project_id."""
    repo = make_project_dir(tmp_path, "epsilon")
    toml_file = make_toml_file(tmp_path, {"epsilon": {"repo_root": str(repo)}})

    projects = load_projects_toml(toml_file)

    assert projects["epsilon"].display_name == "epsilon"


def test_load_cli_tool_from_iw_orch_json(tmp_path: Path) -> None:
    """cli_tool is read from .iw-orch.json, defaulting to 'opencode'."""
    repo_opencode = make_project_dir(tmp_path, "proj1")
    repo_claude = make_project_dir(tmp_path, "proj2", iw_config={"cli_tool": "claude"})

    toml_file = make_toml_file(
        tmp_path,
        {
            "proj1": {"repo_root": str(repo_opencode)},
            "proj2": {"repo_root": str(repo_claude)},
        },
    )

    projects = load_projects_toml(toml_file)

    assert projects["proj1"].cli_tool == "opencode"
    assert projects["proj2"].cli_tool == "claude"


def test_load_worktree_base_from_iw_orch_json(tmp_path: Path) -> None:
    """worktree_base defaults to '.worktrees' if not specified."""
    repo = make_project_dir(tmp_path, "wt", iw_config={"worktree_base": "my-worktrees"})
    repo_default = make_project_dir(tmp_path, "wtd")

    toml_file = make_toml_file(
        tmp_path,
        {
            "wt": {"repo_root": str(repo)},
            "wtd": {"repo_root": str(repo_default)},
        },
    )

    projects = load_projects_toml(toml_file)

    assert projects["wt"].worktree_base == "my-worktrees"
    assert projects["wtd"].worktree_base == ".worktrees"


def test_load_multiple_projects(tmp_path: Path) -> None:
    """Multiple projects are loaded correctly."""
    repo_a = make_project_dir(tmp_path, "proj-a")
    repo_b = make_project_dir(tmp_path, "proj-b")

    toml_file = make_toml_file(
        tmp_path,
        {
            "proj-a": {"repo_root": str(repo_a)},
            "proj-b": {"repo_root": str(repo_b), "enabled": False},
        },
    )

    projects = load_projects_toml(toml_file)

    assert len(projects) == 2
    assert projects["proj-a"].enabled is True
    assert projects["proj-b"].enabled is False


def test_load_empty_file(tmp_path: Path) -> None:
    """An empty projects.toml returns an empty dict."""
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text("# no projects yet\n")

    projects = load_projects_toml(toml_file)

    assert projects == {}


# ---------------------------------------------------------------------------
# Invalid project entries — skipped gracefully
# ---------------------------------------------------------------------------


def test_missing_repo_root_skips_project(tmp_path: Path) -> None:
    """A project without repo_root is skipped (logged as warning)."""
    toml_file = make_toml_file(tmp_path, {"bad": {"enabled": True}})

    projects = load_projects_toml(toml_file)

    assert "bad" not in projects


def test_nonexistent_repo_root_skips_project(tmp_path: Path) -> None:
    """A project whose repo_root doesn't exist is skipped."""
    toml_file = make_toml_file(tmp_path, {"ghost": {"repo_root": "/nonexistent/path/12345"}})

    projects = load_projects_toml(toml_file)

    assert "ghost" not in projects


def test_invalid_iw_orch_json_uses_defaults(tmp_path: Path) -> None:
    """An invalid .iw-orch.json doesn't fail — project loads with defaults."""
    repo = make_project_dir(tmp_path, "broken")
    (repo / ".iw-orch.json").write_text("not valid json {{{")

    toml_file = make_toml_file(tmp_path, {"broken": {"repo_root": str(repo)}})

    projects = load_projects_toml(toml_file)

    # Project still loads — just with defaults
    assert "broken" in projects
    assert projects["broken"].cli_tool == "opencode"


def test_invalid_toml_syntax_returns_empty(tmp_path: Path) -> None:
    """A malformed projects.toml returns an empty dict without crashing."""
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text("[projects.bad\nthis is broken toml ===\n")

    projects = load_projects_toml(toml_file)

    assert projects == {}


def test_valid_and_invalid_project_coexist(tmp_path: Path) -> None:
    """Valid projects load even if sibling entries are invalid."""
    valid_repo = make_project_dir(tmp_path, "valid")
    toml_file = make_toml_file(
        tmp_path,
        {
            "valid": {"repo_root": str(valid_repo)},
            "invalid": {"repo_root": "/nowhere/nonexistent"},
        },
    )

    projects = load_projects_toml(toml_file)

    assert "valid" in projects
    assert "invalid" not in projects


# ---------------------------------------------------------------------------
# ProjectRegistry — mtime tracking and reload detection
# ---------------------------------------------------------------------------


def test_registry_initial_load(tmp_path: Path) -> None:
    """registry.load() returns all valid projects."""
    repo = make_project_dir(tmp_path, "myproject")
    toml_file = make_toml_file(tmp_path, {"myproject": {"repo_root": str(repo)}})

    registry = ProjectRegistry(path=toml_file)
    projects = registry.load()

    assert "myproject" in projects


def test_registry_is_stale_false_after_load(tmp_path: Path) -> None:
    """After loading, is_stale() returns False (mtime is current)."""
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text("")

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    assert not registry.is_stale()


def test_registry_is_stale_true_after_modification(tmp_path: Path) -> None:
    """After the file is modified, is_stale() returns True."""
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text("")

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    # Simulate file modification by changing mtime
    registry._mtime = 0.0  # force stale  # noqa: SLF001

    assert registry.is_stale()


def test_registry_detects_new_project(tmp_path: Path) -> None:
    """reload() detects a project that was added since the last load."""
    repo_a = make_project_dir(tmp_path, "proj-a")
    toml_file = make_toml_file(tmp_path, {"proj-a": {"repo_root": str(repo_a)}})

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    # Add a new project
    repo_b = make_project_dir(tmp_path, "proj-b")
    make_toml_file(
        tmp_path,
        {
            "proj-a": {"repo_root": str(repo_a)},
            "proj-b": {"repo_root": str(repo_b)},
        },
    )

    new_projects, changes = registry.reload()

    assert changes.get("proj-b") == "added"
    assert "proj-b" in new_projects


def test_registry_detects_removed_project(tmp_path: Path) -> None:
    """reload() detects a project that was removed since the last load."""
    repo_a = make_project_dir(tmp_path, "proj-a")
    repo_b = make_project_dir(tmp_path, "proj-b")
    toml_file = make_toml_file(
        tmp_path,
        {
            "proj-a": {"repo_root": str(repo_a)},
            "proj-b": {"repo_root": str(repo_b)},
        },
    )

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    # Remove proj-b
    make_toml_file(tmp_path, {"proj-a": {"repo_root": str(repo_a)}})

    _, changes = registry.reload()

    assert changes.get("proj-b") == "removed"


def test_registry_detects_project_disabled(tmp_path: Path) -> None:
    """reload() detects when a project transitions from enabled to disabled."""
    repo = make_project_dir(tmp_path, "proj")
    toml_file = make_toml_file(tmp_path, {"proj": {"repo_root": str(repo), "enabled": True}})

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    make_toml_file(tmp_path, {"proj": {"repo_root": str(repo), "enabled": False}})

    new_projects, changes = registry.reload()

    assert changes.get("proj") == "disabled"
    assert new_projects["proj"].enabled is False


def test_registry_detects_project_enabled(tmp_path: Path) -> None:
    """reload() detects when a project transitions from disabled to enabled."""
    repo = make_project_dir(tmp_path, "proj")
    toml_file = make_toml_file(tmp_path, {"proj": {"repo_root": str(repo), "enabled": False}})

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    make_toml_file(tmp_path, {"proj": {"repo_root": str(repo), "enabled": True}})

    _, changes = registry.reload()

    assert changes.get("proj") == "enabled"


def test_registry_unchanged_project(tmp_path: Path) -> None:
    """reload() marks unchanged projects as 'unchanged'."""
    repo = make_project_dir(tmp_path, "proj")
    toml_file = make_toml_file(tmp_path, {"proj": {"repo_root": str(repo)}})

    registry = ProjectRegistry(path=toml_file)
    registry.load()

    # Reload the same file content
    _, changes = registry.reload()

    assert changes.get("proj") == "unchanged"
