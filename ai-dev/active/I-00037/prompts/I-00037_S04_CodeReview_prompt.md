# I-00037_S04_CodeReview_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step Being Reviewed**: S03 (Frontend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations expected.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document
- `ai-dev/active/I-00037/reports/I-00037_S01_Backend_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S02_CodeReview_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S03_Frontend_report.md`
- `dashboard/utils/batch_progress.py` -- Helper (unchanged; do NOT re-review here)
- `dashboard/routers/project_dashboard.py` -- Just edited by S03
- `dashboard/routers/batches.py` -- Just edited by S03
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/I-00037/reports/I-00037_S04_CodeReview_report.md`

## Context

S03 wired both dashboard routers to the shared helper
`compute_batch_step_progress()`. Your job is to verify that the wiring is
correct, that both callers now read from one source of truth, and that no
template/dataclass/API contract drift slipped in.

Read the design doc's Fix Plan (steps S01-S04) and Acceptance Criteria before
reviewing.

## Review Checklist

### 1. Correctness — both routers call the helper (CRITICAL-class)

- [ ] `dashboard/routers/project_dashboard.py:_active_batches()` imports
  `compute_batch_step_progress` from `dashboard.utils.batch_progress`.
- [ ] `_active_batches()` calls the helper **once per request**, outside the
  per-batch `for` loop. A per-batch call (N queries) is a HIGH finding.
- [ ] The `progress_pct` field on `BatchSummary` is populated from the
  helper's result, not from the `done/total` item counts. **If line 137's old
  `int((done / total * 100) if total > 0 else 0)` is still present → CRITICAL**
  (the bug would still ship).
- [ ] `dashboard/routers/batches.py:_all_batches()` now uses the helper
  instead of the inline Python step-loading loop. The old
  `db.scalars(select(WorkflowStep)...)` block should be gone.
- [ ] Both callers handle the "batch missing from helper dict" case
  gracefully (e.g., `.get(batch.id, 0)`). A raw `dict[key]` would `KeyError`
  on any drift between the two queries.

### 2. Item-level fields preserved (HIGH-class)

- [ ] In `project_dashboard.py`, `total_items` and `completed_items` on
  `BatchSummary` are still derived from the `BatchItem` grouped query
  (`counts.get(batch.id, (0, 0))`). **NOT** from the helper dict.
- [ ] In `batches.py`, `total_items` and `completed_items` on `BatchRow` are
  still derived from the item-based count (the existing
  `sum(1 for it in items if it.status.value in ("completed", "merged"))`
  pattern). **NOT** overwritten with step counts.
- [ ] This is the reporting user's explicit instruction — the Items display
  stays item-based; only the percentage switches.

### 3. Scope hygiene (HIGH-class)

- [ ] No template files were edited
  (`dashboard/templates/pages/project/dashboard.html`,
  `.../batches.html`, `.../fragments/batches_table_rows.html`).
- [ ] `BatchSummary` and `BatchRow` dataclasses (field names, types, defaults)
  are unchanged.
- [ ] `dashboard/utils/batch_progress.py` was NOT edited in S03 (S01 owns it).
- [ ] No test files added in S03 — tests belong to S05.

### 4. Code Quality

- [ ] Imports organised (stdlib / third-party / project; alphabetical within
  blocks).
- [ ] `batch_ids` list constructed once and reused for both the existing query
  and the helper call — no repeated list construction.
- [ ] If `batches.py` had unused imports after removing the inline loop (e.g.,
  `WorkflowStep` may or may not still be needed), they are cleaned up.
- [ ] No dead code left from the refactor (old comments referring to the
  removed step loop should be gone).

### 5. Behavioural parity check

Spot-check by reading the two routers side-by-side:

- Given the same `project_id` and a batch with `batch_id = X`, both
  `_active_batches()` and `_all_batches()` should produce the **same
  integer** for `progress_pct` of batch X. If you can trace a code path where
  they could differ (different arguments to the helper, different `batch_ids`
  scoping, different post-processing), that is a **CRITICAL** finding — it
  would silently reintroduce the bug.

### 6. Security

- `project_id` still scopes both queries on both routers.
- No user input goes into raw SQL.

### 7. Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`.

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — passes on both edited routers.
2. `make typecheck` — no regressions.
3. `make test-unit` — baseline passes. (New tests in S05.)
4. Spot-run `uv run pytest tests/dashboard -v` if such a directory exists, to
   catch any router-level test that still asserted the old item-based
   percentage.

## Severity Levels

| Severity | Use when |
|----------|----------|
| CRITICAL | Old item-based `pct = int(...)` line still present in `project_dashboard.py`; helper result ignored; router paths could produce different `progress_pct` for the same batch; `KeyError` path; template edited |
| HIGH | `BatchSummary`/`BatchRow` shape changed; helper called N times (per-batch); `completed_items`/`total_items` accidentally switched to step counts |
| MEDIUM (fixable) | Dead code left behind, unused imports, duplicated `batch_ids` construction |
| MEDIUM (suggestion) | Naming, log-line additions, minor restructuring |
| LOW | Nitpicks |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00037",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|correctness",
      "file": "",
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
