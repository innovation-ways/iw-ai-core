# CR-00013_S03_Backend_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design document
- `ai-dev/active/CR-00013/reports/CR-00013_S01_Backend_report.md` — S01 report (timing middleware now in place; lean on it to verify improvements)
- `dashboard/routers/projects.py` — `_project_stats` (C1)
- `dashboard/routers/project_dashboard.py` — `_active_batches` (C2)
- `dashboard/routers/batches.py` — `_batch_item_rows` (C3)
- `dashboard/routers/items.py` — `_get_steps` (C4)
- `dashboard/routers/running.py` — `_query_failed_steps` (C5)
- `orch/db/models.py` — ORM models for join targets (`WorkItem`, `WorkflowStep`, `StepRun`, `BatchItem`, `Batch`, `Project`)

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S03_Backend_report.md` — step report

## Context

You are rewriting five N+1 query hotspots on the dashboard's busiest routes. Each hotspot currently runs a loop that issues one (or more) extra query per row. Replace each with a bounded-query approach — either a single aggregation with `GROUP BY`, or a bulk fetch with `IN (...)` / `selectinload` and a client-side map.

Read the design doc first (Section "Current Behavior" enumerates the exact symptoms; AC3 enumerates the target routes). Read `orch/CLAUDE.md` for ORM conventions.

## Requirements

### 1. C1 — `_project_stats` in `dashboard/routers/projects.py:71-120`

Currently: for each `Project`, issues 4 separate count queries (likely over `WorkItem` / `BatchItem` / etc. — inspect the code to confirm).

Desired: **one** aggregation query that groups by `project_id` and returns all four counts per project in a single round-trip. Build a `dict[project_id, stats]` and zip with the projects list. Maintain the return shape (template contract must not change).

### 2. C2 — `_active_batches` in `dashboard/routers/project_dashboard.py:102-121`

Currently: 2 count queries per active batch.

Desired: one query with `GROUP BY batch_id` aggregating both counts. Build a map keyed by batch id and attach counts to each batch in a single pass. Return shape unchanged.

### 3. C3 — `_batch_item_rows` in `dashboard/routers/batches.py:114-181`

Currently: per-item `WorkItem` query and per-item `WorkflowStep` query inside the loop.

Desired:

- Collect all `(project_id, work_item_id)` tuples from the `BatchItem` rows.
- Issue one bulk `select(WorkItem).where(tuple_(WorkItem.project_id, WorkItem.id).in_([...]))` (or equivalent). Build a dict keyed by `(project_id, id)`.
- Issue one bulk `WorkflowStep` query covering all referenced step ids. Build a dict.
- Iterate batch items and look up from the dicts. Zero queries inside the loop body.

### 4. C4 — `_get_steps` in `dashboard/routers/items.py:322-330`

Currently: per-step `StepRun` query (last run per step).

Desired:

- Collect all step ids first.
- One query using a window function (`DISTINCT ON (step_id) ... ORDER BY step_id, created_at DESC` in PostgreSQL) or a grouped subquery to get the latest `StepRun` per step.
- Build a `dict[step_id, StepRun]` and attach to each step.
- This function is called from multiple item-detail routes (`items.py:770, 803, 832, 888`); the single refactor must cover all of them.

### 5. C5 — `_query_failed_steps` in `dashboard/routers/running.py:132-137`

Currently: per-failed-step `StepRun` last-run query.

Desired: same bulk-load pattern as C4 — one query with `DISTINCT ON` or a grouped subquery to get last runs for all failed steps in one round-trip.

## Constraints

- **Return shape must not change.** Templates still render the same context objects. If you need to attach new fields, do so additively.
- **No N+1 queries inside Jinja templates.** If you find a template that triggers lazy-loads via the ORM, add the necessary `selectinload` or preload in the router.
- **Use SQLAlchemy 2.0 idioms** (`select(...)` with `.where()`, not legacy `Query` API).
- **Composite PK aware.** `WorkItem` has a composite PK `(project_id, id)`. Use `tuple_(...)` in `WHERE ... IN` clauses or an equivalent.
- **Keep sync.** The engine and session are sync; do not introduce async here.

## Project Conventions

Read `orch/CLAUDE.md` and `dashboard/CLAUDE.md`.

- Composite PKs on multi-project tables (`work_items`, `batch_items`, etc.).
- `DaemonEvent.metadata` is `event_metadata` in Python (not relevant here, but watch for analogous reserved attrs).
- Append-only tables (`step_runs`, `fix_cycles`, `daemon_events`) — never UPDATE.

## TDD Requirement

Follow TDD:

1. **RED**: Write failing tests first. For each hotspot, use a query-count fixture (SQLAlchemy `after_cursor_execute` event) to assert that the number of queries is ≤K (a small constant) for N varying in {0, 1, 10}. Use the testcontainer fixture.
2. **GREEN**: Rewrite each hotspot to pass the bound.
3. **REFACTOR**: Extract a shared helper if duplication emerges (optional).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `make quality`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/projects.py",
    "dashboard/routers/project_dashboard.py",
    "dashboard/routers/batches.py",
    "dashboard/routers/items.py",
    "dashboard/routers/running.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
