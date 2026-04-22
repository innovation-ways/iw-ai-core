# I-00034: Item view step Duration is incorrect when a step goes through retries or fix cycles

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-22
**Reported By**: sergio (user report)
**Status**: Draft

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

## Description

On the Item detail page in the dashboard, the per-step **Duration** column and the header **Total Time** card understate the wall-clock time of steps that went through retries or fix cycles. A step that actually took 15 minutes across three fix cycles displays as "20s" or "30s" because the displayed duration reflects only the final successful iteration. The time spent in prior failed runs, daemon poll gaps, fix-prompt generation, and setup is invisible — which silently destroys the operational value of the metric for exactly the items operators most care about (slow, flaky, retry-prone steps).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant modules: `dashboard/routers/items.py` (the Item view), `orch/db/models.py` (ORM — `WorkflowStep`, `StepRun`, `FixCycle`), `dashboard/templates/fragments/item_overview.html` and `item_header.html` (where duration is rendered). No DB schema changes are required; this is a read-side fix. Testcontainers-only for DB-touching tests; no live-DB connections.

## Browser Evidence

Browser evidence capture is **deferred** — reproducing the bug visually requires an existing item with ≥1 fix cycle in its history and a running dashboard. Evidence will be produced during the QV browser step (S11) using an `e2e_fixtures/` seed file that synthesises a work item with multi-run step_runs and fix_cycles. The synthetic seed will allow side-by-side pass/fail comparison on the isolated E2E stack.

Evidence folder: `ai-dev/active/I-00034/evidences/pre/` (empty — deferred as documented above).

## Steps to Reproduce

1. Pick any completed work item whose history includes at least one step that ran through ≥1 fix cycle (`fix_cycles` row count ≥ 1 for that step), OR seed one via the `e2e_fixtures` mechanism.
2. Open the Item detail page: `http://localhost:9900/project/{project_id}/item/{item_id}`.
3. In the Overview tab, locate the step that had fix cycles. Note the displayed **Duration** cell for that step, and the **Total Time** metric card at the top.
4. Cross-reference the same step against `step_runs` in the DB: `SELECT MIN(started_at), MAX(completed_at) FROM step_runs WHERE step_id = X UNION ALL SELECT MIN(started_at), MAX(completed_at) FROM fix_cycles WHERE step_id = X`.

**Expected**: The step's Duration equals `MAX(step_runs.completed_at, fix_cycles.completed_at) - MIN(step_runs.started_at, fix_cycles.started_at)` — the full wall-clock span from first attempt to last completion, including the gaps where the step waited for the next daemon poll, fix-prompt generation, or fix-agent launch. The Total Time card equals the span across all steps on the same basis.

**Actual**: Duration shows only the final successful iteration's wall time (often "20s" / "30s" / "1m10s") — orders of magnitude smaller than the true span. Total Time, computed from the same per-step timestamps, is correspondingly compressed.

## Browser Verification Script

