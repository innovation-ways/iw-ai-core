"""Read-only aggregation of all job tables into a unified view.

Job sources and status normalisation
------------------------------------

:code_mapping: ``code_index_jobs.status`` is a TEXT column with values
  ``queued``, ``running``, ``completed``, ``failed``, ``cancelled``.
  These are passed through unchanged.

:doc_generation: ``doc_generation_jobs.status`` is a :class:`JobStatus` enum.
  Normalised values:

  - ``JobStatus.queued`` → ``queued``
  - ``JobStatus.running`` → ``running``
  - ``JobStatus.completed`` → ``completed``
  - ``JobStatus.failed`` → ``failed``

:batch_execution: ``batches.status`` is a :class:`BatchStatus` enum.
  Normalised values:

  - ``BatchStatus.planning`` → ``queued``
  - ``BatchStatus.approved`` → ``queued``
  - ``BatchStatus.executing`` → ``running``
  - ``BatchStatus.paused`` → ``paused``
  - ``BatchStatus.completed`` → ``completed``
  - ``BatchStatus.completed_with_errors`` → ``failed``
  - ``BatchStatus.publishing`` → ``running``
  - ``BatchStatus.published`` → ``completed``
  - ``BatchStatus.publish_failed`` → ``failed``
  - ``BatchStatus.blocked`` → ``failed``
  - ``BatchStatus.archived`` → ``completed``
  - ``BatchStatus.cancelled`` → ``cancelled``

:research: ``project_docs.doc_type = 'research'`` rows.
  Uses :class:`DocStatus` enum; normalised:

  - ``DocStatus.planned`` → ``queued``
  - ``DocStatus.draft`` → ``running``
  - ``DocStatus.published`` → ``completed``
  - ``DocStatus.archived`` → ``completed``

Title normalisation
-------------------

:code_mapping: ``"Code map — " + COALESCE(index_tier, "default")``
:doc_generation: ``ProjectDoc.title`` via ``doc_id`` join, fallback
  ``"Doc generation (orphan)"`` when doc is deleted
:batch_execution: ``"Batch " + id``
:research: ``ProjectDoc.title``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchStatus,
    CodeIndexJob,
    DocGenerationJob,
    DocIndexJob,
    DocStatus,
    JobStatus,
    OssScan,
    ProjectDoc,
    ProjectOssJob,
    ProjectOssJobKind,
    ProjectOssJobStatus,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

from orch.db.models import DocType


class JobType(StrEnum):
    code_mapping = "code_mapping"
    doc_indexing = "doc_indexing"
    doc_generation = "doc_generation"
    batch_execution = "batch_execution"
    research = "research"
    oss_scan = "oss_scan"


@dataclass(frozen=True)
class JobRow:
    job_type: JobType
    job_id: str
    project_id: str
    title: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    triggered_by: str | None
    raw: dict[str, object]


@dataclass(frozen=True)
class JobListResult:
    rows: list[JobRow]
    total: int
    page: int
    page_size: int


def _normalise_doc_status(status: DocStatus) -> str:
    mapping = {
        DocStatus.planned: "queued",
        DocStatus.draft: "running",
        DocStatus.published: "completed",
        DocStatus.archived: "completed",
    }
    return mapping.get(status, status.name)


def _normalise_job_status(status: JobStatus) -> str:
    return status.value


def _normalise_batch_status(status: BatchStatus) -> str:
    mapping = {
        BatchStatus.planning: "queued",
        BatchStatus.approved: "queued",
        BatchStatus.executing: "running",
        BatchStatus.paused: "paused",
        BatchStatus.completed: "completed",
        BatchStatus.completed_with_errors: "failed",
        BatchStatus.publishing: "running",
        BatchStatus.published: "completed",
        BatchStatus.publish_failed: "failed",
        BatchStatus.blocked: "failed",
        BatchStatus.archived: "completed",
        BatchStatus.cancelled: "cancelled",
    }
    return mapping.get(status, status.value)


def _normalise_oss_job_status(status: ProjectOssJobStatus) -> str:
    mapping = {
        ProjectOssJobStatus.queued: "queued",
        ProjectOssJobStatus.running: "running",
        ProjectOssJobStatus.complete: "completed",
        ProjectOssJobStatus.error: "failed",
        ProjectOssJobStatus.cancelled: "cancelled",
    }
    return mapping.get(status, status.value)


class JobsAggregator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_jobs(
        self,
        *,
        project_id: str,
        types: list[JobType] | None = None,
        statuses: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: Literal["started_at", "finished_at", "status", "job_type"] = "started_at",
        sort_dir: Literal["asc", "desc"] = "desc",
    ) -> JobListResult:
        rows: list[JobRow] = []
        raw_rows: list[tuple[JobRow, dict[str, object]]] = []

        if types is None or JobType.code_mapping in types:
            raw_rows.extend(self._fetch_code_mapping(project_id, date_from, date_to))

        if types is None or JobType.doc_indexing in types:
            raw_rows.extend(self._fetch_doc_indexing(project_id, date_from, date_to))

        if types is None or JobType.doc_generation in types:
            raw_rows.extend(self._fetch_doc_generation(project_id, date_from, date_to))

        if types is None or JobType.batch_execution in types:
            raw_rows.extend(self._fetch_batch_execution(project_id, date_from, date_to))

        if types is None or JobType.research in types:
            raw_rows.extend(self._fetch_research(project_id, date_from, date_to))

        if types is None or JobType.oss_scan in types:
            raw_rows.extend(self._fetch_oss_scan(project_id, date_from, date_to))

        for row, _ in raw_rows:
            if statuses and row.status not in statuses:
                continue
            rows.append(row)

        # Sort with a None-safe key: queued jobs have started_at/finished_at=None
        # and Python cannot compare None to datetime. Rows with a missing
        # timestamp always land at the end regardless of direction — they
        # represent jobs that haven't started/finished yet, which is what a
        # user looking at a "most recent" or "oldest first" list expects.
        reverse = sort_dir == "desc"
        with_value = [r for r in rows if getattr(r, sort_by) is not None]
        without_value = [r for r in rows if getattr(r, sort_by) is None]
        with_value.sort(key=lambda r: getattr(r, sort_by), reverse=reverse)
        rows = with_value + without_value

        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = rows[start:end]

        return JobListResult(rows=paginated, total=total, page=page, page_size=page_size)

    def get_job(
        self,
        *,
        project_id: str,
        job_type: JobType,
        job_id: str,
    ) -> JobRow | None:
        if job_type == JobType.code_mapping:
            return self._get_code_mapping(project_id, job_id)
        if job_type == JobType.doc_indexing:
            return self._get_doc_indexing(project_id, job_id)
        if job_type == JobType.doc_generation:
            return self._get_doc_generation(project_id, job_id)
        if job_type == JobType.batch_execution:
            return self._get_batch_execution(project_id, job_id)
        if job_type == JobType.research:
            return self._get_research(project_id, job_id)
        if job_type == JobType.oss_scan:
            return self._get_oss_scan(project_id, job_id)
        return None

    def _fetch_code_mapping(
        self,
        project_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[JobRow, dict[str, object]]]:
        stmt = select(CodeIndexJob).where(CodeIndexJob.project_id == project_id)
        if date_from:
            stmt = stmt.where(CodeIndexJob.triggered_at >= date_from)
        if date_to:
            stmt = stmt.where(CodeIndexJob.triggered_at <= date_to)
        jobs = self._session.scalars(stmt).all()
        results = []
        for job in jobs:
            title = f"Code map — {job.index_tier or 'default'}"
            raw: dict[str, object] = {
                "id": job.id,
                "project_id": job.project_id,
                "status": job.status,
                "provider": job.provider,
                "llm_model": job.llm_model,
                "embed_model": job.embed_model,
                "index_tier": job.index_tier,
                "files_discovered": job.files_discovered,
                "files_indexed": job.files_indexed,
                "chunks_created": job.chunks_created,
                "languages_detected": job.languages_detected,
                "errors": job.errors,
                # NOTE: This is the composite FK to project_docs.id, used here as a
                # presence flag only (the View link goes to /project/{id}/code, not
                # /docs/{id}). Do NOT use this value to build a /docs/{id} URL — see
                # I-00064 and _build_doc_generation_raw for the correct convention.
                "doc_id": job.doc_id,
                "triggered_at": job.triggered_at,
                "completed_at": job.completed_at,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
            results.append(
                (
                    JobRow(
                        job_type=JobType.code_mapping,
                        job_id=job.public_id or job.id,
                        project_id=job.project_id,
                        title=title,
                        status=job.status,
                        started_at=job.triggered_at,
                        finished_at=job.completed_at,
                        triggered_by=None,
                        raw=raw,
                    ),
                    raw,
                )
            )
        return results

    def _fetch_doc_indexing(
        self,
        project_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[JobRow, dict[str, object]]]:
        stmt = select(DocIndexJob).where(DocIndexJob.project_id == project_id)
        if date_from:
            stmt = stmt.where(DocIndexJob.triggered_at >= date_from)
        if date_to:
            stmt = stmt.where(DocIndexJob.triggered_at <= date_to)
        jobs = self._session.scalars(stmt).all()
        results = []
        for job in jobs:
            embed_label = job.embed_model or job.index_tier or "default"
            title = f"Doc index — {embed_label}"
            raw: dict[str, object] = {
                "id": job.id,
                "project_id": job.project_id,
                "status": job.status,
                "provider": job.provider,
                "llm_model": job.llm_model,
                "embed_model": job.embed_model,
                "index_tier": job.index_tier,
                "items_discovered": job.items_discovered,
                "items_indexed": job.items_indexed,
                "chunks_created": job.chunks_created,
                "errors": job.errors,
                "error_message": job.error_message,
                "triggered_at": job.triggered_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
            }
            results.append(
                (
                    JobRow(
                        job_type=JobType.doc_indexing,
                        job_id=job.id,
                        project_id=job.project_id,
                        title=title,
                        status=job.status,
                        started_at=job.started_at,
                        finished_at=job.completed_at,
                        triggered_by=None,
                        raw=raw,
                    ),
                    raw,
                )
            )
        return results

    def _fetch_doc_generation(
        self,
        project_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[JobRow, dict[str, object]]]:
        stmt = select(DocGenerationJob).where(DocGenerationJob.project_id == project_id)
        if date_from:
            stmt = stmt.where(
                (DocGenerationJob.started_at >= date_from)
                | (DocGenerationJob.requested_at >= date_from)
                | (DocGenerationJob.created_at >= date_from)
            )
        if date_to:
            stmt = stmt.where(
                (DocGenerationJob.started_at <= date_to)
                | (DocGenerationJob.requested_at <= date_to)
                | (DocGenerationJob.created_at <= date_to)
            )
        jobs = self._session.scalars(stmt).all()

        doc_ids = [job.doc_id for job in jobs if job.doc_id]
        doc_titles: dict[str, str] = {}
        doc_inner_ids: dict[str, str] = {}
        if doc_ids:
            docs = self._session.scalars(select(ProjectDoc).where(ProjectDoc.id.in_(doc_ids))).all()
            doc_titles = {doc.id: doc.title for doc in docs}
            doc_inner_ids = {doc.id: doc.doc_id for doc in docs}

        results = []
        for job in jobs:
            title = (
                doc_titles.get(job.doc_id, "Doc generation (orphan)")
                if job.doc_id
                else "Doc generation (orphan)"
            )
            status_norm = _normalise_job_status(job.status)
            started = job.started_at or job.requested_at or job.created_at
            triggered_by = job.skill_used or job.trigger_reason
            raw = self._build_doc_generation_raw(
                job,
                inner_doc_id=doc_inner_ids.get(job.doc_id) if job.doc_id else None,
            )
            results.append(
                (
                    JobRow(
                        job_type=JobType.doc_generation,
                        job_id=job.public_id or job.id,
                        project_id=job.project_id,
                        title=title,
                        status=status_norm,
                        started_at=started,
                        finished_at=job.completed_at,
                        triggered_by=triggered_by,
                        raw=raw,
                    ),
                    raw,
                )
            )
        return results

    def _build_doc_generation_raw(
        self, job: DocGenerationJob, inner_doc_id: str | None = None
    ) -> dict[str, object]:
        """Build the raw dict for a DocGenerationJob.

        Used by both _fetch_doc_generation (list view) and _get_doc_generation
        (detail page) to ensure the same field set is always returned,
        preventing missing fields on the detail page.

        raw["doc_id"] MUST be the inner ProjectDoc.doc_id (the user-defined
        identifier within the project), NOT the composite FK. The job detail
        template builds /project/{pid}/docs/{raw.doc_id}, and the docs route
        re-prefixes that with project_id when looking up the row. Passing the
        composite causes a double-prefix 404. See I-00064.
        """
        return {
            "id": job.id,
            "public_id": job.public_id,
            "project_id": job.project_id,
            "doc_id": inner_doc_id,
            "status": job.status.value,
            "requested_at": job.requested_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "agent_output": job.agent_output,
            "error": job.error,
            "agent_pid": job.agent_pid,
            "skill_used": job.skill_used,
            "trigger_reason": job.trigger_reason,
            "lint_warnings": job.lint_warnings,
            "duration_seconds": job.duration_seconds,
            "section_guides_snapshot": job.section_guides_snapshot,
            "guide_snapshot": job.guide_snapshot,
            "created_at": job.created_at,
            "report": job.report,
        }

    def _fetch_batch_execution(
        self,
        project_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[JobRow, dict[str, object]]]:
        stmt = select(Batch).where(Batch.project_id == project_id)
        if date_from:
            stmt = stmt.where(Batch.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Batch.created_at <= date_to)
        batches = self._session.scalars(stmt).all()
        results = []
        for batch in batches:
            status_norm = _normalise_batch_status(batch.status)
            raw: dict[str, object] = {
                "id": batch.id,
                "project_id": batch.project_id,
                "status": batch.status.value,
                "max_parallel": batch.max_parallel,
                "cli_tool": batch.cli_tool,
                "auto_publish": batch.auto_publish,
                "plan_path": batch.plan_path,
                "diagram_path": batch.diagram_path,
                "execution_plan_md": batch.execution_plan_md,
                "created_at": batch.created_at,
                "updated_at": batch.updated_at,
                "completed_at": batch.completed_at,
                "archived_at": batch.archived_at,
            }
            results.append(
                (
                    JobRow(
                        job_type=JobType.batch_execution,
                        job_id=batch.id,
                        project_id=batch.project_id,
                        title=f"Batch {batch.id}",
                        status=status_norm,
                        started_at=batch.created_at,
                        finished_at=batch.completed_at,
                        triggered_by=None,
                        raw=raw,
                    ),
                    raw,
                )
            )
        return results

    def _fetch_research(
        self,
        project_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[JobRow, dict[str, object]]]:
        stmt = select(ProjectDoc).where(
            ProjectDoc.project_id == project_id,
            ProjectDoc.doc_type == DocType.research,
        )
        if date_from:
            stmt = stmt.where(ProjectDoc.created_at >= date_from)
        if date_to:
            stmt = stmt.where(ProjectDoc.created_at <= date_to)
        docs = self._session.scalars(stmt).all()
        results = []
        for doc in docs:
            status_norm = _normalise_doc_status(doc.status)
            finished_at = doc.generated_at if doc.status == DocStatus.published else None
            raw: dict[str, object] = {
                "id": doc.id,
                "project_id": doc.project_id,
                "doc_id": doc.doc_id,
                "title": doc.title,
                "slug": doc.slug,
                "doc_type": doc.doc_type.value,
                "tier": doc.tier.value,
                "editorial_category": doc.editorial_category.value,
                "status": doc.status.value,
                "audience": doc.audience,
                "source_paths": doc.source_paths,
                "content": doc.content,
                "version": doc.version,
                "generated_at": doc.generated_at,
                "generated_by": doc.generated_by,
                "html_path": doc.html_path,
                "pdf_path": doc.pdf_path,
                "broken_links": doc.broken_links,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            }
            results.append(
                (
                    JobRow(
                        job_type=JobType.research,
                        job_id=doc.doc_id,
                        project_id=doc.project_id,
                        title=doc.title,
                        status=status_norm,
                        started_at=doc.created_at,
                        finished_at=finished_at,
                        triggered_by=doc.generated_by,
                        raw=raw,
                    ),
                    raw,
                )
            )
        return results

    def _get_code_mapping(self, project_id: str, job_id: str) -> JobRow | None:
        job = self._session.scalar(
            select(CodeIndexJob).where(
                CodeIndexJob.public_id == job_id,
                CodeIndexJob.project_id == project_id,
            )
        )
        if job is None:
            return None
        raw: dict[str, object] = {
            "id": job.id,
            "project_id": job.project_id,
            "status": job.status,
            "provider": job.provider,
            "llm_model": job.llm_model,
            "embed_model": job.embed_model,
            "index_tier": job.index_tier,
            "files_discovered": job.files_discovered,
            "files_indexed": job.files_indexed,
            "chunks_created": job.chunks_created,
            "languages_detected": job.languages_detected,
            "errors": job.errors,
            # NOTE: This is the composite FK to project_docs.id, used here as a
            # presence flag only (the View link goes to /project/{id}/code, not
            # /docs/{id}). Do NOT use this value to build a /docs/{id} URL — see
            # I-00064 and _build_doc_generation_raw for the correct convention.
            "doc_id": job.doc_id,
            "triggered_at": job.triggered_at,
            "completed_at": job.completed_at,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
        return JobRow(
            job_type=JobType.code_mapping,
            job_id=job.public_id or job.id,
            project_id=job.project_id,
            title=f"Code map — {job.index_tier or 'default'}",
            status=job.status,
            started_at=job.triggered_at,
            finished_at=job.completed_at,
            triggered_by=None,
            raw=raw,
        )

    def _get_doc_indexing(self, project_id: str, job_id: str) -> JobRow | None:
        job = self._session.get(DocIndexJob, job_id)
        if job is None or job.project_id != project_id:
            return None
        embed_label = job.embed_model or job.index_tier or "default"
        raw: dict[str, object] = {
            "id": job.id,
            "project_id": job.project_id,
            "status": job.status,
            "provider": job.provider,
            "llm_model": job.llm_model,
            "embed_model": job.embed_model,
            "index_tier": job.index_tier,
            "items_discovered": job.items_discovered,
            "items_indexed": job.items_indexed,
            "chunks_created": job.chunks_created,
            "errors": job.errors,
            "error_message": job.error_message,
            "triggered_at": job.triggered_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }
        return JobRow(
            job_type=JobType.doc_indexing,
            job_id=job.id,
            project_id=job.project_id,
            title=f"Doc index — {embed_label}",
            status=job.status,
            started_at=job.started_at,
            finished_at=job.completed_at,
            triggered_by=None,
            raw=raw,
        )

    def _get_doc_generation(self, project_id: str, job_id: str) -> JobRow | None:
        # Try lookup by public_id first (new rows), fall back to UUID PK (legacy rows)
        job = self._session.scalar(
            select(DocGenerationJob).where(DocGenerationJob.public_id == job_id)
        )
        if job is None:
            job = self._session.get(DocGenerationJob, job_id)
        if job is None or job.project_id != project_id:
            return None
        doc_title = None
        inner_doc_id: str | None = None
        if job.doc_id:
            doc = self._session.get(ProjectDoc, job.doc_id)
            if doc:
                doc_title = doc.title
                inner_doc_id = doc.doc_id
        title = doc_title or "Doc generation (orphan)"
        return JobRow(
            job_type=JobType.doc_generation,
            job_id=job.public_id or job.id,
            project_id=job.project_id,
            title=title,
            status=_normalise_job_status(job.status),
            started_at=job.started_at or job.requested_at or job.created_at,
            finished_at=job.completed_at,
            triggered_by=job.skill_used or job.trigger_reason,
            raw=self._build_doc_generation_raw(job, inner_doc_id=inner_doc_id),
        )

    def _get_batch_execution(self, project_id: str, job_id: str) -> JobRow | None:
        batch = self._session.get(Batch, (project_id, job_id))
        if batch is None:
            return None
        return JobRow(
            job_type=JobType.batch_execution,
            job_id=batch.id,
            project_id=batch.project_id,
            title=f"Batch {batch.id}",
            status=_normalise_batch_status(batch.status),
            started_at=batch.created_at,
            finished_at=batch.completed_at,
            triggered_by=None,
            raw={"id": batch.id, "project_id": batch.project_id, "status": batch.status.value},
        )

    def _get_research(self, project_id: str, job_id: str) -> JobRow | None:
        doc = self._session.scalar(
            select(ProjectDoc).where(
                ProjectDoc.project_id == project_id,
                ProjectDoc.doc_id == job_id,
                ProjectDoc.doc_type == DocType.research,
            )
        )
        if doc is None:
            return None
        status_norm = _normalise_doc_status(doc.status)
        return JobRow(
            job_type=JobType.research,
            job_id=doc.doc_id,
            project_id=doc.project_id,
            title=doc.title,
            status=status_norm,
            started_at=doc.created_at,
            finished_at=doc.generated_at if doc.status == DocStatus.published else None,
            triggered_by=doc.generated_by,
            raw={"id": doc.id, "project_id": doc.project_id, "status": doc.status.value},
        )

    def _build_oss_job_row(self, job: ProjectOssJob) -> tuple[JobRow, dict[str, object]]:
        scan: OssScan | None = (
            self._session.get(OssScan, job.scan_id) if job.scan_id is not None else None
        )
        title = f"OSS {job.kind.value}"
        raw: dict[str, object] = {
            "id": job.public_id,
            "internal_id": job.id,
            "public_id": job.public_id,
            "project_id": job.project_id,
            "kind": job.kind.value,
            "status": job.status.value,
            "exit_code": job.exit_code,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "scan_id": job.scan_id,
            "stdout_tail": job.stdout_tail,
            "error_message": job.error_message,
            "base_sha": job.base_sha,
        }
        if scan is not None:
            raw["scan_status"] = scan.status.value
            raw["scan_exit_code"] = scan.exit_code
            raw["scan_pill_color"] = scan.pill_color.value if scan.pill_color else None
            raw["scan_summary_json"] = scan.summary_json
            raw["scan_error_message"] = scan.error_message
            raw["scan_head_sha"] = scan.head_sha
        return (
            JobRow(
                job_type=JobType.oss_scan,
                job_id=job.public_id,
                project_id=job.project_id,
                title=title,
                status=_normalise_oss_job_status(job.status),
                started_at=job.started_at or job.created_at,
                finished_at=job.completed_at,
                triggered_by=None,
                raw=raw,
            ),
            raw,
        )

    def _fetch_oss_scan(
        self,
        project_id: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[JobRow, dict[str, object]]]:
        stmt = select(ProjectOssJob).where(
            ProjectOssJob.project_id == project_id,
            ProjectOssJob.kind == ProjectOssJobKind.scan,
        )
        if date_from:
            stmt = stmt.where(ProjectOssJob.created_at >= date_from)
        if date_to:
            stmt = stmt.where(ProjectOssJob.created_at <= date_to)
        jobs = self._session.scalars(stmt).all()
        return [self._build_oss_job_row(job) for job in jobs]

    def _get_oss_scan(self, project_id: str, job_id: str) -> JobRow | None:
        job = self._session.scalar(select(ProjectOssJob).where(ProjectOssJob.public_id == job_id))
        if job is None or job.project_id != project_id:
            return None
        if job.kind != ProjectOssJobKind.scan:
            return None
        row, _ = self._build_oss_job_row(job)
        return row
