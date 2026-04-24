# I-00037: Per-project dashboard still uses item-level batch progress after I-00036

**Type**: Issue
**Severity**: Low
**Created**: 2026-04-24
**Reported By**: sergio (operator observation immediately after I-00036 merge)
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

## ⛔ Migrations: agents generate, daemon applies

This incident requires **NO migration**. If your investigation surfaces a
schema change, STOP and raise a blocker. The `WorkflowStep`, `BatchItem`,
and `Batch` tables already contain everything you need.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

The per-project home page (`/project/{id}/`) "Active batches" card computes its
progress percentage from `BatchItem` counts (`completed+merged / total`), while
the Batches page (`/project/{id}/batches`) — fixed in I-00036 — now computes it
from `WorkflowStep` counts. The two views therefore disagree for the same
batch: on 2026-04-24, BATCH-00044 shows **0%** on the home page but **94%** on
the Batches page; BATCH-00043 shows **0%** vs **42%**. No functional flow is
broken, but the dashboard's primary landing view misrepresents batch progress.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Relevant pointers:

- `dashboard/CLAUDE.md` — routers are thin, business logic in `orch/`; shared
  dashboard helpers live under `dashboard/utils/`.
- `orch/CLAUDE.md` — ORM layer; `WorkflowStep` rows track per-step state.
- `tests/CLAUDE.md` — testcontainer rules, `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
  after `create_all()`, never mock the DB in integration tests.

## Browser Evidence

Pre-fix screenshots captured against the live dashboard (`http://localhost:9900`):

- `ai-dev/active/I-00037/evidences/pre/I-00037-dashboard-home-shows-0pct.png`
  — `/project/iw-ai-core/`: BATCH-00044 and BATCH-00043 both show "0% complete"
  on the Active Batches card.
- `ai-dev/active/I-00037/evidences/pre/I-00037-batches-view-shows-correct-pct.png`
  — `/project/iw-ai-core/batches`: the same two batches show 94% and 42%
  respectively in the Progress column.

Together they demonstrate the divergence: both pages render `batch.progress_pct`,
but the value is computed in two different places with two different formulas.

## Steps to Reproduce

1. Have at least one batch with status `executing` where the inner work-item(s)
   are mid-flight (several `WorkflowStep` rows completed but no `BatchItem` has
   yet reached `completed`/`merged`). The live DB contained BATCH-00044
   (94% of steps done, 0% of items done) and BATCH-00043 (42% / 0%) at the
   time of reporting.
2. Open `/project/{project_id}/` in the dashboard. Read the "Active batches"
   card's progress bar and "% complete" label.
3. Open `/project/{project_id}/batches` in the dashboard. Read the Progress
   column for the same batch.

**Expected**: Both pages show the same percentage, using the step-based formula
introduced by I-00036 (`done_steps / total_steps * 100`, with
`done_steps = count(status ∈ {completed, skipped})`).

**Actual**: The home page shows 0% (or a different lower value driven by
`completed_batch_items / total_batch_items`), while the Batches page shows the
correct step-based percentage. Users see inconsistent progress for the same
batch depending on which page they open.

## Browser Verification Script

To reproduce against the live environment (read-only, no writes):

```bash
playwright-cli kill-all
playwright-cli open "http://localhost:9900/project/iw-ai-core/"
playwright-cli screenshot --filename ai-dev/active/I-00037/evidences/pre/I-00037-dashboard-home-shows-0pct.png --full-page
playwright-cli open "http://localhost:9900/project/iw-ai-core/batches"
playwright-cli screenshot --filename ai-dev/active/I-00037/evidences/pre/I-00037-batches-view-shows-correct-pct.png --full-page
playwright-cli close
```

Post-fix verification runs in the isolated E2E stack (`$IW_BROWSER_BASE_URL`) —
see `prompts/I-00037_S13_BrowserVerification_prompt.md`.

## Root Cause Analysis

I-00036 fixed only `dashboard/routers/batches.py:_all_batches()`. The
per-project dashboard calls a **different** function in a different router:

`dashboard/routers/project_dashboard.py:_active_batches()` (lines 87-147) uses
a single aggregated SQL query grouped by `batch_id` that counts `BatchItem`
rows only:

```python
rows = db.execute(
    select(
        BatchItem.batch_id,
        func.count(BatchItem.id).label("total"),
        func.sum(
            func.cast(
                func.cast(
                    BatchItem.status.in_([BatchItemStatus.completed, BatchItemStatus.merged]),
                    Integer,
                ),
                Integer,
            )
        ).label("done"),
    )
    .where(BatchItem.project_id == project_id, BatchItem.batch_id.in_(batch_ids))
    .group_by(BatchItem.batch_id)
).all()
...
pct = int((done / total * 100) if total > 0 else 0)           # <-- line 137: item-level
```

