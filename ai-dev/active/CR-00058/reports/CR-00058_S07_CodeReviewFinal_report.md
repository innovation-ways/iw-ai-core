# CR-00058_S07_CodeReviewFinal_Report

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S07 (code-review-final-impl)
**Agent**: code-review-final-impl
**Date**: 2026-05-18

---

## What Was Done

Cross-agent final review of CR-00058 across all implementation outputs (S01–S06). Verified:

1. End-to-end policy round-trip (`.iw-orch.json` → daemon → events → dashboard)
2. Default-preservation invariant
3. Audit trail completeness
4. F-00076 contract test preservation
5. No silent `scope.allowed_paths` expansion
6. Documentation ↔ code alignment
7. Operator UX on all failure paths
8. Dead code audit

---

## Files Changed (CR-00058)

| File | Purpose |
|------|---------|
| `orch/daemon/scope_overlap.py` | `find_blocking_items` kw-only signature; `DEFAULT_BLOCK_PATTERNS` / `DEFAULT_ALLOW_PATTERNS` constants; `_matches` helper |
| `orch/daemon/project_registry.py` | `_parse_overlap_gate`; `overlap_block_patterns` / `overlap_allow_patterns` on `ProjectConfig` |
| `orch/daemon/batch_manager.py` | Policy read from `project_config`; `_emit_overlap_allowed_by_policy_if_needed`; event metadata with `dropped_block_globs` |
| `dashboard/routers/batches.py` | `_get_scope_statuses` queries both event types; `ScopeStatus` dataclass with held/policy_allowed statuses |
| `dashboard/templates/fragments/batch_items_rows.html` | Warning pill for held, info pill for policy_allowed |
| `dashboard/templates/_partials/help/batches.html`, `batch_detail.html`, `queue.html` | New help text linking to Daemon Design §4.9 |
| `.iw-orch.json` | Added explicit `overlap_gate` block (same values as synthesized default) |
| `docs/IW_AI_Core_Daemon_Design.md` | §4.9: overlap_gate schema, decision tree, event shapes, SIGHUP semantics, operator guidance |
| `docs/IW_AI_Core_Architecture.md` | One-sentence mention of per-project overlap_gate policy |
| `tests/unit/daemon/test_scope_overlap.py` | Updated to kw-only signature; `TestDefaultPolicyOverlapGate` with 8 TDD cases |
| `tests/unit/daemon/test_project_registry_overlap_gate.py` | 11 parser/validation unit tests (new file) |
| `tests/integration/daemon/test_overlap_gate_policy.py` | 4 end-to-end integration tests (new file) |
| `tests/integration/daemon/test_batch_manager_scope_gate.py` | Updated to kw-only signature |
| `tests/integration/test_f_00076_gate_performance.py` | Updated to kw-only signature |
| `tests/dashboard/test_batch_held_indicator.py` | Fixed seed data `blocking` → `blocking_item_id` |
| `tests/dashboard/test_batches_router.py` | Fixed seed data `blocking` → `blocking_item_id` |

---

## Cross-Agent Integration Review

### 1. End-to-End Policy Round-Trip ✅

Trace confirmed no drift between layers:

- **`.iw-orch.json`** (`overlap_gate.block_on_overlap = ["**/*"]`, `allow_on_overlap` = 6 test patterns) ✅
- **`project_registry._parse_overlap_gate`** → returns `(block_patterns, allow_patterns)` ✅
- **`ProjectConfig.overlap_block_patterns` / `overlap_allow_patterns`** — set correctly ✅
- **`batch_manager._process_batch`** → passes `cfg.overlap_block_patterns` and `cfg.overlap_allow_patterns` to `find_blocking_items` ✅
- **`scope_overlap.find_blocking_items`** → returns `list[tuple[item_id, conflicting_globs]]` ✅
- **Held path**: `item_held_for_scope` event with `{blocking_item_id, conflicting_globs}` ✅
- **Released path**: `item_overlap_allowed_by_policy` event with `{candidate_item_id, in_flight_item_ids, matched_allow_patterns, dropped_block_globs}` ✅
- **`dashboard/routers/batches.py:_get_scope_statuses`** → reads both event types, builds `ScopeStatus` ✅
- **Template** → warning pill (`status == "held"`) / info pill (`status == "policy_allowed"`) ✅

### 2. Default-Preservation Invariant ✅

**Test**: `test_default_policy_holds_source_overlap_across_batches` in `test_overlap_gate_policy.py`.

Verifies: with synthesized default (no `overlap_gate` block), two batches touching `dashboard/foo.py` produce one held item + one `item_held_for_scope` event + zero `item_overlap_allowed_by_policy` events. ✅

### 3. Audit Trail Completeness ✅

| Event | Trigger | Count |
|-------|---------|-------|
| `item_held_for_scope` | Per blocking item per poll cycle while candidate is held | ✅ Emitted in `_process_batch` loop (lines 464–478) |
| `item_overlap_allowed_by_policy` | Once per launch decision — only when non-default policy releases an item the default would have blocked | ✅ Emitted in `_emit_overlap_allowed_by_policy_if_needed` before `_launch_item` (line 486) |

No policy decision is silent where it should be observable.

### 4. F-00076 Contract Tests ✅

