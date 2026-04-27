"""Unit tests for orch.staleness.alembic_check.

Mocks subprocess.run for all alembic invocations; no live DB required.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.staleness.alembic_check import AlembicStatus, RevisionSummary, check_alembic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_current_output(rev_id: str, rev_msg: str, is_head: bool = True) -> str:
    """Simulate `alembic current --verbose` output."""
    head_marker = " (head)" if is_head else ""
    return (
        f"{rev_id} (rev){head_marker}\nRev: {rev_id}\nParent: <base>\n"
        f"Path: versions/{rev_id}_msg.py\n{rev_msg}\n"
    )


def _make_heads_output(rev_id: str, rev_msg: str) -> str:
    """Simulate `alembic heads --verbose` output."""
    return (
        f"{rev_id} (head)\nRev: {rev_id}\nParent: <base>\n"
        f"Path: versions/{rev_id}_msg.py\n{rev_msg}\n"
    )


# ---------------------------------------------------------------------------
# check_alembic — up_to_date
# ---------------------------------------------------------------------------


class TestCheckAlembicUpToDate:
    def test_current_equals_head_returns_up_to_date(self, tmp_path: Path) -> None:
        """When current == head, returns AlembicStatus with status='up_to_date'."""
        # Create a dummy alembic.ini so the config-existence check passes.
        (tmp_path / "alembic.ini").write_text("[alembic]\n")
        rev = "abc123def456"
        current_out = _make_current_output(rev, "Add user table", is_head=True)
        heads_out = _make_heads_output(rev, "Add user table")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            if "current" in cmd:
                result.stdout = current_out
                result.stderr = ""
            else:
                result.stdout = heads_out
                result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "up_to_date"
        assert status.current == rev
        assert status.head == rev
        assert status.pending == []
        assert status.error is None

    def test_no_config_returns_no_config(self, tmp_path: Path) -> None:
        """Returns no_config when alembic.ini does not exist."""
        status = check_alembic(tmp_path, "nonexistent.ini", db_url_env=None)
        assert status.status == "no_config"
        assert status.error is not None


# ---------------------------------------------------------------------------
# check_alembic — stale
# ---------------------------------------------------------------------------


class TestCheckAlembicStale:
    def test_current_behind_head_returns_stale(self, tmp_path: Path) -> None:
        """When current != head, returns stale with pending revisions listed."""
        # Create a dummy alembic.ini so config existence check passes
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        current_rev = "old_rev_111"
        head_rev = "new_rev_222"

        current_out = _make_current_output(current_rev, "Old migration", is_head=False)
        heads_out = _make_heads_output(head_rev, "New migration")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            if "current" in cmd:
                result.stdout = current_out
                result.stderr = ""
            else:
                result.stdout = heads_out
                result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "stale"
        assert status.current == current_rev
        assert status.head == head_rev
        assert len(status.pending) >= 1

    def test_no_current_revision_with_head_present(self, tmp_path: Path) -> None:
        """When DB has no current revision but heads exist, returns stale."""
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        head_rev = "abc000"
        current_out = ""  # No revision applied
        heads_out = _make_heads_output(head_rev, "First migration")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            if "current" in cmd:
                result.stdout = current_out
                result.stderr = ""
            else:
                result.stdout = heads_out
                result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "stale"
        assert status.current is None


# ---------------------------------------------------------------------------
# check_alembic — unreachable
# ---------------------------------------------------------------------------


class TestCheckAlembicUnreachable:
    def test_connection_refused_returns_unreachable(self, tmp_path: Path) -> None:
        """Returns unreachable when alembic current fails with connection error."""
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            result.stderr = "could not connect to server: Connection refused"
            return result

        with patch("subprocess.run", side_effect=fake_run):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "unreachable"
        assert status.error is not None
        assert "refused" in status.error.lower() or status.error  # has some error detail

    def test_timeout_returns_unreachable(self, tmp_path: Path) -> None:
        """Returns unreachable on subprocess timeout."""
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("alembic", 10)):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "unreachable"
        assert status.error is not None


# ---------------------------------------------------------------------------
# check_alembic — db_url_env handling
# ---------------------------------------------------------------------------


class TestCheckAlembicDbUrlEnv:
    def test_db_url_env_missing_returns_unreachable(self, tmp_path: Path) -> None:
        """Returns unreachable when db_url_env is set but the env var is missing."""
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        with patch.dict(os.environ, {}, clear=True):
            # Remove MY_DB_URL if it happens to be set
            os.environ.pop("MY_DB_URL", None)
            status = check_alembic(tmp_path, "alembic.ini", db_url_env="MY_DB_URL")

        assert status.status == "unreachable"
        assert "MY_DB_URL" in (status.error or "")

    def test_db_url_env_present_passes_to_subprocess(self, tmp_path: Path) -> None:
        """When db_url_env is set and present, subprocess is called with the var injected."""
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        captured_envs: list[dict[str, str]] = []

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            env = kwargs.get("env")
            if env is not None:
                captured_envs.append(dict(env))
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        with (
            patch.dict(os.environ, {"MY_DB_URL": "postgresql://test/db"}),
            patch("subprocess.run", side_effect=fake_run),
        ):
            check_alembic(tmp_path, "alembic.ini", db_url_env="MY_DB_URL")

        # At least one subprocess call should have received IW_ALEMBIC_DB_URL
        assert any("IW_ALEMBIC_DB_URL" in env for env in captured_envs)
        assert any(env.get("IW_ALEMBIC_DB_URL") == "postgresql://test/db" for env in captured_envs)


# ---------------------------------------------------------------------------
# AlembicStatus and RevisionSummary dataclasses
# ---------------------------------------------------------------------------


class TestAlembicStatusDataclass:
    def test_status_fields(self) -> None:
        """AlembicStatus carries all required fields."""
        s = AlembicStatus(
            status="stale",
            current="abc",
            head="def",
            pending=[RevisionSummary(rev_id="def", message="New migration")],
            error=None,
        )
        assert s.status == "stale"
        assert s.current == "abc"
        assert s.head == "def"
        assert len(s.pending) == 1
        assert s.pending[0].rev_id == "def"
        assert s.pending[0].message == "New migration"