No `WorkflowStep` join, so mid-item step progress is invisible.

I-00036's S01 Backend report noted the risk but incorrectly concluded that
`project_dashboard.py` would benefit automatically because it "uses the same
`_all_batches()` function" — it does not. It has its own query path. The bug
leaked through.

There is no shared helper today, which is *why* the two views drifted — future
changes will drift again if we only patch the second site without a shared
source of truth.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/routers/project_dashboard.py` — `_active_batches()` | Computes `progress_pct` from `BatchItem` counts (stale item-level formula). Must switch to the step-based formula introduced in I-00036. |
| `dashboard/routers/batches.py` — `_all_batches()` | Already step-based, but its Python-side step loop should be refactored to call the shared helper so both views are locked to one source of truth. |
| `dashboard/utils/` (new helper file) | Currently no shared progress helper. Fix introduces one so future routers cannot drift again. |
| `dashboard/templates/pages/project/dashboard.html:65-67` | Renders `batch.progress_pct`; no template change needed — value flows through. |
| `dashboard/templates/pages/project/batches.html` / `.../fragments/batches_table_rows.html` | Already render `batch.progress_pct` correctly after I-00036; must continue to show identical values after the refactor. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Create `dashboard/utils/batch_progress.py` with a **bulk step-based progress helper**: `compute_batch_step_progress(project_id, batch_ids, db) -> dict[str, int]` returning `{batch_id: progress_pct}`. Implementation uses one aggregated SQL query joining `WorkflowStep` on `BatchItem` (scoped by `project_id` + `batch_id ∈ batch_ids`): `SELECT BatchItem.batch_id, COUNT(WorkflowStep.id), SUM(CASE WHEN WorkflowStep.status IN (completed, skipped) THEN 1 ELSE 0 END) GROUP BY BatchItem.batch_id`. Return `0` for any batch with `total_steps == 0`. | — |
| S02 | CodeReview | Review S01 (SQL correctness, `project_id` scoping on BOTH BatchItem and WorkflowStep, done set = completed + skipped ONLY, no N+1, `dict` return covers all requested `batch_ids` — missing batches → `0`, type signatures, no business logic in router layer violations, `dashboard/utils/__init__.py` consistency) | — |
| S03 | Frontend | Wire both routers to the helper. (a) `project_dashboard.py:_active_batches()`: keep the existing item-level aggregation for `completed_items`/`total_items` (they drive the "Items" display), but replace line 137 `pct = ...` with a call to the shared helper for `progress_pct`. (b) `batches.py:_all_batches()`: replace the inline Python-side step loop (lines 213-226) with a call to the shared helper. Both routers pass their computed `batch_ids` list. Do NOT change `BatchSummary` / `BatchRow` shapes. Do NOT edit templates. | — |
| S04 | CodeReview | Review S03 (both callers use the helper, `completed_items`/`total_items` item-based preserved in both, no template edits, no dataclass shape changes, imports organised, existing query-optimisation patterns respected) | — |
| S05 | Tests | Reproduction test + regression tests — see Test to Reproduce / TDD Approach. MUST assert `_active_batches()[0].progress_pct == _all_batches()[0].progress_pct` for the same seeded batch (parity lock). | — |
| S06 | CodeReview | Review S05 (semantic assertions, parity assertion present, scenarios cover completed/skipped/failed/needs_fix/in_progress + empty/zero-steps, testcontainer compliance, no DB mocking) | — |
| S07 | CodeReview_Final | Global cross-layer review — both routers read from ONE source of truth; AC1..AC4 met; no shape-only assertions leaked | — |
| S08 | QV: lint | `make lint` | — |
| S09 | QV: format | `uv run ruff format --check .` | — |
| S10 | QV: typecheck | `make typecheck` | — |
| S11 | QV: unit-tests | `make test-unit` | — |
| S12 | QV: integration-tests | `make test-integration` | — |
| S13 | QV: browser verification | Seed partial-progress batch via `e2e_fixtures`, verify identical non-zero percentage on `/project/{id}/` AND `/project/{id}/batches` | — |

Agent slugs: `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration required. The fix is purely in router/helper code.

### Code Changes

- **Files to create**:
  - `dashboard/utils/batch_progress.py` — shared helper (S01)
- **Files to modify**:
  - `dashboard/routers/project_dashboard.py` — `_active_batches()` uses helper for `progress_pct` (S03)
  - `dashboard/routers/batches.py` — `_all_batches()` uses helper for `progress_pct` (S03)
  - `tests/dashboard/test_batches_progress_parity.py` (or equivalent canonical path chosen by Tests agent) — new reproduction + regression + parity tests (S05)
