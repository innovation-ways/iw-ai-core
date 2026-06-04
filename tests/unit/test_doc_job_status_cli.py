"""Unit tests for the `iw doc-job-status` CLI command.

Uses click.testing.CliRunner against the full `cli` group.
The command is read-only — we verify it never mutates DB rows.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import DocGenerationJob, EditorialCategory, JobStatus, ProjectDoc

if TYPE_CHECKING:
    from collections.abc import Generator


def _make_mock_session() -> MagicMock:
    """Return a fully-configured mock session for doc-job-status tests."""
    return MagicMock()


def _make_get_session(mock_session: MagicMock) -> object:
    """Return a get_session factory that yields mock_session."""

    @contextmanager
    def get_session() -> Generator[MagicMock, None, None]:
        """Return get session."""
        yield mock_session

    return get_session


def _make_ctx(mock_session: MagicMock, project_id: str) -> dict:
    """Build the ctx.obj dict that doc_job_status reads."""
    return {"get_session": _make_get_session(mock_session), "project_id": project_id, "json": False}


class TestDocJobStatusCli:
    """Test the new `iw doc-job-status` command via the full CLI."""

    def test_doc_job_status_json_returns_all_keys(self) -> None:
        """--json output contains all required keys per AC9."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        doc = ProjectDoc(
            id=f"{project_id}:doc001",
            project_id=project_id,
            title="Test Document",
            editorial_category=EditorialCategory.technical,
            doc_type="api",
            status="planned",
            tier="minor",
            content="# Test",
        )

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=doc.id,
            public_id="DOC-99901",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
            trigger_reason="job:test",
            section_guides_snapshot={"section1": "guide content"},
            guide_snapshot={"guide": "snapshot"},
        )

        mock_session.scalar.return_value = None
        mock_session.get.side_effect = lambda _model, pk: job if pk == job.id else None

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id, "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, f"exit={result.exit_code} output={result.output}"

        data = json.loads(result.output)
        required_keys = [
            "id",
            "public_id",
            "project_id",
            "doc_id",
            "doc_title",
            "editorial_category",
            "status",
            "skill_used",
            "trigger_reason",
            "agent_pid",
            "section_guides_snapshot",
            "guide_snapshot",
            "started_at",
            "completed_at",
            "requested_at",
            "created_at",
        ]
        for key in required_keys:
            assert key in data, f"missing key: {key}"

    def test_doc_job_status_resolves_by_public_id(self) -> None:
        """The command accepts a public_id (DOC-NNNNN) and resolves it to the job."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            public_id="DOC-PUB01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            agent_pid=12345,
        )

        mock_session.scalar.return_value = job
        mock_session.get.return_value = None

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", "DOC-PUB01", "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["id"] == job.id

    def test_doc_job_status_resolves_by_uuid(self) -> None:
        """The command also accepts the raw UUID."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            public_id="DOC-UUID01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            agent_pid=12345,
        )

        mock_session.scalar.return_value = None
        mock_session.get.return_value = job

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id, "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["id"] == job.id

    def test_doc_job_status_join_returns_doc_title(self) -> None:
        """When doc_id is set, doc_title and editorial_category come from the joined ProjectDoc."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        doc = ProjectDoc(
            id=f"{project_id}:doc-join-test",
            project_id=project_id,
            title="My Joined Document",
            editorial_category=EditorialCategory.functional,
            doc_type="api",
            status="planned",
            tier="minor",
            content="# Doc",
        )

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=doc.id,
            public_id="DOC-JOIN01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            agent_pid=12345,
        )

        mock_session.scalar.return_value = None

        def get_side_effect(model, pk):
            """Return get side effect."""
            if model == DocGenerationJob and pk == job.id:
                return job
            if model == ProjectDoc and pk == doc.id:
                return doc
            return None

        mock_session.get.side_effect = get_side_effect

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id, "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["doc_title"] == "My Joined Document"
        assert data["editorial_category"] == "functional"

    def test_doc_job_status_doc_id_null_returns_null_join_fields(self) -> None:
        """When doc_id is None, doc_title and editorial_category are null — not raised."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=None,
            public_id="DOC-NODOC01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            agent_pid=12345,
        )

        mock_session.scalar.return_value = None
        mock_session.get.return_value = job

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id, "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["doc_id"] is None
        assert data["doc_title"] is None
        assert data["editorial_category"] is None

    def test_doc_job_status_missing_job_exits_nonzero(self) -> None:
        """Invoking with a non-existent job-id exits with non-zero code and error in output."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        mock_session.scalar.return_value = None
        mock_session.get.return_value = None

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", "DOC-NONEXISTENT", "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_doc_job_status_is_read_only(self) -> None:
        """Calling doc-job-status does not mutate the job row (no commit/flush side effects)."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            public_id="DOC-READ01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            agent_pid=12345,
        )

        before_status = job.status
        before_error = job.error

        mock_session.scalar.return_value = None
        mock_session.get.return_value = job

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id, "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output

        assert job.status == before_status
        assert job.error == before_error

    def test_doc_job_status_human_output_renders(self) -> None:
        """Without --json, output contains key labels (smoke test)."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            public_id="DOC-HUMAN01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            agent_pid=12345,
        )

        mock_session.scalar.return_value = None
        mock_session.get.return_value = job

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output
        assert "Status:" in result.output or "Job:" in result.output

    def test_doc_job_status_datetimes_serialised_iso8601(self) -> None:
        """started_at, requested_at etc. are ISO8601 strings parseable by datetime.fromisoformat."""
        project_id = "test-proj"
        mock_session = _make_mock_session()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            public_id="DOC-DATE01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
        )

        mock_session.scalar.return_value = None
        mock_session.get.return_value = job

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--project", project_id, "doc-job-status", job.id, "--json"],
            obj=_make_ctx(mock_session, project_id),
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)

        from datetime import datetime as dt

        for field in ("started_at", "requested_at", "created_at"):
            val = data.get(field)
            if val is not None:
                dt.fromisoformat(val)
