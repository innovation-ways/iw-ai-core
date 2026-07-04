"""Contract tests for `iw batch-list` against a real PostgreSQL testcontainer.

Covers the JSON contract (batches array + per-batch fields), status filtering,
and the human-readable summary line. All tests use the testcontainer
``db_session`` fixture — never the live DB.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import Batch, BatchStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project as ProjectModel


def _make_batch(
    session: Session,
    project_id: str,
    batch_id: str,
    *,
    status: BatchStatus,
) -> None:
    """Insert a minimal Batch row for list assertions.

    Args:
        session: Active testcontainer session.
        project_id: Owning project.
        batch_id: Batch identifier (e.g. ``BATCH-00001``).
        status: Batch status enum.
    """
    session.add(Batch(project_id=project_id, id=batch_id, status=status))
    session.flush()


def _invoke_json(
    runner: CliRunner, args: list[str], get_session: object, project_id: str
) -> object:
    """Invoke the CLI in --json mode with an injected session factory.

    Args:
        runner: Click test runner.
        args: CLI argument list (after the global options).
        get_session: Injected session-factory context manager.
        project_id: Project scope passed via ``--project``.

    Returns:
        The parsed Click result object.
    """
    return runner.invoke(
        cli,
        ["--project", project_id, "--json", *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def test_batch_list_empty_project_returns_empty_array(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: an empty project yields a batches array with no entries."""
    runner = CliRunner()
    result = _invoke_json(runner, ["batch-list"], cli_get_session, test_project.id)

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"
    data = json.loads(result.output)
    assert data == {"batches": []}


def test_batch_list_returns_batches_with_counts(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: created batches appear with the documented per-batch fields."""
    _make_batch(db_session, test_project.id, "BATCH-00001", status=BatchStatus.approved)

    runner = CliRunner()
    result = _invoke_json(runner, ["batch-list"], cli_get_session, test_project.id)

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert len(data["batches"]) == 1
    batch = data["batches"][0]
    assert batch["batch_id"] == "BATCH-00001"
    assert batch["status"] == "approved"
    for key in ("item_count", "completed_count"):
        assert key in batch, f"missing key {key!r} in {batch}"


def test_batch_list_status_filter_narrows_results(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: --status returns only batches in that status."""
    _make_batch(db_session, test_project.id, "BATCH-00001", status=BatchStatus.approved)
    _make_batch(db_session, test_project.id, "BATCH-00002", status=BatchStatus.completed)

    runner = CliRunner()
    result = _invoke_json(
        runner, ["batch-list", "--status", "completed"], cli_get_session, test_project.id
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert len(data["batches"]) == 1
    assert data["batches"][0]["batch_id"] == "BATCH-00002"


def test_batch_list_human_output_summary_line(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: human mode prints a 'Batches (N)' summary header."""
    _make_batch(db_session, test_project.id, "BATCH-00001", status=BatchStatus.approved)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "batch-list"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert result.output.find("Batches (1)") != -1, result.output
    assert result.output.find("BATCH-00001") != -1, result.output
