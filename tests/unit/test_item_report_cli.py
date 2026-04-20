"""Unit tests for the item-report CLI command using Click's CliRunner."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Generator

from click.testing import CliRunner

from orch.cli.item_commands import item_report


def make_get_session(mock_session: MagicMock) -> object:
    """Return a get_session factory that yields mock_session."""

    @contextmanager
    def get_session() -> Generator[MagicMock, None, None]:
        yield mock_session

    return get_session


def make_ctx_obj(mock_session: MagicMock, project_id: str | None = None) -> dict[str, object]:
    return {"get_session": make_get_session(mock_session), "project_id": project_id}


class TestItemReportCli:
    """Test the iw item-report CLI command."""

    def test_exit_code_0_on_success(self) -> None:
        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test"
        mock_item.type.value = "Feature"
        mock_item.status.value = "completed"
        mock_item.project_id = "test-proj"
        mock_session.get.return_value = mock_item

        mock_steps = MagicMock()
        mock_steps.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_steps

        ctx_obj = make_ctx_obj(mock_session, project_id="test-proj")
        runner = CliRunner()

        with patch("orch.cli.item_commands.assemble_execution_report") as mock_assemble:
            mock_data = MagicMock()
            mock_data.work_item_id = "F-00055"
            mock_data.work_item_title = "Test"
            mock_data.work_item_type = "Feature"
            mock_data.work_item_status = "completed"
            mock_data.verdict = "completed"
            mock_data.verdict_badge = "Completed"
            mock_data.item_started_at = None
            mock_data.item_completed_at = None
            mock_data.total_duration_secs = 0.0
            mock_data.steps = []
            mock_data.hotspots = []
            mock_data.generated_at = MagicMock()
            mock_data.generated_at.isoformat.return_value = "2025-01-01T00:00:00"
            mock_assemble.return_value = mock_data

            with patch("orch.cli.item_commands.write_execution_report") as mock_write:
                mock_write.return_value = MagicMock()
                result = runner.invoke(
                    item_report, ["F-00055", "--project", "test-proj"], obj=ctx_obj
                )
                assert result.exit_code == 0, (
                    f"exception: {result.exception}, output: {result.output}"
                )

    def test_exit_code_1_on_unknown_item(self) -> None:
        mock_session = MagicMock()
        mock_session.get.return_value = None

        ctx_obj = make_ctx_obj(mock_session, project_id="test-proj")
        runner = CliRunner()

        with patch("orch.cli.item_commands.assemble_execution_report") as mock_assemble:
            mock_assemble.side_effect = ValueError("Work item F-DOES-NOT-EXIST not found")
            result = runner.invoke(
                item_report, ["F-DOES-NOT-EXIST", "--project", "test-proj"], obj=ctx_obj
            )
            assert result.exit_code == 1, f"exception: {result.exception}, output: {result.output}"

    def test_exit_code_2_on_path_resolution_failure(self) -> None:
        from orch.daemon.execution_report import ExecutionReportResolutionError

        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test"
        mock_item.type.value = "Feature"
        mock_item.status.value = "completed"
        mock_item.project_id = "test-proj"
        mock_session.get.return_value = mock_item

        mock_steps = MagicMock()
        mock_steps.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_steps

        ctx_obj = make_ctx_obj(mock_session, project_id="test-proj")
        runner = CliRunner()

        with patch("orch.cli.item_commands.assemble_execution_report") as mock_assemble:
            mock_data = MagicMock()
            mock_data.work_item_id = "F-00055"
            mock_data.work_item_title = "Test"
            mock_data.work_item_type = "Feature"
            mock_data.work_item_status = "completed"
            mock_data.verdict = "completed"
            mock_data.verdict_badge = "Completed"
            mock_data.item_started_at = None
            mock_data.item_completed_at = None
            mock_data.total_duration_secs = 0.0
            mock_data.steps = []
            mock_data.hotspots = []
            mock_data.generated_at = MagicMock()
            mock_data.generated_at.isoformat.return_value = "2025-01-01T00:00:00"
            mock_assemble.return_value = mock_data

            with patch("orch.cli.item_commands.write_execution_report") as mock_write:
                mock_write.side_effect = ExecutionReportResolutionError(
                    "Neither active nor archive dir exists"
                )
                result = runner.invoke(
                    item_report, ["F-00055", "--project", "test-proj"], obj=ctx_obj
                )
                assert result.exit_code == 2, (
                    f"exception: {result.exception}, output: {result.output}"
                )

    def test_stdout_flag_prints_markdown(self) -> None:
        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test"
        mock_item.type.value = "Feature"
        mock_item.status.value = "completed"
        mock_item.project_id = "test-proj"
        mock_session.get.return_value = mock_item

        mock_steps = MagicMock()
        mock_steps.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_steps

        ctx_obj = make_ctx_obj(mock_session, project_id="test-proj")
        runner = CliRunner()

        with patch("orch.cli.item_commands.assemble_execution_report") as mock_assemble:
            mock_data = MagicMock()
            mock_data.work_item_id = "F-00055"
            mock_data.work_item_title = "Test"
            mock_data.work_item_type = "Feature"
            mock_data.work_item_status = "completed"
            mock_data.verdict = "completed"
            mock_data.verdict_badge = "Completed"
            mock_data.item_started_at = None
            mock_data.item_completed_at = None
            mock_data.total_duration_secs = 0.0
            mock_data.steps = []
            mock_data.hotspots = []
            mock_data.generated_at = MagicMock()
            mock_data.generated_at.isoformat.return_value = "2025-01-01T00:00:00"
            mock_assemble.return_value = mock_data

            with patch("orch.cli.item_commands.render_execution_report_markdown") as mock_render:
                mock_render.return_value = "# Execution Report: F-00055\n\nMarkdown content"
                result = runner.invoke(
                    item_report, ["F-00055", "--stdout", "--project", "test-proj"], obj=ctx_obj
                )
                assert result.exit_code == 0, (
                    f"exception: {result.exception}, output: {result.output}"
                )
                assert "Markdown content" in result.output

    def test_project_flag_respected(self) -> None:
        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test"
        mock_item.type.value = "Feature"
        mock_item.status.value = "completed"
        mock_item.project_id = "custom-proj"
        mock_session.get.return_value = mock_item

        mock_steps = MagicMock()
        mock_steps.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_steps

        ctx_obj = make_ctx_obj(mock_session, project_id="custom-proj")
        runner = CliRunner()

        with patch("orch.cli.item_commands.assemble_execution_report") as mock_assemble:
            mock_data = MagicMock()
            mock_data.work_item_id = "F-00055"
            mock_data.work_item_title = "Test"
            mock_data.work_item_type = "Feature"
            mock_data.work_item_status = "completed"
            mock_data.verdict = "completed"
            mock_data.verdict_badge = "Completed"
            mock_data.item_started_at = None
            mock_data.item_completed_at = None
            mock_data.total_duration_secs = 0.0
            mock_data.steps = []
            mock_data.hotspots = []
            mock_data.generated_at = MagicMock()
            mock_data.generated_at.isoformat.return_value = "2025-01-01T00:00:00"
            mock_assemble.return_value = mock_data

            with patch("orch.cli.item_commands.write_execution_report") as mock_write:
                mock_write.return_value = MagicMock()
                result = runner.invoke(
                    item_report, ["F-00055", "--project", "custom-proj"], obj=ctx_obj
                )
                assert result.exit_code == 0, (
                    f"exception: {result.exception}, output: {result.output}"
                )


class TestItemReportCliNoDiskWrite:
    """Test that --stdout does not write to disk."""

    def test_stdout_does_not_write_file(self) -> None:
        mock_session = MagicMock()
        mock_item = MagicMock()
        mock_item.title = "Test"
        mock_item.type.value = "Feature"
        mock_item.status.value = "completed"
        mock_item.project_id = "test-proj"
        mock_session.get.return_value = mock_item

        mock_steps = MagicMock()
        mock_steps.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_steps

        ctx_obj = make_ctx_obj(mock_session, project_id="test-proj")
        runner = CliRunner()

        with patch("orch.cli.item_commands.assemble_execution_report") as mock_assemble:
            mock_data = MagicMock()
            mock_data.work_item_id = "F-00055"
            mock_data.work_item_title = "Test"
            mock_data.work_item_type = "Feature"
            mock_data.work_item_status = "completed"
            mock_data.verdict = "completed"
            mock_data.verdict_badge = "Completed"
            mock_data.item_started_at = None
            mock_data.item_completed_at = None
            mock_data.total_duration_secs = 0.0
            mock_data.steps = []
            mock_data.hotspots = []
            mock_data.generated_at = MagicMock()
            mock_data.generated_at.isoformat.return_value = "2025-01-01T00:00:00"
            mock_assemble.return_value = mock_data

            with patch("orch.cli.item_commands.render_execution_report_markdown") as mock_render:
                mock_render.return_value = "Markdown output"
                with patch("orch.cli.item_commands.write_execution_report") as mock_write:
                    result = runner.invoke(
                        item_report, ["F-00055", "--stdout", "--project", "test-proj"], obj=ctx_obj
                    )
                    mock_write.assert_not_called()
                    assert result.exit_code == 0, (
                        f"exception: {result.exception}, output: {result.output}"
                    )
