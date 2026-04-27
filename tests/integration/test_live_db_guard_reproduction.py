"""Integration reproduction tests for I-00041.

These tests verify the live-DB guard fires correctly in realistic subprocess
scenarios:
1. A test-context subprocess attempting to connect to the live orch DB
2. A daemon-armed parent spawning an agent subprocess that tries to connect to live DB
3. A positive-control test: operator-context process can connect to testcontainer

All tests in this module run against REAL infrastructure (subprocesses,
testcontainers) but must NEVER write to the live DB on port 5433 except
where explicitly noted.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest
from testcontainers.postgres import PostgresContainer

# The canonical live DB URL — uses the operator's actual env vars.
_LIVE_HOST = os.environ.get("IW_CORE_DB_HOST", "localhost")
_LIVE_PORT = os.environ.get("IW_CORE_DB_PORT", "5433")
_LIVE_URL = f"postgresql://iw_orch:iw_orch@{_LIVE_HOST}:{_LIVE_PORT}/iw_orch"


@pytest.mark.integration
def test_subprocess_in_test_context_cannot_connect_to_live_db() -> None:
    """Reproduces I-00041: a test process (IW_CORE_TEST_CONTEXT=true) must
    NOT be able to connect to the live orch DB on port 5433.

    This is the canonical reproduction: subprocess sets TEST_CONTEXT, sets
    live DB URL env vars to the actual live DB (localhost:5433), then tries
    to create an engine and connect. The guard must refuse it before any
    network call is made.
    """
    code = textwrap.dedent(f"""
        import os
        os.environ['IW_CORE_TEST_CONTEXT'] = 'true'
        os.environ.pop('IW_CORE_OPERATOR_APPLY', None)
        os.environ.pop('IW_CORE_DAEMON_CONTEXT', None)
        os.environ['IW_CORE_DB_HOST'] = {_LIVE_HOST!r}
        os.environ['IW_CORE_DB_PORT'] = '5433'
        live_url = 'postgresql://iw_orch:iw_orch@localhost:5433/iw_orch'
        from orch.db.session import safe_create_engine
        e = safe_create_engine(live_url)
        c = e.connect()
        c.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0, (
        f"GUARD FAILED — subprocess connected to live DB.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "LiveDbConnectionRefused" in result.stderr, (
        f"Wrong refusal type: stderr={result.stderr!r}"
    )
    assert "host:port" in result.stderr, f"Missing host:port in refusal: stderr={result.stderr!r}"


@pytest.mark.integration
def test_daemon_armed_subprocess_via_agent_env_helper_cannot_connect_to_live_db() -> None:
    """Reproduces the daemon → agent leak path I-00041 closes.

    Simulates: parent process has IW_CORE_DAEMON_CONTEXT=true (as the daemon
    would). It spawns a child using _agent_subprocess_env(), which strips
    DAEMON_CONTEXT and arms AGENT_CONTEXT. The child then attempts a live-DB
    connect and MUST be refused.

    This is the attack path that caused the 2026-04-26 dashboard outage.
    """
    parent_env = {
        **os.environ,
        "IW_CORE_DAEMON_CONTEXT": "true",
    }
    parent_env.pop("IW_CORE_AGENT_CONTEXT", None)
    parent_env.pop("IW_CORE_TEST_CONTEXT", None)

    code = textwrap.dedent("""
        import sys
        import os
        from orch.daemon.batch_manager import _agent_subprocess_env
        child_env = _agent_subprocess_env()
        for k in ('IW_CORE_DAEMON_CONTEXT', 'IW_CORE_OPERATOR_APPLY'):
            if k in os.environ and k not in child_env:
                os.environ.pop(k, None)
        for k, v in child_env.items():
            os.environ[k] = v
        os.environ['IW_CORE_DB_HOST'] = 'localhost'
        os.environ['IW_CORE_DB_PORT'] = '5433'
        live_url = 'postgresql://iw_orch:iw_orch@localhost:5433/iw_orch'
        from orch.db.session import safe_create_engine
        e = safe_create_engine(live_url)
        e.connect()
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=parent_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0, (
        f"GUARD FAILED — daemon-armed agent subprocess connected to live DB.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "LiveDbConnectionRefused" in result.stderr, (
        f"Wrong refusal type: stderr={result.stderr!r}"
    )
    assert "host:port" in result.stderr, f"Missing host:port in refusal: stderr={result.stderr!r}"


@pytest.mark.integration
def test_subprocess_with_operator_flag_can_connect_to_testcontainer() -> None:
    """Confirms the guard does NOT over-block: an operator-context process
    against a non-live (testcontainer) URL succeeds.

    This is the positive-control sibling to test_subprocess_in_test_context.
    """
    with PostgresContainer("postgres:15") as pg:
        tc_url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        code = textwrap.dedent(f"""
            import os
            os.environ['IW_CORE_OPERATOR_APPLY'] = 'true'
            os.environ.pop('IW_CORE_TEST_CONTEXT', None)
            os.environ.pop('IW_CORE_DAEMON_CONTEXT', None)
            from orch.db.session import safe_create_engine
            e = safe_create_engine({tc_url!r})
            conn = e.connect()
            conn.close()
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Operator-context process failed against testcontainer URL.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )


@pytest.mark.integration
def test_subprocess_under_test_context_can_connect_to_testcontainer() -> None:
    """Confirms the guard correctly allows test-context processes to connect
    to non-live URLs (testcontainer)."""
    with PostgresContainer("postgres:15") as pg:
        tc_url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        code = textwrap.dedent(f"""
            import os
            os.environ['IW_CORE_TEST_CONTEXT'] = 'true'
            os.environ.pop('IW_CORE_OPERATOR_APPLY', None)
            os.environ.pop('IW_CORE_DAEMON_CONTEXT', None)
            from orch.db.session import safe_create_engine
            e = safe_create_engine({tc_url!r})
            conn = e.connect()
            conn.close()
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Test-context process failed against testcontainer URL.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
