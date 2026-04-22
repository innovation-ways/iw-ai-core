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
