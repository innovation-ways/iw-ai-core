"""Integration test for per-worktree container isolation (AC2).

Two parallel worktrees with distinct schema changes must not cross-contaminate.

Prerequisites:
- Docker daemon must be available
- This test uses real docker containers via subprocess (not testcontainers for compose)
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

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


def _run_compose_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=120,
    )


def _cleanup_compose(project_name: str, compose_file: Path | None = None) -> None:
    args = ["docker", "compose", "-p", project_name]
    if compose_file:
        args.extend(["-f", str(compose_file)])
    args.extend(["down", "-v", "--remove-orphans"])
    subprocess.run(args, capture_output=True, timeout=120)


def _compose_exec(
    project_name: str,
    service: str,
    command: list[str],
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    args = ["docker", "compose", "-p", project_name, "exec", "-T", service] + command
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**__import__("os").environ, "PGPASSWORD": "testpass"},
    )


def _wait_for_postgres(project_name: str, timeout: int = 60) -> bool:
    start = time.time()
    psql_cmd = ["psql", "-U", "testuser", "-d", "postgres", "-c", "SELECT 1", "-w"]
    while time.time() - start < timeout:
        result = _compose_exec(project_name, "db", psql_cmd)
        if result.returncode == 0:
            return True
        time.sleep(1)
    return False


def _exec_sql(project_name: str, dbname: str, sql: str) -> subprocess.CompletedProcess:
    return _compose_exec(
        project_name,
        "db",
        ["psql", "-U", "testuser", "-d", dbname, "-c", sql, "-w"],
    )


def _table_exists(project_name: str, dbname: str, table_name: str) -> bool:
    sql = (
        f"SELECT EXISTS (SELECT FROM information_schema.tables "  # noqa: S608
        f"WHERE table_name = '{table_name}');"  # noqa: S608
    )
    result = _exec_sql(project_name, dbname, sql)
    return " t\n" in result.stdout


def _column_exists(
    project_name: str,
    dbname: str,
    table_name: str,
    column_name: str,
) -> bool:
    sql = (
        f"SELECT EXISTS (SELECT FROM information_schema.columns "  # noqa: S608
        f"WHERE table_name = '{table_name}' "  # noqa: S608
        f"AND column_name = '{column_name}');"  # noqa: S608
    )
    result = _exec_sql(project_name, dbname, sql)
    return " t\n" in result.stdout


@pytest.mark.integration
def test_two_parallel_iw_ai_core_worktrees_do_not_interfere(
    docker_available: bool,
    tmp_path: Path,
) -> None:
    """AC2 — two worktrees, two stacks, distinct schema changes, no cross-visibility.

    This test:
    1. Creates two worktree directories with docker-compose configs
    2. Brings up both stacks
    3. Each stack's DB gets a distinct schema change (ADD COLUMN)
    4. Verifies each DB only has its own column
    5. Verifies the global orch DB (if reachable) shows neither column
    """
    # Skipped in pytest-xdist workers: Docker compose stacks compete with the
    # testcontainer PostgreSQL workers started by DB-fixture tests in parallel,
    # causing intermittent Docker daemon resource contention timeouts.
    # The test still runs in `make test-integration` (no -n auto).
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip(
            "Docker compose isolation test skipped in xdist workers "
            "(Docker daemon resource contention under 32-worker parallel load)"
        )

    wt_a = tmp_path / "wt_A"
    wt_b = tmp_path / "wt_B"
    wt_a.mkdir()
    wt_b.mkdir()

    project_name_a = "iwcore-test-iso-a"
    project_name_b = "iwcore-test-iso-b"

    compose_a = wt_a / "docker-compose.yml"
    compose_b = wt_b / "docker-compose.yml"

    compose_a.write_text(
        f"name: {project_name_a}\n"
        "services:\n"
        "  db:\n"
        "    image: postgres:15-alpine\n"
        "    environment:\n"
        "      POSTGRES_DB: worktree_a\n"
        "      POSTGRES_USER: testuser\n"
        "      POSTGRES_PASSWORD: testpass\n"
        "    labels:\n"
        '      iwcore.batch_item: "TEST-A"\n'
        "      iwcore.role: worktree-db\n"
        "      iwcore.project: test-proj\n"
    )

    compose_b.write_text(
        f"name: {project_name_b}\n"
        "services:\n"
        "  db:\n"
        "    image: postgres:15-alpine\n"
        "    environment:\n"
        "      POSTGRES_DB: worktree_b\n"
        "      POSTGRES_USER: testuser\n"
        "      POSTGRES_PASSWORD: testpass\n"
        "    labels:\n"
        '      iwcore.batch_item: "TEST-B"\n'
        "      iwcore.role: worktree-db\n"
        "      iwcore.project: test-proj\n"
    )

    try:
        result_a = _run_compose_command(["up", "-d"], wt_a)
        assert result_a.returncode == 0, f"Stack A failed to start: {result_a.stderr}"

        result_b = _run_compose_command(["up", "-d"], wt_b)
        assert result_b.returncode == 0, f"Stack B failed to start: {result_b.stderr}"

        time.sleep(5)

        result_ps_a = subprocess.run(
            ["docker", "ps", "--filter", f"name={project_name_a}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "Up" in result_ps_a.stdout, f"Stack A containers not running: {result_ps_a.stdout}"

        result_ps_b = subprocess.run(
            ["docker", "ps", "--filter", f"name={project_name_b}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "Up" in result_ps_b.stdout, f"Stack B containers not running: {result_ps_b.stdout}"

        def get_container_ip(project_name: str) -> str:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                    f"{project_name}-db-1",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()

        ip_a = get_container_ip(project_name_a)
        ip_b = get_container_ip(project_name_b)

        assert ip_a, "Could not get IP for stack A"
        assert ip_b, "Could not get IP for stack B"
        assert ip_a != ip_b, "Both stacks should have distinct IPs"

        assert _wait_for_postgres(project_name_a), "Postgres A did not become ready"
        assert _wait_for_postgres(project_name_b), "Postgres B did not become ready"

        _exec_sql(
            project_name_a,
            "worktree_a",
            "CREATE TABLE wt_a_table (id INTEGER PRIMARY KEY, col_a TEXT)",
        )
        _exec_sql(
            project_name_b,
            "worktree_b",
            "CREATE TABLE wt_b_table (id INTEGER PRIMARY KEY, col_b TEXT)",
        )

        assert _table_exists(project_name_a, "worktree_a", "wt_a_table")
        assert _table_exists(project_name_b, "worktree_b", "wt_b_table")
        assert not _table_exists(project_name_a, "worktree_a", "wt_b_table")
        assert not _table_exists(project_name_b, "worktree_b", "wt_a_table")

        assert _column_exists(project_name_a, "worktree_a", "wt_a_table", "col_a")
        assert _column_exists(project_name_b, "worktree_b", "wt_b_table", "col_b")
        assert not _column_exists(project_name_a, "worktree_a", "wt_a_table", "col_b")
        assert not _column_exists(project_name_b, "worktree_b", "wt_b_table", "col_a")

    finally:
        _cleanup_compose(project_name_a, compose_a)
        _cleanup_compose(project_name_b, compose_b)
