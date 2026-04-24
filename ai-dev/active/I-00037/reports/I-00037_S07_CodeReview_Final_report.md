# S07 CodeReview Final Report — I-00037

## Verdict: PASS

All CRITICAL, HIGH, and MEDIUM-fixable items: **0 findings**.

---

## 1. Completeness vs Design Document

| AC | Requirement | Status | Proof |
|----|-------------|--------|-------|
| AC1 | `/project/{id}/` shows step-based progress | ✅ | `_active_batches()` at `project_dashboard.py:140` uses `step_progress.get(batch.id, 0)` where `step_progress = compute_batch_step_progress(project_id, batch_ids, db)` at line 135 |
| AC2 | Parity between the two views | ✅ | Both routers call the same helper. Parity test `test_dashboard_home_and_batches_view_agree_on_progress` (line 133-191) asserts `dash.progress_pct == full.progress_pct == 30` on the same seeded batch |
| AC3 | Items count unchanged | ✅ | `_active_batches()` lines 131-133 derive `total_items`/`completed_items` from `BatchItem` grouped query. `_all_batches()` lines 217-218 derive via `sum(1 for it in items if it.status.value in ("completed", "merged"))` |
| AC4 | Regression tests exist for the matrix | ✅ | 16-test suite in `test_batches_progress_parity.py`: completed/skipped/failed/needs_fix/in_progress + empty/zero-steps + multi-batch bulk + project_id scoping + parity |
| AC5 | Zero-step batch renders 0%, no crash | ✅ | `test_helper_zero_steps_is_0_not_crash` at line 266 asserts `{batch_id: 0}`. Helper line 72 guards `total > 0` |

---

## 2. Single Source of Truth

- **Exactly ONE function** computes `progress_pct`: `compute_batch_step_progress` in `dashboard/utils/batch_progress.py:17`
- `project_dashboard.py:16` imports it; `project_dashboard.py:135` calls it once bulk before the loop
- `batches.py:14` imports it; `batches.py:205` calls it once bulk before the loop
- Neither router contains an inline step-counting loop or `SUM(CASE WHEN)` over `WorkflowStep`
- `grep -rn "progress_pct" dashboard/routers/` confirms **only 4 producers** (2 dataclass field declarations + 2 assignments), all via the helper

```
dashboard/routers/batches.py:78          → field declaration (BatchRow.progress_pct)
dashboard/routers/batches.py:231         → pct = step_progress.get(batch.id, 0)
dashboard/routers/project_dashboard.py:52 → field declaration (BatchSummary.progress_pct)
dashboard/routers/project_dashboard.py:147 → pct = step_progress.get(batch.id, 0)
```

- `grep -rn "compute_batch_step_progress" dashboard/` confirms **exactly 2 callers**: `project_dashboard.py:135` and `batches.py:205`

---

## 3. Cross-Agent Consistency

- S01 helper signature: `compute_batch_step_progress(project_id: str, batch_ids: Sequence[str], db: Session) -> dict[str, int]`
- S03 caller (project_dashboard.py:135): `compute_batch_step_progress(project_id, batch_ids, db)` — exact match
- S03 caller (batches.py:205): `compute_batch_step_progress(project_id, batch_ids, db)` — exact match
- S05 tests call the helper with the same signature (e.g. line 228: `compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)`)
- No agent added a second utility path that duplicates the helper's work

---

## 4. Scope Hygiene

- Template files: **not edited** (dashboard.html, batches.html, batches_table_rows.html unchanged)
- `BatchSummary` (project_dashboard.py:44-53) and `BatchRow` (batches.py:71-81) dataclasses: **unchanged field names, types, ordering**
- No `orch/` changes
- Lint: 1 pre-existing error in `executor/scope_gate.py:75` (`print` statement) — unrelated to this work item
- No `dashboard/utils/__init__.py` changes

---

## 5. Items-Count Preservation

- `_active_batches()` lines 131-133: `counts[row.batch_id] = (row.total, int(row.done or 0))` — sourced from `BatchItem` aggregation
- `_all_batches()` lines 217-218: `total_items = len(items)` / `completed_items = sum(1 for it in items if ...)` — sourced from `BatchItem` rows
- `test_active_batches_total_items_is_item_count_not_step_count` (line 668-698) explicitly asserts `total_items == 1` with 10 workflow steps seeded

---

## 6. Regression Test Quality

- **Reproduction test IS the bug's proof**: `test_dashboard_home_and_batches_view_agree_on_progress` seeds 3/10 completed steps + 1 in-progress BatchItem and asserts `progress_pct == 30`. Pre-S03 code returned `progress_pct == 0` (item-level). The test would fail on the pre-fix code.
- All `progress_pct` assertions pin specific integers: `== 30`, `== 100`, `== 10`, `== 50`, `== 0`
- Parity assertion present: `dash.progress_pct == full.progress_pct` (line 180)
- Project-scoping test present: `test_helper_scopes_by_project_id` (line 566) seeds two projects with same `work_item_id` and asserts A→30, B→80

---

## 7. Integration Points

- Imports tidy: `dashboard.utils.batch_progress` imports from `orch.db.models` only (BatchItem, StepStatus, WorkflowStep); no circular imports with `orch/` layer
- Dataclass shapes: `BatchSummary` (6 fields) and `BatchRow` (8 fields) unchanged
- Helper called **once per request, outside the loop** in both routers (bulk pattern)

---

## 8. Security

- `project_id` scopes **both** `BatchItem` (via `where()`) and `WorkflowStep` (via the JOIN condition `WorkflowStep.project_id == BatchItem.project_id`) — no path bypasses scope
- No hardcoded secrets or credentials introduced

---

## Test Summary

| Suite | Result |
|-------|--------|
| `make test-unit` | **1395 passed**, 19 warnings (pre-existing, unrelated) |
| `make test-integration` | **974 passed, 10 skipped**, 36 warnings |
| `make lint` | 1 pre-existing error in `executor/scope_gate.py:75` — not touched in this work item |
| `make typecheck` | **Success**: no issues in 150 source files |

---

## Findings

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00037",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1395 unit passed, 974 integration passed, 0 failed",
  "missing_requirements": [],
  "notes": "All 5 acceptance criteria met. Single source of truth structurally enforced — one helper, two callers, zero alternative paths. The lint error on executor/scope_gate.py is pre-existing and unrelated. The root cause (two independent progress computations that could drift again) is eliminated by construction."
}
```