- **Nature of change**: Extract one bulk step-based progress query into a shared helper; both routers call it. Items column in both views stays item-level. No template or schema change.

## File Manifest

All files for this work item live under `ai-dev/active/I-00037/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00037_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00037_S01_Backend_prompt.md` | Prompt | S01 shared helper |
| `prompts/I-00037_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00037_S03_Frontend_prompt.md` | Prompt | S03 wire both routers |
| `prompts/I-00037_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00037_S05_Tests_prompt.md` | Prompt | S05 reproduction + regression + parity tests |
| `prompts/I-00037_S06_CodeReview_prompt.md` | Prompt | S06 review of S05 |
| `prompts/I-00037_S07_CodeReview_Final_prompt.md` | Prompt | S07 final cross-layer review |
| `prompts/I-00037_S13_BrowserVerification_prompt.md` | Prompt | S13 browser verification |
| `evidences/pre/I-00037-dashboard-home-shows-0pct.png` | Evidence | Pre-fix: dashboard home shows 0% |
| `evidences/pre/I-00037-batches-view-shows-correct-pct.png` | Evidence | Pre-fix: batches view shows correct % |

Reports are created during execution in `ai-dev/active/I-00037/reports/`.

Production files touched:

| File | Change |
|------|--------|
| `dashboard/utils/batch_progress.py` | Created |
| `dashboard/routers/project_dashboard.py` | `_active_batches()` calls shared helper |
| `dashboard/routers/batches.py` | `_all_batches()` calls shared helper |
| `tests/dashboard/test_batches_progress_parity.py` (canonical path at the Tests agent's discretion) | Added reproduction + regression + parity tests |

## Test to Reproduce

A failing test that would have FAILED against the current `project_dashboard.py`
and now passes.

```python
def test_I00037_dashboard_home_and_batches_view_agree_on_progress(
    db_session, seed_project
):
    """
    Given a batch with one item + 10 workflow steps, 3 of them `completed`,
    when both _active_batches() (dashboard home) and _all_batches() (batches view) run,
    then BOTH return progress_pct == 30 for the batch — same number, one source of truth.

    Pre-fix, _active_batches() returned 0 (item-level) while _all_batches() returned 30.
    """
    project_id = seed_project.id

    # One work item + 10 workflow steps (3 completed, 7 pending)
    wi = WorkItem(
        project_id=project_id,
        id="I-REPRO37",
        type=WorkItemType.incident,
        status=WorkItemStatus.in_progress,
        title="fixture",
    )
    db_session.add(wi)
    for n in range(1, 11):
        status = StepStatus.completed if n <= 3 else StepStatus.pending
        db_session.add(
            WorkflowStep(
                project_id=project_id,
                work_item_id=wi.id,
                step_id=f"S{n:02d}",
                step_number=n,
                agent_label="backend",
                step_type=StepType.implementation,
                status=status,
            )
        )

    # Batch + in-flight batch item
    batch = Batch(project_id=project_id, id="BATCH-REPRO37", status=BatchStatus.executing)
    db_session.add(batch)
    db_session.add(
        BatchItem(
            project_id=project_id,
            batch_id=batch.id,
            work_item_id=wi.id,
            execution_group=1,
            status=BatchItemStatus.in_progress,
        )
    )
    db_session.commit()

    dashboard_rows = _active_batches(project_id, db_session)
    batches_rows = _all_batches(project_id, db_session, status_filter=[])

    dash = next(r for r in dashboard_rows if r.id == batch.id)
    full = next(r for r in batches_rows if r.id == batch.id)

    # SEMANTIC — pin the expected numeric value (I003 lesson)
    assert dash.progress_pct == 30, f"dashboard home expected 30, got {dash.progress_pct}"
    assert full.progress_pct == 30, f"batches view expected 30, got {full.progress_pct}"
    # PARITY — the two views must NEVER disagree
    assert dash.progress_pct == full.progress_pct

    # Items column must stay item-level (per the reporting user's explicit instruction)
    assert dash.completed_items == 0
    assert dash.total_items == 1
    assert full.completed_items == 0
    assert full.total_items == 1
```

## Browser Verification Test

After the fix is applied to the isolated E2E stack, the qv-browser agent will:

1. Seed a batch with one work item of 10 steps, mark 3 completed (via `e2e_fixtures`).
2. Navigate to `$IW_BROWSER_BASE_URL/project/{id}/` (home) and read the Active Batches progress.
3. Navigate to `$IW_BROWSER_BASE_URL/project/{id}/batches` and read the Progress column for the same batch.
4. Assert BOTH render "30%" (±1% tolerance for rounding) — identical across the two views.
5. Capture post-fix screenshots for comparison with the pre-fix evidence pair.

Full script lives in `prompts/I-00037_S13_BrowserVerification_prompt.md`.

## Acceptance Criteria

### AC1: Bug is fixed — dashboard home shows step-based progress

```
Given a batch with work items whose WorkflowStep rows are partially completed
When I open /project/{id}/
Then the Active Batches card shows progress_pct computed from WorkflowStep counts
 And done_steps counts statuses ∈ {completed, skipped}
 And total_steps counts all WorkflowStep rows for all items in the batch
```

### AC2: Parity — the two views always agree

```
Given any batch in any state on any project
When both /project/{id}/ and /project/{id}/batches render
Then the progress_pct shown for that batch is identical on both pages
 And this is enforced by both routers reading from a single shared helper
```

### AC3: Items count unchanged

```
Given the fix is applied
When I view the Active Batches card on /project/{id}/
Then completed_items / total_items are still computed from BatchItem counts
 And the values match what was shown before the fix (item-level semantics preserved per the reporting user's explicit instruction)
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test from "Test to Reproduce" passes
 And additional regression tests cover: empty batch, zero steps, skipped counts,
     failed/needs_fix/in_progress do NOT count, multi-item aggregation, project_id scoping,
     parity between the two routers
```

### AC5: Zero-step batch renders 0%, not a crash

```
Given a batch whose work items have no WorkflowStep rows yet
When either router calls the helper
Then progress_pct is 0 (not NaN, no division by zero)
 And both pages render without error
```

## Regression Prevention

- The shared helper in `dashboard/utils/batch_progress.py` is the **single source
  of truth** for `progress_pct`. Any future router needing batch progress calls
  the same function — the drift that caused I-00037 becomes structurally harder
  to reintroduce.
- The parity test (`assert dash.progress_pct == full.progress_pct` on the same
  seeded batch) locks the two views together. Any future change that breaks
  parity will fail a test instead of silently shipping.
- The regression matrix covers the same status-classification edges as I-00036
  (`skipped` counts, `failed`/`needs_fix`/`in_progress` do NOT count) so the
  semantics of "done" are pinned in the helper, not re-derived by each caller.

## Dependencies

- **Depends on**: I-00036 (provides the step-based formula and the reference
  implementation in `batches.py:_all_batches()`, which S03 refactors into the
  helper call).
- **Blocks**: None.

## TDD Approach

- **Reproducing test**: `test_I00037_dashboard_home_and_batches_view_agree_on_progress` — as shown above. Pins `30` on both routers AND asserts parity.
- **Unit tests** (drive the helper directly with seeded data; no HTTP):
  - Single batch, 10 steps, 3 done → `30`.
  - Single batch, 10 steps, all done → `100`.
  - Single batch, 0 steps → `0` (edge, no divide-by-zero).
  - Multi-batch: batches {A: 1/10 done, B: 5/10 done, C: 0 steps} → `{A: 10, B: 50, C: 0}`.
  - `skipped` counts as done; `failed` / `needs_fix` / `in_progress` / `pending` do NOT.
  - Helper respects `project_id` scoping: a step row with `project_id != requested` must NOT be counted.
  - Helper returns `0` for a requested `batch_id` with no rows (missing batch).
- **Integration tests** (drive both routers end-to-end): call `_active_batches()` and `_all_batches()` on the same seeded session and assert both return the same non-zero `progress_pct` (the parity lock — mirrors AC2).
- **HTTP smoke test** (via `TestClient`): one request each to `/project/{id}/` and `/project/{id}/batches`, assert both rendered HTML contain the same expected percentage substring.

## Notes

- Per the reporting user's explicit instruction: **only `progress_pct` changes on
  the dashboard**. The `completed_items` / `total_items` fields on
  `BatchSummary` stay item-based (they feed the "0/1 items" label on the Active
  Batches card). The template at
  `dashboard/templates/pages/project/dashboard.html:65-67` is not edited.
- I-00036's note in the design — "verify during the fix whether the same
  calculation is duplicated there; if so, fix both (or refactor to a shared
  helper)" — was correct but the agent didn't follow through. I-00037 resolves
  both the data bug and the underlying drift risk by extracting the helper.
- The helper lives under `dashboard/utils/` per the project's convention
  ("shared dashboard helpers live under `utils/`", `dashboard/CLAUDE.md`) —
  both consumers are dashboard routers and the concern is presentation-layer,
  so `orch/` is not the right home.
- Severity is **Low** — cosmetic inconsistency, no data loss, no blocked
  workflow. Users currently work around it by opening the Batches view to see
  the correct number.
