# ruff: noqa: N999, N802

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.mark.integration
def test_I00128_db_start_refuses_bootstrap_when_pin_set_and_db_down(tmp_path: Path):
    docker_calls = tmp_path / "docker-calls.log"
    _write_exec(
        tmp_path / "docker",
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "${DOCKER_SHIM_LOG}"\n'
        'if [[ "$1" == "compose" && "$2" == "-f" && "$4" == "up" ]]; then\n'
        "  echo 'compose up should not be called' >&2\n"
        "  exit 99\n"
        "fi\n"
        "exit 0\n",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "DOCKER_SHIM_LOG": str(docker_calls),
            "IW_CORE_EXPECTED_INSTANCE_ID": "pinned-id",
            "IW_CORE_DB_HOST": "127.0.0.1",
            "IW_CORE_DB_PORT": "9",
            "IW_CORE_DB_NAME": "iw_orch",
            "IW_CORE_DB_USER": "iw_orch",
            "IW_CORE_DB_PASSWORD": "iw_orch_dev",
        }
    )

    result = subprocess.run(
        ["./ai-core.sh", "db", "start"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Refusing to bootstrap an empty compose database" in result.stderr
    assert "db start-prod" in result.stderr
    calls = docker_calls.read_text() if docker_calls.exists() else ""
    assert "compose -f docker-compose.bootstrap.yml up -d db" not in calls


@pytest.mark.integration
def test_I00128_guard_holds_from_worktree_checkout(tmp_path: Path):
    worktree_dir = tmp_path / ".worktrees" / "I-legacy"
    worktree_dir.mkdir(parents=True)
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.bootstrap.yml").read_text())
    ports = compose["services"]["db"].get("ports", [])
    assert ports == [
        "${IW_CORE_BOOTSTRAP_DB_PORT:?Set IW_CORE_BOOTSTRAP_DB_PORT explicitly "
        "(use ./ai-core.sh db start for safe defaults)}:5432"
    ]
    assert ".worktrees" in str(worktree_dir)


@pytest.mark.integration
def test_I00128_start_prod_uses_postgres_container_name(tmp_path: Path):
    docker_calls = tmp_path / "docker-calls.log"
    _write_exec(
        tmp_path / "docker",
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "${DOCKER_SHIM_LOG}"\n'
        'if [[ "$1" == "ps" ]]; then exit 0; fi\n'
        "exit 0\n",
    )
    _write_exec(tmp_path / "pg_isready", "#!/usr/bin/env bash\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "DOCKER_SHIM_LOG": str(docker_calls),
            "IW_CORE_DB_DATA_DIR": "/tmp/fake-pgdata",
            "IW_CORE_DB_HOST": "127.0.0.1",
            "IW_CORE_DB_PORT": "5433",
            "IW_CORE_DB_NAME": "iw_orch",
            "IW_CORE_DB_USER": "iw_orch",
            "IW_CORE_DB_PASSWORD": "iw_orch_dev",
        }
    )

    result_default = subprocess.run(
        ["./ai-core.sh", "db", "start-prod"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result_default.returncode == 0

    env_override = env.copy()
    env_override["IW_CORE_ORCH_DB_CONTAINER"] = "custom-postgres"
    result_override = subprocess.run(
        ["./ai-core.sh", "db", "start-prod"],
        cwd=PROJECT_ROOT,
        env=env_override,
        capture_output=True,
        text=True,
    )
    assert result_override.returncode == 0

    calls = docker_calls.read_text().splitlines()
    assert any("run -d --name postgres" in call for call in calls)
    assert any("run -d --name custom-postgres" in call for call in calls)
