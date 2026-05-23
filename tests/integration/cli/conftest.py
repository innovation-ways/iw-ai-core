"""Shared fixtures for the `iw` CLI contract tests (CR-00073).

Several contract tests must exercise `iw` end-to-end as a real subprocess —
evidence-ingestion hooks and process-level env-var handling cannot be observed
through Click's in-process `CliRunner`. The `iw_subprocess` fixture below is the
single, audited way to do that against the per-test PostgreSQL clone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Engine


def _uv_binary() -> str:
    """Locate the ``uv`` executable — PATH first, then the per-user install."""
    found = shutil.which("uv")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "uv"
    if fallback.exists():
        return str(fallback)
    return "uv"


@pytest.fixture
def iw_subprocess(
    db_engine: Engine,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Return a callable that runs ``uv run iw`` against the per-test clone.

    The returned callable has the signature
    ``(args, project_id, cwd, timeout=30) -> CompletedProcess`` and builds an
    explicit environment — the pattern established by
    ``tests/integration/cli/test_step_commands_drift.py``:

    * ``IW_CORE_DB_*`` *and* ``IW_CORE_ORCH_DB_*`` both resolve to the
      testcontainer clone created by ``db_engine``. ``iw`` step/approve commands
      resolve their DB via ``orch.config.get_orch_db_url()``, which prefers the
      ``_ORCH_`` variants — the repo ``.env`` points those at the live orch DB,
      so they must be overridden explicitly.
    * ``IW_CORE_DAEMON_CONTEXT=true`` so the connection-layer live-DB guard
      permits the connection. The clone shares ``db_engine``'s host:port, which
      the guard treats as the live orch DB; under ``IW_CORE_TEST_CONTEXT`` it
      would otherwise refuse it. The daemon opt-in is the same mechanism the
      real daemon uses to allow its own engine.
    * ``IW_CORE_AGENT_CONTEXT`` cleared and any ``IW_CORE_OPERATOR*`` flag
      dropped, so leaked parent-shell state cannot change the guard decision.
    """
    url = db_engine.url

    def _run(
        args: list[str],
        project_id: str,
        cwd: str | Path,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "IW_CORE_DB_HOST": url.host or "localhost",
            "IW_CORE_DB_PORT": str(url.port or 5432),
            "IW_CORE_DB_NAME": url.database or "test",
            "IW_CORE_DB_USER": url.username or "test",
            "IW_CORE_DB_PASSWORD": url.password or "test",
            "IW_CORE_ORCH_DB_HOST": url.host or "localhost",
            "IW_CORE_ORCH_DB_PORT": str(url.port or 5432),
            "IW_CORE_ORCH_DB_NAME": url.database or "test",
            "IW_CORE_ORCH_DB_USER": url.username or "test",
            "IW_CORE_ORCH_DB_PASSWORD": url.password or "test",
            "IW_CORE_DAEMON_CONTEXT": "true",
            "IW_CORE_AGENT_CONTEXT": "",
        }
        for key in list(env):
            if key.startswith("IW_CORE_OPERATOR"):
                env.pop(key, None)
        return subprocess.run(
            [_uv_binary(), "run", "iw", "--project", project_id, *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd),
            timeout=timeout,
        )

    return _run
