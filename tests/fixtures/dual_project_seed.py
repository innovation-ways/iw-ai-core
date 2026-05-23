"""Dual-project seeding helper for the cross-project isolation matrix (CR-00074).

``seed_two_projects`` creates two ``Project`` rows (A and B), each seeded with
the full set of project-scoped entities — a ``WorkItem``, a ``Batch``, an
architecture ``ProjectDoc``, a research ``ProjectDoc``, a ``CodeIndexJob`` and a
``DocGenerationJob`` — with **guaranteed-distinct identifiers** between the two
projects so isolation assertions can check that none of project A's identifiers
appear in project B's project-scoped responses (and vice versa).

Every work item and architecture/research doc embeds ``SHARED_SEARCH_KEYWORD``
in its full-text-searchable body so the FTS-backed surfaces (``iw search``, the
global ``/api/docs/search`` route) have real data to match.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchStatus,
    CodeIndexJob,
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# A made-up token present in BOTH projects' work-item bodies AND doc bodies.
# Searching for it must return only the *requested* project's rows when scoped,
# and both projects' rows when queried through a global aggregation surface.
SHARED_SEARCH_KEYWORD = "crossprojisolationseed"


@dataclass(frozen=True)
class ProjectIds:
    """The distinguishable identifiers of one project's seeded entities."""

    work_item_id: str
    work_item_title: str
    batch_id: str
    doc_id: str
    doc_inner_id: str
    doc_title: str
    doc_slug: str
    research_doc_id: str
    research_inner_id: str
    research_title: str
    research_slug: str
    code_index_job_id: str
    doc_generation_job_id: str

    def distinguishing_identifiers(self) -> tuple[str, ...]:
        """Strings that uniquely identify *this* project's seeded data.

        None of these may appear in the *other* project's project-scoped
        response — that absence is exactly what the isolation matrix asserts.
        Every value is an explicitly-chosen, project-distinctive string, never
        UI chrome (project display names / project ids are deliberately
        excluded because the global navigation legitimately lists every
        project).
        """
        return (
            self.work_item_id,
            self.work_item_title,
            self.batch_id,
            self.doc_title,
            self.doc_slug,
            self.research_title,
            self.research_slug,
            self.code_index_job_id,
            self.doc_generation_job_id,
        )


@dataclass(frozen=True)
class TwoProjects:
    """The two seeded projects and their identifier sets."""

    proj_a: Project
    proj_b: Project
    proj_a_ids: ProjectIds
    proj_b_ids: ProjectIds


