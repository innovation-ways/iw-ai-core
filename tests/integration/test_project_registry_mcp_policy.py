"""Integration tests for mcp_policy config round-trip via project registry.

Exercises:
  projects.toml -> load_projects_toml -> _parse_mcp_policy_block -> sync_project_to_db
  -> Project.config JSONB persisted in a real testcontainer-backed DB.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from orch.daemon.project_registry import load_projects_toml, sync_project_to_db
from orch.db.models import Project


def _write_projects_toml(tmp_path: Path, body: str) -> Path:
    """Write a projects.toml file in tmp_path and return its path.

    Args:
        tmp_path: Temporary directory for the file.
        body: TOML content to write.

    Returns:
        Path to the written file.
    """
    toml_path = tmp_path / "projects.toml"
    toml_path.write_text(body, encoding="utf-8")
    return toml_path


def test_mcp_policy_block_roundtrips_into_project_config(
    db_session: object, tmp_path: Path
) -> None:
    """Valid mcp_policy block is persisted into Project.config['mcp_policy']."""
    repo_root = tmp_path / "repos" / "demo"
    repo_root.mkdir(parents=True)
    toml_path = _write_projects_toml(
        tmp_path,
        (
            f"[projects.demo]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_root}"\n\n'
            f"[projects.demo.mcp_policy]\n"
            f'tier1 = "allow"\n'
            f'tier3 = "deny"\n'
            f'default = "ask"\n'
        ),
    )

    projects = load_projects_toml(toml_path)
    assert "demo" in projects
    sync_project_to_db(db_session, projects["demo"])

    persisted = db_session.get(Project, "demo")
    assert persisted is not None
    mcp_policy = persisted.config.get("mcp_policy")
    assert mcp_policy is not None
    assert mcp_policy.get("tier1") == "allow"
    assert mcp_policy.get("tier3") == "deny"
    assert mcp_policy.get("default") == "ask"


def test_invalid_mcp_policy_values_dropped(
    db_session: object, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid decision values are dropped; valid ones are kept."""
    repo_root = tmp_path / "repos" / "demo"
    repo_root.mkdir(parents=True)
    toml_path = _write_projects_toml(
        tmp_path,
        (
            f"[projects.demo]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_root}"\n\n'
            f"[projects.demo.mcp_policy]\n"
            f'tier2 = "ask"\n'
            f'tier3 = "not_a_decision"\n'
        ),
    )
    caplog.set_level(logging.WARNING)

    projects = load_projects_toml(toml_path)
    sync_project_to_db(db_session, projects["demo"])

    persisted = db_session.get(Project, "demo")
    assert persisted is not None
    mcp_policy = persisted.config.get("mcp_policy")
    assert mcp_policy is not None
    assert mcp_policy.get("tier2") == "ask"
    assert "tier3" not in mcp_policy
    assert caplog.text.lower().find("invalid decision") != -1


def test_absent_mcp_policy_block_not_in_config(db_session: object, tmp_path: Path) -> None:
    """When mcp_policy is absent from projects.toml, config has no 'mcp_policy' key."""
    repo_root = tmp_path / "repos" / "demo"
    repo_root.mkdir(parents=True)
    toml_path = _write_projects_toml(
        tmp_path,
        (f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\n'),
    )

    projects = load_projects_toml(toml_path)
    sync_project_to_db(db_session, projects["demo"])

    persisted = db_session.get(Project, "demo")
    assert persisted is not None
    assert "mcp_policy" not in persisted.config
