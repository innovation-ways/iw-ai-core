"""Integration test for executor docker-free invariant (Invariant #1).

Verifies that executor bash scripts do not call docker directly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_executor_scripts_have_zero_docker_invocations() -> None:
    """Invariant #1 — executor bash scripts must not call docker.

    This test greps all executor scripts for docker invocations and asserts none exist
    (except for comments).
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    executor_dir = repo_root / "executor"

    if not executor_dir.exists():
        pytest.skip("executor/ directory not found")

    docker_lines = []
    for script_path in executor_dir.glob("*.sh"):
        result = subprocess.run(
            ["grep", "-n", "-E", r"\bdocker\b", str(script_path)],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            if "#" in line:
                comment_idx = line.index("#")
                code_part = line[:comment_idx]
                if "docker" in code_part.lower():
                    docker_lines.append(f"{script_path}:{line}")
            else:
                docker_lines.append(f"{script_path}:{line}")

    assert len(docker_lines) == 0, f"executor/ scripts contain docker calls: {docker_lines}"
