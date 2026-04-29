"""F-00067 S17 fixture: seed callout docs and in-page TOC content.

Seeds docs that contain:
- V3: [!NOTE] and [!WARNING] blockquotes → callout CSS rendering
- V4/V6: A long module doc with 3+ H2/H3 headings → in-page TOC + typography styles
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory

_ORCH_DAEMON_CONTENT = """# Orchestration Daemon

The orchestration daemon is the single-threaded polling loop that drives the
IW AI Core platform. It selects approved batches, provisions git worktrees,
launches LLM agents, and handles fix cycles.

> [!NOTE]
> The daemon is the only component that writes to the git worktree directory.
> All other components interact with worktrees through the daemon's PostgreSQL
> state machine.

## Responsibilities

- Poll `work_items` every 60 seconds for approved batches
- Provision one git worktree per active item
- Launch `opencode` or `claude-code` with the step prompt
- Monitor PID liveness and capture logs
- Squash-merge completed items back to main

> [!WARNING]
> Never run `docker compose up` from a worktree directory. The bootstrap
> compose file must be invoked explicitly with `-f docker-compose.bootstrap.yml`.

## State Machine

The daemon drives each work item through these phases:

| Phase | Description |
|-------|-------------|
| `design` | Awaiting design doc approval |
| `implementing` | Agent is executing in a worktree |
| `review` | Code review steps running |
| `done` | Squash-merged to main |

### Fix Cycles

When a step fails, the daemon enters a fix cycle (up to 5 retries per step).
Each retry:
1. Analyses the failure log for actionable error patterns
2. Generates a revised prompt
3. Re-launches the agent

## Components

### Batch Manager

Per-project batch orchestration. Batches are approved by the user, then
the daemon picks them up and executes items in parallel.

### Step Monitor

Tracks PID liveness and staleness. If an agent process dies without
writing `step-done`, the monitor detects this on the next poll and marks
the step as failed.

> [!TIP]
> Set `IW_CORE_STALL_THRESHOLD` in `.env` to adjust how long the daemon
> waits before flagging a running step as stalled.

## Configuration

The daemon reads from `orch/config.py` which loads `.env` variables:
- `IW_CORE_POLL_INTERVAL` — poll frequency in seconds (default 60)
- `IW_CORE_STALL_THRESHOLD` — stall detection threshold in seconds
- `IW_CORE_DB_*` — database connection parameters

> [!IMPORTANT]
> The daemon refuses to launch worktrees if `.iw/` is not listed in the
> project's `.gitignore`. This prevents the daemon from accidentally
> committing agent work byproducts to the main branch.
"""

_DASHBOARD_CONTENT = """# FastAPI Dashboard

The dashboard is a FastAPI + Jinja2 + htmx application providing real-time
visibility into the IW AI Core orchestration platform.

> [!NOTE]
> The dashboard is read-heavy and write-light. All mutations go through
> htmx endpoints that write to the shared PostgreSQL DB.

## Architecture

The dashboard is a single FastAPI application with multiple routers:

- `/project/{id}/` — per-project home
- `/project/{id}/code` — code understanding (RAG)
- `/project/{id}/docs` — documentation catalog
- `/project/{id}/tests` — test runner UI

### Request Lifecycle

1. Request hits `dashboard/app.py` factory
2. Router validates project ownership
3. Business logic delegates to `orch/` layer
4. Jinja2 template renders response with htmx partials

## Pages

### Project Home

Active items, daemon health, quick-action buttons.

### Work Item Detail

Tabs for overview, design doc, reports, artifacts, logs, fix cycles.

### Batch View

Parallel execution timeline with per-item status chips.

### Code View

Architecture map, module docs, symbol explainer, streaming Q&A.

> [!WARNING]
> The Code Q&A feature requires a running Ollama instance. If Ollama
> is unreachable, the QA endpoint returns 503 with a descriptive message.

## Styling

Tailwind CSS with a pre-built `dashboard/static/styles.css`.
Regenerate with `make css` after editing templates.

### Typography

Document pages (`docs_detail.html`) style headings:
- H1: font-weight 700, bottom border
- H2: font-weight 600, border-bottom, distinct from H1
- H3: font-weight 600, muted color

## API Design

htmx endpoints return HTML fragments. JSON endpoints (for JS clients) are
prefixed with `/api/`.
"""


def seed(db: Session) -> None:
    project_id = "iw-ai-core"

    from orch.db.models import ProjectDoc

    docs_to_seed = [
        {
            "doc_id": "module-orch-daemon",
            "title": "Orchestration Daemon",
            "slug": f"{project_id}-module-orch-daemon",
            "content": _ORCH_DAEMON_CONTENT,
        },
        {
            "doc_id": "module-dashboard",
            "title": "FastAPI Dashboard",
            "slug": f"{project_id}-module-dashboard",
            "content": _DASHBOARD_CONTENT,
        },
    ]

    for doc_data in docs_to_seed:
        pk = f"{project_id}:{doc_data['doc_id']}"
        existing = db.get(ProjectDoc, pk)
        if existing is None:
            db.add(
                ProjectDoc(
                    id=pk,
                    project_id=project_id,
                    doc_id=doc_data["doc_id"],
                    title=doc_data["title"],
                    slug=doc_data["slug"],
                    doc_type=DocType.module,
                    tier=DocTier.fully_automated,
                    editorial_category=EditorialCategory.technical,
                    status=DocStatus.published,
                    content=doc_data["content"],
                    version=1,
                )
            )
        else:
            existing.content = doc_data["content"]

    db.flush()