The QV Browser step (S11) will execute the verification against the isolated E2E stack. The verification script lives in the S11 prompt (`prompts/I-00034_S11_BrowserVerification_prompt.md`) and depends on an `e2e_fixtures` seed file that plants a synthetic work item with multi-run history. Outline:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/<project-id>/item/<seeded-item-id>"
playwright-cli snapshot
playwright-cli screenshot --filename ai-dev/active/I-00034/evidences/post/I-00034_v1_step_duration.png
# Verify: Duration cell for the retry-prone step equals the expected aggregate
# (compare to the known values baked into the seed fixture).
```

See S11 prompt for full per-verification detail.

## Root Cause Analysis

The dashboard's Item view reads step Duration from `WorkflowStep.started_at` / `WorkflowStep.completed_at` — but those two columns are overwritten (and reset to `NULL`) every time a step is retried or enters a fix cycle. The canonical, preserved timeline lives in the append-only `step_runs` and `fix_cycles` tables, which the dashboard does not consult for this computation.

**Reset sites** (`step.started_at`/`completed_at` → `None`):

- `orch/daemon/fix_cycle.py:201-202` — retry path (`retry_step`) resets the step back to `pending`.
- `orch/daemon/fix_cycle.py:258-259` — fix-cycle entry path (`attempt_fix_cycle`) transitions `failed → needs_fix`.
- `orch/daemon/fix_cycle.py:406-407` — post-fix reset when the fix agent succeeds and the step is re-queued.
- `orch/cli/step_commands.py:501-502` — `iw step-restart` (manual one-step restart).
- `orch/cli/step_commands.py:607-608` — `iw step-restart-from` (restart-from-step).

**Re-set site** (new `step.started_at` each launch):

- `orch/cli/step_commands.py:204` — `iw step-start` sets `step.started_at = datetime.now(UTC)` on every agent launch.
- `orch/daemon/batch_manager.py:535` — daemon sets `step.started_at = now` when launching the step.

**Read sites** (the bug surfaces):

- `dashboard/routers/items.py:334-336` — per-step duration:
  ```python
  dur: float | None = None
  if step.started_at and step.completed_at:
      dur = (step.completed_at - step.started_at).total_seconds()
  ```
- `dashboard/routers/items.py:364-369` — item-level total duration, computed from `min(step.started_at)` / `max(step.completed_at)` across steps — inherits the same truncated timestamps.

**Why append-only tables save us**: `step_runs` and `fix_cycles` are documented as append-only (see `orch/db/models.py:517` comment and `orch/CLAUDE.md`). Every retry appends a new `StepRun` row with its own `started_at` / `completed_at`; every fix cycle appends a `FixCycle` row with its own timestamps. The full history is intact — the dashboard just has to read it.

**Why the current code is structured this way**: `WorkflowStep.started_at` / `completed_at` are used by other call sites for "most recent activity" semantics (e.g. age-sorting pending/in-progress steps). Changing their semantics would have wide blast radius. The minimal, correct fix is to change the **read path** in the Item view to aggregate from `step_runs` + `fix_cycles`. No schema change, no daemon change.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Dashboard Item router — per-step duration | `dashboard/routers/items.py` (`_get_steps`, ~line 334) | Displays last-iteration wall time instead of first-start-to-last-complete span |
| Dashboard Item router — total duration metric | `dashboard/routers/items.py` (`_get_metrics`, ~line 364) | Inherits the same truncation via `min(started_at)` / `max(completed_at)` over already-truncated per-step timestamps |
| Overview pipeline + step table template | `dashboard/templates/fragments/item_overview.html` | Renders the truncated `step.duration_secs` in two places (pipeline tooltip row + table column) |
| Item header metric card | `dashboard/templates/fragments/item_header.html` | Renders the truncated `metrics.total_duration_secs` in the "Total Time" card |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | `dashboard/routers/items.py` — change `_get_steps` and `_get_metrics` to compute duration from `MIN(started_at)` across `step_runs` ∪ `fix_cycles` through `MAX(completed_at)` (or `now` if step is in-flight). Bulk-query to avoid N+1 (aggregate per-step with a single `GROUP BY step_id` query). | — |
| S02 | CodeReview_Backend | Review S01 | — |
| S03 | Tests | Reproduction test + regression tests exercising multi-run / fix-cycle timelines | — |
| S04 | CodeReview_Tests | Review S03 — enforce semantic correctness (specific duration values, not just `> 0`) | — |
| S05 | CodeReview_Final | Global review — no regressions to synthetic setup/merge rows, in-progress behaviour still live-ticks, AC1–AC5 coverage | — |
| S06 | QV: lint | `make lint` | — |
| S07 | QV: format | `uv run ruff format --check .` | — |
| S08 | QV: typecheck | `uv run mypy orch/ dashboard/` | — |
| S09 | QV: unit-tests | `make test-unit` | — |
| S10 | QV: integration-tests | `make test-integration` | — |
| S11 | QV: browser | Verify on E2E stack that a synthetic item with multi-run history shows the aggregated duration | — |

Agent slugs: `backend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None. The fix is purely a read-side change in `dashboard/routers/items.py`. No ORM model changes, no column additions, no Alembic migration.

### Code Changes

- **Files to modify**:
  - `dashboard/routers/items.py` — `_get_steps` and `_get_metrics` (duration computation)
  - `tests/integration/dashboard/` — new test file(s) for the Item view duration aggregation (exact path to be chosen by the Tests agent consistent with `tests/CLAUDE.md`)
- **Files NOT to modify**:
  - `orch/daemon/fix_cycle.py` — keep the existing reset behaviour; other call sites depend on "most recent activity" semantics of `step.started_at`.
  - `orch/cli/step_commands.py` — same rationale.
  - `orch/db/models.py` — no column additions (append-only tables already carry the truth).
  - Templates — the Jinja templates already render `step.duration_secs` / `metrics.total_duration_secs`; the fix flows through the existing fields. The Item view's step table renders `—` for in-progress rows (no live-ticker on this page) — unchanged.
