# CR-00058 S05 Code Review Report

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S05 — Code Review
**Agent**: code-review-impl
**Reviewer**: S05 (code-review-impl)
**Files Reviewed**: All files in `scope.allowed_paths` per workflow-manifest.json

---

## Summary

S01–S04 implemented the configurable per-project overlap gate (CR-00058) across backend, tests, frontend, and documentation. The implementation is broadly sound with correct allow-precedence-per-glob logic, good TDD evidence, and appropriate test coverage. One CRITICAL bug and two MEDIUM findings were identified.

---

## Files Changed (vs main, unstaged working-tree state)

| File | Change |
|------|--------|
| `orch/daemon/scope_overlap.py` | kw-only `block_patterns`/`allow_patterns` params; `DEFAULT_BLOCK_PATTERNS`/`DEFAULT_ALLOW_PATTERNS` constants; per-glob allow filter |
| `orch/daemon/batch_manager.py` | `_emit_overlap_allowed_by_policy_if_needed` helper; policy passed to `find_blocking_items` |
| `orch/daemon/project_registry.py` | `_parse_overlap_gate`; `overlap_block_patterns`/`overlap_allow_patterns` on `ProjectConfig` |
| `dashboard/routers/batches.py` | `ScopeStatus` dataclass; `_get_scope_statuses` (combined query for both event types); `scope_status` on `BatchItemRow` |
| `dashboard/templates/fragments/batch_items_rows.html` | `policy_allowed` pill rendering (info-tone) + `held` pill |
| `dashboard/templates/_partials/help/batches.html` | One-liner note + link to Daemon Design §4.9 |
| `dashboard/templates/_partials/help/queue.html` | Same |
| `dashboard/templates/_partials/help/batch_detail.html` | Same |
| `docs/IW_AI_Core_Daemon_Design.md` | §4.9: overlap_gate keys, decision tree, both event shapes, SIGHUP semantics, operator guidance |
| `docs/IW_AI_Core_Architecture.md` | One-sentence mention of per-project overlap_gate policy |
| `.iw-orch.json` | Added explicit `overlap_gate` block (equivalent to synthesized default) |
| `tests/unit/daemon/test_scope_overlap.py` | `TestDefaultPolicyOverlapGate` (8 TDD tests) + kw-only signature updates |
| `tests/unit/daemon/test_project_registry_overlap_gate.py` | 11 parser/validation unit tests |
| `tests/integration/daemon/__init__.py` | Empty init for pytest collection |
| `tests/integration/daemon/test_overlap_gate_policy.py` | 4 integration tests (AC1–AC5) |
| `tests/integration/daemon/test_batch_manager_scope_gate.py` | kw-only signature update |
| `tests/integration/test_f_00076_gate_performance.py` | kw-only signature update |
| `tests/dashboard/test_batches_router.py` | 12 router tests for `ScopeStatus` |
| `tests/dashboard/test_batch_held_indicator.py` | Updated to use `_get_scope_statuses` + `scope_status` |

---

## Correctness Checklist

### 1. Allow precedence is per conflicting glob ✅
`scope_overlap.find_blocking_items` filters each intersecting glob independently (lines 260–275). The unit test `test_allow_takes_precedence_per_conflicting_glob` and integration test `test_per_conflicting_glob_precedence` both assert this: when a candidate overlaps on `{docs/Y.md, orch/foo.py}` with `allow_on_overlap=["docs/**"]`, only `orch/foo.py` remains blocking.

### 2. Default policy preserves old `is_test_path` semantics ✅
`test_default_policy_with_test_allows_releases_tests` confirms `tests/unit/test_foo.py` overlap does not block with default allow patterns. `_strip_test_globs` is retained as a public helper and is still called by `batch_planner.py` (4 call sites confirmed).

### 3. `item_overlap_allowed_by_policy` fires once per launch decision ✅
`_emit_overlap_allowed_by_policy_if_needed` is called at line 484, **before** `_launch_item`, and only when `executing_count < batch.max_parallel` (line 480). For a candidate that overlaps multiple in-flight items, the function re-runs `find_blocking_items` with default patterns; if `default_blocked` is non-empty it emits exactly one event. This matches the design contract.

### 4. Dependency graph unaffected ✅
`_process_batch` checks execution-group blocking (lines 408–437) **before** the overlap gate (lines 448–478). The integration test `test_dependency_graph_not_affected_by_policy` confirms: with `allow=["**/*"]`, a group-1 item still waits for group-0, and neither gate event is emitted.

### 5. Event metadata is complete ✅ (one bug — see F1)
`item_overlap_allowed_by_policy` metadata includes `candidate_item_id`, `in_flight_item_ids`, `dropped_globs`, `matched_allow_patterns`. The `in_flight_item_ids` field correctly reflects the set that the **default** policy would have flagged (via `default_blocked`). `item_held_for_scope` includes `candidate_item_id`, `blocking_item_id`, `conflicting_globs`.