def _seed_one_project(
    session: Session,
    project: Project,
    label: str,
    *,
    work_item_type: WorkItemType,
) -> ProjectIds:
    """Seed one project with the full project-scoped entity set.

    ``label`` ("Alpha" / "Beta") drives every identifier so the two projects'
    rows never collide. Returns the project's ``ProjectIds``.
    """
    now = datetime.now(UTC)
    pid = project.id
    upper = label.upper()
    lower = label.lower()

    # --- WorkItem (visible on the project queue + iw search) ---
    work_item_id = f"WI-{upper}-001"
    work_item_title = f"Work Item {label}"
    session.add(
        WorkItem(
            project_id=pid,
            id=work_item_id,
            type=work_item_type,
            title=work_item_title,
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            design_doc_content=(
                f"# {work_item_title}\n\n"
                f"Cross-project isolation fixture body for project {pid}. "
                f"Full-text search token: {SHARED_SEARCH_KEYWORD}."
            ),
        )
    )

    # --- Batch ---
    batch_id = f"BATCH-{upper}-001"
    session.add(
        Batch(
            id=batch_id,
            project_id=pid,
            status=BatchStatus.approved,
            max_parallel=2,
            cli_tool="opencode",
            auto_publish=False,
            created_at=now - timedelta(hours=2),
        )
    )

    # --- Architecture ProjectDoc (visible on /docs + global doc search) ---
    doc_inner_id = f"doc-{lower}-001"
    doc_id = f"{pid}:{doc_inner_id}"
    doc_title = f"Architecture: Project {label}"
    doc_slug = f"architecture-{lower}"
    session.add(
        ProjectDoc(
            id=doc_id,
            project_id=pid,
            doc_id=doc_inner_id,
            title=doc_title,
            slug=doc_slug,
            doc_type=DocType.architecture,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            audience=[],
            source_paths=[],
            content=(
                f"# {doc_title}\n\n"
                f"Architecture content for project {pid}. "
                f"Full-text search token: {SHARED_SEARCH_KEYWORD}."
            ),
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=1),
        )
    )

    # --- Research ProjectDoc (visible on /research) ---
    research_inner_id = f"research-{lower}-001"
    research_doc_id = f"{pid}:{research_inner_id}"
    research_title = f"Research: {label} Findings"
    research_slug = f"research-{lower}-findings"
    session.add(
        ProjectDoc(
            id=research_doc_id,
            project_id=pid,
            doc_id=research_inner_id,
            title=research_title,
            slug=research_slug,
            doc_type=DocType.research,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            audience=[],
            source_paths=[],
            content=f"# {research_title}\n\nResearch body for project {pid}.",
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=1),
        )
    )
    session.flush()

    # --- CodeIndexJob (code-index row; before_insert allocates public_id) ---
    cij = CodeIndexJob(
        id=f"cij-{lower}-001",
        project_id=pid,
        status="completed",
        provider="local",
        llm_model="gemma4:31b",
        embed_model="manutic/nomic-embed-code",
        index_tier="balanced",
        files_discovered=10,
        files_indexed=9,
        chunks_created=120,
        languages_detected=["Python"],
        errors=[],
        triggered_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
    )
    session.add(cij)
    session.flush()  # before_insert → allocates the CM-NNNNN public_id

    # --- DocGenerationJob (job-like row) ---
    dgj = DocGenerationJob(
        id=f"dgj-{lower}-001",
        project_id=pid,
        doc_id=doc_id,
        status=JobStatus.completed,
        requested_at=now - timedelta(hours=3),
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
        skill_used="skill:iw-doc-generator",
        trigger_reason="manual",
        duration_seconds=3600,
        created_at=now - timedelta(hours=3),
    )
    session.add(dgj)
    session.flush()

    return ProjectIds(
        work_item_id=work_item_id,
        work_item_title=work_item_title,
        batch_id=batch_id,
        doc_id=doc_id,
        doc_inner_id=doc_inner_id,
        doc_title=doc_title,
        doc_slug=doc_slug,
        research_doc_id=research_doc_id,
        research_inner_id=research_inner_id,
        research_title=research_title,
        research_slug=research_slug,
        code_index_job_id=cij.public_id or cij.id,
        doc_generation_job_id=dgj.public_id or dgj.id,
    )


def seed_two_projects(session: Session, proj_a: Project | None = None) -> TwoProjects:
    """Create two projects and seed each with the full project-scoped entity set.

    When *proj_a* is provided (e.g. the existing ``test_project`` fixture row),
    it is reused as project A — the helper only adds project B alongside it.
    When *proj_a* is ``None`` the helper creates project A itself.

    All identifiers are guaranteed distinct between the two projects so
    isolation assertions can safely check that project A's identifiers are
    absent from project B's project-scoped responses.
    """
    if proj_a is None:
        proj_a = Project(
            id="test-proj",
            display_name="Test Project",
            repo_root="/repos/test",
            config={},
        )
        session.add(proj_a)

    proj_b = Project(
        id="second-proj",
        display_name="Second Project",
        repo_root="/repos/second",
        config={},
    )
    session.add(proj_b)
    session.flush()

    ids_a = _seed_one_project(session, proj_a, "Alpha", work_item_type=WorkItemType.Feature)
    ids_b = _seed_one_project(session, proj_b, "Beta", work_item_type=WorkItemType.Issue)
    session.flush()

    return TwoProjects(proj_a=proj_a, proj_b=proj_b, proj_a_ids=ids_a, proj_b_ids=ids_b)