- **Nature of change**:
  - Introduce a small helper (in `dashboard/routers/items.py` or a sibling `_duration_helpers.py` — agent's call) that, given a list of `WorkflowStep` DB ids, returns `dict[int, tuple[datetime | None, datetime | None]]` mapping step_id → `(earliest_started, latest_completed)` aggregated across `step_runs` ∪ `fix_cycles`.
  - Use bulk `SELECT step_id, MIN(started_at), MAX(completed_at) FROM step_runs WHERE step_id IN (...) GROUP BY step_id` (+ the analogous query for `fix_cycles`), then combine in Python. ONE query per table, not one-per-step — N+1 is forbidden per `tests/CLAUDE.md` conventions.
  - For in-progress steps (no `MAX(completed_at)`), fall through so the existing `duration.js` live-ticker drives the display (current behaviour).
  - For steps that never started (no rows in either table), duration is `None` (current behaviour preserved).

## File Manifest

All files for this work item live under `ai-dev/active/I-00034/`.

| File | Type | Purpose |
|------|------|---------|
| `I-00034_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00034_S01_Backend_prompt.md` | Prompt | Backend fix — duration aggregation in Item router |
| `prompts/I-00034_S02_CodeReview_Backend_prompt.md` | Prompt | Per-agent review of S01 |
| `prompts/I-00034_S03_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00034_S04_CodeReview_Tests_prompt.md` | Prompt | Per-agent review of S03 |
| `prompts/I-00034_S05_CodeReview_Final_prompt.md` | Prompt | Global final review |
| `prompts/I-00034_S11_BrowserVerification_prompt.md` | Prompt | QV browser verification on E2E stack |
| `e2e_fixtures/001_i00034_retry_history.py` | Seed fixture | Created during S11 — synthetic item with multi-run step_runs and fix_cycles so the E2E stack can render the fix end-to-end |

Implementation files touched (created/modified at execution time — not pre-created):

| File | Created By | Type | Purpose |
|------|-----------|------|---------|
| `dashboard/routers/items.py` | S01 | Modified | `_get_steps` + `_get_metrics` use aggregated timestamps from `step_runs` ∪ `fix_cycles` |
| `tests/integration/dashboard/test_items_duration.py` (or existing file) | S03 | New/Modified | Reproduction + regression tests |

Reports are written during execution under `ai-dev/active/I-00034/reports/`.

## Test to Reproduce

The reproducing test lives in the integration test suite (requires the PostgreSQL testcontainer to exercise real `MIN`/`MAX` aggregation with `step_runs` and `fix_cycles`). It must FAIL against the current `dashboard/routers/items.py` and PASS after S01's fix.

```python
# tests/integration/dashboard/test_items_duration.py (sketch; exact layout per tests/CLAUDE.md)

from datetime import UTC, datetime, timedelta

def test_I00034_step_duration_spans_first_run_to_last_completion(
    db_session,
    project_factory,
    work_item_factory,
    workflow_step_factory,
    step_run_factory,
    fix_cycle_factory,
):
    """I-00034: step duration must include ALL retries + fix cycles, not just the last run."""
    # Arrange: one workflow step that went through: run1 (failed) -> fix cycle -> run2 (success)
    project = project_factory()
    item = work_item_factory(project_id=project.id)
    step = workflow_step_factory(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        # These timestamps reflect the LAST iteration only (current buggy state)
        started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),  # last run = 30s
        status="completed",
    )
    # First failed attempt: 12:00:00 -> 12:02:00 (2 minutes)
    step_run_factory(
        step_id=step.id,
        run_number=1,
        status="failed",
        started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 22, 12, 2, 0, tzinfo=UTC),
    )
    # Fix cycle: 12:03:00 -> 12:09:00 (6 minutes — fix agent ran)
    fix_cycle_factory(
        step_id=step.id,
        cycle_number=1,
        started_at=datetime(2026, 4, 22, 12, 3, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 22, 12, 9, 0, tzinfo=UTC),
        status="completed",
    )
    # Final successful run: 12:10:00 -> 12:10:30 (30s)
    step_run_factory(
        step_id=step.id,
        run_number=2,
        status="completed",
        started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
    )

    # Act: call the Item router's step fetcher
    from dashboard.routers.items import _get_steps
    steps = _get_steps(project.id, item.id, db_session)

    # Assert: semantic — the real duration is 10m30s (from 12:00:00 to 12:10:30),
    # NOT the 30s shown by the buggy code.
    target = next(s for s in steps if s.step_id == step.step_id)
    assert target.duration_secs == pytest.approx(10 * 60 + 30)  # 630 seconds
    # Also verify it INCLUDES the between-iteration gap (not just sum of run+cycle wall times)
    assert target.duration_secs > 2 * 60 + 6 * 60 + 30  # > sum of run1+cycle+run2
```

The Tests agent (S03) is responsible for adapting this to the actual fixture idioms in `tests/CLAUDE.md` and adding the `_get_metrics` total-duration companion case.

## Browser Verification Test

The QV Browser step (S11) verifies the fix end-to-end on the isolated E2E stack. Because the E2E stack starts from a fresh DB with only the baseline seed (no fix-cycle history), S11 installs an `e2e_fixtures/` file that seeds a synthetic work item with the same multi-run / fix-cycle shape as the integration test above. The verification then:

1. Navigates to `$IW_BROWSER_BASE_URL/project/<seeded-project>/item/<seeded-item>` and asserts the Duration cell for the retry-prone step matches the expected aggregate (e.g. `10m30s`, not `30s`), and the Total Time card includes the full span.
2. Navigates to a neighbouring item that did NOT retry, and asserts its Duration is unchanged (no regression on the happy path).
3. Captures screenshots in `evidences/post/`.

Full script lives in `prompts/I-00034_S11_BrowserVerification_prompt.md`.

## Acceptance Criteria

### AC1: Per-step duration spans first attempt to last completion

```
Given a completed workflow step whose history has N ≥ 2 step_runs and/or ≥ 1 fix_cycles
When the Item detail page is rendered
Then the step's Duration equals MAX(completed_at across step_runs ∪ fix_cycles) minus MIN(started_at across step_runs ∪ fix_cycles)
And this includes the gaps between runs (daemon poll waits, fix prompt generation)
```

### AC2: Total Time metric card spans first-step-start to last-step-end correctly

```
Given a work item with at least one step that went through fix cycles
When the Item detail page is rendered
Then the "Total Time" metric card equals MAX(last-step's aggregated completed_at) minus MIN(first-step's aggregated started_at)
And the metric is consistent with the sum of the per-step durations, adjusted only for genuine gaps between steps
```

### AC3: In-progress steps render unchanged

```
Given a step that is currently in_progress (at least one step_runs or fix_cycles row has started_at but no completed_at)
When the Item detail page is rendered
Then duration_secs is None and the template renders "—" in the Duration cell (item_overview.html:68-76)
And the "Started" column shows the aggregated earliest started_at (a display improvement), not the last-iteration start
And no template is modified (the fix is router-only)
```

### AC4: Happy-path steps (single run, no retries) show identical duration to before

```
Given a step that ran exactly once and succeeded
When the Item detail page is rendered
Then the Duration cell shows the same value it showed before this fix
And no regression is observed for items with no fix cycles
```

### AC5: Bug is fixed + regression test exists

```
Given the reproducing test from tests/integration/dashboard/
When the test suite runs against the fixed code
Then the reproducing test PASSES
And the same test FAILS against the pre-fix code (proof of RED phase)
```

## Regression Prevention

- **Test coverage**: The new integration test explicitly asserts semantic equality against a precomputed expected duration — not `> 0`, not shape-only — so any future regression that accidentally reverts to reading `WorkflowStep.started_at` / `completed_at` directly will trip the test.
- **Query-count assertion**: The test asserts the new aggregation runs at most `k` SQL statements regardless of step count (bulk `GROUP BY`), preventing an innocent "fix" from becoming an N+1.
- **Comment anchor**: S01 leaves a one-line comment on the new aggregation helper pointing back to I-00034, so future readers understand why the Item view deliberately does NOT trust `WorkflowStep.started_at` / `completed_at`.
- **No schema change required**: By resolving this at the read path rather than by adding a `first_started_at` column, we avoid two failure modes — forgetting to populate the new column on one of the many reset paths, and requiring a migration + backfill for existing rows.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: `tests/integration/dashboard/test_items_duration.py::test_I00034_step_duration_spans_first_run_to_last_completion` — fails on the current code, passes after S01.
- **Unit tests**: A unit test for the pure aggregation helper introduced in S01 (takes a list of `(started_at, completed_at)` tuples across runs + cycles and returns `(min_start, max_end)`). Exercises: empty input → `(None, None)`; all runs completed → correct span; in-progress run (completed_at is None) → correct partial span; mixed nulls on cycles.
- **Integration tests**: The reproducing test above, plus a companion `test_I00034_total_duration_spans_full_item` exercising `_get_metrics` on the same fixture shape; plus a `test_I00034_happy_path_no_retries_duration_unchanged` asserting no regression for single-run items.

## Notes

- **Scope is deliberately narrow**: read-side only. We are *not* proposing to change the daemon's behaviour of resetting `step.started_at` on retry. Other consumers of `WorkflowStep.started_at` expect "most recent activity" semantics; changing that would widen the blast radius beyond what this bug justifies.
- **"Wait for next daemon run" time is included for free**: because the gap between `StepRun[i].completed_at` and `StepRun[i+1].started_at` sits between the two rows' own timestamps, taking `MIN(started_at)` to `MAX(completed_at)` naturally absorbs the poll-interval wait — no special handling needed.
- **Synthetic setup/merge rows**: `_get_steps` prepends `_synthetic_setup_step(bi)` and appends `_synthetic_merge_step(bi)`. These derive their duration from `BatchItem` timestamps, not `WorkflowStep` — they are untouched by this fix and must remain so.
- **Timezone handling**: `step_runs.started_at` and `fix_cycles.started_at` are `TIMESTAMPTZ`; the existing code already subtracts them with `.total_seconds()`. The helper preserves UTC arithmetic.