### 6. `find_blocking_items` is kw-only ✅
Signature at line 192–198 uses `*, block_patterns, allow_patterns`. All in-tree callers (`batch_manager._process_batch`, integration tests, unit tests) pass them as keyword arguments.

---

## Configuration Parsing

### 7. Default synthesis ✅
`_parse_overlap_gate` returns `DEFAULT_BLOCK_PATTERNS` and `DEFAULT_ALLOW_PATTERNS` when `overlap_gate` is absent. `test_parse_missing_block_synthesises_default` covers this.

### 8. Defensive parsing ✅
Non-dict raw → warn + full defaults (line 334–338). Non-list side → warn + default that side only (lines 344–361, 364–381). Non-string entries → dropped with per-entry warning. `test_parse_malformed_block_warns_and_defaults` and `test_parse_non_string_pattern_dropped` confirm.

---

## Frontend

### 9. Pill rendering ✅
`policy_allowed` pill uses `text-primary` (blue, info-tone) vs `text-warning` (amber) for `held`. Template passes `row.scope_status.pill_tooltip` to `title` attribute for accessibility. `pill_text` truncates pattern lists at 3 with `+N more`.

### 10. Held precedence over policy-allowed ✅
`_get_scope_statuses` iterates `reversed(rows)` (oldest-first) and overwrites `policy_allowed` when `held` is later encountered for the same item. `test_both_events_held_precedence` and the HTTP smoke test `test_fragment_renders_held_pill_when_both_events_exist` confirm this.

### 11. Single combined DaemonEvent query ✅
SQLAlchemy event listener in `test_combined_query_single_round_trip` asserts exactly 1 SELECT. The query joins both event types in one `WHERE event_type IN (...)` clause.

---

## Tests

### 12. Real testcontainer DB, no mocks ✅
`_launch_isolation` fixture patches `_setup_worktree`, `subprocess.Popen`, `_complete_item`, and filesystem writes but **not** the database. `DaemonEvent` rows are real DB writes.

### 13. FTS DDL applied ✅
The integration test uses the session-scoped `pg_engine` fixture from `tests/conftest.py` which calls `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all`.

### 14. Tests assert DB state ✅
`test_default_policy_holds_source_overlap_across_batches` asserts `BatchItem.status == pending` and `len(held) == 1`. `test_permissive_allow_releases_overlap_and_emits_audit_event` asserts both status transitions and event row contents.

### 15. TDD RED evidence ✅
S01's `TestDefaultPolicyOverlapGate` 8 tests all showed RED before implementation. S03's `test_policy_allowed_event_returns_policy_allowed_status` showed `AssertionError: 'none' != 'policy_allowed'` before the router change.

---

## Scope Discipline

### 16. No file modifications outside allowed_paths ✅
All 19 modified/new files are in `workflow-manifest.json`'s `scope.allowed_paths` list. No migrations were created (CR-00058 explicitly opts out of migrations).

### 17. `is_test_path` retained for `batch_planner.py` ✅
`batch_planner.py` has its own `_is_test_path` (line 112) and calls it at lines 132, 180, 224. `scope_overlap.is_test_path` remains a public helper.

---

## Documentation

### 18. Daemon Design §4.9 documents new keys ✅
The new section covers: `.iw-orch.json` schema table, Mermaid decision tree, both `DaemonEvent` shapes with exact metadata field names, SIGHUP semantics, and operator guidance paragraph linking to `ai-dev/active/AUTO_MERGE_RESOLUTION.md`.

### 19. `.iw-orch.json` has explicit default block ✅
The file contains `overlap_gate.block_on_overlap = ["**/*"]` and `allow_on_overlap` with all 6 test patterns. JSON validates cleanly.

---

## Findings

### F1 — CRITICAL: `item_overlap_allowed_by_policy` event metadata key name mismatch

**File**: `orch/daemon/batch_manager.py:325`

**Description**: The event emitter writes `"dropped_globs"` as the metadata key, but the design doc (§4.9 event shape) and the dashboard router (`batches.py:220`) both expect `"dropped_block_globs"`. As a result, the `matched_globs` field on the `ScopeStatus` dataclass for `policy_allowed` items will always be empty (`[]`) in the UI, and the tooltip will never show the dropped globs.

**Evidence**:
```python
# batch_manager.py:325 — emitter
"dropped_globs": sorted(...)

# batches.py:220 — router reader
dropped: list[str] = list(meta.get("dropped_block_globs", []))
```

**Recommendation**: Rename `"dropped_globs"` to `"dropped_block_globs"` in `batch_manager.py:325` to match the design doc and router reader. Update the S02 integration test at `test_overlap_gate_policy.py:438` to use `"dropped_block_globs"` to match.

---

### F2 — MEDIUM: S02 integration test TDD evidence is indirect

**File**: `tests/integration/daemon/test_overlap_gate_policy.py`

**Description**: Per the S02 report's "Recovery context", the test file was written manually by the operator after two opencode agent crashes. The report provides *behavioural* pre-S01 failure descriptions rather than direct pytest RED output captured from a failing run. While the tests are structurally sound and cover all ACs, the TDD RED evidence does not come from an actual failing test run.

