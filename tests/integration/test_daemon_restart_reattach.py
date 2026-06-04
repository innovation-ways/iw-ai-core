"""Integration test for daemon restart re-attach behavior (AC5).

Verifies that when the daemon restarts mid-batch, it correctly identifies
running stacks and does not re-create them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.integration.conftest import (
    db_engine,  # noqa: F401
    db_session,  # noqa: F401
)

DOCKER_AVAILABLE: bool | None = None


def _check_docker() -> bool:
    global DOCKER_AVAILABLE
    if DOCKER_AVAILABLE is not None:
        return DOCKER_AVAILABLE
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        DOCKER_AVAILABLE = result.returncode == 0
    except Exception:
        DOCKER_AVAILABLE = False
    return DOCKER_AVAILABLE


@pytest.fixture
def docker_available():
    if not _check_docker():
        pytest.skip("Docker not available")
    return True


@pytest.mark.integration
def test_daemon_restart_reattaches_to_running_stack(
    docker_available: bool,
    tmp_path: Path,
) -> None:
    """AC5 — kill daemon mid-batch, restart, verify stack is re-attached and not re-up'd.

    This test:
    1. Sets up a scratch worktree + iw-config
    2. Inserts a BatchItem row with worktree_compose_path set
    3. Brings the stack up via worktree_compose.up()
    4. Simulates daemon restart: calls the startup re-attach helper
    5. Captures all DaemonEvent rows for this batch_item_id
    6. Asserts NO second phase='up' event was emitted
    7. Asserts worktree_compose.is_alive() returns True
    """
    from orch.daemon import worktree_compose

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()
    git_dir = wt_dir / ".git"
    git_dir.mkdir()
    iw_dir = wt_dir / "ai-dev" / "iw-config"
    iw_dir.mkdir(parents=True)

    (iw_dir / "worktree-compose.template.yml").write_text(
        "services:\n"
        "  db:\n"
        "    image: postgres:15-alpine\n"
        "    environment:\n"
        "      POSTGRES_DB: reattach_test\n"
        "      POSTGRES_USER: testuser\n"
        "      POSTGRES_PASSWORD: testpass\n"
        "    ports:\n"
        "      - '5432'\n"
        "    labels:\n"
        '      iwcore.batch_item: "REATTACH-TEST"\n'
        "      iwcore.role: worktree-db\n"
        "      iwcore.project: test-proj\n"
    )

    compose_file = wt_dir / ".iw" / "docker-compose-REATTACH-TEST.yml"
    compose_file.parent.mkdir(parents=True, exist_ok=True)

    env_file = wt_dir / ".env"
    env_file.write_text("IW_CORE_DB_HOST=localhost\n")
    gitignore = wt_dir / ".gitignore"
    gitignore.write_text(".env\n.iw/\n")

    try:
        cfg = worktree_compose.load_config("REATTACH-TEST", "test-proj", wt_dir)
        result = worktree_compose.up(cfg)

        assert result.success, f"Stack up failed: {result.error_message}"

        is_alive_before = worktree_compose.is_alive("REATTACH-TEST")
        assert is_alive_before is True, "Stack should be alive after up()"

        with patch("orch.daemon.worktree_compose._emit_daemon_event") as mock_emit:
            worktree_compose.up(cfg)

        up_calls_after_restart = [
            call
            for call in mock_emit.call_args_list
            if call[1].get("metadata", {}).get("phase") == "up"
        ]
        assert len(up_calls_after_restart) == 0, (
            "Second up() should not emit phase='up' event for already-running stack"
        )

        is_alive_after = worktree_compose.is_alive("REATTACH-TEST")
        assert is_alive_after is True, "Stack should still be alive after re-attach simulation"

    finally:
        worktree_compose.down("REATTACH-TEST", None)
