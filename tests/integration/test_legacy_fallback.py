"""Integration test for legacy fallback behavior (AC7).

Verifies that projects without iw-config fall back silently without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.conftest import (
    db_engine,  # noqa: F401
    db_session,  # noqa: F401
)


@pytest.fixture
def worktree_without_iw_config(tmp_path: Path) -> Path:
    """Create a worktree directory without ai-dev/iw-config."""
    wt = tmp_path / "legacy_worktree"
    wt.mkdir()
    (wt / ".env").write_text("IW_CORE_OTHER=value\n")
    gitignore = wt / ".gitignore"
    gitignore.write_text(".env\nother\n")
    return wt


@pytest.mark.integration
def test_project_without_iw_config_has_iw_config_returns_false(
    worktree_without_iw_config: Path,
) -> None:
    """AC7 — has_iw_config returns False when no iw-config directory exists."""
    from orch.daemon import worktree_compose

    wt = worktree_without_iw_config

    assert worktree_compose.has_iw_config(wt) is False
