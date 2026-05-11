"""DocService — CRUD operations for ProjectDoc, version snapshots, FTS query."""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import io
import re
import subprocess
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal  # noqa: F401

import httpx
import yaml
from sqlalchemy import func, select, text

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

from orch.db.models import (
    DocGenerationJob,
    DocInstanceGuide,
    DocSectionGuide,
    DocStatus,
    DocTier,
    DocType,
    DocTypeGuide,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
    ProjectDocVersion,
)
from orch.doc_sections import extract_sections, split_by_sections  # noqa: F401

# Type alias defined after all imports so ruff's E402 guard (on the import block
# above) does not incorrectly suppress F401 on this line.
JobOutcome = Literal["completed", "failed_timeout", "failed_process_exited", "failed_agent_error"]


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
        doc_type: DocType | None = None,
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
        if doc_type is not None:
            doc.doc_type = doc_type
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

        section_rows = self.list_section_guides(project_id, doc_id)
        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project_id,
            doc_id=f"{project_id}:{doc_id}",
            status=JobStatus.queued,
            requested_at=datetime.now(UTC),
            trigger_reason=trigger_reason,
            section_guides_snapshot={row.section_name: row.guide_md for row in section_rows}
            if section_rows
            else None,
            guide_snapshot=self._effective_guide(project_id, doc_id, doc.doc_type.value),
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
        *,
        worktree_path: str | Path | None = None,
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

        # ── Observability: agent_output + report ─────────────────────
        project_for_worktree = self._session.get(Project, job.project_id)
        if worktree_path is None and project_for_worktree is not None:
            worktree_path = project_for_worktree.repo_root

        log_path: Path | None = None
        if worktree_path is not None:
            log_path = Path(worktree_path) / "ai-dev" / "logs" / f"doc_job_{job.id}.log"

        log_text = ""
        log_size_bytes = 0
        log_line_count = 0
        if log_path is not None:
            from orch.doc_report import read_log_tail

            log_text, log_size_bytes, log_line_count = read_log_tail(log_path)

        job.agent_output = log_text

        outcome: JobOutcome
        if error is None:
            outcome = "completed"
        elif "timeout" in error.lower():
            outcome = "failed_timeout"
        elif "agent process exited" in error.lower():
            outcome = "failed_process_exited"
        else:
            outcome = "failed_agent_error"

        cli_tool = "opencode"
        command_issued: str | None = None
        if project_for_worktree is not None and project_for_worktree.config:
            cli_tool = project_for_worktree.config.get("cli_tool", "opencode")

        if cli_tool == "opencode":
            command_issued = f'opencode run "/doc-job {job.id}" --dangerously-skip-permissions'
        elif cli_tool == "claude":
            command_issued = f'claude -p "/doc-job {job.id}" --permission-mode bypassPermissions'

        from orch.doc_report import build_execution_report

        job.report = build_execution_report(
            job=job,
            project=project_for_worktree,
            log_text=log_text,
            log_size_bytes=log_size_bytes,
            log_line_count=log_line_count,
            outcome=outcome,
            command_issued=command_issued,
            cli_tool=cli_tool,
        )

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

    def diff_versions(
        self,
        project_id: str,
        doc_id: str,
        version_old: int,
        version_new: int,
    ) -> list[str]:
        id_ = f"{project_id}:{doc_id}"
        result_old = self._session.execute(
            select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == id_)
            .where(ProjectDocVersion.version == version_old)
        )
        version_old_record = result_old.scalar_one_or_none()
        if version_old_record is None:
            raise KeyError(f"Version {version_old} not found for doc '{id_}'")

        result_new = self._session.execute(
            select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == id_)
            .where(ProjectDocVersion.version == version_new)
        )
        version_new_record = result_new.scalar_one_or_none()
        if version_new_record is None:
            raise KeyError(f"Version {version_new} not found for doc '{id_}'")

        if version_old >= version_new:
            raise ValueError("version_old must be less than version_new")

        old_content = version_old_record.content or ""
        new_content = version_new_record.content or ""

        return list(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"v{version_old}",
                tofile=f"v{version_new}",
                n=3,
            )
        )

    def _is_ssrf_blocked(self, url: str) -> bool:
        try:
            parsed = re.match(r"https?://([^/:]+)", url)
            if not parsed:
                return True
            hostname = parsed.group(1)

            if hostname in ("localhost", "::1"):
                return True
            if hostname.startswith("127."):
                return True
            if hostname.endswith((".local", ".internal")):
                return True

            ssrf_blocks = (
                "10.",
                "172.16.",
                "172.17.",
                "172.18.",
                "172.19.",
                "172.20.",
                "172.21.",
                "172.22.",
                "172.23.",
                "172.24.",
                "172.25.",
                "172.26.",
                "172.27.",
                "172.28.",
                "172.29.",
                "172.30.",
                "172.31.",
                "192.168.",
            )
            return any(hostname.startswith(block) for block in ssrf_blocks)
        except Exception:
            return True

    def validate_links(
        self,
        doc: ProjectDoc,
        repo_root: str,
        max_links: int = 20,
    ) -> list[dict[str, str]]:
        pattern = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
        links = [(m.group(1), m.group(2)) for m in pattern.finditer(doc.content or "")]

        broken: list[dict[str, str]] = []

        for _, url in links[:max_links]:
            if url.startswith(("http://", "https://")):
                if self._is_ssrf_blocked(url):
                    broken.append({"url": url, "type": "external", "status": "blocked_ssrf"})
                    continue

                try:
                    response = httpx.head(url, timeout=5, follow_redirects=True)
                    status = response.status_code
                    if 200 <= status < 400:
                        pass
                    elif 400 <= status < 500:
                        broken.append({"url": url, "type": "external", "status": str(status)})
                    else:
                        broken.append(
                            {"url": url, "type": "external", "status": f"transient_{status}"}
                        )
                except httpx.HTTPStatusError as e:
                    broken.append(
                        {"url": url, "type": "external", "status": str(e.response.status_code)}
                    )
                except Exception:
                    broken.append({"url": url, "type": "external", "status": "error"})
            else:
                path = Path(repo_root) / url
                if path.exists():
                    pass
                else:
                    broken.append({"url": url, "type": "internal", "status": "not_found"})

        doc.broken_links = broken if broken else None
        self._session.flush()

        return broken

    def export_bundle(
        self,
        _project_id: str,
        doc_ids: list[str],
        render_html_fn: Callable[[str, ProjectDoc], str],
        render_pdf_fn: Callable[[str], bytes | None],
    ) -> bytes:
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc_id in doc_ids:
                doc = self._session.get(ProjectDoc, doc_id)
                if doc is None or doc.content is None:
                    continue

                slug = doc.slug or doc.doc_id

                html_content = render_html_fn(doc.content, doc)
                pdf_bytes = render_pdf_fn(html_content)

                if len(doc_ids) == 1:
                    zf.writestr(f"{slug}.md", doc.content)
                    zf.writestr(f"{slug}.html", html_content)
                    if pdf_bytes is not None:
                        zf.writestr(f"{slug}.pdf", pdf_bytes)
                    zf.writestr(
                        "_generation_notes.md",
                        f"| Field | Value |\n|---|---|\n"
                        f"| doc_id | {doc.doc_id} |\n"
                        f"| project_id | {doc.project_id} |\n"
                        f"| title | {doc.title} |\n"
                        f"| version | {doc.version} |\n"
                        f"| doc_type | {doc.doc_type.value} |\n"
                        f"| generated_by | {doc.generated_by or ''} |\n"
                        f"| generated_at | {doc.generated_at or ''} |\n"
                        f"| pdf_available | {pdf_bytes is not None} |\n",
                    )
                else:
                    zf.writestr(f"{slug}/{slug}.md", doc.content)
                    zf.writestr(f"{slug}/{slug}.html", html_content)
                    if pdf_bytes is not None:
                        zf.writestr(f"{slug}/{slug}.pdf", pdf_bytes)
                    zf.writestr(
                        f"{slug}/_generation_notes.md",
                        f"| Field | Value |\n|---|---|\n"
                        f"| doc_id | {doc.doc_id} |\n"
                        f"| project_id | {doc.project_id} |\n"
                        f"| title | {doc.title} |\n"
                        f"| version | {doc.version} |\n"
                        f"| doc_type | {doc.doc_type.value} |\n"
                        f"| generated_by | {doc.generated_by or ''} |\n"
                        f"| generated_at | {doc.generated_at or ''} |\n"
                        f"| pdf_available | {pdf_bytes is not None} |\n",
                    )

        buf.seek(0)
        return buf.getvalue()

    def search_docs_global(
        self,
        search: str,
        doc_type: DocType | None = None,
        status: DocStatus | None = None,
        tier: DocTier | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[tuple[ProjectDoc, str]]:
        if not search or not search.strip():
            return []

        query = (
            select(
                ProjectDoc,
                text(
                    "ts_headline('english', content, plainto_tsquery('english', :search), "
                    "'MaxWords=35, MinWords=20, ShortWord=3, MaxFragments=2, "
                    'FragmentDelimiter=" ... "\') AS headline'
                ).bindparams(search=search),
            )
            .join(Project, ProjectDoc.project_id == Project.id)
            .where(ProjectDoc.content_search.op("@@")(func.plainto_tsquery("english", search)))
        )

        if doc_type is not None:
            query = query.where(ProjectDoc.doc_type == doc_type)
        if tier is not None:
            query = query.where(ProjectDoc.tier == tier)
        if project_id is not None:
            query = query.where(ProjectDoc.project_id == project_id)

        if status is None:
            query = query.where(ProjectDoc.status != DocStatus.archived)
        elif status != DocStatus.archived:
            query = query.where(ProjectDoc.status == status)

        query = query.order_by(
            text("ts_rank(content_search, plainto_tsquery('english', :search)) DESC").bindparams(
                search=search
            )
        )
        query = query.limit(limit)

        result = self._session.execute(query)
        rows = result.all()

        return [(row[0], row[1]) for row in rows]

    # -----------------------------------------------------------------------
    # Type Guide
    # -----------------------------------------------------------------------

    def get_type_guide(self, doc_type: str) -> str | None:
        guide = self._session.get(DocTypeGuide, doc_type)
        return guide.guide_md if guide is not None else None

    def save_type_guide(self, doc_type: str, guide_md: str) -> DocTypeGuide:
        guide = self._session.get(DocTypeGuide, doc_type)
        if guide is None:
            guide = DocTypeGuide(doc_type=doc_type, guide_md=guide_md)
            self._session.add(guide)
        else:
            guide.guide_md = guide_md
        self._session.flush()
        return guide

    # -----------------------------------------------------------------------
    # Instance Guide
    # -----------------------------------------------------------------------

    def get_instance_guide(self, project_id: str, doc_id: str) -> str | None:
        full_id = f"{project_id}:{doc_id}"
        guide = self._session.get(DocInstanceGuide, full_id)
        return guide.guide_md if guide is not None else None

    def save_instance_guide(self, project_id: str, doc_id: str, guide_md: str) -> DocInstanceGuide:
        full_id = f"{project_id}:{doc_id}"
        guide = self._session.get(DocInstanceGuide, full_id)
        if guide is None:
            guide = DocInstanceGuide(doc_id=full_id, guide_md=guide_md)
            self._session.add(guide)
        else:
            guide.guide_md = guide_md
        self._session.flush()
        return guide

    def delete_instance_guide(self, project_id: str, doc_id: str) -> bool:
        full_id = f"{project_id}:{doc_id}"
        guide = self._session.get(DocInstanceGuide, full_id)
        if guide is None:
            return False
        self._session.delete(guide)
        self._session.flush()
        return True

    def _effective_guide(self, project_id: str, doc_id: str, doc_type: str) -> str | None:
        instance = self.get_instance_guide(project_id, doc_id)
        if instance is not None:
            return instance
        type_guide = self.get_type_guide(doc_type)
        if type_guide is not None:
            return type_guide
        # Guard: don't re-query _default if doc_type is already "_default"
        if doc_type != "_default":
            default_guide = self.get_type_guide("_default")
            if default_guide is not None:
                return default_guide
        return None

    # -----------------------------------------------------------------------
    # Section Guide
    # -----------------------------------------------------------------------

    def get_section_guide(self, project_id: str, doc_id: str, section_name: str) -> str | None:
        """Return the editorial guide for a specific section, or None if not set."""
        composite_id = f"{project_id}:{doc_id}"
        row = self._session.execute(
            select(DocSectionGuide)
            .where(DocSectionGuide.doc_id == composite_id)
            .where(DocSectionGuide.section_name == section_name)
        ).scalar_one_or_none()
        return row.guide_md if row else None

    def save_section_guide(
        self, project_id: str, doc_id: str, section_name: str, guide_md: str
    ) -> DocSectionGuide:
        """Create or update the section guide for the given (doc, section) pair."""
        composite_id = f"{project_id}:{doc_id}"
        row = self._session.execute(
            select(DocSectionGuide)
            .where(DocSectionGuide.doc_id == composite_id)
            .where(DocSectionGuide.section_name == section_name)
        ).scalar_one_or_none()
        if row is None:
            row = DocSectionGuide(doc_id=composite_id, section_name=section_name, guide_md=guide_md)
            self._session.add(row)
        else:
            row.guide_md = guide_md
        self._session.flush()
        return row

    def delete_section_guide(self, project_id: str, doc_id: str, section_name: str) -> bool:
        """Remove the section guide for a (doc, section) pair. Returns True if deleted."""
        composite_id = f"{project_id}:{doc_id}"
        row = self._session.execute(
            select(DocSectionGuide)
            .where(DocSectionGuide.doc_id == composite_id)
            .where(DocSectionGuide.section_name == section_name)
        ).scalar_one_or_none()
        if row is not None:
            self._session.delete(row)
            self._session.flush()
            return True
        return False

    def list_section_guides(self, project_id: str, doc_id: str) -> list[DocSectionGuide]:
        """Return all section guides for the given document, ordered by section_name."""
        composite_id = f"{project_id}:{doc_id}"
        return list(
            self._session.execute(
                select(DocSectionGuide)
                .where(DocSectionGuide.doc_id == composite_id)
                .order_by(DocSectionGuide.section_name)
            )
            .scalars()
            .all()
        )
