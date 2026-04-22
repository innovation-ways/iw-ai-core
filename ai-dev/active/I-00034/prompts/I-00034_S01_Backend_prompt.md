# I-00034_S01_Backend_prompt

**Work Item**: I-00034 -- Item view step Duration is incorrect when a step goes through retries or fix cycles
**Step**: S01
**Agent**: Backend

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

## Input Files

- `ai-dev/active/I-00034/I-00034_Issue_Design.md` -- Design document (read the **Root Cause Analysis** and **Code Changes** sections first)
- `dashboard/routers/items.py` -- current implementation (the file you will modify)
- `orch/db/models.py` -- ORM definitions for `WorkflowStep`, `StepRun`, `FixCycle`
- `dashboard/CLAUDE.md` and `orch/CLAUDE.md` -- layer conventions
- `tests/CLAUDE.md` -- N+1 rules, testcontainer rules

## Output Files

- Modified: `dashboard/routers/items.py`
- New (optional): `dashboard/routers/_duration_helpers.py` if the aggregation helper warrants its own module (agent's call — do NOT create for a single trivial function)
- `ai-dev/active/I-00034/reports/I-00034_S01_Backend_report.md` -- Step report

## Context

You are fixing a **read-side bug** in the dashboard's Item view. The per-step **Duration** column and the header **Total Time** metric card are reading `WorkflowStep.started_at` / `WorkflowStep.completed_at`, but those two columns are reset to `NULL` every time a step is retried or enters a fix cycle and then re-set on the next launch. As a result, a step that actually took 15 minutes across three fix cycles displays as "20s" or "30s".

The **append-only** `step_runs` and `fix_cycles` tables preserve the full timeline. Your fix is to change the read path in `dashboard/routers/items.py` to compute duration from `MIN(started_at)` across `step_runs ∪ fix_cycles` through `MAX(completed_at)` across the same.

**DO NOT change** `WorkflowStep.started_at` / `completed_at` semantics, the daemon reset logic, the ORM schema, or anything in `orch/daemon/` or `orch/cli/`. Other consumers depend on the "most recent activity" semantics — changing them is out of scope.

Read `ai-dev/active/I-00034/I-00034_Issue_Design.md` end-to-end before touching code. Then read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`.

## Requirements

### 1. Fix `_get_steps` — per-step duration aggregation

Current code (approximately `dashboard/routers/items.py:322-356`) loops over `workflow_steps`, fetches `StepRun`s for each step one-by-one, and computes `dur = (step.completed_at - step.started_at).total_seconds()`.

Change the duration computation so that for each step:

- `earliest_started_at` = `MIN(started_at)` across `step_runs` where `step_id = step.id` ∪ `fix_cycles` where `step_id = step.id`
- `latest_completed_at` = `MAX(completed_at)` across the same two sets
- If `earliest_started_at` is `None` (step never launched), `duration_secs = None` (unchanged from today).
- If `earliest_started_at` is set but `latest_completed_at` is `None` (step is still in-flight — at least one row has `started_at` but no `completed_at`), `duration_secs = None` so the existing client-side `duration.js` live-ticker owns the display (current behaviour). The returned `StepDetail.started_at` for the row must be `earliest_started_at` so the live-ticker computes the right elapsed time.
- Otherwise, `duration_secs = (latest_completed_at - earliest_started_at).total_seconds()`.

**N+1 is forbidden.** You MUST issue at most **two** aggregation queries total for the entire `_get_steps` call, regardless of how many workflow steps the item has:

```python
# Pseudocode
step_db_ids = [s.id for s in workflow_steps]
run_spans = dict(db.execute(
    select(StepRun.step_id, func.min(StepRun.started_at), func.max(StepRun.completed_at))
    .where(StepRun.step_id.in_(step_db_ids))
    .group_by(StepRun.step_id)
).all())
cycle_spans = dict(db.execute(
    select(FixCycle.step_id, func.min(FixCycle.started_at), func.max(FixCycle.completed_at))
    .where(FixCycle.step_id.in_(step_db_ids))
    .group_by(FixCycle.step_id)
).all())
# Combine per step_id in Python (guard None carefully)
```

The existing per-step `runs` fetch (used for `last_run.error_message`, `run_count`) remains — do not remove it. Do not loop it into the aggregation.

The **StepDetail** dataclass's `started_at` field should surface the aggregated `earliest_started_at` (not `step.started_at`). This ensures the "Started" column in the Item table reflects the true first-launch time. `completed_at` should surface `latest_completed_at`.

### 2. Fix `_get_metrics` — total_duration_secs

Current code (approximately `dashboard/routers/items.py:361-392`) computes `total_dur = (max(completed_ats) - min(started_ats)).total_seconds()` from the per-step `StepDetail.started_at` / `completed_at` values.

Because you're already surfacing the aggregated `earliest_started_at` / `latest_completed_at` on each `StepDetail` (per Requirement 1), this function becomes correct automatically — provided you pull from the corrected `StepDetail` fields.

Verify the following behaviours:

- `total_duration_secs` covers **synthetic setup** (BatchItem.started_at) on the low end and **synthetic merge** on the high end when those are present — their `started_at`/`completed_at` come from `_synthetic_setup_step` / `_synthetic_merge_step` and are NOT touched by this change. The `min`/`max` over the list continues to absorb them correctly.
- If no step has a `started_at` yet, `total_duration_secs` remains `None`.

### 3. In-progress rows behave exactly as before

The Item view's step table (`dashboard/templates/fragments/item_overview.html:68-76`) does NOT live-tick: when `step.duration_secs is None` it simply renders `—`. There is no `data-started-at` attribute on these rows (the live-ticker in `dashboard/static/duration.js` is used by `running_table.html` and `step_row.html`, not by the Item view).

Therefore, for this fix:

- For an in-progress step (at least one `step_runs` or `fix_cycles` row has `started_at` but `completed_at` is `NULL`), `duration_secs = None` — the template will render `—`, unchanged from before.
- `StepDetail.started_at` should still be the aggregated earliest start (so the "Started" column in the step table shows the true first-launch time, not the last-iteration start). This is a display improvement, not a correctness requirement for live-ticking.

Do **not** touch `item_overview.html`, `item_header.html`, or `duration.js`. The fix is router-only.

### 4. Do NOT touch

- `orch/daemon/fix_cycle.py` — keep the reset logic
- `orch/cli/step_commands.py` — keep `step.started_at = datetime.now(UTC)` on each launch
- `orch/db/models.py` — no new columns, no new indexes (the bulk `GROUP BY` is run per-request and the existing `idx_step_runs_step` index on `step_id` already supports it)
- `_synthetic_setup_step` and `_synthetic_merge_step` helpers — keep as-is
- The dashboard templates `item_overview.html` / `item_header.html` unless Requirement 3 forces it

### 5. Report helper, if one

If you extract an aggregation helper, keep it small, pure (takes `db: Session` + `step_db_ids: list[int]`, returns `dict[int, tuple[datetime | None, datetime | None]]`), and unit-testable. The Tests agent (S03) will write a unit test for it. If the helper fits cleanly as a small private function inside `items.py`, that's fine — do NOT create a new file just to host five lines of code.

### 6. One-line comment anchor

At the aggregation call site, leave a single short comment explaining why the Item view does NOT trust `WorkflowStep.started_at` / `completed_at` — point to `I-00034`. Example:

```python
# I-00034: WorkflowStep.started_at/completed_at reflect only the LAST iteration
# (daemon resets them on retry/fix-cycle). Aggregate from append-only step_runs ∪ fix_cycles.
```

One line of comment is enough — do not over-document.

## Project Conventions

Read the project's `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md` for:

- Layer boundaries: routers stay thin — most logic in the router is fine because this is a small read-side aggregation. Do NOT push logic into `orch/` just for the sake of layering.
- SQLAlchemy 2.0 style (`select(...)`, `db.execute(...).all()`), sync sessions.
- Testcontainers-only for DB tests (S03's concern, not yours, but note the constraint).
- N+1 is forbidden for dashboard routes (see `tests/CLAUDE.md`).

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write a failing test **first** that demonstrates the bug for the `_get_steps` function. Seed a step with multiple `StepRun`s + a `FixCycle` such that the last run is 30s but the true span is 10m30s. Assert `duration_secs == pytest.approx(630)`.
2. **GREEN**: Implement the aggregation in `_get_steps` and `_get_metrics`. Run the test — it must pass.
3. **REFACTOR**: If the aggregation reads awkwardly, extract the helper described in Requirement 5. Do NOT refactor `_get_batch_item`, `_read_report_file`, or any unrelated helper.

**Do not skip the RED phase.** If the failing test is written but S03 is the canonical owner of the reproduction test, write a minimal RED test in your own scratch location to prove your change moves the needle, then delete it and let S03 own the committed test. Record in your report that you did this.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — all pre-existing unit tests must still pass
2. Run `make test-integration` — all pre-existing integration tests must still pass
3. Run `make lint` — zero errors
4. Run `uv run mypy orch/ dashboard/` — zero errors on the files you touched
5. Do NOT report `tests_passed: true` unless all of the above succeed

If a pre-existing test fails that touches `_get_steps` or `_get_metrics`, it likely encoded the buggy behaviour — read it carefully. If its assertion is semantic-but-wrong (e.g. asserts the last-iteration value), update it with a comment explaining why. If it's shape-only, leave it alone.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00034",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

- `completion_status`: Use `complete` when `_get_steps` AND `_get_metrics` are both fixed AND all tests still pass.
- `notes`: Record whether you extracted a helper, any template tweak you had to make for Requirement 3, and the query count of the new aggregation (should be exactly 2 for the step-span aggregation).
