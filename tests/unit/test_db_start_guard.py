"""Unit tests for db start guard."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DbStartResult:
    returncode: int
    stdout: str
    stderr: str
    docker_calls: list[str]


def _run_db_start(
    *,
    expected_instance_id: str | None,
    db_ready_sequence: list[int],
) -> DbStartResult:
    """Return run db start."""
    repo_root = Path(__file__).resolve().parents[2]

    sandbox = Path(tempfile.mkdtemp(prefix="db-start-guard-"))
    try:
        test_bin = sandbox / "bin"
        test_bin.mkdir(parents=True, exist_ok=True)

        docker_log = sandbox / "docker.log"

        docker_stub = test_bin / "docker"
        docker_stub.write_text(
            '#!/usr/bin/env bash\necho "$*" >> "${DOCKER_CALL_LOG}"\nexit 0\n',
            encoding="utf-8",
        )
        docker_stub.chmod(0o755)

        probe_state = sandbox / "probe-state"

        probe_stub_body = (
            "#!/usr/bin/env bash\n"
            'state_file="${DB_READY_STATE_FILE}"\n'
            'sequence_csv="${DB_READY_SEQUENCE:-1}"\n'
            "IFS=',' read -r -a sequence <<< \"$sequence_csv\"\n"
            "idx=0\n"
            'if [[ -f "$state_file" ]]; then\n'
            '  idx=$(cat "$state_file")\n'
            "fi\n"
            "if (( idx < ${#sequence[@]} )); then\n"
            '  code="${sequence[$idx]}"\n'
            "else\n"
            '  code="${sequence[-1]}"\n'
            "fi\n"
            'echo $((idx + 1)) > "$state_file"\n'
            'exit "$code"\n'
        )

        pg_isready_stub = test_bin / "pg_isready"
        pg_isready_stub.write_text(probe_stub_body, encoding="utf-8")
        pg_isready_stub.chmod(0o755)

        nc_stub = test_bin / "nc"
        nc_stub.write_text(probe_stub_body, encoding="utf-8")
        nc_stub.chmod(0o755)

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{test_bin}:{env.get('PATH', '')}",
                "DOCKER_CALL_LOG": str(docker_log),
                "DB_READY_SEQUENCE": ",".join(str(code) for code in db_ready_sequence),
                "DB_READY_STATE_FILE": str(probe_state),
                "IW_CORE_DB_HOST": "127.0.0.1",
                "IW_CORE_DB_PORT": "65534",
                "IW_CORE_DB_NAME": "iw_orch",
                "IW_CORE_DB_USER": "iw_orch",
                "IW_CORE_DB_PASSWORD": "iw_orch_dev",
            }
        )

        if expected_instance_id is None:
            env.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        else:
            env["IW_CORE_EXPECTED_INSTANCE_ID"] = expected_instance_id

        completed = subprocess.run(
            ["bash", "ai-core.sh", "db", "start"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        docker_calls = (
            docker_log.read_text(encoding="utf-8").splitlines() if docker_log.exists() else []
        )

        return DbStartResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            docker_calls=docker_calls,
        )
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def _has_bootstrap_up_call(calls: list[str]) -> bool:
    return any(
        "compose" in call and " up " in f" {call} " and " -d " in f" {call} " and " db" in call
        for call in calls
    )


def test_i00122_db_start_refuses_bootstrap_when_instance_pinned() -> None:
    """Verifies that i00122 db start refuses bootstrap when instance pinned."""
    result = _run_db_start(
        expected_instance_id="11111111-2222-3333-4444-555555555555",
        db_ready_sequence=[1],
    )

    assert result.returncode != 0
    assert not _has_bootstrap_up_call(result.docker_calls)
    assert (
        "Refusing to bootstrap an empty compose database over the production port." in result.stderr
    )


def test_db_start_bootstraps_on_fresh_dev_machine_when_no_identity_pinned() -> None:
    """Verifies that db start bootstraps on fresh dev machine when no identity pinned."""
    result = _run_db_start(expected_instance_id="", db_ready_sequence=[1, 0])

    assert result.returncode == 0
    assert _has_bootstrap_up_call(result.docker_calls)


def test_db_start_is_noop_when_db_already_up() -> None:
    """Verifies that db start is noop when db already up."""
    result = _run_db_start(
        expected_instance_id="11111111-2222-3333-4444-555555555555",
        db_ready_sequence=[0],
    )

    assert result.returncode == 0
    assert not _has_bootstrap_up_call(result.docker_calls)
    assert result.docker_calls == []
