"""Unit tests for orch.staleness.alembic_check.

Mocks subprocess.run for all alembic invocations; no live DB required.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.staleness.alembic_check import (
    AlembicStatus,
    RevisionSummary,
    check_alembic,
)

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
    """Tests for check_alembic when the DB is at the head revision."""

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
    """Tests for check_alembic when the DB is behind the head revision."""

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
    """Tests for check_alembic when the database is unreachable."""

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
    """Tests for check_alembic db_url_env parameter handling."""

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
    """Tests for the AlembicStatus and RevisionSummary dataclass structures."""

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


# ---------------------------------------------------------------------------
# Real-world alembic verbose output — regression coverage
# ---------------------------------------------------------------------------
#
# The fake fixtures above use a synthetic format that does not match what
# `alembic current --verbose` / `alembic heads --verbose` actually emit.
# These tests pin the parser to real-world output so that a divergence
# between the parser and alembic's actual format is caught.


_REAL_CURRENT_OUTPUT = (
    "Current revision(s) for postgresql+psycopg://iw_orch:***@localhost:5433/iw_orch:\n"
    "Rev: fdf63560ff02 (head)\n"
    "Parent: bd4ed52cad71\n"
    "Path: /repo/orch/db/migrations/versions/fdf63560ff02_oss_job_public_id.py\n"
    "\n"
    "    Add public_id (O-XXXXX) to project_oss_job and backfill\n"
    "    \n"
    "    Revision ID: fdf63560ff02\n"
    "    Revises: bd4ed52cad71\n"
    "    Create Date: 2026-04-27 23:00:00.000000\n"
    "    \n"
    "    OSS jobs previously surfaced their bigserial integer id (1, 2, 3, ...)\n"
)

_REAL_HEADS_OUTPUT = (
    "Rev: fdf63560ff02 (head)\n"
    "Parent: bd4ed52cad71\n"
    "Path: /repo/orch/db/migrations/versions/fdf63560ff02_oss_job_public_id.py\n"
    "\n"
    "    Add public_id (O-XXXXX) to project_oss_job and backfill\n"
    "    \n"
    "    Revision ID: fdf63560ff02\n"
    "    Revises: bd4ed52cad71\n"
    "    Create Date: 2026-04-27 23:00:00.000000\n"
    "    \n"
    "    OSS jobs previously surfaced their bigserial integer id (1, 2, 3, ...)\n"
)


class TestParseRealAlembicOutput:
    """Regression tests pinning the parser against real alembic verbose output."""

    def test_parse_revision_from_real_current_output(self) -> None:
        """`alembic current --verbose` stdout is parsed to the rev_id (not 'Current')."""
        from orch.staleness.alembic_check import _parse_revision_from_verbose

        assert _parse_revision_from_verbose(_REAL_CURRENT_OUTPUT) == "fdf63560ff02"

    def test_parse_revision_from_real_heads_output(self) -> None:
        """`alembic heads --verbose` stdout is parsed to the rev_id (not 'Rev:')."""
        from orch.staleness.alembic_check import _parse_revision_from_verbose

        assert _parse_revision_from_verbose(_REAL_HEADS_OUTPUT) == "fdf63560ff02"

    def test_parse_message_from_real_heads_output(self) -> None:
        """Message is the docstring's first line, not the docstring metadata."""
        from orch.staleness.alembic_check import _parse_message_from_verbose

        msg = _parse_message_from_verbose(_REAL_HEADS_OUTPUT)
        assert msg == "Add public_id (O-XXXXX) to project_oss_job and backfill"
        # Must NOT smush in docstring metadata or body.
        assert "Revision ID:" not in msg
        assert "Create Date:" not in msg

    def test_check_alembic_at_head_with_real_output_returns_up_to_date(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: when DB and code are at the same revision, status='up_to_date'.

        Regression: previously the parser returned the literal 'Current' for the
        current rev and 'Rev:' for the head rev, so this case was always reported
        as 'stale' with a nonsense message in the dashboard.
        """
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            if "current" in cmd:
                result.stdout = _REAL_CURRENT_OUTPUT
            else:
                result.stdout = _REAL_HEADS_OUTPUT
            result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "up_to_date"
        assert status.current == "fdf63560ff02"
        assert status.head == "fdf63560ff02"
        assert status.pending == []

    def test_check_alembic_no_current_with_real_heads_output_returns_stale(
        self, tmp_path: Path
    ) -> None:
        """Empty `alembic current` (no migrations applied) + heads present → stale."""
        (tmp_path / "alembic.ini").write_text("[alembic]\n")

        no_current_output = (
            "Current revision(s) for postgresql+psycopg://iw_orch:***@localhost:5433/iw_orch:\n"
        )

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.returncode = 0
            result.stdout = no_current_output if "current" in cmd else _REAL_HEADS_OUTPUT
            result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            status = check_alembic(tmp_path, "alembic.ini", db_url_env=None)

        assert status.status == "stale"
        assert status.current is None
        assert status.head == "fdf63560ff02"
        assert len(status.pending) == 1
        assert status.pending[0].rev_id == "fdf63560ff02"
        assert (
            status.pending[0].message == "Add public_id (O-XXXXX) to project_oss_job and backfill"
        )
