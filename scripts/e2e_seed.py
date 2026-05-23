"""E2E seed script — insert the minimum data needed for browser verification.

Idempotent: re-running the script on an already-seeded DB is a no-op.

Writes:
  - Project 'iw-ai-core' with code_understanding.ollama_url pointing at the
    in-stack Ollama stub (resolved via $IW_E2E_OLLAMA_URL, falls back to
    http://e2e-ollama:11434 inside the compose network).
  - ProjectDoc 'architecture-map' (Level-1) with a Components section that
    lists two modules — 'orch/daemon' and 'dashboard/' — so the chat
    panel's module navigation has something to click.
  - ProjectDoc entries for each module (Level-2) so module-detail views
    render non-empty.

The Level-1 markdown mirrors the shape expected by orch/rag/parser.py
(backtick-with-description rows), matching what integration tests use
(see tests/integration/test_code_module_routes.py:42).

## Per-item fixtures

After the central seed runs, this script discovers and executes per-item
fixture files matching ``ai-dev/{active,archive}/<item>/e2e_fixtures/*.py``.
Each fixture file must export a ``seed(db: Session) -> None`` function.
Files within a directory load in lexical order (use numeric prefixes:
``001_workflow.py``, ``002_runs.py``).

Fixtures are how a work item that depends on historical data declares the
DB rows its browser verification needs. The mechanism solves the recurring
QvBrowser failure where verifications expect data the fresh E2E DB does
not contain.

### Insert-order gotcha for fixture authors

If your fixture adds a parent row and a child row that references it via
foreign key, SQLAlchemy's unit-of-work will sort the INSERTs **only when
the ORM has a ``relationship()`` between the two mappers** — a bare
``ForeignKeyConstraint`` in ``__table_args__`` is not enough. Without that
relationship, the child INSERT can race ahead of the parent and you get a
``ForeignKeyViolation`` at flush time. ``BatchItem``→``WorkItem`` and
``BatchItem``→``Batch`` are wired this way in ``orch/db/models.py``;
when you add a new model, either declare the matching ``relationship()``
on the child mapper or insert an explicit ``db.flush()`` between the
parent ``add()`` and the child ``add()`` in your fixture.

``tests/integration/test_e2e_seed.py`` runs this script end-to-end
against a fresh schema and is the regression net for fixture authoring.

Run with:  uv run python scripts/e2e_seed.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    Project,
    ProjectDoc,
    WorkItem,
    WorkItemType,
)
from orch.db.session import get_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"

LEVEL1_CONTENT = """# IW AI Core — Architecture Map

The IW AI Core platform orchestrates AI-assisted development workflows across
projects. The system is organised around a polling daemon, a web dashboard,
and a CLI bridge.

## Components

- `orch/daemon/` -- Orchestration Daemon: polls the database, launches agent
  worktrees, and drives the fix-cycle state machine
- `dashboard/` -- FastAPI Dashboard: real-time visibility and manual controls
  for the orchestration platform, served at port 9900
- `orch/rag/` -- Code Understanding: LanceDB indexing, module-gen, symbol-gen,
  and RAG Q&A with work-item-aware citations

## Data Flow

