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

Run with:  uv run python scripts/e2e_seed.py
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    Project,
    ProjectDoc,
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

## Data Flow

The daemon reads approved batches from PostgreSQL and launches agents in
isolated git worktrees. Progress is streamed to the dashboard via SSE.
"""

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
            doc_type=DocType.research,
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
                slug=f"{PROJECT_ID}-{module['slug']}",
                doc_type=DocType.research,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=module["content"],
                version=1,
            )
        )


def seed() -> None:
    with get_session() as db:
        _seed_project(db)
        db.flush()
        _seed_level1(db)
        _seed_modules(db)
        db.commit()
    sys.stdout.write(
        f"e2e_seed: project {PROJECT_ID} + architecture-map + {len(MODULE_DOCS)} modules\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        sys.stderr.write(f"e2e_seed: failed: {exc}\n")
        sys.stderr.flush()
        sys.exit(1)
