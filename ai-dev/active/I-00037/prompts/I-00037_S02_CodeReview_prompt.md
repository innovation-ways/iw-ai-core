# I-00037_S02_CodeReview_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations expected. If S01 touched alembic, flag it CRITICAL.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document
- `ai-dev/active/I-00037/reports/I-00037_S01_Backend_report.md` -- S01 report
- `dashboard/utils/batch_progress.py` -- New helper
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00037/reports/I-00037_S02_CodeReview_report.md` -- Review report

## Context

S01 created the shared step-based progress helper
`dashboard/utils/batch_progress.py`. This helper will become the **single
source of truth** for batch `progress_pct` across both
`dashboard/routers/project_dashboard.py` (S03) and
`dashboard/routers/batches.py` (S03). Your review must catch anything that
would cause drift, wrong counts, or performance issues before S03 wires the
callers.

Read the design doc's Root Cause, Fix Plan, and Acceptance Criteria. Then
read the helper line by line.

## Review Checklist

### 1. Correctness (CRITICAL-class)

- [ ] `project_id` is applied to **both** the `BatchItem` filter and the
  `WorkflowStep` join condition. A missing `project_id` on the join would
  cross-project-contaminate counts. **If missing → CRITICAL.**
- [ ] `done` set is **exactly** `{StepStatus.completed, StepStatus.skipped}`.
  Not `{completed}` alone (would undercount), not `{completed, skipped, failed}`
  (would overcount). **If wrong → CRITICAL.**
- [ ] `total_steps` counts all `WorkflowStep` rows for the batch's items,
  regardless of status. `failed`/`needs_fix`/`pending`/`in_progress` count
  toward total but not toward done.
- [ ] Division-by-zero is handled: batch with zero steps → `progress_pct == 0`,
  no `NaN`, no exception.
- [ ] `SUM(...)` result handled when the group is empty (`None` vs `0`
  depending on dialect — must resolve to `0`).
- [ ] Return dict covers every requested `batch_id`: batches with no rows
  map to `0` instead of being missing. (Consumers iterate their own batch
  list and index; a `KeyError` would 500 the dashboard.)
- [ ] Empty `batch_ids` input short-circuits (no query, return `{}`).

### 2. Architecture Compliance

- [ ] File lives at `dashboard/utils/batch_progress.py` per
  `dashboard/CLAUDE.md`.
- [ ] Helper is importable as a pure function — no FastAPI dependency
  injection, no Jinja templates, no logging-side-effects.
- [ ] Public signature matches design doc: `compute_batch_step_progress(project_id: str, batch_ids: Sequence[str], db: Session) -> dict[str, int]`.
- [ ] ORM model imports from `orch.db.models` use the project's established
  style (compare to `dashboard/routers/batches.py` imports).

### 3. Code Quality

- [ ] Readable and ≤ ~50 lines; no dead code.
- [ ] No N+1: exactly one executed statement per call (plus an optional
  short-circuit for empty input).
- [ ] SQL uses SA 2.0 `select()` / `func.sum` / `case` — not raw strings,
  not SA 1.x `Query`.
- [ ] Type annotations match SA 2.0 style used elsewhere in the repo.

### 4. Scope hygiene (HIGH-class)

- [ ] S01 did **NOT** edit `dashboard/routers/project_dashboard.py` or
  `dashboard/routers/batches.py` — that is S03's job. If S01 changed either,
  flag **HIGH** (wrong step boundary; makes the audit trail messy and
  pre-empts S03's design decisions). The helper must exist standalone.
- [ ] No template files edited.
- [ ] No test files committed in S01 — tests belong to S05.
- [ ] No changes to `BatchRow` / `BatchSummary` dataclasses.

### 5. Security

- `batch_ids` flows from user-controlled URL state into a parameterised
  `.in_()` — confirm SQLAlchemy parameter binding (not string concat).

### 6. Project Conventions

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`.

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — must pass on `dashboard/utils/batch_progress.py`.
2. `make typecheck` — must pass.
3. `make test-unit` — baseline must still pass (new tests arrive in S05).

## Severity Levels

| Severity | Use when |
|----------|----------|
| CRITICAL | Missing `project_id` scoping, wrong `done` set, `SUM`/`None` crash, helper edits a router/template in S01 scope, `KeyError` for requested batch |
| HIGH | N+1 query, wrong dataclass signature, import loop, non-SA-2.0 style that conflicts with the module's conventions |
| MEDIUM (fixable) | Missing type hints, poor naming, docstring absent, unnecessary branch |
| MEDIUM (suggestion) | Alternative SQL shape, alternative file layout |
| LOW | Nitpicks |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00037",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|correctness",
      "file": "dashboard/utils/batch_progress.py",
      "line": 0,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM-fixable findings.