The daemon reads approved batches from PostgreSQL and launches agents in
isolated git worktrees. Progress is streamed to the dashboard via SSE.
"""

# Module slug derivation: path.strip("/").replace("/", "-").lower()
# e.g.  "orch/daemon/" → "orch-daemon",  "orch/rag/" → "orch-rag"
# Per-item fixtures that seed diagram docs MUST use "diagram-module-{slug}"
# as the doc_id so the /modules/{slug}/diagram endpoint resolves them.
MODULE_DOCS: list[dict[str, str]] = [
    {
        "path": "orch/daemon",
        "slug": "orch-daemon",
        "title": "Orchestration Daemon",
        "content": (
            "# Orchestration Daemon\n\n"
            "The orchestration daemon is the single-threaded polling loop that\n"
            "drives the platform. It selects approved batches, provisions git\n"
            "worktrees, launches LLM agents, and handles fix cycles.\n\n"
            "## Responsibilities\n\n"
            "- Poll `work_items` every 60s for approved batches\n"
            "- Provision one git worktree per active item\n"
            "- Launch `opencode` or `claude-code` with the step prompt\n"
            "- Monitor PID liveness and capture logs\n"
            "- Squash-merge completed items back to main\n"
        ),
    },
    {
        "path": "dashboard",
        "slug": "dashboard",
        "title": "FastAPI Dashboard",
        "content": (
            "# FastAPI Dashboard\n\n"
            "The dashboard is a FastAPI + Jinja2 + htmx application that\n"
            "provides real-time visibility into the orchestration platform.\n\n"
            "## Pages\n\n"
            "- Project home with active items and daemon health\n"
            "- Work item detail with per-step logs and evidence\n"
            "- Batch view with parallel execution timeline\n"
            "- Search across designs, prompts, and reports\n"
        ),
    },
    {
        "path": "orch/rag",
        "slug": "orch-rag",
        "title": "Code Understanding (RAG)",
        "content": (
            "# Code Understanding (RAG)\n\n"
            "The RAG module provides code indexing, module documentation\n"
            "generation, symbol explanation, and streaming Q&A with\n"
            "work-item-aware citations.\n\n"
            "## Components\n\n"
            "- `indexer.py` — file discovery, chunking, embedding via LanceDB\n"
            "- `module_gen.py` — Level-2 per-module doc generation\n"
            "- `qa.py` — streaming RAG Q&A with citations\n"
            "- `parser.py` — architecture map module extraction\n"
        ),
    },
]


def _ollama_url() -> str:
    return os.environ.get("IW_E2E_OLLAMA_URL", "http://e2e-ollama:11434")


def _seed_project(db: Session) -> None:
    existing = db.get(Project, PROJECT_ID)
    config = {
        "code_understanding": {
            "provider": "local",
            "index_tier": "fast",
            "ollama_url": _ollama_url(),
        }
    }
    if existing is None:
        db.add(
            Project(
                id=PROJECT_ID,
                display_name="IW AI Core (E2E)",
                repo_root="/app",
                config=config,
                enabled=True,
            )
        )
    else:
        existing.config = {**(existing.config or {}), **config}


def _seed_level1(db: Session) -> None:
    doc_id = "architecture-map"
    pk = f"{PROJECT_ID}:{doc_id}"
    existing = db.get(ProjectDoc, pk)
    if existing is not None:
        existing.content = LEVEL1_CONTENT
        existing.version = (existing.version or 0) + 1
        return
    db.add(
        ProjectDoc(
            id=pk,
            project_id=PROJECT_ID,
            doc_id=doc_id,
            title="IW AI Core — Architecture Map",
            slug=f"{PROJECT_ID}-architecture-map",
            doc_type=DocType.architecture,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            content=LEVEL1_CONTENT,
            version=1,
        )
    )


def _seed_modules(db: Session) -> None:
    for module in MODULE_DOCS:
        doc_id = f"module-{module['slug']}"
        pk = f"{PROJECT_ID}:{doc_id}"
        existing = db.get(ProjectDoc, pk)
        if existing is not None:
            existing.content = module["content"]
            continue
        db.add(
            ProjectDoc(
                id=pk,
                project_id=PROJECT_ID,
                doc_id=doc_id,
                title=module["title"],
                slug=f"{PROJECT_ID}-module-{module['slug']}",
                doc_type=DocType.module,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=module["content"],
                version=1,
            )
        )


def _seed_index_job(db: Session) -> None:
    """Insert a completed CodeIndexJob so /code renders the architecture map.

    The dashboard's code_page route only shows the Level-1 doc when a
    CodeIndexJob with status='completed' exists that references it — without
    this, the page shows the "No code map generated yet" empty state even
    though the ProjectDoc exists.
    """
    # Import locally so the formatter doesn't strip these when the function
    # is added incrementally — keeps the hook's ruff --fix from dropping
    # symbols it can't trace from the top-level imports alone.
    from datetime import UTC, datetime  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415

    from orch.db.models import CodeIndexJob  # noqa: PLC0415

    arch_doc_pk = f"{PROJECT_ID}:architecture-map"
    existing = db.scalar(
        select(CodeIndexJob).where(
            CodeIndexJob.project_id == PROJECT_ID,
            CodeIndexJob.status == "completed",
        )
    )
    now = datetime.now(UTC)
    if existing is not None:
        existing.doc_id = arch_doc_pk
        existing.completed_at = now
        return
    db.add(
        CodeIndexJob(
            project_id=PROJECT_ID,
            status="completed",
            provider="local",
            llm_model="stub:latest",
            embed_model="stub:latest",
            index_tier="fast",
            files_discovered=42,
            files_indexed=42,
            chunks_created=100,
            languages_detected=["python"],
            doc_id=arch_doc_pk,
            triggered_at=now,
            completed_at=now,
        )
    )


def _seed_work_items(db: Session) -> None:
    """Insert work items with design_doc_content so the work-item-aware pipeline can function.

    The task instructions require: "the orchestrator seeds at least one project with
    ≥3 work items and their design docs". We create 3 items (Feature, CR, Incident)
    with design_doc_content so AC1, AC2, AC5, AC6, AC7, AC10 work correctly.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    items_data = [
        {
            "id": "F-00055",
            "type": WorkItemType.Feature,
            "title": "Work-item-aware Code Q&A pipeline",
            "status": "completed",
            "phase": "done",
            "design_doc_content": (
                "The work-item-aware Code Q&A pipeline enriches responses with "
                "citations linking to the relevant work items (Features, Change Requests, "
                "Incidents). The feed below the answer shows related items from the project "
                "history. AC1: work-item citation chips, AC2: item detail links, "
                "AC5: history feed, AC6: tone switch, AC7: /findusages, AC10: feed rows."
            ),
            "summary": "Work-item-aware Code Q&A with citations and history feed",
        },
        {
            "id": "CR-00001",
            "type": WorkItemType.ChangeRequest,
            "title": "Ollama stub integration for E2E testing",
            "status": "completed",
            "phase": "done",
            "design_doc_content": (
                "This CR introduces a minimal Ollama API stub (scripts/e2e_ollama_stub.py) "
                "that returns deterministic stub responses for E2E browser verification. "
                "The stub implements GET /, GET /api/tags, POST /api/embeddings, "
                "POST /api/chat, and POST /api/generate endpoints with stub:latest model."
            ),
            "summary": "E2E Ollama stub for browser verification",
        },
        {
            "id": "I-00001",
            "type": WorkItemType.Issue,
            "title": "Streaming response broken in E2E stack",
            "status": "completed",
            "phase": "done",
            "design_doc_content": (
                "The QA endpoint was returning 500 Internal Server Error in the E2E stack "
                "because the dashboard configured an unreachable Ollama URL (e2e-ollama:11434) "
                "that is only accessible inside the docker-compose network. "
                "Fix: ensure the stub server runs and is reachable, and seed work items."
            ),
            "summary": "E2E stack QA endpoint 500 error root cause investigation",
        },
        # S03: approved work item for test_journey_queue_to_merge (Journey 2)
        {
            "id": "F-E2E-001",
            "type": WorkItemType.Feature,
            "title": "E2E queue-to-merge smoke item",
            "status": "approved",
            "phase": "active",
            "design_doc_content": (
                "This item exists to support browser-verification journey tests. "
                "It is in 'approved' status so the Queue page shows a batch-creation "
                "action, enabling the queue-to-merge smoke journey."
            ),
            "summary": "E2E smoke — approved item for queue-to-merge journey",
        },
    ]

    now = datetime.now(UTC)
    for item_data in items_data:
        existing = db.get(WorkItem, (PROJECT_ID, item_data["id"]))
        if existing is not None:
            existing.design_doc_content = item_data["design_doc_content"]
            existing.summary = item_data["summary"]
            existing.status = item_data["status"]
            existing.phase = item_data["phase"]
            continue
        db.add(
            WorkItem(
                project_id=PROJECT_ID,
                id=item_data["id"],
                type=item_data["type"],
                title=item_data["title"],
                status=item_data["status"],
                phase=item_data["phase"],
                design_doc_content=item_data["design_doc_content"],
                summary=item_data["summary"],
                created_at=now,
            )
        )

    # S03: Seed a second work item in 'approved' state for Journey 5 (Jobs filters).
    # The Jobs page shows at least 2–3 different job types: code_index, doc_generation,
    # and research_draft jobs. The existing _seed_index_job already creates one
    # completed CodeIndexJob. We add one more approved item so the queue is non-empty.
    approved_item_id = "CR-E2E-SEED"
    if db.get(WorkItem, (PROJECT_ID, approved_item_id)) is None:
        db.add(
            WorkItem(
                project_id=PROJECT_ID,
                id=approved_item_id,
                type=WorkItemType.ChangeRequest,
                title="E2E jobs-filter seed item",
                status="approved",
                phase="active",
                design_doc_content=(
                    "Approved item for E2E jobs-filter journey — provides "
                    "an approved queue entry for testing multi-select filters."
                ),
                summary="E2E seed for Jobs filter journey",
                created_at=now,
            )
        )


