"""Integration tests for ai_assistant config round-trip via project registry.

These tests exercise:
projects.toml -> load_projects_toml/_build_project_config -> sync_project_to_db
-> Project.config JSONB persisted in a real testcontainer-backed DB.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from orch.daemon.project_registry import load_projects_toml, sync_project_to_db
from orch.db.models import Project


def _write_projects_toml(tmp_path: Path, body: str) -> Path:
    toml_path = tmp_path / "projects.toml"
    toml_path.write_text(body, encoding="utf-8")
    return toml_path


def test_ai_assistant_block_roundtrips_into_project_config(db_session, tmp_path: Path) -> None:
    repo_root = tmp_path / "repos" / "demo"
    repo_root.mkdir(parents=True)
    toml_path = _write_projects_toml(
        tmp_path,
        (
            f"[projects.demo]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_root}"\n\n'
            f"[projects.demo.ai_assistant]\n"
            f'models = ["anthropic/claude-sonnet-4-6", "openai/gpt-5.3-codex"]\n'
            f'default_model = "anthropic/claude-sonnet-4-6"\n'
        ),
    )

    projects = load_projects_toml(toml_path)
    assert "demo" in projects
    sync_project_to_db(db_session, projects["demo"])

    persisted = db_session.get(Project, "demo")
    assert persisted is not None
    assert persisted.config.get("ai_assistant") == {
        "models": ["anthropic/claude-sonnet-4-6", "openai/gpt-5.3-codex"],
        "default_model": "anthropic/claude-sonnet-4-6",
    }


def test_invalid_default_model_is_dropped_but_models_persist(
    db_session, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    repo_root = tmp_path / "repos" / "demo"
    repo_root.mkdir(parents=True)
    toml_path = _write_projects_toml(
        tmp_path,
        (
            f"[projects.demo]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_root}"\n\n'
            f"[projects.demo.ai_assistant]\n"
            f'models = ["anthropic/claude-opus-4-7", "openai/gpt-5.3-codex"]\n'
            f'default_model = "ollama/gemma4:26b"\n'
        ),
    )
    caplog.set_level(logging.WARNING)

    projects = load_projects_toml(toml_path)
    assert "demo" in projects
    sync_project_to_db(db_session, projects["demo"])

    persisted = db_session.get(Project, "demo")
    assert persisted is not None
    assert persisted.config.get("ai_assistant") == {
        "models": ["anthropic/claude-opus-4-7", "openai/gpt-5.3-codex"],
    }
    assert any(
        "default_model" in record.message and "ignoring default_model" in record.message
        for record in caplog.records
    ), f"Expected warning about invalid default_model, got: {[r.message for r in caplog.records]}"


def test_absent_ai_assistant_block_results_in_no_ai_assistant_key(
    db_session, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repos" / "demo"
    repo_root.mkdir(parents=True)
    toml_path = _write_projects_toml(
        tmp_path,
        (f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\n'),
    )

    projects = load_projects_toml(toml_path)
    assert "demo" in projects
    sync_project_to_db(db_session, projects["demo"])

    persisted = db_session.get(Project, "demo")
    assert persisted is not None
    assert "ai_assistant" not in persisted.config
