"""DocService — CRUD operations for ProjectDoc, version snapshots, FTS query."""

from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import yaml
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


def _path_matches_pattern(source_pattern: str, changed_paths: list[str]) -> bool:

    for cp in changed_paths:
        if fnmatch.fnmatch(cp, source_pattern):
            return True
        if fnmatch.fnmatch(source_pattern, cp):
            return True
        if "/" in source_pattern and "/" in cp:
            sp_parts = source_pattern.split("/")
            cp_parts = cp.split("/")
            if len(sp_parts) == len(cp_parts) and all(
                fnmatch.fnmatch(sp_parts[i], cp_parts[i])
                if "*" in sp_parts[i] or "?" in sp_parts[i]
                else sp_parts[i] == cp_parts[i]
                for i in range(len(sp_parts))
            ):
                return True
    return False


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

    def get_stale_docs(
        self,
        project_id: str,
        repo_root: str,
        threshold_hours: int = 24,  # noqa: ARG002
    ) -> list[tuple[ProjectDoc, str, datetime]]:
        docs = (
            self._session.query(ProjectDoc)
            .filter(
                ProjectDoc.project_id == project_id,
                ProjectDoc.source_paths != [],
                ProjectDoc.generated_at.is_not(None),
                ProjectDoc.status != DocStatus.archived,
            )
            .all()
        )
        stale: list[tuple[ProjectDoc, str, datetime]] = []
        for doc in docs:
            for path in doc.source_paths:
                result = subprocess.run(
                    ["git", "log", "-1", "--format=%ct", "--", path],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    continue
                if not result.stdout.strip():
                    continue
                try:
                    mtime_epoch = int(result.stdout.strip())
                except ValueError:
                    continue
                mtime = datetime.fromtimestamp(mtime_epoch, tz=UTC)
                if doc.generated_at is not None and mtime > doc.generated_at:
                    stale.append((doc, path, mtime))
                    break
        return stale

    def find_docs_by_source_path(
        self,
        project_id: str,
        changed_paths: list[str],
    ) -> list[ProjectDoc]:
        docs = (
            self._session.query(ProjectDoc)
            .filter(
                ProjectDoc.project_id == project_id,
                ProjectDoc.status != DocStatus.archived,
            )
            .all()
        )
        matched: list[ProjectDoc] = []
        for doc in docs:
            if not doc.source_paths:
                continue
            for sp in doc.source_paths:
                if _path_matches_pattern(sp, changed_paths):
                    matched.append(doc)
                    break
        return matched

    def lint_doc_content(
        self,
        content: str,
        editorial_category: EditorialCategory,
        forbidden_phrases: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        if forbidden_phrases is None:
            forbidden_phrases = [
                "cutting-edge",
                "state-of-the-art",
                "revolutionary",
                "game-changing",
                "leverage",
                "synergy",
                "robust solution",
            ]

        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            try:
                yaml.safe_load(fm_match.group(1))
            except yaml.YAMLError:
                warnings.append(
                    {
                        "rule": "frontmatter_parseable",
                        "message": "Frontmatter is not valid YAML",
                        "section": None,
                    }
                )
        else:
            warnings.append(
                {
                    "rule": "frontmatter_required",
                    "message": "Document must start with YAML frontmatter",
                    "section": None,
                }
            )

        for phrase in forbidden_phrases:
            if phrase.lower() in content.lower():
                warnings.append(
                    {
                        "rule": "forbidden_phrase",
                        "message": f"Forbidden phrase: '{phrase}'",
                        "section": None,
                    }
                )

        cat_str = (
            editorial_category.value
            if hasattr(editorial_category, "value")
            else str(editorial_category)
        )

        if cat_str == "technical":
            if "## Purpose" not in content:
                warnings.append(
                    {
                        "rule": "required_section_purpose",
                        "message": "Missing '## Purpose' section",
                        "section": "Purpose",
                    }
                )
            if "## Architecture" not in content:
                warnings.append(
                    {
                        "rule": "required_section_architecture",
                        "message": "Missing '## Architecture' section",
                        "section": "Architecture",
                    }
                )
            if not re.search(r"```", content):
                warnings.append(
                    {
                        "rule": "has_code_block",
                        "message": "Document must contain at least one fenced code block",
                        "section": None,
                    }
                )
        elif cat_str == "functional":
            if "## Overview" not in content:
                warnings.append(
                    {
                        "rule": "required_section_overview",
                        "message": "Missing '## Overview' section",
                        "section": "Overview",
                    }
                )
            if "## Key Capabilities" not in content:
                warnings.append(
                    {
                        "rule": "required_section_capabilities",
                        "message": "Missing '## Key Capabilities' section",
                        "section": "Key Capabilities",
                    }
                )
        elif cat_str == "guide":
            if "## Prerequisites" not in content:
                warnings.append(
                    {
                        "rule": "required_section_prerequisites",
                        "message": "Missing '## Prerequisites' section",
                        "section": "Prerequisites",
                    }
                )
            if "## Steps" not in content:
                warnings.append(
                    {
                        "rule": "required_section_steps",
                        "message": "Missing '## Steps' section",
                        "section": "Steps",
                    }
                )

        return warnings

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
        trigger_reason: str | None = None,
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
            trigger_reason=trigger_reason,
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

        if error is None and job.doc_id is not None:
            doc = self._session.get(ProjectDoc, job.doc_id)
            if doc is not None and doc.content is not None:
                project = self._session.get(Project, job.project_id)
                forbidden = None
                if project and project.config:
                    forbidden = project.config.get("doc_generation", {}).get("forbidden_phrases")
                warnings = self.lint_doc_content(doc.content, doc.editorial_category, forbidden)
                if warnings:
                    job.lint_warnings = warnings

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
