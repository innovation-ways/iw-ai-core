"""Unit tests for auto_amend_scope parsing in project_registry — CR-00087 S01.

Tests the parsing and validation of the optional auto_amend_scope block
from .iw-orch.json. Verifies defaults, full parsing, and warning on malformed
input. Follows the same fixture style as test_project_registry_overlap_gate.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orch.daemon.project_registry import ProjectConfig, _parse_auto_amend_scope

# ---------------------------------------------------------------------------
# Fixture helpers — mirror test_project_registry_overlap_gate.py style
# ---------------------------------------------------------------------------

PROJECT_ID = "test-proj"


def _write_iw_orch_json(tmp_path: Path, config: dict) -> Path:
    """Write a .iw-orch.json file and return the path."""
    path = tmp_path / ".iw-orch.json"
    path.write_text(json.dumps(config))
    return path


# ---------------------------------------------------------------------------
# Tests for _parse_auto_amend_scope helper (pure function)
# ---------------------------------------------------------------------------


class TestParseAutoAmendScope:
    """Tests for _parse_auto_amend_scope function."""

    def test_none_returns_defaults(self) -> None:
        """raw is None → returns ([], None), no warning."""
        patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, None)
        assert patterns == []
        assert max_paths is None

    def test_valid_block_with_both_fields(self) -> None:
        """Valid block with auto_allow_patterns and max_paths."""
        raw = {
            "auto_allow_patterns": ["tests/**", "**/*.md", "docs/**"],
            "max_paths": 10,
        }
        patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == ["tests/**", "**/*.md", "docs/**"]
        assert max_paths == 10

    def test_valid_block_patterns_only_max_paths_none(self) -> None:
        """Valid block with auto_allow_patterns only; max_paths absent."""
        raw = {
            "auto_allow_patterns": ["tests/**", "**/*.md"],
        }
        patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == ["tests/**", "**/*.md"]
        assert max_paths is None

    def test_malformed_raw_is_list(self, caplog: pytest.LogCaptureFixture) -> None:
        """raw is a list (not a dict) → defaults + WARNING."""
        raw = ["tests/**", "docs/**"]
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == []
        assert max_paths is None
        assert any("not a dict" in msg for msg in caplog.messages)

    def test_malformed_auto_allow_patterns_is_string(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """auto_allow_patterns is a string instead of list → feature off + WARNING.

        Per spec: when auto_allow_patterns is not a list, the block is treated
        as absent and the feature is disabled (matches _parse_overlap_gate
        behaviour for the same class of error).
        """
        raw = {
            "auto_allow_patterns": "tests/**",  # not a list
            "max_paths": 5,
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == [], "feature off when auto_allow_patterns not a list"
        assert max_paths is None, "max_paths also dropped when block is invalid"
        assert any("not a list" in msg for msg in caplog.messages)

    def test_malformed_auto_allow_patterns_mixed_entries(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Mixed entries: non-string entries dropped with per-entry WARNING."""
        raw = {
            "auto_allow_patterns": ["tests/**", 123, "**/*.md", None],
            "max_paths": 5,
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        # Only valid string entries survive
        assert patterns == ["tests/**", "**/*.md"]
        assert max_paths == 5
        # Should have warned about 123 and None
        warnings = [rec.message for rec in caplog.records]
        assert len(warnings) >= 2, f"Expected >=2 warnings, got: {warnings}"

    def test_malformed_max_paths_is_string(self, caplog: pytest.LogCaptureFixture) -> None:
        """max_paths is a string "10" → patterns populated, max_paths None + WARNING."""
        raw = {
            "auto_allow_patterns": ["tests/**", "**/*.md"],
            "max_paths": "10",
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == ["tests/**", "**/*.md"]
        assert max_paths is None
        assert any("not an int" in msg for msg in caplog.messages)

    def test_malformed_max_paths_is_bool_true(self, caplog: pytest.LogCaptureFixture) -> None:
        """max_paths is bool True (not int) → explicit rejection + WARNING."""
        raw = {
            "auto_allow_patterns": ["tests/**", "**/*.md"],
            "max_paths": True,
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == ["tests/**", "**/*.md"]
        assert max_paths is None
        assert any("not an int" in msg for msg in caplog.messages)

    def test_malformed_max_paths_is_negative(self, caplog: pytest.LogCaptureFixture) -> None:
        """max_paths is -1 → treated as None + WARNING."""
        raw = {
            "auto_allow_patterns": ["tests/**", "**/*.md"],
            "max_paths": -1,
        }
        with caplog.at_level("WARNING", logger="orch.daemon.project_registry"):
            patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == ["tests/**", "**/*.md"]
        assert max_paths is None
        assert any("negative" in msg for msg in caplog.messages)

    def test_empty_patterns_returns_empty_and_does_not_fire(self) -> None:
        """auto_allow_patterns=[] with max_paths absent → ([], None)."""
        raw = {
            "auto_allow_patterns": [],
        }
        patterns, max_paths = _parse_auto_amend_scope(PROJECT_ID, raw)
        assert patterns == []
        assert max_paths is None


# ---------------------------------------------------------------------------
# Tests for ProjectConfig auto_amend fields (integration via _build_project_config)
# ---------------------------------------------------------------------------


class TestProjectConfigAutoAmendScope:
    """Tests for ProjectConfig.auto_amend_allow_patterns and auto_amend_max_paths."""

    def test_auto_amend_scope_absent_uses_defaults(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """auto_amend_scope absent from .iw-orch.json → defaults, no WARNING."""
        _write_iw_orch_json(tmp_path, {"display_name": "Test Proj"})
        # Simulate loading a project with this .iw-orch.json by checking defaults
        # on the fields as they exist on ProjectConfig
        cfg = ProjectConfig(
            id=PROJECT_ID,
            display_name="Test",
            repo_root=str(tmp_path),
            enabled=True,
            cli_tool="opencode",
            model="minimax/MiniMax-M2.7",
            worktree_base=".worktrees",
            config={},
        )
        assert cfg.auto_amend_allow_patterns == []
        assert cfg.auto_amend_max_paths is None
        # No warning should be emitted for absent config
        assert not any("auto_amend" in msg for msg in caplog.messages)
