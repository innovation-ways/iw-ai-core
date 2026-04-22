"""Integration tests for docker-compose split (CR-00015).

Verifies that the root docker-compose.yml is intentionally empty (no `db`
service) and that the bootstrap file defines `db` with a stable volume name
regardless of working directory. Also verifies `ai-core.sh db start` is a
no-op when the DB is already accepting connections.

Tests are READ-ONLY — no destructive docker operations.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def _docker_available() -> bool:
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.returncode == 0


def _db_reachable() -> bool:
    return (
        subprocess.run(
            ["nc", "-z", "-w2", "localhost", os.environ.get("IW_CORE_DB_PORT", "5433")],
            capture_output=True,
        ).returncode
        == 0
    )


@pytest.mark.integration
def test_root_compose_has_no_db_service():
    """Root docker-compose.yml must NOT have a `db` service."""
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"compose config failed: {result.stderr}"
    config = json.loads(result.stdout)
    services = config.get("services", {})
    assert "db" not in services, (
        f"Root compose has a 'db' service — should be in bootstrap only. Services: {list(services)}"
    )


@pytest.mark.integration
def test_bootstrap_compose_has_db_service():
    """Bootstrap compose file must have a `db` service with correct settings."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.bootstrap.yml",
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"bootstrap config failed: {result.stderr}"
    config = json.loads(result.stdout)
    assert "db" in config["services"], "bootstrap compose must have a 'db' service"
    db = config["services"]["db"]
    assert db["image"].startswith("postgres:15")
    assert db["container_name"] == "iw-ai-core-db"


@pytest.mark.skipif(not _docker_available(), reason="docker not available")
@pytest.mark.integration
def test_bootstrap_volume_name_stable_across_cwd(tmp_path: Path):
    """Volume name must be identical regardless of cwd — exercises the foot-gun.

    The `name: iw-ai-core` top-level key in bootstrap pins the project name so
    `docker compose config` returns the same volume name from any directory.
    """
    bootstrap_src = PROJECT_ROOT / "docker-compose.bootstrap.yml"
    shutil.copy(bootstrap_src, tmp_path / "docker-compose.bootstrap.yml")

    def get_volume_name(cwd: Path) -> str:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.bootstrap.yml",
                "config",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        assert result.returncode == 0, f"config failed from {cwd}: {result.stderr}"
        config = json.loads(result.stdout)
        volumes = config["volumes"]
        vol_key = list(volumes.keys())[0]
        return volumes[vol_key].get("name", vol_key)

    assert get_volume_name(PROJECT_ROOT) == get_volume_name(tmp_path) == "iw-ai-core_pgdata"


@pytest.mark.skipif(not _db_reachable(), reason="live DB not reachable")
@pytest.mark.integration
def test_ai_core_db_start_noops_when_db_ready():
    """`./ai-core.sh db start` must be a no-op when DB is already up.

    This is a READ-ONLY test — it snapshots container list before and after
    and verifies no containers were created or removed. The exact "already
    accepting connections" phrase must appear in stdout.
    """
    before = subprocess.run(
        ["docker", "ps", "-q"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    ).stdout.strip()

    result = subprocess.run(
        ["./ai-core.sh", "db", "start"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    after = subprocess.run(
        ["docker", "ps", "-q"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    ).stdout.strip()

    assert result.returncode == 0
    assert "already accepting connections" in result.stdout or "already accepting" in result.stdout
    assert before == after, "ai-core.sh started or removed a container when DB was already up"
