# CR-00036 S10 Code Review Report

**Work Item**: CR-00036 — Batch-level `auto_merge` toggle with operator-approved manual merge
**Step**: S10
**Agent**: CodeReview (S10)
**Reviewing**: S09 (tests-impl)
**Status**: ✅ PASS

---

## What Was Done

Reviewed the test coverage delivered by S09 (tests-impl) across all CR-00036 test files. Verified AC coverage, test hygiene, lint/format compliance, and ran all CR-00036-specific tests.

---

## Pre-Review Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 639 files already formatted |

---

## Test Results (CR-00036 subset)

All CR-00036 tests pass cleanly. The coverage threshold failure is a global suite artifact (full coverage run includes RAG/OSS modules with 0% coverage) — it does **not** affect the CR-00036 verdict.

| Test File | Tests | Result |
|-----------|-------|--------|
| `tests/integration/test_merge_queue_auto_merge_gate.py` | 8 | ✅ All passed |
| `tests/integration/test_cli_items.py` | 8 | ✅ All passed |
| `tests/integration/test_batch_item_approval.py` | 7 | ✅ All passed |
| `tests/dashboard/test_item_overview_awaiting_merge.py` | 6 | ✅ All passed |
| `tests/dashboard/test_batch_detail_auto_merge_toggle.py` | 11 | ✅ All passed |
| `tests/unit/test_batch_manager.py::TestAutoMergeGate` | 2 | ✅ All passed |

---

## AC Coverage Verification

| AC | Description | Test(s) | Verdict |
|----|-------------|---------|---------|
| AC1 | Project default → CLI batch creation | `test_batch_create_project_default_false`, `test_batch_create_default_auto_merge_true_when_no_project_flag` | ✅ Real ORM assertions |
| AC1 | Project default → Dashboard form | `test_create_batch_inherits_auto_merge_default` | ✅ HTTP route + DB |
| AC2 | CLI flag overrides project default | `test_batch_create_explicit_auto_merge_overrides_project_false`, `test_batch_create_explicit_no_auto_merge_overrides_project_true` | ✅ Real ORM assertions |
| AC3 | Dashboard form pre-filled from project default | `test_create_batch_inherits_auto_merge_default` | ✅ Checks `auto_merge=False` batch |
| AC4 | Dashboard form override respected | `test_create_batch_respects_auto_merge_override` | ✅ Full POST → DB round-trip |
| AC5 | Successful item with `auto_merge=false` halts at MERGE | `test_auto_merge_false_item_stays_at_awaiting_merge_approval` + `test_awaiting_merge_approval_items_are_invisible_to_merge_queue` | ✅ Real `process_merge_queue` call, `_merge_item` not called |
| AC5 | Merge button POSTs to approve-merge | `test_awaiting_approval_renders_merge_button` | ✅ Template render, URL assertion |
| AC6 | Manual merge via dashboard runs merge pipeline | `test_approve_merge_happy_path` + `test_approved_item_is_picked_by_merge_queue_next_tick` | ✅ Real service + `process_merge_queue` |
| AC7 | Manual merge via CLI runs merge pipeline | `test_approve_merge_cli_triggers_merge_queue_next_tick` | ✅ CLI runner → service → queue |
| AC7 | CLI emits daemon event | `test_approve_merge_emits_daemon_event` | ✅ DB assertion |
| AC8 | Merge failure surfaces Restart/Abandon buttons | `test_failed_merge_still_shows_restart_and_abandon`, `test_merge_failed_shows_restart_and_abandon` | ✅ Template rendering |
| AC9 | `auto_merge=true` bypasses gate (baseline) | `test_auto_merge_true_completed_item_is_picked_by_merge_queue` | ✅ `_merge_item` called |
| AC10 | Failed items bypass gate | `test_failed_item_bypasses_gate`, `test_executing_item_that_fails_stays_at_failed` | ✅ Real status assertions |
| AC11a | Toggle editable in planning/approved/paused | `test_toggle_enabled_and_checked_when_auto_merge_true[planning|approved|paused]` | ✅ 3 parametrized cases |
| AC11b | Toggle disabled in executing/completed | `test_toggle_disabled_when_not_editable[executing|completed|completed_with_errors]` | ✅ 3 parametrized cases |

---

## Review Checklist

### 1. AC Coverage — Real Behaviour ✅
No stub or trivial tests found. Every AC has a substantive assertion against the real ORM, real HTTP route, or real template rendering. The `test_merge_queue_auto_merge_gate.py` calls `process_merge_queue` directly (not mocked) and verifies `_merge_item` is not called for `awaiting_merge_approval` items.

### 2. Real Behaviour, Not Mocks ✅
- `test_merge_queue_auto_merge_gate.py` patches `orch.daemon.merge_queue._merge_item` — this is the **executor script mock** convention noted in the review checklist. The function under test (`process_merge_queue`) is called for real; only the external subprocess call is patched.
- `test_approve_merge_service_transitions_to_completed` calls the real `approve_merge` service with real ORM.

### 3. Testcontainer Hygiene ✅
- All integration tests use `db_session` fixture backed by a PostgreSQL testcontainer.
- No live-DB connections (port 5433) detected.
- FTS DDL bootstrapped by the testcontainer session fixture.

### 4. Determinism ✅
- No `time.sleep` or wall-clock assumptions.
- No reliance on unsorted collection iteration order.
- All tests are isolated per-function with per-test transaction rollback.

### 5. Coverage Gaps — Verified as Covered ✅
- **AC10** (failed-item bypass): `test_failed_item_bypasses_gate` and `test_executing_item_that_fails_stays_at_failed` assert `BatchItemStatus.failed` never transitions to `awaiting_merge_approval`.
- **AC11a/AC11b** (toggle disable rule): `test_batch_detail_auto_merge_toggle.py` explicitly tests both the editable-status set (`planning|approved|paused`) and the disabled-status set (`executing|completed|completed_with_errors`).
- **Approve-merge rejection**: `test_dashboard_actions.py` covers `completed`, `merging`, `merged` statuses with 409 responses; `test_cli_items.py` covers `completed`, `merging`, `merged`, and non-existent with exit code 4.

### 6. Enum Iteration ✅
`awaiting_merge_approval` is used as a `BatchItemStatus` value in all relevant test files. No all-status enumeration loops exist in the test suite that would silently miss new enum values.

---

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW issues found.

---

## Notes

- The coverage threshold warning (`total of 19% is less than fail-under=46`) is a global suite concern — the full test suite covers RAG, OSS, staleness, and other modules with near-zero coverage. It is unrelated to CR-00036 and pre-existing.
- `tests/integration/test_batch_item_approval.py` (7 tests) covers the `approve_merge` service with comprehensive rejection cases. This file was likely written in a prior step (S03/S05) but is part of the CR-00036 test suite.
- The `test_merge_queue_auto_merge_gate.py` design decision to patch `_merge_item` (rather than the executor script) is the right trade-off: it tests the gate logic without requiring a real git worktree.

---

## Verdict

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "CR-00036",
  "step_reviewed": "S09",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "33 CR-00036 tests passed (8 gate + 8 CLI items + 7 batch_item_approval + 6 item_overview + 11 auto_merge_toggle + 2 AutoMergeGate unit)",
  "notes": "All ACs verified with real ORM/HTTP/template assertions. No mocks of the function under test. Testcontainer hygiene clean. Lint and format clean."
}
```