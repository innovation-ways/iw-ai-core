"""Unit tests for migrations CLI commands — smoke tests using CliRunner with mocks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from orch.cli.migrations_commands import apply_migrations, dry_run, list_pending
from orch.db.safe_migrate import DryRunResult, MultipleHeadsError, Revision


@pytest.fixture
def cli_runner():
    """Provide cli runner for tests."""
    return CliRunner()


class TestApplyRefusesWithoutOperatorFlag:
    """Tests for ApplyRefusesWithoutOperatorFlag scenarios."""

    def test_apply_refuses_without_operator_flag(self, cli_runner: CliRunner) -> None:
        """Verifies that apply refuses without operator flag."""
        result = cli_runner.invoke(apply_migrations, [])
        assert result.exit_code == 3
        assert "--i-am-operator" in result.output or "required" in result.output.lower()

    def test_apply_refuses_with_json_output(self, cli_runner: CliRunner) -> None:
        """Verifies that apply refuses with json output."""
        result = cli_runner.invoke(apply_migrations, ["--json"])
        assert result.exit_code == 3


class TestApplyRefusesInAgentContext:
    """Tests for ApplyRefusesInAgentContext scenarios."""

    def test_apply_refuses_in_agent_context(
        self, cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that apply refuses in agent context."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        result = cli_runner.invoke(apply_migrations, ["--i-am-operator"])
        assert result.exit_code == 2

    def test_apply_refuses_in_agent_context_json(
        self, cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that apply refuses in agent context json."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        result = cli_runner.invoke(apply_migrations, ["--i-am-operator", "--json"])
        assert result.exit_code == 2
        import json

        data = json.loads(result.output)
        assert data["code"] == 2


class TestListPending:
    """Tests for ListPending scenarios."""

    @patch("orch.cli.migrations_commands.list_pending_revisions")
    def test_list_pending_ok(
        self,
        mock_list: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that list pending ok."""
        mock_list.return_value = [
            Revision(
                id="abc123",
                description="add users table",
                down_revision="xyz789",
            )
        ]

        result = cli_runner.invoke(list_pending, [])

        assert result.exit_code == 0
        assert "abc123" in result.output
        assert "add users table" in result.output
        assert "xyz789" in result.output

    @patch("orch.cli.migrations_commands.list_pending_revisions")
    def test_list_pending_json(
        self,
        mock_list: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that list pending json."""
        import json

        mock_list.return_value = [
            Revision(
                id="abc123",
                description="add users table",
                down_revision="xyz789",
            )
        ]

        result = cli_runner.invoke(list_pending, ["--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == "abc123"

    @patch("orch.cli.migrations_commands.list_pending_revisions")
    def test_list_pending_empty(
        self,
        mock_list: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that list pending empty."""
        mock_list.return_value = []

        result = cli_runner.invoke(list_pending, [])

        assert result.exit_code == 0
        assert "No pending migrations" in result.output


class TestDryRun:
    """Tests for DryRun scenarios."""

    @patch("testcontainers.postgres.PostgresContainer")
    def test_dry_run_success(
        self,
        mock_container_cls: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that dry run success."""
        mock_container = MagicMock()
        mock_container.get_connection_url.return_value = (
            "postgresql+psycopg2://test:test@localhost:5432/test"
        )
        mock_container_cls.return_value = mock_container

        with patch("orch.cli.migrations_commands.safe_dry_run") as mock_dry_run:
            mock_dry_run.return_value = DryRunResult(
                revisions_applied=["abc123"],
                success=True,
                duration_ms=100,
                stdout_tail="",
                stderr_tail="",
                error_message=None,
            )

            result = cli_runner.invoke(dry_run, [])

        assert result.exit_code == 0
        assert "succeeded" in result.output.lower()

    @patch("testcontainers.postgres.PostgresContainer")
    def test_dry_run_failure_exit_code(
        self,
        mock_container_cls: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that dry run failure exit code."""
        mock_container = MagicMock()
        mock_container.get_connection_url.return_value = (
            "postgresql+psycopg2://test:test@localhost:5432/test"
        )
        mock_container_cls.return_value = mock_container

        with patch("orch.cli.migrations_commands.safe_dry_run") as mock_dry_run:
            mock_dry_run.return_value = DryRunResult(
                revisions_applied=[],
                success=False,
                duration_ms=50,
                stdout_tail="",
                stderr_tail="ERROR: relation does not exist",
                error_message="relation does not exist",
            )

            result = cli_runner.invoke(dry_run, [])

        assert result.exit_code == 5
        assert "FAILED" in result.output


class TestMultiHead:
    """Tests for MultiHead scenarios."""

    @patch("orch.cli.migrations_commands.list_pending_revisions")
    def test_multi_head_exit_code(
        self,
        mock_list: MagicMock,
        cli_runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that multi head exit code."""
        mock_list.side_effect = MultipleHeadsError(
            "Multiple alembic heads detected: ['head1', 'head2']. Create a merge revision."
        )

        result = cli_runner.invoke(list_pending, [])

        assert result.exit_code == 4
