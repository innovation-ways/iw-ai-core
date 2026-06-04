# IW AI Core — Phase 2 Detailed Design

**Project**: IW AI Core (Innovation Ways AI Core Platform)
**Repo**: `iw-ai-core`
**Author**: Sergio G. + Claude
**Created**: 2026-03-29
**Status**: Design Draft
**Last updated**: 2026-03-31 (planning session — decisions on DB centralization, workflow definition, skill registration)

---

## 1. Vision & Motivation

### Background

While building InnoForge, the AI agent workflow system evolved organically from simple shell scripts into a production-grade Python daemon + bash step executor + web dashboard. It manages batches of work items (features, incidents, change requests) across isolated git worktrees with automated code review, fix cycles, quality validation, and sequential merging.

The system now handles 130+ incidents, 140+ features, 35+ change requests, and 50+ batches — but it's tightly coupled to the InnoForge codebase. Every script, skill, agent spec, and dashboard lives inside InnoForge's repository.

### Goal

Extract the AI orchestration layer into a standalone, multi-project platform called **IW AI Core**. A single developer logs into one dashboard, sees all active projects, selects a project, and manages its full AI workflow lifecycle — designing, executing, reviewing, and shipping work items — exactly as today but across any number of projects.

### Key Principles

1. **Pragmatic** — Single developer, single machine. No over-engineering.
2. **Preserve what works** — Keep all proven resilience patterns (polling, manifest-as-truth, worktree isolation, short-lived LLM sessions, deterministic bash).
3. **Incremental migration** — InnoForge keeps running on Phase 1 until Phase 2 is validated.
4. **Database-backed** — Replace file-based tracking with PostgreSQL for queryability and analytics.
5. **Files for content, DB for state** — LLM agents still read/write files. The DB stores metadata, status, and analytics.

---

## 2. System Architecture

### 2.1. Filesystem Layout

```
/home/sergiog/dev/
├── iw-ai-core/                       # Standalone platform repo
│   ├── CLAUDE.md                     # Platform-level context
│   ├── .claude/skills/               # Platform-level (base) skills
│   ├── .claude/agents/               # Platform-level agents
│   ├── iw-development-fw/            # Shared framework (symlink)
│   ├── orch/                         # Python package — daemon + core logic
│   │   ├── daemon.py                 # Multi-project daemon (event loop)
│   │   ├── batch_manager.py          # Project-aware batch manager
│   │   ├── batch_planner.py          # Dependency analysis + group assignment
│   │   ├── state_machine.py          # Batch/item/step state transitions
│   │   ├── manifest.py               # Manifest I/O (DB-backed, JSON sync)
│   │   ├── project_registry.py       # Project discovery + config loading
│   │   ├── quota_monitor.py          # LLM usage/quota polling + caching
│   │   ├── git_status.py             # Per-project git state tracking
│   │   └── db/
│   │       ├── models.py             # SQLAlchemy models
│   │       ├── session.py            # DB session factory
│   │       └── migrations/           # Alembic for platform DB
│   ├── executor/                     # Bash scripts — step execution
│   │   ├── step_executor.sh          # Project-aware step executor
│   │   ├── step_executor_lib.sh      # Shared functions (verdict parsing, manifest I/O)
│   │   ├── worktree_setup.sh         # Project-aware worktree creation
│   │   └── worktree_commit.sh        # Commit + merge coordination
│   ├── dashboard/                    # FastAPI web dashboard
│   │   ├── app.py                    # FastAPI application
│   │   ├── routers/
│   │   │   ├── projects.py           # Project selector + overview
│   │   │   ├── batches.py            # Batch list + detail + actions
│   │   │   ├── items.py              # Work item detail + recovery actions
│   │   │   ├── tests.py              # Test runs + history
│   │   │   ├── analytics.py          # Per-project analytics dashboard
│   │   │   ├── daemon.py             # Daemon lifecycle control
│   │   │   └── system.py             # Cross-project system status
│   │   ├── templates/                # Jinja2 templates
│   │   ├── static/                   # CSS, JS (htmx)
│   │   └── sse.py                    # Server-Sent Events for live updates
│   ├── templates/                    # Default workflow templates (fallback)
│   │   ├── Feature_Design_Template.md
│   │   ├── Issue_Design_Template.md
│   │   └── ...
│   ├── pyproject.toml
│   ├── Makefile
│   ├── projects.toml                 # Central project registry
│   └── docker-compose.yml            # PostgreSQL (port 5433)
│
├── iw-doc-plan/main/iw-doc-plan/     # InnoForge (existing project)
│   ├── CLAUDE.md                     # Project-specific context (unchanged)
│   ├── .claude/skills/               # InnoForge-specific skills
│   ├── .claude/agents/               # InnoForge-specific agents
│   ├── ai-dev/
│   │   ├── workflow.md               # Workflow definition: steps, agents, timeout hints (owned by project)
│   │   ├── design/
│   │   │   ├── active/               # Design docs awaiting execution (content only, state is in DB)
│   │   │   └── done/                 # Archived design docs
│   │   └── templates/                # Project-specific prompt templates
│   │   # NOTE: tracking/ folder (Features_tracking.md etc.) is ELIMINATED — DB owns IDs
│   │   # NOTE: work/ folder (manifest JSONs) is ELIMINATED — DB owns execution state
│   └── .iw-orch.json                 # Project registration file
│
└── other-project/                    # Future projects follow same pattern
    ├── .iw-orch.json
    ├── .claude/skills/, agents/
    └── ai-dev/
        ├── workflow.md               # That project's workflow definition
        └── design/active/, done/
```

### 2.2. Deployment Model (iw-dev-01)