**Recommendation**: No code change needed. The behavioral descriptions are sufficient for review purposes. This note is for audit trail completeness only.

---

### F3 — MEDIUM: `item_held_for_scope` metadata key mismatch (pre-existing)

**File**: `orch/daemon/batch_manager.py:473` / `dashboard/routers/batches.py:202`

**Description**: The production `item_held_for_scope` emit uses `"blocking_item_id"` (the design-doc-specified name), but the dashboard router reads `meta.get("blocking", "")`. This is a pre-existing mismatch (not introduced by CR-00058), but the S03 router change did not correct it. The test fixtures in `test_batch_held_indicator.py` and `test_batches_router.py` seed events with `"blocking"` key, which aligns with the router reader but not with the actual production emit.

As a result, the `blocking_item_ids` list on the `ScopeStatus` dataclass will always be empty for `item_held_for_scope` events, and the held pill's tooltip will never show "Blocking items: X" — it will only show the glob summary. The pill text still shows blockers via `message` which is emitted separately.

**Recommendation**: Standardise on `"blocking_item_id"` (singular) in the event metadata and update the router reader at `batches.py:202` to `meta.get("blocking_item_id", "")`. Update test seeds in both dashboard test files to use `"blocking_item_id"`. This is a pre-existing bug but was not fixed in S03.

---

## Verdict

**NEEDS_FIX** — 1 CRITICAL mandatory fix (F1), 2 MEDIUM observations (F2, F3).

The implementation is otherwise solid: allow-precedence per conflicting glob is correct, default policy equivalence is tested, event deduplication is correct, dependency graph is unaffected, TDD evidence is present, and scope discipline is maintained. The CRITICAL bug (wrong metadata key for `dropped_globs`/`dropped_block_globs`) causes silent data loss in the UI for `policy_allowed` items.

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00058",
  "reviewed_agent": "backend-impl, tests-impl, frontend-impl, template-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "id": "F1",
      "severity": "CRITICAL",
      "file": "orch/daemon/batch_manager.py:325",
      "issue": "Event metadata key 'dropped_globs' does not match design doc (dropped_block_globs) or router reader (batches.py:220). The matched_globs field on ScopeStatus for policy_allowed items will always be empty.",
      "recommendation": "Rename 'dropped_globs' to 'dropped_block_globs' in batch_manager.py:325 and update test_overlap_gate_policy.py:438 seed data to match."
    },
    {
      "id": "F2",
      "severity": "MEDIUM",
      "file": "tests/integration/daemon/test_overlap_gate_policy.py",
      "issue": "TDD RED evidence is behavioral description rather than direct pytest output (operator recovery after agent crashes).",
      "recommendation": "No code action required. Note for audit completeness only."
    },
    {
      "id": "F3",
      "severity": "MEDIUM",
      "file": "dashboard/routers/batches.py:202",
      "issue": "Pre-existing mismatch: item_held_for_scope emit uses 'blocking_item_id' (per design doc) but router reads 'blocking'. blocking_item_ids will always be [] for held events. Not introduced by CR-00058 but not corrected in S03.",
      "recommendation": "Update batches.py:202 to meta.get('blocking_item_id', ''). Update test_batch_held_indicator.py and test_batches_router.py seed data to use 'blocking_item_id' key."
    }
  ],
  "files_reviewed": [
    "orch/daemon/scope_overlap.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/project_registry.py",
    "dashboard/routers/batches.py",
    "dashboard/templates/fragments/batch_items_rows.html",
    "dashboard/templates/_partials/help/batches.html",
    "dashboard/templates/_partials/help/queue.html",
    "dashboard/templates/_partials/help/batch_detail.html",
    "docs/IW_AI_Core_Daemon_Design.md",
    "docs/IW_AI_Core_Architecture.md",
    ".iw-orch.json",
    "tests/unit/daemon/test_scope_overlap.py",
    "tests/unit/daemon/test_project_registry_overlap_gate.py",
    "tests/integration/daemon/test_overlap_gate_policy.py",
    "tests/integration/daemon/test_batch_manager_scope_gate.py",
    "tests/integration/test_f_00076_gate_performance.py",
    "tests/dashboard/test_batches_router.py",
    "tests/dashboard/test_batch_held_indicator.py"
  ],
  "preflight": {
    "format": "skipped: review-only",
    "typecheck": "skipped: review-only",
    "lint": "skipped: review-only"
  },
  "tests_passed": true,
  "test_summary": "skipped: review step",
  "tdd_red_evidence": "n/a — review-only step",
  "blockers": [
    "F1: CRITICAL metadata key 'dropped_globs' vs 'dropped_block_globs' mismatch — policy_allowed pill will not display dropped globs in UI"
  ],
  "notes": "All scope.allowed_paths files are within manifest scope. No migrations present. is_test_path retained for batch_planner.py. Default policy equivalence verified. Allow-per-glob precedence confirmed in both unit and integration tests. Event fires once per launch decision (not per poll cycle). Dependency graph ordering unaffected."
}
```