- **`tests/integration/test_f_00076_scope_extraction_round_trip.py`** — unchanged by CR-00058 (tests `impacted_paths` provenance, not the gate). ✅
- **`tests/integration/test_f_00076_gate_performance.py`** — updated to kw-only signature, all 3 tests pass. ✅

### 5. No Silent `scope.allowed_paths` Expansion ✅

CR-00058 does not touch the `scope.allowed_paths` manifest field or the merge-time `scope_gate_enabled` enforcement. The overlap gate operates exclusively on `WorkItem.impacted_paths` (the DB column) and the `.iw-orch.json` `overlap_gate` block. No cross-contamination. ✅

### 6. Documentation ↔ Code Alignment ✅

- **Daemon Design §4.9**: Decision tree accurately reflects `find_blocking_items` + per-glob allow filter + event emission branches. ✅
- **Event metadata**: design doc examples match actual emit code:
  - `item_held_for_scope`: `{blocking_item_id, conflicting_globs}` (batch_manager.py:473) ✅
  - `item_overlap_allowed_by_policy`: `{candidate_item_id, in_flight_item_ids, matched_allow_patterns, dropped_block_globs}` (batch_manager.py:323–339) ✅
- **`.iw-orch.json` example**: `allow_on_overlap` test patterns exactly match `DEFAULT_ALLOW_PATTERNS` in `scope_overlap.py`. ✅

### 7. Operator UX on All Failure Paths ✅

- **Malformed `overlap_gate` (not a dict)**: warns → returns `(DEFAULT_BLOCK_PATTERNS, DEFAULT_ALLOW_PATTERNS)`. Does not crash. ✅
- **Non-list `block_on_overlap`**: warns → keeps default for that side. ✅
- **Non-string entries in block/allow lists**: drops per-entry with warning. ✅
- **Missing project (race with SIGHUP)**: `ProjectRegistry` preserves last-known-good state. ✅

### 8. `is_test_path` Dead Code Audit ✅

`is_test_path` (scope_overlap.py:62) is used by:
- **`orch/batch_planner.py`** at lines 132 and 180 — filters test paths from dependency analysis (correct, separate concern)
- **`tests/unit/test_batch_planner_dependencies.py`** — cross-impl consistency test

Not dead. The function is a public helper for callers that want to compose defaults, as documented. ✅

---

## Test Results

| Suite | Result |
|-------|--------|
| `tests/unit/daemon/test_scope_overlap.py` + `test_project_registry_overlap_gate.py` | **71 passed** |
| `tests/integration/daemon/test_overlap_gate_policy.py` + `test_batch_manager_scope_gate.py` + `test_f_00076_gate_performance.py` | **15 passed** |
| `tests/dashboard/test_batch_held_indicator.py` + `test_batches_router.py` | **20 passed** |
| **Total** | **106 passed** |

---

## S05/S06 Findings: Resolution Status

| Finding | Severity | Status |
|---------|----------|--------|
| F1: `dropped_globs` vs `dropped_block_globs` mismatch | CRITICAL | ✅ Fixed in S06 (batch_manager.py:325) |
| F3: `blocking` vs `blocking_item_id` mismatch (pre-existing) | MEDIUM | ✅ Fixed in S06 (batches.py:202 + test seed data) |
| F2: TDD RED evidence is description | MEDIUM | ✅ Noted; no code action required |

---

## Notes

- CRITICAL finding F1 and MEDIUM finding F3 from S05 were both resolved in S06. No new CRITICAL or HIGH findings introduced by any agent.
- The `item_held_for_scope` `blocking_item_id` / `item_overlap_allowed_by_policy` `dropped_block_globs` keys now match between emit, design doc, and router reader.
- The F-00076 performance contract is maintained: gate evaluation completes in <100ms for 50 in-flight items.
- All 106 tests pass with the final kw-only signature across all affected test files.

---

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00058",
  "completion_status": "complete",
  "findings": [],
  "files_reviewed": [
    "orch/daemon/scope_overlap.py",
    "orch/daemon/project_registry.py",
    "orch/daemon/batch_manager.py",
    "dashboard/routers/batches.py",
    "dashboard/templates/fragments/batch_items_rows.html",
    "docs/IW_AI_Core_Daemon_Design.md",
    ".iw-orch.json",
    "tests/unit/daemon/test_scope_overlap.py",
    "tests/unit/daemon/test_project_registry_overlap_gate.py",
    "tests/integration/daemon/test_overlap_gate_policy.py",
    "tests/integration/daemon/test_batch_manager_scope_gate.py",
    "tests/integration/test_f_00076_gate_performance.py",
    "tests/dashboard/test_batch_held_indicator.py",
    "tests/dashboard/test_batches_router.py"
  ],
  "preflight": {
    "format": "skipped:review-only",
    "typecheck": "skipped:review-only",
    "lint": "skipped:review-only"
  },
  "tests_passed": true,
  "test_summary": "71 unit + 15 integration + 20 dashboard = 106 passed",
  "tdd_red_evidence": "n/a — review-only step",
  "blockers": [],
  "notes": "No CRITICAL/HIGH findings remain. All S05/S06 findings were resolved. Policy round-trip is drift-free. Default-preservation invariant holds. Audit trail complete. F-00076 contract tests preserved. Documentation matches code. Operator UX graceful on all failure paths. is_test_path is not dead (used by batch_planner.py)."
}
```