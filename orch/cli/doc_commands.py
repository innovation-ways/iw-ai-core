"""doc CLI commands: doc-update, doc-job-start, doc-job-done."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from orch.cli.utils import output_error, resolve_project
from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, JobStatus  # noqa: F401
from orch.doc_service import DocService

_MAX_CONTENT_SIZE = 10 * 1024 * 1024


@click.command("doc-update", short_help="Upsert a project documentation record")
@click.argument("doc_id")
@click.option("--title", "title", default=None, help="Document title")
@click.option(
    "--slug", "slug", default=None, help="URL-safe slug (auto-derived from title if omitted)"
)
@click.option(
    "--doc-type",
    "doc_type",
    type=click.Choice([e.value for e in DocType]),
    default=None,
    help="Document type enum value",
)
@click.option(
    "--tier",
    "tier",
    type=click.Choice([e.value for e in DocTier]),
    default=None,
    help="Automation tier",
)
@click.option(
    "--editorial-category",
    "editorial_category",
    type=click.Choice([e.value for e in EditorialCategory]),
    default=None,
    help="Editorial category",
)
@click.option(
    "--status",
    "status",
    type=click.Choice([e.value for e in DocStatus]),
    default=None,
    help="Document status",
)
@click.option(
    "--audience",
    "audience",
    default=None,
    help="Comma-separated audience list (e.g., 'architects,senior-developers')",
)
@click.option(
    "--source-paths",
    "source_paths",
    default=None,
    help="Comma-separated list of source file paths",
)
@click.option(
    "--content",
    "content",
    default=None,
    help="Markdown content inline (mutually exclusive with --content-file)",
)
@click.option(
    "--content-file",
    "content_file",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    help="Path to markdown file (use '-' for stdin)",
)
@click.option(
    "--generated-by",
    "generated_by",
    default=None,
    help="Generator identifier (e.g., 'skill:iw-doc-generator')",
)
@click.option(
    "--trigger-reason",
    "trigger_reason",
    default=None,
    help="Reason stored in version snapshot",
)
@click.option(
    "--version",
    "version",
    type=int,
    default=None,
    help="Override version number (default: auto-increment)",
)
@click.pass_context
def doc_update(
    ctx: click.Context,
    doc_id: str,
    title: str | None,
    slug: str | None,
    doc_type: str | None,
    tier: str | None,
    editorial_category: str | None,
    status: str | None,
    audience: str | None,
    source_paths: str | None,
    content: str | None,
    content_file: Path | None,
    generated_by: str | None,
    trigger_reason: str | None,
    version: int | None,  # noqa: ARG001  # Not yet wired to DocService
) -> None:
    """Upsert a project documentation record.

    Creates or updates the ProjectDoc for the given project and doc ID.
    If the doc already exists and content changed, a new ProjectDocVersion
    snapshot is created automatically.
    """
    if content is not None and content_file is not None:
        click.echo("Error: --content and --content-file are mutually exclusive", err=True)
        sys.exit(2)

    if content_file is not None:
        if str(content_file) == "-":
            content = sys.stdin.read()
        else:
            content = content_file.read_text(encoding="utf-8")

    if content is not None and len(content.encode("utf-8")) > _MAX_CONTENT_SIZE:
        click.echo("Content exceeds maximum size (10 MB)", err=True)
        sys.exit(2)

    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            from orch.db.models import Project

            project = session.get(Project, project_id)
            if project is None:
                output_error(ctx, f"Project '{project_id}' not found", 1)

            parsed_audience: list[str] | None = None
            if audience is not None:
                parsed_audience = [s.strip() for s in audience.split(",") if s.strip()]

            parsed_source_paths: list[str] | None = None
            if source_paths is not None:
                parsed_source_paths = [s.strip() for s in source_paths.split(",") if s.strip()]

            parsed_doc_type: DocType | None = None
            if doc_type is not None:
                parsed_doc_type = DocType(doc_type)

            parsed_tier: DocTier | None = None
            if tier is not None:
                parsed_tier = DocTier(tier)

            parsed_editorial_category: EditorialCategory | None = None
            if editorial_category is not None:
                parsed_editorial_category = EditorialCategory(editorial_category)

            parsed_status: DocStatus | None = None
            if status is not None:
                parsed_status = DocStatus(status)

            svc = DocService(session)
            existing = svc.get_doc(project_id, doc_id)
            old_content_hash: str | None = None
            if existing is not None and existing.content is not None:
                old_content_hash = hashlib.sha256(existing.content.encode("utf-8")).hexdigest()

            kwargs: dict[str, Any] = {}
            if title is not None:
                kwargs["title"] = title
            if slug is not None:
                kwargs["slug"] = slug
            if parsed_doc_type is not None:
                kwargs["doc_type"] = parsed_doc_type
            if parsed_tier is not None:
                kwargs["tier"] = parsed_tier
            if parsed_editorial_category is not None:
                kwargs["editorial_category"] = parsed_editorial_category
            if parsed_status is not None:
                kwargs["status"] = parsed_status
            if parsed_audience is not None:
                kwargs["audience"] = parsed_audience
            if parsed_source_paths is not None:
                kwargs["source_paths"] = parsed_source_paths
            if content is not None:
                kwargs["content"] = content
            if generated_by is not None:
                kwargs["generated_by"] = generated_by
            if trigger_reason is not None:
                kwargs["trigger_reason"] = trigger_reason

            doc, _created = svc.upsert_doc(project_id, doc_id, **kwargs)

            snapshot_created = False
            if content is not None:
                new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                snapshot_created = old_content_hash != new_hash

            click.echo(
                json.dumps(
                    {
                        "doc_id": doc.id,
                        "project_id": doc.project_id,
                        "version": doc.version,
                        "status": doc.status.value,
                        "snapshot_created": snapshot_created,
                    }
                )
            )

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 3)


# ---------------------------------------------------------------------------
# doc-job-start: mark a queued DocGenerationJob as running
# ---------------------------------------------------------------------------


@click.command("doc-job-start")
@click.argument("job_id")
@click.option("--pid", "pid", type=int, default=None, help="Agent process ID")
@click.option("--skill", "skill", default=None, help="Skill used (e.g., iw-doc-generator)")
@click.pass_context
def doc_job_start(ctx: click.Context, job_id: str, pid: int | None, skill: str | None) -> None:
    """Mark a queued DocGenerationJob as running.

    Transitions the job from 'queued' to 'running' and records the agent PID
    and skill used. Idempotent — if the job is already running, exits 0 without
    error.
    """
    get_session = ctx.obj["get_session"]

    already_running = False

    try:
        with get_session() as session:
            svc = DocService(session)
            job = svc.get_doc_job(job_id)

            if job is None:
                output_error(ctx, f"Job '{job_id}' not found", 1)

            if job.status == JobStatus.running:
                already_running = True
            elif job.status != JobStatus.queued:
                output_error(
                    ctx,
                    (
                        f"Job '{job_id}' is in status '{job.status.value}',"
                        " expected 'queued' or 'running'"
                    ),
                    2,
                )

            if not already_running:
                job.status = JobStatus.running
                job.started_at = datetime.now(UTC)
                job.agent_pid = pid
                job.skill_used = skill
                session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 3)

    click.echo(json.dumps({"job_id": job_id, "status": "running"}))
    sys.exit(0)


# ---------------------------------------------------------------------------
# doc-job-done: mark a running DocGenerationJob as completed or failed
# ---------------------------------------------------------------------------


@click.command("doc-job-done")
@click.argument("job_id")
@click.option("--error", "error", default=None, help="Error message if the job failed")
@click.pass_context
def doc_job_done(ctx: click.Context, job_id: str, error: str | None) -> None:
    """Mark a running DocGenerationJob as completed (or failed with --error).

    Idempotent — calling this on an already-completed or already-failed job
    exits 0 without error.
    """
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            svc = DocService(session)
            job = svc.get_doc_job(job_id)

            if job is None:
                output_error(ctx, f"Job '{job_id}' not found", 1)

            if job.status in (JobStatus.completed, JobStatus.failed):
                final_status = job.status.value
                click.echo(json.dumps({"job_id": job_id, "status": final_status}))
                sys.exit(0)

            job.completed_at = datetime.now(UTC)
            if error is None:
                job.status = JobStatus.completed
                final_status = "completed"
            else:
                job.status = JobStatus.failed
                job.error = error
                final_status = "failed"

            if job.started_at is not None:
                job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())

            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 3)

    click.echo(json.dumps({"job_id": job_id, "status": final_status}))
    sys.exit(0)