def _repo_root() -> Path:
    """Return the repository root (the parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def _discover_fixture_files(repo_root: Path) -> list[Path]:
    """Find all per-item fixture files in lexical order.

    Looks under both ``ai-dev/active`` and ``ai-dev/archive`` so a verifying
    item can declare data it needs from any other item (active or archived).
    Returns an empty list if no ``ai-dev`` directory exists (e.g. fresh
    project with no work items yet).
    """
    fixtures: list[Path] = []
    for parent in ("active", "archive"):
        base = repo_root / "ai-dev" / parent
        if not base.exists():
            continue
        # */e2e_fixtures/*.py — sorted so file order is deterministic
        for fixture_file in sorted(base.glob("*/e2e_fixtures/*.py")):
            if fixture_file.name.startswith("_"):
                continue  # skip __init__.py and private modules
            fixtures.append(fixture_file)
    return fixtures


def _run_fixture(fixture_path: Path, db: Session) -> None:
    """Load a fixture file and call its ``seed(db)`` function.

    Raises if the fixture has no ``seed`` callable or if ``seed(db)`` raises —
    fixtures must opt out via guard rather than swallow errors, otherwise
    silent partial seeds reintroduce the empty-DB QvBrowser failure class.
    """
    module_name = f"e2e_fixture_{fixture_path.parent.parent.name}_{fixture_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, fixture_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load fixture spec for {fixture_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    seed_fn = getattr(module, "seed", None)
    if seed_fn is None or not callable(seed_fn):
        raise RuntimeError(f"Fixture {fixture_path} has no callable seed(db: Session) -> None")
    seed_fn(db)


def _seed_per_item_fixtures(db: Session) -> int:
    """Discover and run all per-item fixture files. Returns count run."""
    fixtures = _discover_fixture_files(_repo_root())
    for fixture_path in fixtures:
        sys.stdout.write(f"e2e_seed: running fixture {fixture_path.relative_to(_repo_root())}\n")
        sys.stdout.flush()
        _run_fixture(fixture_path, db)
        db.flush()
    return len(fixtures)


_E2E_SEED_GUARDRAIL_EXIT_CODE = 2


def _check_production_guardrail() -> None:
    """Fail-fast guardrail: refuse to run against a pinned production DB without IW_E2E_SEED=1.

    If IW_CORE_EXPECTED_INSTANCE_ID is set (indicating a production-like target)
    and IW_E2E_SEED is NOT set, exit immediately with code 2 before opening any
    session. This prevents accidental corruption of production data when the
    script is run from a host whose .env points at the live orchestration DB.

    Bootstrap mode (IW_CORE_EXPECTED_INSTANCE_ID unset) is always allowed —
    a fresh install has no instance ID and cannot be misidentified as prod.
    """
    from orch.db.identity import get_expected_instance_id

    expected_id = get_expected_instance_id()
    if expected_id is None:
        return
    if os.environ.get("IW_E2E_SEED", "").strip():
        return
    sys.stderr.write(
        "e2e_seed: ERROR: IW_CORE_EXPECTED_INSTANCE_ID is set but IW_E2E_SEED is not.\n"
        "  This script targets the E2E database only. Running it against the\n"
        "  production orchestration DB (port 5433) would corrupt production data.\n"
        "  To run against the E2E stack, set IW_E2E_SEED=1 in the environment.\n"
        "  To run on a fresh bootstrap (no production DB configured), unset\n"
        "  IW_CORE_EXPECTED_INSTANCE_ID and re-run.\n"
    )
    sys.stderr.flush()
    sys.exit(_E2E_SEED_GUARDRAIL_EXIT_CODE)


def seed() -> None:
    _check_production_guardrail()
    with get_session() as db:
        _seed_project(db)
        db.flush()
        _seed_level1(db)
        _seed_modules(db)
        db.flush()
        _seed_index_job(db)
        db.flush()
        _seed_work_items(db)
        db.flush()
        fixtures_run = _seed_per_item_fixtures(db)
        db.commit()
    sys.stdout.write(
        f"e2e_seed: project {PROJECT_ID} + {len(MODULE_DOCS)} modules + index job "
        f"+ work items + {fixtures_run} per-item fixture(s)\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        sys.stderr.write(f"e2e_seed: failed: {exc}\n")
        sys.stderr.flush()
        sys.exit(1)
