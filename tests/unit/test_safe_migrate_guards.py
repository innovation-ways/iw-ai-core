"""Extended guard and edge-case coverage for orch.db.safe_migrate.

Beyond the smoke tests in test_safe_migrate.py, this module covers:
- Exact-string semantics of IW_CORE_AGENT_CONTEXT guard
- dry_run ValueError when tempdb_url == live_db_url
- list_pending_revisions on an empty (fresh) DB
- MultipleHeadsError.args includes both head revision IDs
- pending_migration_log written even when alembic raises
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orch.db.safe_migrate import (
    AgentContextForbiddenError,
    MultipleHeadsError,
    _assert_not_agent_context,
    list_pending_revisions,
)


class TestAgentContextGuardSemantics:
    """Exact-string semantics: ONLY 'true' triggers the guard.

    This choice avoids footguns from values like 'yes', '1', 'TRUE', etc.
    The guard is a security boundary — we require an exact match to prevent
    accidental bypasses from common truthy values.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "TRUE",
            "True",
            "1",
            "yes",
            "YES",
            "true\n",
            " true",
        ],
    )
    def test_does_not_raise_for_non_exact_true(self, value: str) -> None:  # noqa: assertion-scanner
        with patch.dict("os.environ", {"IW_CORE_AGENT_CONTEXT": value}, clear=False):
            _assert_not_agent_context()

    @pytest.mark.parametrize(
        "value",
        [
            "",
            None,
        ],
    )
    def test_does_not_raise_when_absent_or_empty(self, value: str | None) -> None:  # noqa: assertion-scanner
        env = {} if value is None else {"IW_CORE_AGENT_CONTEXT": value}
        with patch.dict("os.environ", env, clear=False):
            _assert_not_agent_context()

    def test_raises_only_for_exact_true(self) -> None:
        env = {"IW_CORE_AGENT_CONTEXT": "true"}
        with patch.dict("os.environ", env, clear=False), pytest.raises(AgentContextForbiddenError):
            _assert_not_agent_context()


class TestDryRunLiveDbUrlGuard:
    """dry_run refuses when tempdb_url matches the live DB URL."""

    def test_raises_value_error_when_tempdb_equals_live(self) -> None:
        from orch.db.safe_migrate import dry_run

        live_url = "postgresql+psycopg://user:pass@localhost:5433/iw_core"
        with (
            patch("orch.db.safe_migrate.get_db_url", return_value=live_url),
            pytest.raises(ValueError, match="dry_run called on live DB"),
        ):
            dry_run(live_url)


class TestListPendingRevisionsEmptyDb:
    """list_pending_revisions on a fresh DB (no alembic_version table row).

    A fresh testcontainer has no alembic_version row, so current_rev is None.
    walk_revisions from 'base' should return all revisions in order.
    """

    def test_returns_all_revisions_when_db_is_empty(self) -> None:
        mock_rev_a = MagicMock()
        mock_rev_a.revision = "abc123"
        mock_rev_a.description = "init"
        mock_rev_a.down_revision = None

        mock_rev_b = MagicMock()
        mock_rev_b.revision = "def456"
        mock_rev_b.description = "add users"
        mock_rev_b.down_revision = "abc123"

        mock_script_dir = MagicMock()
        mock_script_dir.get_heads.return_value = ["def456"]
        mock_script_dir.walk_revisions.return_value = iter([mock_rev_b, mock_rev_a])

        with (
            patch(
                "alembic.script.ScriptDirectory.from_config",
                return_value=mock_script_dir,
            ),
            patch(
                "orch.db.safe_migrate._current_revision_from_db",
                return_value=None,
            ),
        ):
            result = list_pending_revisions("postgresql+psycopg://unused/db")

        assert len(result) == 2
        assert result[0].id == "abc123"
        assert result[1].id == "def456"


class TestMultipleHeadsErrorArgs:
    """MultipleHeadsError.args includes both head revision IDs."""

    def test_args_contains_both_heads(self) -> None:
        mock_script_dir = MagicMock()
        mock_script_dir.get_heads.return_value = ["rev_a", "rev_b"]

        with (
            patch("orch.db.safe_migrate.assert_engine_url_allowed"),
            patch(
                "alembic.script.ScriptDirectory.from_config",
                return_value=mock_script_dir,
            ),
            pytest.raises(MultipleHeadsError) as exc_info,
        ):
            list_pending_revisions()

        assert "rev_a" in exc_info.value.args[0]
        assert "rev_b" in exc_info.value.args[0]
        assert "rev_a" in str(exc_info.value)
        assert "rev_b" in str(exc_info.value)


class TestMigrationLogWrittenOnAlembicFailure:
    """pending_migration_log is written even when alembic raises.

    This is critical for audit completeness: every call to apply() that
    reaches the lock-acquisition point should be logged, regardless of
    whether alembic succeeds or raises.
    """

    def test_apply_logs_when_alembic_raises(self) -> None:
        from orch.db.safe_migrate import apply

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_txn = MagicMock()
        mock_conn.begin.return_value = mock_txn
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose.return_value = None
        mock_txn.close.return_value = None
        mock_conn.close.return_value = None

        with (
            patch("orch.db.safe_migrate._assert_not_agent_context"),
            patch("orch.db.safe_migrate._acquire_migration_lock"),
            patch(
                "orch.db.safe_migrate.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "orch.db.safe_migrate.get_migration_lock_timeout_secs",
                return_value=0,
            ),
            patch(
                "orch.db.safe_migrate._assert_no_self_blockers",
            ),
            patch(
                "orch.db.safe_migrate._run_alembic_upgrade",
                side_effect=RuntimeError("alembic炸了"),
            ),
            patch("orch.db.safe_migrate._write_migration_log") as mock_log,
        ):
            with pytest.raises(RuntimeError, match="alembic炸了"):
                apply("postgresql+psycopg://unused/db", batch_id=99)

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["phase"] == "apply"
            assert call_kwargs["success"] is False
            assert call_kwargs["batch_id"] == 99

    def test_rollback_logs_when_alembic_raises(self) -> None:
        from orch.db.safe_migrate import rollback

        with (
            patch("orch.db.safe_migrate._assert_not_agent_context"),
            patch("orch.db.safe_migrate._acquire_migration_lock"),
            patch(
                "orch.db.safe_migrate._run_alembic_downgrade",
                side_effect=RuntimeError("downgrade exploded"),
            ),
            patch("orch.db.safe_migrate._write_migration_log") as mock_log,
        ):
            with pytest.raises(RuntimeError, match="downgrade exploded"):
                rollback("postgresql+psycopg://unused/db", batch_id=77)

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["phase"] == "rollback"
            assert call_kwargs["success"] is False
            assert call_kwargs["batch_id"] == 77