```
┌──────────────────────────────────────────────────────────────┐
│  iw-dev-01                                                    │
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ PostgreSQL     │  │ orch-daemon   │  │ orch-dashboard   │  │
│  │ (port 5433)   │  │ (1 process)   │  │ (port 9900)      │  │
│  │ DB: iw_orch   │  │ polls all     │  │ FastAPI+Jinja2   │  │
│  └───────┬───────┘  │ projects      │  │ +htmx            │  │
│          │          └───────┬───────┘  └────────┬─────────┘  │
│          └──────────────────┼───────────────────┘            │
│                             │                                 │
│     ┌───────────────────────┼───────────────────────┐        │
│     │                       │                       │        │
│     ▼                       ▼                       ▼        │
│  InnoForge (8000)      Project B               Project C    │
│  + worktrees           + worktrees             + worktrees   │
└──────────────────────────────────────────────────────────────┘
```

- **One daemon process** manages all projects (iterates per poll cycle)
- **One dashboard** at port 9900 (separate from any project's own ports)
- **Dedicated PostgreSQL** at port 5433 (separate from InnoForge's 5432 app DB)
- Process management: `iw-ai-core start|stop|status` CLI or systemd

### 2.3. Project Registration

Each project places `.iw-orch.json` in its repo root:

```json
{
  "project_id": "innoforge",
  "display_name": "InnoForge Document Platform",
  "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan",
  "id_prefixes": {
    "Feature": "F",
    "Issue": "I",
    "ChangeRequest": "CR",
    "Batch": "BATCH"
  },
  "worktree_base": ".worktrees",
  "ai_dev_dir": "ai-dev",
  "cli_tool": "opencode",
  "setup_commands": {
    "deps": "python3 -m venv .venv && .venv/bin/pip install -q -e '.[dev]' && cd frontend && npm install --silent"
  },
  "quality_gates": ["ruff", "mypy", "pytest", "coverage", "semgrep"],
  "max_parallel": 4,
  "branch_prefix": "agent"
}
```

Central discovery via `projects.toml` in the platform repo:

```toml
[[project]]
id = "innoforge"
path = "/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan"
enabled = true

[[project]]
id = "other-project"
path = "/home/sergiog/dev/other-project"
enabled = true
```

The daemon re-reads `projects.toml` on SIGHUP or every N poll cycles. New projects are onboarded by adding an entry to `projects.toml` and placing `.iw-orch.json` in the project.

### 2.4. Project Discovery Flow

```
Daemon startup
  → Read projects.toml
  → For each entry:
    → Read {path}/.iw-orch.json
    → Validate config (repo exists, ai-dev/ exists)
    → Register in DB (INSERT ON CONFLICT UPDATE)
    → Instantiate BatchManager for this project
  → Begin main loop
```

---

## 3. Data Model (PostgreSQL)

### 3.1. Core Principle

**DB is the single source of truth for all state. Files store content only.**

- **State → DB**: IDs, statuses, timestamps, file paths, dependencies, process info, batch manifests, step results, analytics — everything operational lives in PostgreSQL
- **Content → files**: Design docs, prompts, and reports remain as files in each project's `ai-dev/`. These are human-authored/reviewed artifacts that benefit from git history and diff visibility.
- **No tracking markdown files**: `ai-dev/tracking/` (Features_tracking.md, Incident_tracking.md, etc.) is eliminated entirely. The DB `id_sequences` table replaces it with atomic, race-condition-free allocation.
- **No workflow-manifest.json as writable agent interface**: Manifests are superseded by DB state. The daemon writes a read-only "execution brief" at worktree setup time (so agents know their step details), but agents NEVER write state back to files — they call the `iw` CLI instead.
- **Agents interact via CLI**: LLM agents call `iw` commands to read state and report progress. The `iw` CLI is the bridge between agent filesystem context and the DB.

### 3.2. Schema

```sql
-- ============================================================
-- Projects
-- ============================================================
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,              -- "innoforge"
    display_name    TEXT NOT NULL,
    repo_root       TEXT NOT NULL,                 -- absolute path
    config          JSONB NOT NULL DEFAULT '{}',   -- full .iw-orch.json
    enabled         BOOLEAN NOT NULL DEFAULT true,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- ID Sequences (replaces tracking/*.md files)
-- ============================================================
CREATE TABLE id_sequences (
    project_id      TEXT NOT NULL REFERENCES projects(id),
    prefix          TEXT NOT NULL,                 -- "F", "I", "CR", "BATCH"
    next_number     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, prefix)
);

-- ============================================================
-- Work Items
-- ============================================================
CREATE TABLE work_items (
    id              TEXT NOT NULL,                 -- "I115"
    project_id      TEXT NOT NULL REFERENCES projects(id),
    type            TEXT NOT NULL,                 -- Feature, Issue, ChangeRequest
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft', -- draft/approved/in_progress/completed/failed/paused
    phase           TEXT NOT NULL DEFAULT 'active',-- active/work/done
    config          JSONB NOT NULL DEFAULT '{}',   -- fix_cycle_max, browser_verification, etc.
    depends_on      TEXT[] DEFAULT '{}',
    blocks          TEXT[] DEFAULT '{}',
    design_doc_path TEXT,                          -- relative to ai-dev/ in project
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    PRIMARY KEY (project_id, id)
);

-- ============================================================
-- Workflow Steps
-- ============================================================
CREATE TABLE workflow_steps (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL,
    work_item_id    TEXT NOT NULL,
    step_number     INTEGER NOT NULL,
    step_id         TEXT NOT NULL,                 -- "S01", "S02"
    agent_label     TEXT NOT NULL,                 -- "Frontend", "CodeReview_Frontend"
    opencode_agent  TEXT NOT NULL,                 -- "frontend-impl"
    step_type       TEXT NOT NULL,                 -- implementation, code_review, code_review_final, quality_validation
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',-- pending/in_progress/completed/failed/needs_fix
    prompt_file     TEXT,                          -- relative path
    report_file     TEXT,                          -- relative path
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    FOREIGN KEY (project_id, work_item_id) REFERENCES work_items(project_id, id),
    UNIQUE (project_id, work_item_id, step_number)
);

-- ============================================================
-- Step Runs (each execution attempt)
-- ============================================================
CREATE TABLE step_runs (
    id              SERIAL PRIMARY KEY,
    step_id         INTEGER NOT NULL REFERENCES workflow_steps(id),
    run_number      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',-- running/completed/failed/timeout
    exit_code       INTEGER,
    log_file        TEXT,
    report_file     TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    duration_secs   FLOAT
);

-- ============================================================
-- Fix Cycles
-- ============================================================
CREATE TABLE fix_cycles (
    id              SERIAL PRIMARY KEY,
    step_id         INTEGER NOT NULL REFERENCES workflow_steps(id),
    cycle_number    INTEGER NOT NULL,
    trigger_type    TEXT NOT NULL,                 -- code_review, quality_validation
    trigger_report  TEXT,                          -- path to review report that triggered this
    fix_prompt      TEXT,                          -- path to generated fix prompt
    fix_report      TEXT,                          -- path to fix report
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

-- ============================================================
-- Batches
-- ============================================================
CREATE TABLE batches (
    id              TEXT NOT NULL,                 -- "BATCH-050"
    project_id      TEXT NOT NULL REFERENCES projects(id),
    status          TEXT NOT NULL DEFAULT 'planning',
    max_parallel    INTEGER NOT NULL DEFAULT 4,
    cli_tool        TEXT NOT NULL DEFAULT 'opencode',
    auto_publish    BOOLEAN NOT NULL DEFAULT false,-- auto push + CI after batch completes
    plan_path       TEXT,
    diagram_path    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    PRIMARY KEY (project_id, id)
);

-- ============================================================
-- Batch Items
-- ============================================================
CREATE TABLE batch_items (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT NOT NULL,
    batch_id        TEXT NOT NULL,
    work_item_id    TEXT NOT NULL,
    execution_group INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending',-- pending/setting_up/executing/completed/merged/failed/stalled
    pid             INTEGER,
    started_at      TIMESTAMPTZ,
    merged_at       TIMESTAMPTZ,
    notes           TEXT,
    stall_count     INTEGER DEFAULT 0,
    last_progress   TEXT,
    worktree_info   JSONB DEFAULT '{}',
    merge_info      JSONB DEFAULT '{}',
    FOREIGN KEY (project_id, batch_id) REFERENCES batches(project_id, id),
    FOREIGN KEY (project_id, work_item_id) REFERENCES work_items(project_id, id)
);

-- ============================================================
-- Migration Lock (replaces migration_lock.json)
-- ============================================================
CREATE TABLE migration_locks (
    project_id      TEXT PRIMARY KEY REFERENCES projects(id),
    current_holder  TEXT,                          -- work item ID or NULL
    branch          TEXT,
    locked_at       TIMESTAMPTZ,
    head_revision   TEXT
);
-- Atomic locking via: SELECT ... FOR UPDATE

-- ============================================================
-- Daemon Events (for dashboard display + analytics)
-- ============================================================
CREATE TABLE daemon_events (
    id              SERIAL PRIMARY KEY,
    project_id      TEXT,                          -- NULL for system-level events
    event_type      TEXT NOT NULL,                 -- batch_started, item_launched, item_merged, item_failed, etc.
    entity_id       TEXT,                          -- batch or item ID
    message         TEXT,
    metadata        JSONB DEFAULT '{}',            -- extra structured data
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_work_items_status ON work_items(project_id, status);
CREATE INDEX idx_work_items_phase ON work_items(project_id, phase);
CREATE INDEX idx_batch_items_status ON batch_items(project_id, batch_id, status);
CREATE INDEX idx_workflow_steps_item ON workflow_steps(project_id, work_item_id);
CREATE INDEX idx_daemon_events_recent ON daemon_events(created_at DESC);
CREATE INDEX idx_daemon_events_project ON daemon_events(project_id, created_at DESC);
CREATE INDEX idx_step_runs_step ON step_runs(step_id);
CREATE INDEX idx_fix_cycles_step ON fix_cycles(step_id);
```

### 3.3. ID Management

Replace markdown tracking files with atomic DB sequences:

```python
def next_id(project_id: str, prefix: str) -> str:
    """Atomically allocate the next sequential ID for a project."""
    with db.begin():
        row = db.execute(
            select(IdSequence)
            .where(IdSequence.project_id == project_id, IdSequence.prefix == prefix)
            .with_for_update()
        ).one()
        new_id = f"{prefix}{row.next_number:03d}"
        row.next_number += 1
    return new_id
```

No ID collisions possible. `FOR UPDATE` row lock guarantees atomicity even under concurrent requests.

### 3.4. Historical Data Import

Start fresh in the DB. Build an import script (`orch/import_history.py`) that:
1. Scans `ai-dev/done/` recursively
2. Parses each `workflow-manifest.json`
3. Inserts work items, steps, runs, fix cycles into DB
4. Preserves original timestamps
5. Idempotent (can re-run safely via `ON CONFLICT DO NOTHING`)

This runs as a one-time migration per project, not part of the critical path.

---

## 4. Dashboard

### 4.1. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Web framework | FastAPI | Proper async routing, native SSE, auto API docs |
| Templating | Jinja2 | Already proven, no migration cost |
| Interactivity | htmx | Progressive enhancement, zero build step, partial page updates |
| Styling | Current CSS (evolved) | Existing dashboard CSS works well |
| Real-time | SSE (Server-Sent Events) | Replaces meta-refresh, lightweight |

No React SPA. No build pipeline. Single developer, internal tool.

### 4.2. Page Structure & Navigation

```
/ (root)
├── Project Selector
│   ├── InnoForge — 2 active batches, 15 items this week, main: 3 unpushed
│   └── Other Project — idle, main: clean
│
/project/{id}/
├── Dashboard .............. Batch overview, active items, stats, git status
├── Batches ................ All batches, filterable by status
│   └── /batch/{batch_id} . Batch detail: plan, diagram, items, logs, actions
├── Queue & Backlog ........ Pending items + designs awaiting approval
├── History ................ Completed items, filterable by type/date
├── Analytics .............. Success rates, fix cycles, agent effectiveness, trends
├── Tests .................. Test runs, history, flaky detection
├── Agents ................. Agent activity (OpenCode session tree)
├── Docs ................... Doc generation tracking
│
/system/
├── Daemon Status .......... Cross-project daemon health, PID, uptime
├── All Active Work ........ Aggregated view across all projects
└── Configuration .......... projects.toml, LLM quota, system settings
```

Sidebar has a **project selector dropdown** at the top. All pages are scoped via URL prefix `/project/{project_id}/...`.

### 4.3. Authentication

**v1: No authentication.** Single user on local machine, dashboard listens on localhost/LAN only.

**Future (optional):** Simple token-based auth via env var + FastAPI middleware. No user database needed.

---

## 5. Feature: LLM Usage Quota Footer

### 5.1. Overview

A persistent footer bar across all dashboard pages showing real-time LLM quota for all configured providers.

### 5.2. Visual Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Claude Code: ████████░░ 63% (5h) │ ██░░░░░░░░ 26% (7d) resets Apr 5      │
│ MiniMax:     1245/1500 prompts (17%) resets in 3h 17m                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

Color-coded: green (<50%), yellow (50-80%), red (>80%).

### 5.3. Claude Code Quota

**Endpoint** (undocumented, used internally by Claude Code's own status line):
```
GET https://api.anthropic.com/api/oauth/usage
Authorization: Bearer <token>
anthropic-beta: oauth-2025-04-20
```

**Response:**
```json
{
  "five_hour": { "utilization": 37.0, "resets_at": "2026-03-29T08:59:59Z" },
  "seven_day": { "utilization": 26.0, "resets_at": "2026-04-05T14:59:59Z" }
}
```

**Credential source:** `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`

**Critical limitation:** Aggressively rate-limited (~5 requests per token before 429). Must cache aggressively.

**Implementation:**
- Background poller in `orch/quota_monitor.py`
- Poll every **5 minutes** (usage changes on multi-hour timescales)
- Cache response to file with TTL
- On 429: serve stale cache, do NOT attempt token refresh automatically (risks breaking active Claude Code sessions)
- Dashboard fetches from `GET /api/quota` which returns cached data

### 5.4. MiniMax Quota

**Endpoint** (documented, stable):
```
GET https://platform.minimax.io/v1/api/openplatform/coding_plan/remains?GroupId={GROUP_ID}
Authorization: Bearer <CODING_PLAN_API_KEY>
```

**Response:** Used/total/remaining prompts + reset timestamp.

**No aggressive rate limiting.** Can poll every 1-2 minutes safely.

**Credentials:** Configured in platform env vars (`MINIMAX_GROUP_ID`, `MINIMAX_CODING_API_KEY`).

### 5.5. Architecture

```
quota_monitor.py (background thread)
  ├── poll_claude_quota() every 300s → cache file
  ├── poll_minimax_quota() every 120s → cache file
  └── Exposes get_cached_quota() → dict

dashboard/routers/system.py
  └── GET /api/quota → returns cached quota JSON

dashboard/templates/base.html (footer)
  └── JavaScript fetches /api/quota every 60s, updates footer bars
```

### 5.6. Extensibility

New LLM providers added by implementing a `QuotaProvider` interface:

```python
class QuotaProvider(ABC):
    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def poll_interval_secs(self) -> int: ...
    @abstractmethod
    def fetch_quota(self) -> QuotaResult: ...
```

---

## 6. Feature: Analytics Dashboard

### 6.1. Overview

Per-project analytics page showing historical effectiveness metrics. Powered by DB queries over work items, steps, runs, and fix cycles.

### 6.2. Key Metrics

| Metric | Query Source | Display |
|--------|-------------|---------|
| **First-pass success rate** | Steps with 0 fix cycles / total steps | % by agent type, trend over time |
| **Fix cycle frequency** | fix_cycles grouped by agent_label | Bar chart: which agents trigger most fixes |
| **Avg time to completion** | work_items.completed_at - created_at | By type (Feature/Issue/CR), trend |
| **Batch efficiency** | batch_items completed vs failed per batch | Success rate per batch, trend |
| **Quality gate failures** | QV step failures by gate type | Distribution: lint/tests/types/coverage/semgrep |
| **Escalation rate** | Items where fix_cycles >= max and status=failed | % over time |
| **Step duration** | step_runs.duration_secs by step_type | Avg/p95 by step type |
| **Merge conflict rate** | batch_items where merge_info contains conflict | % per batch |

### 6.3. Dashboard Views

1. **Overview cards** — Key metrics at a glance (success rate, avg completion time, escalation rate)
2. **Trend charts** — Metrics over time (weekly/monthly). Rendered server-side or with a lightweight JS charting library (Chart.js or similar, no npm build).
3. **Agent effectiveness table** — Per-agent breakdown: success rate, avg fix cycles, avg duration
4. **Quality gate breakdown** — Which gates fail most, trend over time
5. **Filterable** — By date range, work item type, batch

### 6.4. Data Source

All analytics come from DB queries. No separate analytics pipeline. The daemon_events table provides event-level granularity for time-based analysis.

---

## 7. Feature: One-Click Recovery Actions

### 7.1. Overview

Dashboard actions to recover from failures without SSH + manual manifest editing.

### 7.2. Available Actions

| Action | When Available | What It Does |
|--------|---------------|--------------|
| **Retry step** | Step status = failed | Reset step to pending, clear last run, re-launch |
| **Skip step** | Step status = failed/needs_fix | Mark step as completed (manual override), advance workflow |
| **Restart from step N** | Item in_progress or failed | Reset steps N..last to pending, resume from step N |
| **Kill item** | Item executing (PID alive) | SIGTERM the process, mark as failed |
| **Re-queue item** | Item failed within a batch | Reset item to pending, daemon will re-launch when slot available |
| **Force-merge** | Item completed but merge failed (conflict) | Attempt merge with manual conflict resolution flag |
| **Pause batch** | Batch executing | Set pause flag; running items finish, no new items launch |
| **Resume batch** | Batch paused | Remove pause flag, daemon resumes launching |
| **Archive batch** | Batch completed/completed_with_errors | Move batch + items to done/ |

### 7.3. Implementation

Each action is a POST endpoint in `dashboard/routers/items.py` or `batches.py`:

```
POST /project/{project_id}/api/item/{item_id}/retry-step/{step_number}
POST /project/{project_id}/api/item/{item_id}/skip-step/{step_number}
POST /project/{project_id}/api/item/{item_id}/restart-from/{step_number}
POST /project/{project_id}/api/item/{item_id}/kill
POST /project/{project_id}/api/item/{item_id}/requeue
POST /project/{project_id}/api/batch/{batch_id}/pause
POST /project/{project_id}/api/batch/{batch_id}/resume
POST /project/{project_id}/api/batch/{batch_id}/archive
```

Actions update DB state. The daemon picks up changes on next poll cycle and acts accordingly. For kill: sends SIGTERM directly, then updates DB.

### 7.4. Confirmation

All destructive actions (kill, skip, force-merge) require a confirmation dialog before executing. Non-destructive actions (retry, re-queue, pause) execute immediately.

---

## 8. Feature: Dashboard Toast Notifications

### 8.1. Overview

SSE-powered in-browser notifications for key workflow events. Replaces "check the dashboard every 10 minutes" with instant visual feedback when the page is open.

### 8.2. Events That Trigger Toasts

| Event | Severity | Message Example |
|-------|----------|-----------------|
| Batch completed | Success | "BATCH-050 completed: 6/6 items merged" |
| Batch completed with errors | Warning | "BATCH-050 finished: 4/6 items merged, 2 failed" |
| Item failed | Error | "I115 failed at S02 (CodeReview): fix cycles exhausted" |
| Item escalated | Error | "I118 escalated: merge conflict on template_service.py" |
| Item stalled | Warning | "I120 stalled: no progress for 30 minutes" |
| Item merged | Info | "I115 merged to main successfully" |
| Batch auto-published | Success | "BATCH-050 auto-published: git push + CI passed" |
| Batch auto-publish failed | Error | "BATCH-050 publish failed: CI tests failed" |
| LLM quota warning | Warning | "Claude Code 5h quota at 85% — resets in 1h 20m" |

### 8.3. Implementation

```
daemon writes event → daemon_events table
                          ↓
dashboard SSE endpoint polls daemon_events (last 60s)
                          ↓
GET /api/stream/notifications → SSE stream
                          ↓
JavaScript renders toast (top-right, auto-dismiss after 10s, click to navigate)
```

Toast UI: Small card in top-right corner. Color-coded by severity. Click navigates to relevant item/batch. Stack up to 5, oldest auto-dismiss.

---

## 9. Feature: Execution Timeline (Gantt View)

### 9.1. Overview

Visual timeline showing when each item in a batch started, which steps ran when, where fix cycles occurred, and when merges happened.

### 9.2. Data Source

- `batch_items.started_at`, `merged_at`
- `workflow_steps.started_at`, `completed_at`
- `step_runs.started_at`, `completed_at`
- `fix_cycles.started_at`, `completed_at`

### 9.3. Rendering

Server-rendered SVG or lightweight JS library (no npm build). Each item is a horizontal bar. Steps are colored segments within the bar. Fix cycles shown as red marks. Merge shown as a distinct marker.

```
Time →  12:00   12:15   12:30   12:45   13:00   13:15
I115    ████████████████████████████████████████▓▓  ✓ merged
        S01(FE)  S02(CR) S03(T)  S04(CR) S05(GR) S06(QV)
                    ↑fix

I116    ████████████████████████████████████████████████▓▓  ✓ merged
        S01(BE)      S02(CR)  S03(API)  S04(CR) S05(GR) S06(QV)

I117    ██████████████████████████  ✗ failed
        S01(DB)  S02(CR) ↑fix↑fix↑fix↑fix↑fix ESCALATED
```

### 9.4. Location

Available on the batch detail page (`/project/{id}/batch/{batch_id}`), as an additional tab alongside the current items table and logs view.

---

## 10. Feature: Auto-Publish After Batch

### 10.1. Overview

Optional per-batch setting: after all items are successfully merged to the local main branch, automatically push to origin and trigger CI.

### 10.2. Batch Configuration

When creating a batch, the user can set `auto_publish: true`. Stored in `batches.auto_publish` column.

### 10.3. Publish Flow

```
All batch items merged to local main
  ↓
auto_publish == true?
  ├── No → Batch status: completed. Human publishes manually.
  └── Yes → Begin publish sequence:
        1. Run project's quality gates (from .iw-orch.json → quality_gates)
        2. Run project's test suite (from .iw-orch.json → test_commands)
        3. If all pass:
        │   a. git push origin main
        │   b. Wait for CI pipeline (if detectable via API)
        │   c. Batch status: published
        │   d. Toast: "BATCH-050 auto-published successfully"
        └── If any fail:
            a. Batch status: publish_failed
            b. Toast: "BATCH-050 publish failed: {reason}"
            c. Human intervention required
```

### 10.4. Safety Guardrails

- Auto-publish **never** force-pushes
- If the remote main has diverged (someone else pushed), publish fails safely
- The quality gate + test run happens AFTER all merges, on the final integrated state
- Publish failure does NOT roll back the merges — items stay merged locally, human decides next step

### 10.5. New Batch States

```
planning → approved → executing → completed → publishing → published
                                     │             │
                                     │             └→ publish_failed
                                     └→ completed_with_errors (no publish attempted)
```

---

## 11. Feature: Git Status Panel

### 11.1. Overview

Per-project display of the current state of the main branch: uncommitted changes, unpushed commits, branch status relative to remote.

### 11.2. Data Collected

| Metric | Git Command | Display |
|--------|-------------|---------|
| Uncommitted files | `git status --porcelain` | Count + list |
| Staged but uncommitted | `git diff --cached --name-only` | Count + list |
| Unpushed commits | `git log origin/main..HEAD --oneline` | Count + commit list |
| Behind remote | `git log HEAD..origin/main --oneline` | Count (after fetch) |
| Current branch | `git branch --show-current` | Branch name |
| Last push timestamp | `git log origin/main -1 --format=%ci` | Relative time |
| Active worktrees | `git worktree list` | Count + list |

### 11.3. Display Locations

1. **Project selector cards** (root page): Summary badge — e.g., "3 unpushed" or "clean"
2. **Project dashboard** (main page): Full git status panel with details
3. **Batch detail**: Warning banner if uncommitted changes exist when batch is running

### 11.4. Implementation

`orch/git_status.py` — runs git commands in each project's repo root. Polled every 30 seconds by the daemon. Results cached in memory (not DB — too transient).

```python
@dataclass
class GitStatus:
    branch: str
    uncommitted_count: int
    uncommitted_files: list[str]
    staged_count: int
    unpushed_count: int
    unpushed_commits: list[str]
    behind_count: int
    last_push_at: datetime | None
    active_worktrees: int
```

---

## 12. Orchestrator Evolution

### 12.1. Multi-Project Daemon

```python
class MultiProjectDaemon:
    def __init__(self, config_path: str):
        self.projects: dict[str, ProjectConfig] = {}
        self.managers: dict[str, BatchManager] = {}    # one per project
        self.quota_monitor: QuotaMonitor = QuotaMonitor()
        self.git_monitor: dict[str, GitStatus] = {}

    def _main_loop(self):
        while self._running:
            self._reload_projects_if_needed()

            for project_id, config in self.projects.items():
                if not config.enabled:
                    continue
                manager = self.managers[project_id]

                # Discover and process batches
                active_batches = manager.discover_batches()
                for batch in active_batches:
                    self._process_batch(project_id, manager, batch)
                manager.process_merge_queue()

                # Check for completed batches needing auto-publish
                self._check_auto_publish(project_id, manager)

                # Update git status
                self.git_monitor[project_id] = git_status.collect(config.repo_root)

            # Cross-project services
            self.quota_monitor.poll_if_due()
            time.sleep(self.poll_interval)
```

### 12.2. Worktree Isolation

No changes needed. Each project has its own `.worktrees/` under its repo root. Naturally namespaced. ID collisions across projects (both have I001) are fine — DB uses composite key `(project_id, id)`, worktrees are in different repos.

### 12.3. Step Executor: Project-Aware

```bash
# Phase 2 signature adds project_repo_root:
bash executor/step_executor.sh <item_id> <worktree_path> <log> <cli_tool> <batch_dir> <project_repo_root>
```

Since the worktree IS a full checkout of the project repo, the LLM session automatically gets the project's CLAUDE.md, .claude/skills/, .claude/agents/, and ai-dev/ context. No additional plumbing needed.

### 12.4. DB Interaction Pattern

```
Daemon writes execution_brief.json (READ-ONLY for agents)
  at worktree setup time → agent knows its steps, prompts, context
                 ↓
Agent reads execution_brief.json to understand its task
Agent calls `iw` CLI to report progress → DB updated atomically
  e.g.: iw step-done I145 --step S01 --report path/to/report.md
                 ↓
Daemon polls DB → drives workflow, launches next step, handles failures
                 ↓
Dashboard queries DB → renders pages
```

- **execution_brief.json**: Written once at worktree setup, never updated. Agent reads it to know step definitions, prompt file paths, input/output expectations. Read-only.
- **`iw` CLI**: The only way agents update state. Calls go to the DB. Agents never write to manifest/state files.
- The daemon is the only DB writer for execution orchestration state. The CLI is the only DB writer for agent-reported step results. Dashboard is read-only.

---

## 13. The `iw` CLI — Agent Interface

### 13.1. Overview

`iw` is the command-line interface that bridges LLM agents and the iw-ai-core database. It is installed once on the machine (via `pip install -e .`) and available on PATH. Agents call it; the DB does the work. The LLM never reads or writes state files.

### 13.2. Core Commands

**ID allocation** — replaces reading tracking markdown files:
```bash
iw next-id --type feature --project innoforge    # → F089
iw next-id --type incident --project innoforge   # → I145
iw next-id --type cr --project innoforge         # → CR042
```

**Work item registration** — called by skill script (not LLM) after design doc is created:
```bash
iw register F089 "Add template versioning" \
  --project innoforge \
  --design-doc ai-dev/design/active/F089_Feature_Design.md
```
Atomic. If called twice with the same ID, it is idempotent (ON CONFLICT DO NOTHING).

**Step lifecycle** — agents report progress:
```bash
iw step-start I145 --step S01                              # mark step in_progress
iw step-done  I145 --step S01 --report path/to/report.md  # mark completed + attach report
iw step-fail  I145 --step S01 --reason "type errors"       # mark failed
```

**Design doc retrieval** — agents read context:
```bash
iw get-design I145          # prints design doc content to stdout
iw get-design I145 --path   # prints just the file path
```

**Migration lock** — replaces migration_lock.json:
```bash
iw migration-lock acquire I145 --project innoforge   # atomic DB lock
iw migration-lock release I145 --project innoforge
iw migration-lock status   --project innoforge       # who holds the lock
```

### 13.3. Why Skill Script Registers, Not LLM

When a user runs `/iw-new-feature`, the flow is:

```
Skill script (bash)
  1. calls: iw next-id --type feature --project innoforge → F089
  2. passes F089 to LLM session: "create design doc for F089"
  3. LLM creates: ai-dev/design/active/F089_Feature_Design.md + prompts
  4. skill script calls: iw register F089 "..." --design-doc path/to/doc.md
  5. Done — DB knows about F089 regardless of how the LLM session ended
```

If the LLM session crashes between steps 3 and 4, the skill script still calls `iw register` on exit. The design doc file exists and the DB entry is created. Nothing is lost.

Previously, step 4 was the LLM updating `Features_tracking.md` — which it could forget, and which had no atomicity guarantees.

### 13.4. Execution Brief

At worktree setup time, the daemon writes `ai-dev/execution_brief.json` into the worktree. This file is **read-only for agents** — they never update it:

```json
{
  "item_id": "I145",
  "project_id": "innoforge",
  "title": "Fix template rendering timeout",
  "design_doc": "ai-dev/design/active/I145_Issue_Design.md",
  "current_step": "S01",
  "steps": [
    {
      "step_id": "S01",
      "agent_label": "Backend",
      "prompt_file": "ai-dev/design/active/prompts/I145_S01_Backend_prompt.md",
      "status": "pending"
    }
  ]
}
```

The LLM reads this to orient itself. All state transitions go through `iw` CLI.

---

## 14. Skill & Agent Framework

### 14.1. Three-Tier Architecture

```
Tier 1: Platform Skills (iw-ai-core/.claude/skills/)
  → Workflow: iw-batch-execute, iw-batch-status, iw-batch-stop, iw-workflow
  → Design: iw-new-feature, iw-new-incident, iw-new-cr, iw-review-design
  → Generic: plan-agent, system-architect, deep-research
  → Brand: iw-brand-config, iw-blog-writer, iw-pitch-deck

Tier 2: Framework Agents (iw-development-fw/agents/)
  → Implementation: backend-impl, frontend-impl, database-impl, api-impl
  → Review: code-review-impl, code-review-fix-impl, code-review-final-impl
  → QV: quality-validation-impl
  → Orchestrator: orchestrator

Tier 3: Project Skills (each project's .claude/skills/)
  → Project-specific: innoforge-testing, innoforge-ui
  → Customized workflows, project-specific agents
```

### 14.2. Base Skill Distribution: Symlink Injection

At worktree setup time, `executor/worktree_setup.sh` symlinks platform skills into the worktree:

```bash
ORCH_ROOT="/home/sergiog/dev/iw-ai-core"
WORKTREE_SKILLS="$WORKTREE_DIR/.claude/skills"

# Symlink platform skills that don't conflict with project skills
for skill_dir in "$ORCH_ROOT/.claude/skills/"*/; do
    skill_name=$(basename "$skill_dir")
    if [[ ! -d "$WORKTREE_SKILLS/$skill_name" ]]; then
        ln -s "$skill_dir" "$WORKTREE_SKILLS/$skill_name"
    fi
done
```

**Project skills always take precedence.** Platform versions only symlinked if no project override exists.

### 14.3. Framework Sharing

`iw-development-fw/` shared via symlink (pragmatic for single machine). Each project references it from its own repo root.

### 14.4. Template Resolution

Project-specific templates checked first, platform defaults as fallback:

```python
def get_template(project_root: str, template_name: str) -> str:
    project_path = os.path.join(project_root, "ai-dev", "templates", template_name)
    if os.path.isfile(project_path):
        return project_path
    return os.path.join(ORCH_ROOT, "templates", template_name)
```

---

## 15. Resilience Patterns Preserved

| Pattern | Phase 1 (Current) | Phase 2 (IW AI Core) |
|---------|-------------------|----------------------|
| Source of truth | JSON manifests | DB (execution_brief.json is read-only agent context) |
| Polling | File mtime checks (60s) | DB queries (60s) |
| Worktree isolation | Per-item git worktree | Unchanged |
| Short-lived LLM sessions | One session per step | Unchanged |
| Deterministic bash | step_executor.sh | Same scripts, live in platform repo |
| Sequential merge queue | One merge at a time | One merge at a time per project |
| PID locking | .ai-dev-daemon.pid | Unchanged |
| Atomic writes | jq + tmp + mv | DB transactions (`iw` CLI calls; agent never writes state files) |
| Idempotent operations | File existence checks | `ON CONFLICT` / row checks |
| Daemon restart recovery | Resume from first non-completed step | Unchanged (DB makes it even more reliable) |

---

## 16. Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Dashboard | FastAPI + Jinja2 + htmx | Async routing, SSE native, no SPA build pipeline |
| Database | PostgreSQL 15+ (port 5433) | Already on machine, JSONB, proven |
| ORM | SQLAlchemy 2.0 (sync) | Daemon is sync; keep it simple |
| Migrations | Alembic | Consistent tooling |
| Charts | Chart.js (CDN) | Lightweight, no npm build, good enough for analytics |
| Step executor | Bash (keep) | Deterministic, no-LLM state transitions |
| Daemon | Python (keep) | Proven, single-threaded polling loop |

**Explicitly NOT added:** Redis, Celery, React SPA, Kubernetes, gRPC, WebSocket (SSE is sufficient).

---

## 17. Migration Strategy

### Phase 2a — Scaffold (Week 1)

1. Create `iw-ai-core/` repo with directory structure
2. `docker-compose.yml` for PostgreSQL (port 5433)
3. DB schema + Alembic migrations (all tables from Section 3)
4. Copy daemon code from `scripts/ai_dev_daemon/`, parameterize `repo_root`
5. Copy step executor scripts from `scripts/`, add `project_repo_root` parameter
6. Port dashboard from `scripts/ai_dashboard/` to FastAPI
7. Add project selector page + project-scoped routes
8. Register InnoForge as first project

**InnoForge keeps running on Phase 1 during all of this. Zero disruption.**

### Phase 2b — Dual-Write Bridge (Week 2)

1. Daemon writes to both JSON manifests AND DB simultaneously
2. Dashboard reads from DB instead of scanning `ai-dev/` directories
3. Verify: dashboard shows identical data from DB as it did from files
4. Build historical import script, run against InnoForge's `ai-dev/done/`

### Phase 2c — Cutover (Week 3)

1. Stop Phase 1 daemon
2. Start Phase 2 daemon
3. Verify InnoForge works identically through Phase 2 platform
4. Update InnoForge's Makefile to delegate to platform CLI
5. Retire Phase 1 scripts from InnoForge repo (archive, don't delete)

### Phase 2d — New Features + Second Project

1. Implement: analytics, recovery actions, toasts, timeline, auto-publish, git status, quota footer
2. Onboard second project: add `.iw-orch.json` + register in `projects.toml`
3. Daemon auto-discovers it on next config reload

### What Moves vs. Stays

**Moves to `iw-ai-core/`:**
- `scripts/ai_dev_daemon/` → `orch/`
- `scripts/ai_dashboard/` → `dashboard/`
- `scripts/step_executor.sh`, `step_executor_lib.sh` → `executor/`
- `scripts/worktree_setup.sh`, `worktree_commit.sh` → `executor/`
- `scripts/batch_dispatcher.sh`, `batch_launch.sh` → `executor/`

**Stays in project repos:**
- `CLAUDE.md` — project-specific context
- `.claude/skills/` — project-specific skills
- `.claude/agents/` — project-specific agents
- `ai-dev/design/` — design docs, prompts, reports (content only — git history is valuable here)
- `ai-dev/workflow.md` — workflow definition for this project (steps, agents, timeout hints)
- `ai-dev/templates/` — project-specific prompt templates
- `iw-development-fw/` — framework reference
- `Makefile` — updated to call platform CLI

**Eliminated from project repos:**
- `ai-dev/tracking/` — Features_tracking.md, Incident_tracking.md, etc. → replaced by DB `id_sequences`
- `ai-dev/work/` — manifest JSONs, batch manifests → replaced by DB state
- `scripts/ai_dev_daemon/`, `scripts/ai_dashboard/`, executor scripts → moved to platform

**Added to project repos:**
- `.iw-orch.json` — project registration config
- `ai-dev/workflow.md` — workflow step definition (if not already present)

---

## 17. Decisions

### 17.1. Closed Decisions (2026-03-31)

| # | Decision | Resolution | Rationale |
|---|----------|-----------|-----------|
| D1 | DB scope | **DB owns ALL state** — IDs, manifests, batch state, step results, fix cycles | Eliminates fragile markdown tracking files; atomic ID allocation; single source of truth |
| D2 | Design docs location | **Stay as files in each project's `ai-dev/design/`** (Option A) | Content benefits from git history and human review; not operational state |
| D3 | Workflow definition | **`ai-dev/workflow.md` per project** — not in `.iw-orch.json` or iw-ai-core | Workflow evolves with the project; versioned alongside the code |
| D4 | Work item registration | **Skill script calls `iw register`** (Option B) — not LLM | Guarantees registration even on session crash; removes LLM responsibility for state |
| D5 | Cross-project batches | **No** — each batch belongs to one project | Keeps routing and state simple; single developer doesn't need cross-project batches |
| D6 | Framework distribution | **Symlink** (single machine, pragmatic) | No submodule overhead; machine-local deployment |
| D7 | DB for daemon | **Sync SQLAlchemy** | Daemon is single-threaded polling loop; async adds complexity for no benefit |
| D8 | Dashboard port | **9900** | Avoids confusion with InnoForge's own dashboard during migration |

### 17.2. Open Decisions

| # | Decision | Options | Current Lean |
|---|----------|---------|-------------|
| O1 | Config hot-reload | SIGHUP vs daemon restart | SIGHUP (cleaner, low complexity) |
| O2 | Chart library | Chart.js vs server-rendered SVG | Chart.js CDN (richer interactivity, zero build) |
| O3 | execution_brief.json format | JSON vs TOML vs Markdown | JSON (machine-readable, consistent with existing tooling) |
| O4 | `iw` CLI distribution | Installed to PATH vs called by absolute path | PATH (`pip install -e .` adds `iw` entry point) |

---

## Appendix A: State Machines

### A.1. Batch States

```
planning ──(approve)──> approved ──(daemon picks up)──> executing
                                        ├──> paused ──(resume)──> executing
                                        ├──> completed ──(auto_publish?)──> publishing ──> published
                                        │                                       └──> publish_failed
                                        └──> completed_with_errors (no publish)
```

### A.2. Batch Item States

```
pending ──(setup)──> setting_up ──(launch)──> executing
                                                ├──(complete)──> completed ──(merge)──> merged
                                                ├──(fail)──> failed ──(requeue)──> pending
                                                └──(stall)──> stalled ──(reset)──> pending
```

### A.3. Workflow Step States

```
pending ──(execute)──> in_progress ──(pass)──> completed
                           │
                           └──(review fail)──> needs_fix ──(fix cycle)──> in_progress
                                                   │
                                                   └──(max cycles)──> failed (escalate)
```

---

## Appendix B: API Endpoints Summary

### Project Routes (`/project/{project_id}/`)

```
GET  /                                    Project dashboard
GET  /batches                             Batch list
GET  /batch/{batch_id}                    Batch detail
GET  /batch/{batch_id}/timeline           Gantt view
GET  /queue                               Queue & backlog
GET  /history                             History
GET  /analytics                           Analytics dashboard
GET  /tests                               Test runs
GET  /agents                              Agent activity
```

### Action Routes

```
POST /api/item/{item_id}/retry-step/{n}   Retry a failed step
POST /api/item/{item_id}/skip-step/{n}    Skip a step (manual override)
POST /api/item/{item_id}/restart-from/{n} Restart from step N
POST /api/item/{item_id}/kill             Kill executing item
POST /api/item/{item_id}/requeue          Re-queue failed item
POST /api/batch/{batch_id}/pause          Pause batch
POST /api/batch/{batch_id}/resume         Resume batch
POST /api/batch/{batch_id}/archive        Archive completed batch
POST /api/batch/{batch_id}/publish        Manually trigger publish
```

### System Routes

```
GET  /api/quota                           LLM usage quota (cached)
GET  /api/stream/notifications            SSE notification stream
GET  /api/git-status/{project_id}         Git status for project
POST /api/daemon/start                    Start daemon
POST /api/daemon/stop                     Stop daemon
POST /api/daemon/restart                  Restart daemon
GET  /api/daemon/status                   Daemon health
```
