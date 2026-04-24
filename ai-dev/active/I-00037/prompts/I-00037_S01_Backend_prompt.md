# I-00037_S01_Backend_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: read-only `docker ps/inspect/logs`, testcontainers spun up by
pytest fixtures, `./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident requires **NO migration**. If a schema change surfaces, STOP and
raise a blocker. `WorkflowStep`, `BatchItem`, and `Batch` already contain
everything you need.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document
- `ai-dev/active/I-00037/evidences/pre/I-00037-dashboard-home-shows-0pct.png` -- Pre-fix screenshot (dashboard home showing 0%)
- `ai-dev/active/I-00037/evidences/pre/I-00037-batches-view-shows-correct-pct.png` -- Pre-fix screenshot (batches view showing 94%)
- `dashboard/routers/batches.py` -- Reference implementation (I-00036 step-based calc at lines 213-226)
- `dashboard/routers/project_dashboard.py` -- Stale item-based calc at line 137 (will be rewired in S03, not here)
- `orch/db/models.py` -- `Batch`, `BatchItem`, `WorkflowStep`, `StepStatus`, `BatchItemStatus`

## Output Files

- `dashboard/utils/batch_progress.py` -- New shared helper (created this step)
- `ai-dev/active/I-00037/reports/I-00037_S01_Backend_report.md` -- Step report

## Context

The per-project home (`/project/{id}/`) and the Batches view
(`/project/{id}/batches`) currently compute batch `progress_pct` in two
different places with two different formulas. I-00036 fixed only the second
site. This step extracts a **single source of truth** so S03 can wire both
routers to it.

**You are ONLY creating the helper in this step.** Do NOT edit
`project_dashboard.py` or `batches.py` — that is S03's job. Your sole output
is a new file `dashboard/utils/batch_progress.py` and a report.

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, and `orch/CLAUDE.md` before touching
code.

## Requirements

### 1. Create `dashboard/utils/batch_progress.py`

Public API:

```python
from collections.abc import Sequence
from sqlalchemy.orm import Session

def compute_batch_step_progress(
    project_id: str,
    batch_ids: Sequence[str],
    db: Session,
) -> dict[str, int]:
    """
    Return {batch_id: progress_pct} for each requested batch.

    progress_pct = round(done_steps / total_steps * 100) as an int in [0, 100],
    where:
      - total_steps = count of WorkflowStep rows for all work items
        referenced by BatchItems of the batch, scoped to project_id.
      - done_steps  = count of those WorkflowStep rows with status in
        {StepStatus.completed, StepStatus.skipped}.

    Batches with no steps (empty batch, or items with no WorkflowStep rows yet)
    map to 0. Any requested batch_id not present in the DB also maps to 0 —
    the caller can iterate its own batch list and index into the dict without
    handling KeyError.
    """
```

### 2. Implementation: ONE aggregated SQL query, not a Python loop

Use a single SQLAlchemy `select()` joining `WorkflowStep` on `BatchItem`,
grouped by `BatchItem.batch_id`. Example shape (adjust to match SA 2.0 style
already in use in the repo):

```python
from sqlalchemy import Integer, case, func, select

stmt = (
    select(
        BatchItem.batch_id,
        func.count(WorkflowStep.id).label("total"),
        func.sum(
            case(
                (WorkflowStep.status.in_(
                    [StepStatus.completed, StepStatus.skipped]
                ), 1),
                else_=0,
            )
        ).label("done"),
    )
    .join(
        WorkflowStep,
        (WorkflowStep.project_id == BatchItem.project_id)
        & (WorkflowStep.work_item_id == BatchItem.work_item_id),
    )
    .where(
        BatchItem.project_id == project_id,
        BatchItem.batch_id.in_(batch_ids),
    )
    .group_by(BatchItem.batch_id)
)
```

Critical correctness points:

- **`project_id` MUST scope BOTH** `BatchItem` (via the `where`) **AND**
  `WorkflowStep` (via the join condition). Otherwise a same-named
  `work_item_id` in another project could inflate the counts.
- `done` set is **exactly** `{StepStatus.completed, StepStatus.skipped}`.
  `failed`, `needs_fix`, `pending`, `in_progress` all count toward `total` but
  NOT toward `done`.
- Use `COALESCE` / `or 0` when reading `row.done` — `SUM` of an empty group
  can be `None` depending on driver.
- After executing, initialise the return dict as `{bid: 0 for bid in batch_ids}`
  and overwrite with computed values so batches with no rows default to `0`
  (no `KeyError` for consumers, matches docstring contract).

### 3. Edge cases (explicit)

- Empty `batch_ids` input → return `{}` without executing the query.
- `total_steps == 0` → `progress_pct == 0` (no divide-by-zero; do NOT
  propagate `NaN`).
- `progress_pct` is `int`, in `[0, 100]`. Match the existing `int(...)` style
  used in `batches.py`; `round()` is also acceptable — justify in the step
  report if you choose it.

### 4. Placement and imports

- File path: `dashboard/utils/batch_progress.py` — `dashboard/CLAUDE.md`
  documents `utils/` as the location for shared dashboard helpers.
- If `dashboard/utils/__init__.py` does not exist, create an empty one (check
  first). If it already exists, do NOT modify it (avoid re-export churn —
  callers import from `dashboard.utils.batch_progress` directly).
- Import ORM models from `orch.db.models` with the project's existing import
  style (see how `dashboard/routers/project_dashboard.py` and
  `dashboard/routers/batches.py` do it).

### 5. Do NOT

- Do NOT edit `dashboard/routers/project_dashboard.py`. (S03)
- Do NOT edit `dashboard/routers/batches.py`. (S03)
- Do NOT edit any template file.
- Do NOT change `BatchSummary` or `BatchRow` dataclasses.
- Do NOT write tests in this step — S05 owns tests. You may run a local
  REPL/scratch check to sanity-check your helper, but do not commit any test
  files.

## Project Conventions

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`:

- SQLAlchemy 2.0 `Mapped[]` / `select()` style
- Composite PKs — `(project_id, batch_id)`, `(project_id, work_item_id)`,
  `(project_id, work_item_id, step_id)`
- Thin routers; helpers live under `dashboard/utils/` or `orch/`
- `psycopg` v3 driver; testcontainers for DB-backed tests (N/A this step —
  no tests written here)

## TDD Requirement

Tests belong to S05. You should still:

1. Write a throwaway local `uv run python -c "..."` script to hit the helper
   against a known-state batch in your dev DB (do NOT commit) OR run the
   existing unit suite.
2. Run lint/typecheck on your new file before reporting complete.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — all unit tests must pass (baseline; new tests come in S05).
2. `make lint` and `make typecheck` — no regressions.
3. Do **NOT** report `tests_passed: true` unless all unit tests pass with zero
   failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/utils/batch_progress.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Confirm that NOTHING in dashboard/routers/ was edited; confirm project_id is used in BOTH the BatchItem scope AND the WorkflowStep join condition; state whether dashboard/utils/__init__.py pre-existed."
}
```
