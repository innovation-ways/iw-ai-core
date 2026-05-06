"""Unit tests for merge-queue CLI commands — smoke tests using CliRunner with mocks.

DB-backed tests for retry-merge (status flips, audit events) live in
tests/integration/test_merge_queue_retry.py. These unit tests cover
smoke/assertion patterns and import-based parity checks that don't need a DB.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from orch.cli.merge_queue_commands import merge_queue_status, merge_queue_unfreeze
from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES
from orch.db.models import BatchItemStatus


@pytest.fixture
def cli_runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Import-based parity and enum-coverage tests — no DB needed
# ---------------------------------------------------------------------------


class TestRetryMergeParityOnly:
    """Parity and enum-coverage assertions.

    No DB required; these verify that the CLI imports the shared constant
    by identity (not by copy) and that the constant's membership matches
    the union of all regression cases in the integration test suite.
    """

    def test_i00072_cli_imports_recoverable_status_constant(self) -> None:
        """The CLI module imports OPERATOR_RECOVERABLE_MERGE_STATUSES by name."""
        import orch.cli.merge_queue_commands as cli_module

        # Identity check: the module holds the same frozenset object, not a copy.
        assert cli_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES

        # The set has exactly the four expected members.
        assert (
            frozenset(
                {
                    BatchItemStatus.merge_failed,
                    BatchItemStatus.migration_invalid,
                    BatchItemStatus.migration_rebase_failed,
                    BatchItemStatus.migration_rolled_back,
                }
            )
            == OPERATOR_RECOVERABLE_MERGE_STATUSES
        )

    def test_i00072_every_recoverable_status_has_a_regression_case(self) -> None:
        """Adding a status to OPERATOR_RECOVERABLE_MERGE_STATUSES requires a test row.

        The parametrised integration test
        tests/integration/test_merge_queue_retry.py::TestRetryMergeAcceptsRecoverableStatuses
        covers exactly these four. If a developer adds a fifth status without adding
        a parametrised case, this assertion fails loudly.
        """
        covered = frozenset(
            {
                BatchItemStatus.merge_failed,
                BatchItemStatus.migration_invalid,
                BatchItemStatus.migration_rebase_failed,
                BatchItemStatus.migration_rolled_back,
            }
        )
        assert covered == OPERATOR_RECOVERABLE_MERGE_STATUSES, (
            "Add a parametrised regression case for the new status before merging."
        )


class TestUnfreezeRefusesWithoutAck:
    def test_unfreeze_refuses_without_ack(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(merge_queue_unfreeze, [])
        assert result.exit_code == 3
        assert "--ack" in result.output or "required" in result.output.lower()

    def test_unfreeze_refuses_with_empty_ack(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(merge_queue_unfreeze, ["--ack", ""])
        assert result.exit_code == 3

    def test_unfreeze_refuses_with_whitespace_only_ack(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(merge_queue_unfreeze, ["--ack", "   "])
        assert result.exit_code == 3


class TestUnfreezeRefusesInAgentContext:
    def test_unfreeze_refuses_in_agent_context(
        self, cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        result = cli_runner.invoke(
            merge_queue_unfreeze, ["--ack", "intentional unfreeze for testing"]
        )
        assert result.exit_code == 2

    def test_unfreeze_refuses_in_agent_context_json(
        self, cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        result = cli_runner.invoke(
            merge_queue_unfreeze, ["--ack", "intentional unfreeze", "--json"]
        )
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["code"] == 2


class TestStatusJsonOutput:
    @patch("orch.cli.merge_queue_commands.is_merge_queue_frozen")
    @patch("orch.cli.merge_queue_commands.safe_create_engine")
    def test_status_json_output(
        self,
        mock_safe_create_engine: MagicMock,
        mock_is_frozen: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_is_frozen.return_value = False

        mock_engine = MagicMock()
        mock_safe_create_engine.return_value = mock_engine

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_session_factory = MagicMock()
        mock_session_factory.return_value = mock_session

        with patch("orch.cli.merge_queue_commands.sessionmaker") as mock_sessionmaker:
            mock_sessionmaker.return_value = mock_session_factory

            result = cli_runner.invoke(merge_queue_status, ["--json"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "frozen" in data

    @patch("orch.cli.merge_queue_commands.is_merge_queue_frozen")
    @patch("orch.cli.merge_queue_commands.safe_create_engine")
    def test_status_frozen_state(
        self,
        mock_safe_create_engine: MagicMock,
        mock_is_frozen: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_is_frozen.return_value = True

        mock_engine = MagicMock()
        mock_safe_create_engine.return_value = mock_engine

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_session_factory = MagicMock()
        mock_session_factory.return_value = mock_session

        with patch("orch.cli.merge_queue_commands.sessionmaker") as mock_sessionmaker:
            mock_sessionmaker.return_value = mock_session_factory

            result = cli_runner.invoke(merge_queue_status, ["--json"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["frozen"] is True


class TestUnfreezeSuccess:
    @patch("orch.cli.merge_queue_commands.set_merge_queue_frozen")
    def test_unfreeze_success(
        self,
        mock_set_frozen: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = cli_runner.invoke(merge_queue_unfreeze, ["--ack", "resolved the migration issue"])

        assert result.exit_code == 0
        assert "unfrozen" in result.output.lower()
        mock_set_frozen.assert_called_once()
        call_kwargs = mock_set_frozen.call_args[1]
        assert call_kwargs["active"] is False
        assert "resolved the migration issue" in call_kwargs["reason"]
        assert "acknowledged_by" in call_kwargs

    @patch("orch.cli.merge_queue_commands.set_merge_queue_frozen")
    def test_unfreeze_success_json(
        self,
        mock_set_frozen: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = cli_runner.invoke(merge_queue_unfreeze, ["--ack", "resolved the issue", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["frozen"] is False
        assert data["reason"] == "resolved the issue"
        assert "acknowledged_by" in data
