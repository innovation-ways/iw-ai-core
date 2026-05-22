"""Dashboard integration tests — depends on integration db_session fixture.

This file acts as a conftest entry point so that tests/dashboard/ test files
can use the db_session fixture defined in tests/integration/conftest.py.

It also exposes ``seed_contract_test_data`` — a shared, representative-dataset
seed helper used by the CR-00072 contract test layer
(``test_route_contract_sweep.py`` + ``test_schemathesis_contract.py``). The
helper inserts one row in every entity a dashboard route is likely to read
(project, work item + steps, batch + batch item, docs, doc-generation job,
test run, daemon event) so that path parameters can be resolved to real IDs
and route handlers exercise their happy path instead of short-circuiting on a
404.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

# Re-export the integration conftest fixtures so they are visible to pytest
# when collecting tests under tests/dashboard/.
# pytest automatically loads conftest.py from the parent directories,
# but since tests/dashboard/ is not under tests/integration/ we need
# this file to ensure the integration conftest is visible.
# Import fixtures from integration conftest so pytest can discover them
from tests.integration.conftest import (  # noqa: F401
    _db_test_connection,
    _pgtestdb_setup,
    db_engine,
    db_session,
    db_session_factory,
    pg_container,
    test_project,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# CR-00072 — shared contract-sweep seed helper
# ---------------------------------------------------------------------------

#: Deterministic IDs for the seeded contract dataset. Exposed as a dict by
#: ``seed_contract_test_data`` so the route sweep can build a path-parameter
#: substitution map from real values.
CONTRACT_ITEM_ID = "CR-90001"
CONTRACT_BATCH_ID = "B-CR72-001"
CONTRACT_DOC_ID = "cr72-arch-overview"
CONTRACT_RESEARCH_DOC_ID = "cr72-research-note"
CONTRACT_JOB_ID = "dgj-cr72-001"
CONTRACT_STEP_ID = "S01"


def seed_contract_test_data(session: Session, project: Project) -> dict[str, str]:
    """Seed one representative row per dashboard-relevant entity.

    Returns a substitution map ``{param_name: value}`` keyed by the FastAPI
    path-parameter names the dashboard routes use (``project_id``, ``item_id``,
    ``batch_id``, ``doc_id``, ``job_id``, ``step_id``, ``run_id``). The route
    sweep formats parametrized route paths with these values.

    Idempotent within a transaction: the caller owns the ``db_session`` and is
    expected to ``commit()`` afterwards.
    """
    from orch.db.models import (
        Batch,
        BatchItem,
        BatchStatus,
        DaemonEvent,
        DocGenerationJob,
        DocStatus,
        DocTier,
        DocType,
        EditorialCategory,
        JobStatus,
        ProjectDoc,
        StepStatus,
        StepType,
        TestRun,
        WorkflowStep,
        WorkItem,
    )

    now = datetime.now(UTC)
    project_id = project.id

    # --- Work item + workflow steps -------------------------------------
    work_item = WorkItem(
        project_id=project_id,
        id=CONTRACT_ITEM_ID,
        type="ChangeRequest",
        title="CR-00072 contract sweep seed work item",
        status="completed",
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(work_item)

    session.add(
        WorkflowStep(
            project_id=project_id,
            work_item_id=CONTRACT_ITEM_ID,
            step_number=1,
            step_id=CONTRACT_STEP_ID,
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
    )
    session.add(
        WorkflowStep(
            project_id=project_id,
            work_item_id=CONTRACT_ITEM_ID,
            step_number=2,
            step_id="S02",
            agent_label="CodeReview",
            step_type=StepType.code_review,
            status=StepStatus.completed,
        )
    )

    # --- Batch + batch item --------------------------------------------
    session.add(
        Batch(
            project_id=project_id,
            id=CONTRACT_BATCH_ID,
            status=BatchStatus.completed,
            created_at=now - timedelta(hours=3),
            completed_at=now - timedelta(hours=1),
        )
    )
    session.add(
        BatchItem(
            project_id=project_id,
            batch_id=CONTRACT_BATCH_ID,
            work_item_id=CONTRACT_ITEM_ID,
            status="completed",
            execution_group=0,
        )
    )

    # --- Catalogue doc + research doc ----------------------------------
    session.add(
        ProjectDoc(
            id=f"{project_id}:{CONTRACT_DOC_ID}",
            project_id=project_id,
            doc_id=CONTRACT_DOC_ID,
            title="CR-00072 Architecture Overview",
            slug="cr72-arch-overview",
            doc_type=DocType.architecture,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            audience=[],
            source_paths=[],
            content="# CR-00072 seed doc\n\nRepresentative content for the route sweep.",
            version=1,
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=1),
        )
    )
    session.add(
        ProjectDoc(
            id=f"{project_id}:{CONTRACT_RESEARCH_DOC_ID}",
            project_id=project_id,
            doc_id=CONTRACT_RESEARCH_DOC_ID,
            title="CR-00072 Research Note",
            slug="cr72-research-note",
            doc_type=DocType.research,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            audience=[],
            source_paths=[],
            content="# CR-00072 research note\n\nRepresentative research content.",
            version=1,
            generated_at=now - timedelta(hours=2),
            generated_by="skill:iw-research",
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=1),
        )
    )
    # Flush the docs before the doc-generation job — DocGenerationJob.doc_id is
    # an FK into project_docs.id and must exist before the job INSERT.
    session.flush()

    # --- Doc-generation job --------------------------------------------
    session.add(
        DocGenerationJob(
            id=CONTRACT_JOB_ID,
            project_id=project_id,
            doc_id=f"{project_id}:{CONTRACT_DOC_ID}",
            status=JobStatus.completed,
            requested_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=1),
        )
    )

    # --- Test run -------------------------------------------------------
    # status / run_type / created_at carry server defaults — omitted so the
    # DB fills them (the test_run_status PG enum is applied by migrations).
    test_run = TestRun(
        project_id=project_id,
        category="unit",
        command="uv run pytest tests/unit/ -q",
    )
    session.add(test_run)

    # --- Daemon event (running views / auto-merge feed) ----------------
    session.add(
        DaemonEvent(
            project_id=project_id,
            event_type="batch_completed",
            entity_id=CONTRACT_BATCH_ID,
            message="CR-00072 seed event",
            event_metadata={},
        )
    )

    session.flush()

    return {
        "project_id": project_id,
        "item_id": CONTRACT_ITEM_ID,
        "batch_id": CONTRACT_BATCH_ID,
        "doc_id": CONTRACT_DOC_ID,
        "job_id": CONTRACT_JOB_ID,
        "step_id": CONTRACT_STEP_ID,
        "run_id": str(test_run.id),
    }
