"""Integration tests for ProjectRegistry self_assess flag handling.

Uses a real projects.toml file on disk (tmp_path) to exercise
_build_project_config and ProjectRegistry.load() end-to-end.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from orch.daemon.project_registry import (
    ProjectRegistry,
)


class TestSelfAssessFlagRoundTrip:
    """AC1: self_assess flag in projects.toml → ProjectConfig.self_assess_enabled."""

    def test_flag_true_roundtrips(self, tmp_path: Path) -> None:
        """projects.toml with self_assess=true yields self_assess_enabled=True."""
        repo_root = tmp_path / "repos" / "demo"
        repo_root.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\nself_assess = true\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert "demo" in projects
        assert projects["demo"].self_assess_enabled is True

    def test_flag_false_roundtrips(self, tmp_path: Path) -> None:
        """projects.toml with self_assess=false yields self_assess_enabled=False."""
        repo_root = tmp_path / "repos" / "demo"
        repo_root.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\nself_assess = false\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert "demo" in projects
        assert projects["demo"].self_assess_enabled is False

    def test_flag_absent_defaults_false(self, tmp_path: Path) -> None:
        """projects.toml without self_assess key defaults to False."""
        repo_root = tmp_path / "repos" / "demo"
        repo_root.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert "demo" in projects
        assert projects["demo"].self_assess_enabled is False

    def test_multiple_projects_mixed_flags(self, tmp_path: Path) -> None:
        """Two projects with different self_assess values are loaded independently."""
        repo_alpha = tmp_path / "repos" / "alpha"
        repo_beta = tmp_path / "repos" / "beta"
        repo_gamma = tmp_path / "repos" / "gamma"
        repo_alpha.mkdir(parents=True)
        repo_beta.mkdir(parents=True)
        repo_gamma.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f"[projects.alpha]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_alpha}"\n'
            f"self_assess = true\n\n"
            f"[projects.beta]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_beta}"\n'
            f"self_assess = false\n\n"
            f"[projects.gamma]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_gamma}"\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert projects["alpha"].self_assess_enabled is True
        assert projects["beta"].self_assess_enabled is False
        assert projects["gamma"].self_assess_enabled is False


class TestNonBoolFlagValue:
    """Boundary: non-bool self_assess values log a warning and default to False."""

    @pytest.mark.parametrize(
        "raw_value",
        [
            '"true"',  # TOML string "true"
            '"yes"',  # TOML string "yes"
            "1",  # TOML integer 1
            '"1"',  # TOML string "1"
        ],
    )
    def test_non_bool_value_warns_and_defaults_false(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, raw_value: str
    ) -> None:
        """Non-bool self_assess values default to False and log a warning."""
        repo_root = tmp_path / "repos" / "demo"
        repo_root.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f"[projects.demo]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_root}"\n'
            f"self_assess = {raw_value}\n",
            encoding="utf-8",
        )
        caplog.set_level(logging.WARNING)

        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert "demo" in projects
        assert projects["demo"].self_assess_enabled is False
        messages = [r.message for r in caplog.records]
        assert any("non-bool" in msg or "defaulting" in msg for msg in messages), (
            f"Expected warning about non-bool self_assess, got: {messages}"
        )

    def test_flag_case_sensitivity_false_is_not_true(self, tmp_path: Path) -> None:
        """Python bool("false") is True, but our code checks isinstance(..., bool)."""
        repo_root = tmp_path / "repos" / "demo"
        repo_root.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\nself_assess = false\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        # Explicit False must be respected (not coerced to True)
        assert projects["demo"].self_assess_enabled is False

    def test_flag_absent_defaults_false(self, tmp_path: Path) -> None:
        """projects.toml without self_assess key defaults to False."""
        repo_root = tmp_path / "repos" / "demo"
        repo_root.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f'[projects.demo]\nenabled = true\nrepo_root = "{repo_root}"\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert "demo" in projects
        assert projects["demo"].self_assess_enabled is False

    def test_multiple_projects_mixed_flags(self, tmp_path: Path) -> None:
        """Two projects with different self_assess values are loaded independently."""
        repo_alpha = tmp_path / "repos" / "alpha"
        repo_beta = tmp_path / "repos" / "beta"
        repo_gamma = tmp_path / "repos" / "gamma"
        repo_alpha.mkdir(parents=True)
        repo_beta.mkdir(parents=True)
        repo_gamma.mkdir(parents=True)
        toml = tmp_path / "projects.toml"
        toml.write_text(
            f"[projects.alpha]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_alpha}"\n'
            f"self_assess = true\n\n"
            f"[projects.beta]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_beta}"\n'
            f"self_assess = false\n\n"
            f"[projects.gamma]\n"
            f"enabled = true\n"
            f'repo_root = "{repo_gamma}"\n',
            encoding="utf-8",
        )
        registry = ProjectRegistry(path=toml)
        projects = registry.load()

        assert projects["alpha"].self_assess_enabled is True
        assert projects["beta"].self_assess_enabled is False
        assert projects["gamma"].self_assess_enabled is False
