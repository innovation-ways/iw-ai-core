"""DocService — CRUD operations for ProjectDoc, version snapshots, FTS query."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import (
    DocGenerationJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
    ProjectDocVersion,
)


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = slug.replace(" ", "-")
    result = []
    for ch in slug:
        if ch.isalnum() or ch in "-_":
            result.append(ch)
        else:
            result.append("-")
    slug = "".join(result)
    slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
    if not slug:
        slug = "untitled"
    return slug


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class DocService:
    __slots__ = ("_session",)

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_doc(
        self,
        project_id: str,
        doc_id: str,
        title: str,
        doc_type: DocType,
        tier: DocTier,
        editorial_category: EditorialCategory,
        status: DocStatus = DocStatus.planned,
        slug: str | None = None,
        audience: list[str] | None = None,
        source_paths: list[str] | None = None,
        content: str | None = None,
        generated_by: str | None = None,
        trigger_reason: str | None = None,
    ) -> ProjectDoc:
        project = self._session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project '{project_id}' not found")

        id_ = f"{project_id}:{doc_id}"
        if slug is None:
            slug = _slugify(title)

        doc = ProjectDoc(
            id=id_,
            project_id=project_id,
            doc_id=doc_id,
            title=title,
            slug=slug,
            doc_type=doc_type,
            tier=tier,
            editorial_category=editorial_category,
            status=status,
            audience=audience or [],
            source_paths=source_paths or [],
            content=content,
            version=0,
            generated_at=datetime.now(UTC) if content else None,
            generated_by=generated_by,
        )
        self._session.add(doc)

        if content is not None:
            self._session.flush()
            version = ProjectDocVersion(
                doc_id=id_,
                version=1,
                content=content,
                generated_by=generated_by,
                trigger_reason=trigger_reason or "cli:iw doc-update",
            )
            self._session.add(version)
            doc.version = 1

        self._session.flush()
        return doc

    def update_doc(
        self,
        project_id: str,
        doc_id: str,
        *,
        title: str | None = None,
        status: DocStatus | None = None,
        tier: DocTier | None = None,
        editorial_category: EditorialCategory | None = None,
        audience: list[str] | None = None,
        source_paths: list[str] | None = None,
        content: str | None = None,
        generated_by: str | None = None,
        html_path: str | None = None,
        pdf_path: str | None = None,
        trigger_reason: str | None = None,
    ) -> ProjectDoc:
        id_ = f"{project_id}:{doc_id}"
        doc = self._session.get(ProjectDoc, id_)
        if doc is None:
            raise KeyError(f"Document '{id_}' not found")

        if title is not None:
            doc.title = title
        if status is not None:
            doc.status = status
        if tier is not None:
            doc.tier = tier
        if editorial_category is not None:
            doc.editorial_category = editorial_category
        if audience is not None:
            doc.audience = audience
        if source_paths is not None:
            doc.source_paths = source_paths
        if generated_by is not None:
            doc.generated_by = generated_by
        if html_path is not None:
            doc.html_path = html_path
        if pdf_path is not None:
            doc.pdf_path = pdf_path

        if content is not None:
            current_hash = _content_hash(doc.content) if doc.content else None
            new_hash = _content_hash(content)

            if current_hash != new_hash:
                doc.version += 1
                doc.content = content
                doc.generated_at = datetime.now(UTC)

                version = ProjectDocVersion(
                    doc_id=id_,
                    version=doc.version,
                    content=content,
                    generated_by=generated_by or doc.generated_by,
                    trigger_reason=trigger_reason or "cli:iw doc-update",
                )
                self._session.add(version)

                doc.html_path = None
                doc.pdf_path = None

        self._session.flush()
        return doc

    def upsert_doc(
        self,
        project_id: str,
        doc_id: str,
        **kwargs: Any,
    ) -> tuple[ProjectDoc, bool]:
        existing = self.get_doc(project_id, doc_id)
        if existing is not None:
            return self.update_doc(project_id, doc_id, **kwargs), False
        return self.create_doc(project_id, doc_id, **kwargs), True

    def get_doc(self, project_id: str, doc_id: str) -> ProjectDoc | None:
        id_ = f"{project_id}:{doc_id}"
        return self._session.get(ProjectDoc, id_)

    def list_docs(
        self,
        project_id: str,
        doc_type: DocType | None = None,
        status: DocStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectDoc]:
        query = select(ProjectDoc).where(ProjectDoc.project_id == project_id)
        if doc_type is not None:
            query = query.where(ProjectDoc.doc_type == doc_type)
        if status is not None:
            query = query.where(ProjectDoc.status == status)
        if search:
            query = query.where(
                ProjectDoc.content_search.op("@@")(func.plainto_tsquery("english", search))
            )
            query = query.order_by(
                text(
                    "ts_rank(content_search, plainto_tsquery('english', :search)) DESC"
                ).bindparams(search=search)
            )
        else:
            query = query.order_by(ProjectDoc.updated_at.desc())
        query = query.limit(limit).offset(offset)
        result = self._session.execute(query)
        return list(result.scalars().all())

    def list_doc_versions(self, project_id: str, doc_id: str) -> list[ProjectDocVersion]:
        id_ = f"{project_id}:{doc_id}"
        result = self._session.execute(
            select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == id_)
            .order_by(ProjectDocVersion.version.desc())
        )
        return list(result.scalars().all())

    def get_stale_docs(self, project_id: str, threshold_hours: int = 24) -> list[ProjectDoc]:
        now = datetime.now(UTC)
        result = self._session.execute(
            select(ProjectDoc)
            .where(ProjectDoc.project_id == project_id)
            .where(ProjectDoc.source_paths != [])
            .where(ProjectDoc.generated_at.is_not(None))
            .where(ProjectDoc.generated_at < now - timedelta(hours=threshold_hours))
            .where(ProjectDoc.status != DocStatus.archived)
        )
        return list(result.scalars().all())

    def delete_doc(self, project_id: str, doc_id: str) -> bool:
        id_ = f"{project_id}:{doc_id}"
        doc = self._session.get(ProjectDoc, id_)
        if doc is None:
            return False
        self._session.delete(doc)
        self._session.flush()
        return True

    def create_doc_job(
        self,
        project_id: str,
        doc_id: str,
        requested_by: str = "user",  # noqa: ARG002
    ) -> DocGenerationJob:
        doc = self.get_doc(project_id, doc_id)
        if doc is None:
            raise KeyError(f"Document '{project_id}:{doc_id}' not found")
        import uuid

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=f"{project_id}:{doc_id}",
            status=JobStatus.queued,
            requested_at=datetime.now(UTC),
        )
        self._session.add(job)
        self._session.flush()
        return job

    def start_doc_job(
        self,
        job_id: str,
        pid: int | None = None,
        skill_used: str | None = None,
    ) -> DocGenerationJob:
        job = self._session.get(DocGenerationJob, job_id)
        if job is None:
            raise ValueError(f"Job '{job_id}' not found")
        if job.status != JobStatus.queued:
            raise ValueError(f"Job '{job_id}' is in status '{job.status.value}', expected 'queued'")
        job.status = JobStatus.running
        job.started_at = datetime.now(UTC)
        job.agent_pid = pid
        job.skill_used = skill_used
        self._session.flush()
        return job

    def complete_doc_job(
        self,
        job_id: str,
        error: str | None = None,
    ) -> DocGenerationJob:
        job = self._session.get(DocGenerationJob, job_id)
        if job is None:
            raise ValueError(f"Job '{job_id}' not found")
        if job.status in (JobStatus.completed, JobStatus.failed):
            return job
        job.completed_at = datetime.now(UTC)
        if error is None:
            job.status = JobStatus.completed
        else:
            job.status = JobStatus.failed
            job.error = error
        if job.started_at is not None:
            job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())
        self._session.flush()
        return job

    def get_running_jobs_count(self, project_id: str) -> int:
        return (
            self._session.query(DocGenerationJob)
            .filter(
                DocGenerationJob.project_id == project_id,
                DocGenerationJob.status == JobStatus.running,
            )
            .count()
        )

    def get_queued_jobs(self, project_id: str, limit: int = 10) -> list[DocGenerationJob]:
        return (
            self._session.query(DocGenerationJob)
            .filter(
                DocGenerationJob.project_id == project_id,
                DocGenerationJob.status == JobStatus.queued,
            )
            .order_by(DocGenerationJob.requested_at.asc())
            .limit(limit)
            .all()
        )

    def get_stalled_jobs(self, timeout_minutes: int = 10) -> list[DocGenerationJob]:
        now = datetime.now(UTC)
        threshold = now - timedelta(minutes=timeout_minutes)
        return (
            self._session.query(DocGenerationJob)
            .filter(
                DocGenerationJob.status == JobStatus.running,
                DocGenerationJob.started_at.isnot(None),
                DocGenerationJob.started_at < threshold,
            )
            .all()
        )

    def get_doc_job(self, job_id: str) -> DocGenerationJob | None:
        return self._session.get(DocGenerationJob, job_id)
