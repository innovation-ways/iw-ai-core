# I-00090_S01_Backend_prompt

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item generates NO migration. Do not run `alembic revision` or any
alembic upgrade/downgrade/stamp commands. If something appears to require
a schema change, STOP and raise a blocker — this is intentionally a
query-layer-only fix.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00090 --json`. The `workflow-manifest.json` file is a design-time snapshot.
- `ai-dev/active/I-00090/I-00090_Issue_Design.md` -- Design document
- `ai-dev/active/I-00090/I-00090_Functional.md` -- Functional summary
- `ai-dev/active/I-00090/evidences/pre/I-00090-bug-evidence.png` -- pre-fix screenshot
- `ai-dev/active/I-00090/evidences/pre/I-00090-bug-evidence-snapshot.yml` -- pre-fix a11y snapshot
- Existing code: `dashboard/routers/running.py` (the file you will edit)
- `orch/db/models.py` (for the `WorkItemStatus` enum at line 107, `WorkItem.archived_at` at line 605)
- `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md` for project conventions

## Output Files

- `ai-dev/active/I-00090/reports/I-00090_S01_Backend_report.md` -- Step report

## Context

You are implementing the fix for **I-00090** — the system-wide and per-project Running Tasks pages currently show step rows from work items that are no longer active (completed, cancelled, or archived). Today on production this manifests as four stale CR rows (CR-00023, CR-00049, CR-00052, CR-00054) in the "Failed / Needs Attention" table.

Read the design document first to understand the full scope (active-item definition, out-of-scope helpers, why item-level `failed` still surfaces). Then read `dashboard/CLAUDE.md` and `orch/CLAUDE.md` for project-specific patterns.

## Requirements

### 1. Add the active-item predicate to `_query_failed_steps()`

In `dashboard/routers/running.py`, modify `_query_failed_steps(db, project_id=None)` (lines ~132–190) so that the SQL `WHERE` clause additionally restricts to "currently active" `WorkItem` rows.

Add (after the existing `.where(WorkflowStep.status.in_([StepStatus.failed, StepStatus.needs_fix]))` predicate):

```python
.where(WorkItem.archived_at.is_(None))
.where(WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.cancelled]))
```

Add the import for `WorkItemStatus` from `orch.db.models` if it is not already imported in that file's import block. The existing imports already include `WorkItem`, so the join is reused — no new join is needed.

Use SQLAlchemy 2.0 idiom: `WorkItem.archived_at.is_(None)` (NOT `== None` — ruff/SQLAlchemy convention; see `orch/CLAUDE.md`).

### 2. Add the same predicate to `_query_recent_completions()`

In the same file, modify `_query_recent_completions(db, project_id=None)` (lines ~193–226) identically. The active-item condition has the same definition: not archived AND status not in (completed, cancelled).

### 3. Leave the running-now helpers UNCHANGED

`_query_running_now()` and `get_running_count()` are intentionally out of scope for this fix (see design doc → Notes). Do NOT touch them. If you believe they should be changed, raise a blocker — do not silently expand scope, because hiding an orphaned running step without also emitting a `daemon_event` warning could mask a real daemon defect.

### 4. Template is unchanged

`dashboard/templates/pages/system/running.html` does not need to change. The existing `{% for %}` block degrades to an empty `<tbody>` when there are no rows.

### 5. Do not modify any test file in this step

The Tests step (S03) owns all test additions. Your job here is the production code change only. The TDD RED evidence for this fix is owned by S03 — see the "TDD Requirement" section below.

## Project Conventions

Read the project's `CLAUDE.md`, `dashboard/CLAUDE.md`, and `orch/CLAUDE.md` for:

- Architecture patterns and layer boundaries (routers stay thin; helpers stay in the same file are OK)
- SQLAlchemy 2.0 idiom (`Mapped[]`, `is_(None)`, no `metadata` reserved-word collisions)
- The append-only contract on `step_runs` / `workflow_steps` (do NOT attempt to "fix" the data by rewriting step status on archive — that's explicitly NOT how this bug should be fixed)
- Conventional naming, import ordering, and ruff/mypy expectations

## TDD Requirement

This fix is a query-layer change whose RED-first test is owned by the dedicated Tests step (S03), not by this Backend step. The Tests-step prompt explicitly requires:

1. The first test added (e.g. `test_query_failed_steps_excludes_completed_item`) MUST fail against pre-S01 code with an `AssertionError`, then pass after S01's predicate is in place.
2. S03's report contains the RED-run snippet as `tdd_red_evidence`.

For this Backend step, your `tdd_red_evidence` field MUST be either:

- A snippet showing you ran one of the eventual Tests-step assertions manually against your in-progress branch and observed the predicate behave correctly (preferred), OR
- The literal string `"n/a — query-only filter; behavioural tests added in S03 (tests-impl); see S03 report for RED evidence"` (acceptable for this query-helper fix where the test surface lives in the next step).

Do NOT skip the RED phase entirely — at minimum, write a small inline reproduction in your shell (e.g. seed two items in a temp testcontainer-backed REPL session and call `_query_failed_steps()` before and after your change). Capture what you observed in your report `notes`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report.

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you
   touched. Errors elsewhere are pre-existing — note them in your report but
   do not ignore your own.
3. **`make lint`** — must report zero errors.

Populate the `preflight` object in the result contract recording each command's outcome.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full
test suite**. Full-suite execution is owned by the dedicated QV gate steps
downstream (`unit-tests`, `integration-tests`).

Targeted verification for this step:

```bash
# If a test file already exists when you run (it won't yet, because S03 hasn't run):
uv run pytest tests/dashboard/test_running_router_active_filter.py -v

# Otherwise, exercise the dashboard router quickly with a narrow unit test
# that already exists in the repo (e.g. an existing /system/running test):
grep -rln "_query_failed_steps\|_query_recent_completions\|/system/running" tests/ | head -5
# and run the narrowest match.
```

Do NOT run `make test-integration` or `make test-unit` — those are gates S11/S12 and will run with their own (longer) budgets.

## Migration Verification

N/A — this step generates NO migration.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/running.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "n/a — query-only filter; behavioural tests added in S03 (tests-impl); see S03 report for RED evidence",
  "blockers": [],
  "notes": "Optional: inline reproduction notes if you did one."
}
```

- `completion_status`: `complete` only when both helpers have the new predicate and the preflight gates are all `ok`/`fixed`.
- `files_changed`: should contain exactly `dashboard/routers/running.py`. If anything else appears, justify it in `notes`.
- `blockers`: raise if you believe the running-now helpers also need filtering (DO NOT silently expand scope).
