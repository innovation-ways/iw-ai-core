"""Unit tests for orch.db.safe_migrate."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orch.db.safe_migrate import (
    AgentContextForbiddenError,
    MultipleHeadsError,
    _assert_not_agent_context,
    apply,
    dry_run,
    is_live_db_url,
    list_pending_revisions,
    rollback,
)


class TestAssertNotAgentContext:
    def test_does_not_raise_when_env_false(self) -> None:
        with patch.dict("os.environ", {"IW_CORE_AGENT_CONTEXT": "false"}, clear=False):
            _assert_not_agent_context()

    def test_does_not_raise_when_env_absent(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            _assert_not_agent_context()

    def test_raises_when_env_true(self) -> None:
        env = {"IW_CORE_AGENT_CONTEXT": "true"}
        with patch.dict("os.environ", env, clear=False), pytest.raises(AgentContextForbiddenError):
            _assert_not_agent_context()


class TestApply:
    def test_apply_refuses_in_agent_context(self) -> None:
        env = {"IW_CORE_AGENT_CONTEXT": "true"}
        with patch.dict("os.environ", env, clear=False), pytest.raises(AgentContextForbiddenError):
            apply("postgresql+psycopg://unused/db")


class TestRollback:
    def test_rollback_refuses_in_agent_context(self) -> None:
        env = {"IW_CORE_AGENT_CONTEXT": "true"}
        with patch.dict("os.environ", env, clear=False), pytest.raises(AgentContextForbiddenError):
            rollback("postgresql+psycopg://unused/db")


class TestDryRun:
    def test_dry_run_refuses_live_url(self) -> None:
        with (
            patch("orch.db.safe_migrate.get_db_url", return_value="postgresql+psycopg://live/db"),
            pytest.raises(ValueError, match="dry_run called on live DB"),
        ):
            dry_run("postgresql+psycopg://live/db")


class TestListPendingRevisions:
    def test_multiple_heads_raises(self) -> None:
        mock_script_dir = MagicMock()
        mock_script_dir.get_heads.return_value = ["rev_a", "rev_b"]

        with patch(
            "alembic.script.ScriptDirectory.from_config",
            return_value=mock_script_dir,
        ):
            with pytest.raises(MultipleHeadsError) as exc_info:
                list_pending_revisions()
            assert "rev_a" in str(exc_info.value)
            assert "rev_b" in str(exc_info.value)
            assert "alembic merge" in str(exc_info.value)


class TestIsLiveDbUrl:
    def test_is_live_db_url_matches_config(self) -> None:
        db_url = "postgresql+psycopg://user:pass@localhost:5433/iw_core"
        with patch("orch.db.safe_migrate.get_db_url", return_value=db_url):
            assert is_live_db_url(db_url) is True
            assert is_live_db_url("postgresql+psycopg://user:pass@other:5433/iw_core") is False


class TestBuildAlembicConfig:
    def test_build_alembic_config_override_respected(self) -> None:
        from orch.db.safe_migrate import _build_alembic_config

        cfg = _build_alembic_config(
            "postgresql+psycopg://u:p@host:5432/db", script_location="/wt/orch/db/migrations"
        )
        assert cfg.get_main_option("script_location") == "/wt/orch/db/migrations"
        assert cfg.get_main_option("sqlalchemy.url") == "postgresql+psycopg://u:p@host:5432/db"

    def test_build_alembic_config_falls_back_to_default(self) -> None:
        from orch.db.safe_migrate import MIGRATIONS_SCRIPT_LOCATION, _build_alembic_config

        cfg = _build_alembic_config("postgresql+psycopg://u:p@host:5432/db")
        assert cfg.get_main_option("script_location") == MIGRATIONS_SCRIPT_LOCATION


class TestWriteMigrationLog:
    def test_write_migration_log_old_revision_persisted(self) -> None:
        from orch.db.safe_migrate import _write_migration_log

        with (
            patch(
                "orch.db.safe_migrate.get_db_url",
                return_value="postgresql+psycopg://u:p@host:5432/db",
            ),
            patch("orch.db.safe_migrate.create_engine") as mock_engine,
        ):
            mock_session = MagicMock()
            mock_sm = MagicMock()
            mock_sm.return_value = mock_session
            mock_engine.return_value.pool_pre_ping = True
            with patch("orch.db.safe_migrate.sessionmaker", return_value=mock_sm):
                _write_migration_log(
                    revision="rev1",
                    direction="upgrade",
                    phase="rebase",
                    batch_id=42,
                    success=True,
                    stdout_tail="",
                    stderr_tail="",
                    error_message=None,
                    old_revision="old_rev1",
                )
                mock_session.add.assert_called_once()
                entry = mock_session.add.call_args[0][0]
                assert entry.old_revision == "old_rev1"
                assert entry.phase == "rebase"
                mock_session.commit.assert_called_once()

    def test_write_migration_log_backward_compat_no_old_revision(self) -> None:
        from orch.db.safe_migrate import _write_migration_log

        with (
            patch(
                "orch.db.safe_migrate.get_db_url",
                return_value="postgresql+psycopg://u:p@host:5432/db",
            ),
            patch("orch.db.safe_migrate.create_engine") as mock_engine,
        ):
            mock_session = MagicMock()
            mock_sm = MagicMock()
            mock_sm.return_value = mock_session
            mock_engine.return_value.pool_pre_ping = True
            with patch("orch.db.safe_migrate.sessionmaker", return_value=mock_sm):
                _write_migration_log(
                    revision="rev1",
                    direction="upgrade",
                    phase="dry_run",
                    batch_id=42,
                    success=True,
                    stdout_tail="",
                    stderr_tail="",
                    error_message=None,
                )
                mock_session.add.assert_called_once()
                entry = mock_session.add.call_args[0][0]
                assert entry.old_revision is None
                assert entry.phase == "dry_run"
                mock_session.commit.assert_called_once()


class TestAssertNotAgentContextRelax:
    def test_blocks_against_orch_db_when_agent_context(self) -> None:
        from orch.db.safe_migrate import _assert_not_agent_context

        with (
            patch.dict(
                "os.environ",
                {"IW_CORE_AGENT_CONTEXT": "true", "IW_CORE_PER_WORKTREE_DB": "false"},
                clear=False,
            ),
            pytest.raises(AgentContextForbiddenError),
        ):
            _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

    def test_allows_against_per_worktree_db_when_per_worktree_flag_set(self) -> None:
        from orch.db.safe_migrate import _assert_not_agent_context

        with patch.dict(
            "os.environ",
            {"IW_CORE_AGENT_CONTEXT": "true", "IW_CORE_PER_WORKTREE_DB": "true"},
            clear=False,
        ):
            _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

    def test_blocks_against_orch_db_even_with_per_worktree_flag(self) -> None:
        from orch.db.safe_migrate import _assert_not_agent_context

        with (
            patch.dict(
                "os.environ",
                {"IW_CORE_AGENT_CONTEXT": "true", "IW_CORE_PER_WORKTREE_DB": "true"},
                clear=False,
            ),
            pytest.raises(AgentContextForbiddenError),
        ):
            _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")

    def test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant(
        self,
    ) -> None:
        from orch.db.safe_migrate import _assert_not_agent_context

        with patch.dict(
            "os.environ",
            {"IW_CORE_AGENT_CONTEXT": "false", "IW_CORE_PER_WORKTREE_DB": "true"},
            clear=False,
        ):
            _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")

    def test_allows_outside_agent_context_without_flag(self) -> None:
        from orch.db.safe_migrate import _assert_not_agent_context

        with patch.dict(
            "os.environ",
            {"IW_CORE_AGENT_CONTEXT": "false"},
            clear=False,
        ):
            _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
