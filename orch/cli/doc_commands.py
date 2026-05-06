"""doc CLI commands: doc-update, doc-job-start, doc-job-done."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from sqlalchemy import select

from orch.cli.utils import output_error, resolve_project
from orch.daemon.state_machine import validate_work_item_status
from orch.db.models import (  # noqa: F401
    DocGenerationJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)
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

            work_item_auto_completed = False
            if doc.doc_type == DocType.research:
                work_item = session.get(WorkItem, (project_id, doc_id))
                if (
                    work_item is not None
                    and work_item.type == WorkItemType.Research
                    and work_item.status == WorkItemStatus.draft
                ):
                    validate_work_item_status(
                        WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Research
                    )
                    work_item.status = WorkItemStatus.completed
                    work_item.phase = (
                        WorkItemPhase.done
                    )  # research items transition phase directly to done — see CR-00010
                    work_item.completed_at = datetime.now(UTC)
                    work_item_auto_completed = True

            click.echo(
                json.dumps(
                    {
                        "doc_id": doc.id,
                        "project_id": doc.project_id,
                        "version": doc.version,
                        "status": doc.status.value,
                        "snapshot_created": snapshot_created,
                        "work_item_auto_completed": work_item_auto_completed,
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


# ---------------------------------------------------------------------------
# docs-check-stale: check which docs are stale based on git mtime
# ---------------------------------------------------------------------------


@click.command("docs-check-stale")
@click.argument("project_id")
@click.option(
    "--threshold-hours",
    "threshold_hours",
    type=int,
    default=24,
    help="Staleness threshold in hours (default: 24)",
)
@click.pass_context
def docs_check_stale(ctx: click.Context, project_id: str, threshold_hours: int) -> None:
    """Check which docs are stale based on git mtime of source files.

    Exits 0 if all docs are current, exits 1 if any docs are stale.
    """
    from datetime import timedelta

    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            from orch.db.models import Project

            project = session.get(Project, project_id)
            if project is None:
                output_error(ctx, f"Project '{project_id}' not found", 1)

            svc = DocService(session)
            stale = svc.get_stale_docs(project_id, project.repo_root, threshold_hours)

            if not stale:
                click.echo("All docs are current.")
                sys.exit(0)

            now = datetime.now(UTC)
            for doc, changed_path, source_mtime in stale:
                age = now - source_mtime
                if age < timedelta(hours=1) or age < timedelta(days=1):
                    age_str = f"modified {age.seconds // 3600}h ago"
                else:
                    days = age.days
                    age_str = f"modified {days}d ago"
                click.echo(f"STALE  {doc.doc_id:<30} {changed_path} ({age_str})")

            sys.exit(1)

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 3)


@click.command("docs-export")
@click.argument("project_id")
@click.argument("doc_ids", nargs=-1)
@click.option(
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory for ZIP files",
)
@click.pass_context
def docs_export(
    ctx: click.Context,
    project_id: str,
    doc_ids: tuple[str, ...],
    output_dir: Path,
) -> None:
    """Export project docs as ZIP bundles.

    PROJECT_ID is the project identifier.

    DOC_IDS are specific doc IDs to export. If none given, exports all
    non-archived docs in the project.
    """
    get_session = ctx.obj["get_session"]

    if not output_dir.is_absolute():
        click.echo("Error: --output-dir must be an absolute path", err=True)
        sys.exit(2)

    if not output_dir.exists():
        click.echo(f"Error: --output-dir '{output_dir}' does not exist", err=True)
        sys.exit(2)

    try:
        with get_session() as session:
            project = session.get(Project, project_id)
            if project is None:
                click.echo(f"Error: Project '{project_id}' not found", err=True)
                sys.exit(1)

            svc = DocService(session)

            if doc_ids:
                docs = []
                for did in doc_ids:
                    doc = svc.get_doc(project_id, did)
                    if doc is None:
                        click.echo(
                            f"Error: Doc '{did}' not found in project '{project_id}'", err=True
                        )
                        sys.exit(2)
                    docs.append(doc)
            else:
                all_docs = svc.list_docs(project_id, limit=1000)
                docs = [d for d in all_docs if d.status != DocStatus.archived]

            if not docs:
                click.echo("No docs to export.")
                sys.exit(0)

            def render_html(content: str, _doc: Any) -> str:
                return f"<html><body>{content}</body></html>"

            def render_pdf(_html: str) -> bytes | None:
                return None

            doc_id_list = [d.id for d in docs]
            zip_bytes = svc.export_bundle(project_id, doc_id_list, render_html, render_pdf)

            if len(docs) == 1:
                slug = docs[0].slug or docs[0].doc_id
                output_path = output_dir / f"{slug}.zip"
            else:
                output_path = output_dir / f"{project_id}-docs-export.zip"

            output_path.write_bytes(zip_bytes)
            click.echo(f"Exported {len(docs)} doc(s) to {output_path}")
            sys.exit(0)

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 3)


# ---------------------------------------------------------------------------
# doc-job-status: read-only job context for an agent
# ---------------------------------------------------------------------------


@click.command("doc-job-status")
@click.argument("job_id")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def doc_job_status(ctx: click.Context, job_id: str, json_output: bool) -> None:
    """Show the full context of a DocGenerationJob (read-only).

    Returns job status, joined ProjectDoc metadata (title, editorial_category),
    and the snapshot fields so an agent can produce the right content.
    """
    if json_output:
        ctx.obj["json"] = True
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    result: dict[str, Any] = {}

    try:
        with get_session() as session:
            # Try public_id first (DOC-NNNNN), then UUID PK
            job = session.scalar(
                select(DocGenerationJob).where(DocGenerationJob.public_id == job_id)
            )
            if job is None:
                job = session.get(DocGenerationJob, job_id)
            if job is None or job.project_id != project_id:
                output_error(
                    ctx,
                    f"doc-generation job '{job_id}' not found",
                    1,
                )

            doc_title: str | None = None
            editorial_category: str | None = None
            if job.doc_id:
                doc = session.get(ProjectDoc, job.doc_id)
                if doc:
                    doc_title = doc.title
                    editorial_category = (
                        doc.editorial_category.value
                        if hasattr(doc.editorial_category, "value")
                        else str(doc.editorial_category)
                    )

            result = {
                "id": job.id,
                "public_id": job.public_id,
                "project_id": job.project_id,
                "doc_id": job.doc_id,
                "doc_title": doc_title,
                "editorial_category": editorial_category,
                "status": job.status.value if job.status else None,
                "skill_used": job.skill_used,
                "trigger_reason": job.trigger_reason,
                "agent_pid": job.agent_pid,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "requested_at": job.requested_at.isoformat() if job.requested_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "section_guides_snapshot": job.section_guides_snapshot,
                "guide_snapshot": job.guide_snapshot,
            }

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        click.echo(f"Job: {result['id']}")
        click.echo(f"  Public ID:    {result['public_id'] or '—'}")
        click.echo(f"  Project:      {result['project_id']}")
        click.echo(f"  Doc ID:       {result['doc_id'] or '—'}")
        click.echo(f"  Doc title:    {result['doc_title'] or '—'}")
        click.echo(f"  Editorial:    {result['editorial_category'] or '—'}")
        click.echo(f"  Status:       {result['status']}")
        click.echo(f"  Skill:        {result['skill_used'] or '—'}")
        click.echo(f"  Trigger:      {result['trigger_reason'] or '—'}")
        click.echo(f"  Agent PID:    {result['agent_pid'] or '—'}")
        click.echo(f"  Started:      {result['started_at'] or '—'}")
        click.echo(f"  Completed:    {result['completed_at'] or '—'}")
        click.echo(f"  Requested:    {result['requested_at'] or '—'}")
        click.echo(f"  Created:      {result['created_at'] or '—'}")
        if result["section_guides_snapshot"]:
            click.echo(f"  Section guides: {len(result['section_guides_snapshot'])} section(s)")
        click.echo(f"  Guide snapshot: {'present' if result['guide_snapshot'] else 'none'}")
