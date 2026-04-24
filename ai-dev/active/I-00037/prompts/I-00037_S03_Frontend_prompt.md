# I-00037_S03_Frontend_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step**: S03
**Agent**: Frontend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident requires no migration.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document
- `ai-dev/active/I-00037/reports/I-00037_S01_Backend_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S02_CodeReview_report.md`
- `dashboard/utils/batch_progress.py` -- Shared helper from S01
- `dashboard/routers/project_dashboard.py` -- Stale `_active_batches()` (line 137 is the target)
- `dashboard/routers/batches.py` -- Step-based `_all_batches()` from I-00036 (lines 213-226 are the target)
- `dashboard/templates/pages/project/dashboard.html` (read only; must NOT edit)
- `dashboard/templates/pages/project/batches.html` (read only)
- `dashboard/templates/fragments/batches_table_rows.html` (read only)

## Output Files

- `ai-dev/active/I-00037/reports/I-00037_S03_Frontend_report.md`

## Context

S01 produced the shared helper `compute_batch_step_progress()` under
`dashboard/utils/batch_progress.py`. You are wiring **both** dashboard
routers to call it so the two views lock to one source of truth.

Note: although the affected files are Python routers (not JS/HTML), this
step is classified as "Frontend" in the IW workflow because it targets the
dashboard presentation layer — the behaviour the end user sees on the home
page. The dashboard project is Jinja2 + htmx + Tailwind; there is no
separate React/TS tier.

Read `CLAUDE.md` and `dashboard/CLAUDE.md` first.

## Requirements

### 1. Wire `dashboard/routers/project_dashboard.py:_active_batches()`

Current code (lines ~87-147) does a grouped `SELECT` on `BatchItem` to compute
both `completed_items`/`total_items` AND `progress_pct` from item statuses.

Change:

- **Keep** the existing grouped `BatchItem` SELECT exactly as-is. Its output
  (`total`, `done`) feeds `completed_items` and `total_items` on
  `BatchSummary`. This is intentional — per the reporting user's explicit
  instruction, the Items display ("0/1") stays item-based.
- **Replace** the percentage computation at line ~137
  (`pct = int((done / total * 100) if total > 0 else 0)`) with a call to the
  shared helper:

  ```python
  from dashboard.utils.batch_progress import compute_batch_step_progress

  ...

  step_progress = compute_batch_step_progress(project_id, batch_ids, db)
  for batch in batches:
      total, done = counts.get(batch.id, (0, 0))
      pct = step_progress.get(batch.id, 0)
      result.append(
          BatchSummary(
              id=batch.id,
              status=batch.status.value,
              total_items=total,        # item-based, unchanged
              completed_items=done,     # item-based, unchanged
              progress_pct=pct,         # step-based, via shared helper
          )
      )
  ```

- Call the helper **once** per request (outside the Python `for` loop), passing
  the full `batch_ids` list — the helper is bulk by design. Do NOT call it per
  batch.

### 2. Wire `dashboard/routers/batches.py:_all_batches()`

Current code (lines 195-246, specifically 213-226) loads all `WorkflowStep`
rows for all work items in Python, then counts them in a comprehension.

Change:

- **Replace** that inline Python step-loading and counting with a single
  `compute_batch_step_progress(project_id, batch_ids, db)` call before the
  per-batch `for` loop.
- Inside the `for` loop, index the result dict: `pct = step_progress.get(batch.id, 0)`.
- `total_items` and `completed_items` stay as they are today (item-based,
  I-00036 already got that right).

Result: the net effect is a refactor — the batches view still shows the same
step-based percentages it shows now (94%, 42%, etc.), but via the shared
helper.

### 3. Do NOT

- Do NOT edit `dashboard/templates/pages/project/dashboard.html`.
- Do NOT edit `dashboard/templates/pages/project/batches.html`.
- Do NOT edit `dashboard/templates/fragments/batches_table_rows.html`.
- Do NOT change the `BatchSummary` or `BatchRow` dataclass shapes.
- Do NOT change the `data-sort-progress` behaviour (keep `progress_pct` as
  `int` on both dataclasses).
- Do NOT add tests — tests belong to S05.
- Do NOT edit `dashboard/utils/batch_progress.py` — S01 owns the helper.
  If you find a bug in the helper, raise a blocker instead of patching it
  here (the step boundary matters for the audit trail).

### 4. Performance

Both callers now run one extra aggregated query (the helper call) per page
request. That is acceptable — the dashboard home previously had only the
`BatchItem` grouped query; it picks up one more. The Batches view previously
loaded every `WorkflowStep` as ORM objects into Python — the refactor actually
reduces payload because the helper does the counting in SQL.

### 5. Manual smoke check

Before reporting complete, start a local dev session against a DB with at
least one mid-flight batch and visually confirm:

- `/project/{id}/` shows the same non-zero percentage for that batch that
  `/project/{id}/batches` shows.
- The "0/1 items" label on the home card is unchanged.

If the dev environment is unavailable, note it in the report — the S13
browser step will still catch any bug.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`:

- Thin routers — delegating to `dashboard/utils/` is the right pattern.
- Do NOT break the Jinja2 template variables (`batch.progress_pct`,
  `batch.completed_items`, `batch.total_items`, `batch.status`).
- Imports grouped as stdlib / third-party / project, each block alphabetical.

## TDD Requirement

Tests belong to S05. Run the existing dashboard tests to confirm no
regression:

- `make test-unit`
- `make lint`
- `make typecheck`

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` passes with zero failures.
2. `make lint` and `make typecheck` — no regressions.
3. Do **NOT** report `tests_passed: true` unless the above hold.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "I-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/project_dashboard.py",
    "dashboard/routers/batches.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Confirm: (a) templates untouched, (b) BatchSummary/BatchRow shapes unchanged, (c) helper invoked once per request (not in the loop), (d) completed_items/total_items still item-based in both routers, (e) smoke check outcome if a dev environment was available."
}
```
