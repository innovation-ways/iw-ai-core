# CR-00028 S09 — Final Cross-Agent Code Review Report

**Reviewer**: code-review-final-impl
**Step**: S09
**Work Item**: CR-00028 — Don't cascade merge-time failures to dependent items
**Date**: 2026-05-02

---

## Summary

Cross-agent review complete. The end-to-end chain (enum → merge queue → batch_manager → actions → templates → tests) holds correctly. All 7 acceptance criteria are covered by tests. The `merge_abandoned` SSE event is registered in both `_TOAST_EVENTS` and `_TOAST_SEVERITY`. All button actions use the modal pattern (`hx-get` → `/confirm-item/`, no `hx-confirm`). 5 lint violations and 1 format violation exist in S07-changed files (will be fixed at S10/S11 gates — not CRITICAL).

---

## Files Changed (CR-00028 scope)

| File | Step | Change |
|------|------|--------|
| `orch/db/models.py` | S01 | Added `BatchItemStatus.merge_failed`; added to `TERMINAL_BATCH_ITEM_STATUSES` |
| `orch/db/migrations/versions/48218f84b69f_cr_00028_add_merge_failed...py` | S01 | `ALTER TYPE ... ADD VALUE IF NOT EXISTS 'merge_failed'`; no-op downgrade |
| `orch/daemon/merge_queue.py` | S03 | Line 136: `failed` for no-worktree-path (unrecoverable, cascading); line 296: `merge_failed` for `MergeError`/`TimeoutExpired` (non-cascading) |
| `orch/daemon/batch_manager.py` | S03 | `_BLOCKING_TERMINAL_STATUSES` excludes `merge_failed`, `migration_invalid`, `migration_rebase_failed`; `_current_execution_group` treats them as non-terminal |
| `dashboard/routers/actions.py` | S03 | `restart-merge` accepts 3 recoverable statuses; new `abandon-merge` flips them → `failed`; `_ITEM_ACTION_LABELS["abandon-merge"]` registered with `danger=True` |
| `dashboard/routers/sse.py` | S03 | `"merge_abandoned"` in `_TOAST_EVENTS` and `_TOAST_SEVERITY["warning"]` |
| `dashboard/routers/items.py` | S05 | `_merge_status()` maps recoverable statuses → `"merge_failed"` display value |
| `dashboard/templates/components/status_badge.html` | S05 | `merge_failed` → `bg-warning`; `migration_invalid`/`migration_rebase_failed` also upgraded to `bg-warning` |
| `dashboard/templates/components/action_button.html` | S05 | `abandon_merge_button` macro uses `hx-get` modal pattern (no `hx-confirm`) |
| `dashboard/templates/fragments/item_overview.html` | S05 | Button condition extended to show both Restart and Abandon for `merge_failed` status |
| 8 new/modified test files | S07 | Full AC coverage: AC1–AC7 |

---

## Checklist 1 — Completeness vs Design Doc

| Design Section | Status | Evidence |
|----------------|-------|---------|
| `merge_failed` added to enum | ✅ | `models.py:153` |
| Migration with IF NOT EXISTS | ✅ | `48218f84b69f...py:21` |
| `merge_queue.py:289` → `merge_failed` | ✅ | `merge_queue.py:296` |
| `merge_queue.py:136` → `failed` (unrecoverable) | ✅ | `merge_queue.py:140` with CR-00028 comment |
| `_BLOCKING_TERMINAL_STATUSES` excludes 3 statuses | ✅ | `batch_manager.py:62–67` with CR-00028 comment |
| `_current_execution_group` treats them as non-terminal | ✅ | `batch_manager.py:1382–1391` with CR-00028 comment |
| `restart-merge` accepts 3 statuses | ✅ | `actions.py:925–929` (`_ALLOWED_RETRY_STATUSES`), `actions.py:943` (`.in_()` check) |
| `abandon-merge` flips → `failed` + emits event | ✅ | `actions.py:1046–1056` |
| `_ITEM_ACTION_LABELS["abandon-merge"]` with `danger=True` | ✅ | `actions.py:124–129` |
| `merge_abandoned` in `_TOAST_EVENTS` | ✅ | `sse.py:71` |
| `merge_abandoned` in `_TOAST_SEVERITY` | ✅ | `sse.py:124` |
| `_merge_status` maps 3 statuses → `"merge_failed"` | ✅ | `items.py:561–567` |
| `status_badge.html` adds `merge_failed` (warning color) | ✅ | `status_badge.html:9` |
| `abandon_merge_button` macro uses modal pattern | ✅ | `action_button.html:52` (hx-get, no hx-confirm) |
| AC1: `MergeError` → `merge_failed` (not `failed`) | ✅ | Unit test `test_merge_error_writes_merge_failed_not_failed` + 5 updated tests |
| AC2: `merge_failed` doesn't cascade | ✅ | Integration test `test_recoverable_merge_failure_does_not_cascade[merge_failed]` |
| AC3: `migration_invalid`/`migration_rebase_failed` don't cascade | ✅ | Parametrized integration + unit tests |
| AC4: no-worktree-path → `failed` (NOT `merge_failed`) | ✅ | `TestNoWorktreePathStillWritesFailed` (3 tests) |
| AC5: `restart-merge` resumes from `merge_failed` | ✅ | `test_actions_restart_merge_preconditions.py` (parametrized 3 statuses) |
| AC6: `abandon-merge` flips → `failed`, triggers cascade | ✅ | `test_abandon_merge_triggers_cascade.py` + unit test |
| AC7: Dashboard renders badge + buttons | ✅ | `_merge_status` tests + SSE registry tests; browser deferred to S15 |

**All design sections implemented. All 7 ACs covered.**

---

## Checklist 2 — Chain Integrity

Trace: `worktree_commit.sh` exits non-zero → `merge_queue._merge_item` catches `MergeError` → `batch_item.status = BatchItemStatus.merge_failed` (line 296) → `WorkItem` reverts to `failed` (line 299) → `merge_conflict` event emitted (line 305) → `db.commit()` → daemon poll: `_process_batch` calls `_current_execution_group` (line 309) → returns group 0 (line 1376: `merge_failed` is non-terminal) → `failed_in_prior_group` check (line 320): `merge_failed not in _BLOCKING_TERMINAL_STATUSES` → **no cascade** → group 1 items stay `pending` → operator clicks "Retry merge" in dashboard → `hx-get /confirm-item/restart-merge/{id}` → modal → `POST /actions/{project}/item/{id}/restart-merge` → `status → completed` → next merge_queue poll picks up item, re-merges.

**Chain intact. No breaks found.**

---

## Checklist 3 — Cross-Agent Consistency

| Check | Status | Notes |
|-------|--------|-------|
| Status references use enum members | ✅ | `BatchItemStatus.merge_failed`, `BatchItemStatus.failed`, etc. No raw strings in code |
| `merge_abandoned` in `_TOAST_EVENTS` | ✅ | `sse.py:71` |
| `merge_abandoned` in `_TOAST_SEVERITY` | ✅ | `sse.py:124` (`"warning"`) |
| `merge_conflict` (pre-existing) in both | ✅ | `sse.py:70` (in _TOAST_EVENTS); not in _TOAST_SEVERITY (error-level default) |
| `abandon_merge_button` uses `hx-get` modal pattern | ✅ | `action_button.html:52` — `hx-get="/project/{id}/api/confirm-item/abandon-merge/{id}"` |
| **No `hx-confirm`** on abandon or retry buttons | ✅ | Confirmed — neither button has `hx-confirm` attribute |
| `_ITEM_ACTION_LABELS["abandon-merge"]` has `danger=True` | ✅ | `actions.py:129` |
| `restart_merge_button` also uses modal pattern | ✅ | `action_button.html:40` — `hx-get="/project/{id}/api/confirm-item/restart-merge/{id}"` |
| `_merge_status` returns `"merge_failed"` string | ✅ | `items.py:567` — flows to badge lookup and button condition |
| `status_badge.html` maps `"merge_failed"` → `bg-warning` | ✅ | `status_badge.html:9` — distinct from `"failed"` (line 8: `bg-destructive`) |
| Button condition shows both buttons for `merge_failed` | ✅ | `item_overview.html:94–96` — `{% if step.status == 'merge_failed' %}` |

**All cross-agent consistency checks pass.**

---

## Checklist 4 — Integration Points

| Check | Status | Notes |
|-------|--------|-------|
| Migration file clean | ✅ | `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'merge_failed'` — valid PostgreSQL 14+ |
| Migration downgrade is no-op | ✅ | `pass` with documented comment explaining PostgreSQL limitation |
| Migration revision chain | ✅ | Head `561ddde7f5fb` → `48218f84b69f` (head) — verified via `alembic history` |
| Confirm-modal pattern for both buttons | ✅ | Both `restart_merge_button` and `abandon_merge_button` use `hx-get → /confirm-item/<action>/<id>` |
| `daemon_event.metadata` → `event_metadata` Python attr | ✅ | `actions.py:193` uses `event_metadata=metadata or {}` — correct |
| DaemonEvent emit sites use `_emit_event` / `_emit` | ✅ | `merge_queue.py` and `actions.py` both use correct helpers |

---

## Checklist 5 — Test Coverage (Holistic)

- **AC1**: `test_merge_error_writes_merge_failed_not_failed`, `test_timeout_writes_merge_failed`, `test_workitem_reverts_to_failed_on_merge_error`, `test_merge_conflict_event_emitted_on_merge_error`
- **AC2**: `test_recoverable_merge_failure_does_not_cascade[merge_failed]` (integration), `test_current_execution_group_treats_recoverable_as_open[merge_failed]` (unit)
- **AC3**: `test_recoverable_merge_failure_does_not_cascade[migration_invalid/migration_rebase_failed]` (integration + unit)
- **AC4**: `TestNoWorktreePathStillWritesFailed` (3 tests)
- **AC5**: `test_restart_merge_accepts_recoverable_status` (parametrized 3 statuses), `test_restart_merge_resets_to_completed`, `test_restart_merge_emits_merge_restarted_event`
- **AC6**: `test_abandon_merge_flips_to_failed_then_cascade_fires` (parametrized), `test_abandon_merge_emits_merge_abandoned_daemon_event`, integration `test_abandon_merge_triggers_cascade`
- **AC7**: `test_merge_status_merge_failed_in_db`, `test_merge_status_migration_invalid_in_db`, `test_merge_abandoned_event_in_sse_toast_events`, `test_merge_abandoned_event_in_sse_toast_severity`; button rendering deferred to S15

**All 7 ACs have test coverage. Both happy path and error paths covered.**

---

## Checklist 6 — Architecture Compliance

| Check | Status | Notes |
|-------|--------|-------|
| Daemon stays sync (no async leaks) | ✅ | All `async def` only in FastAPI router layer, not in daemon |
| Composite PKs respected | ✅ | All queries use `(project_id, work_item_id)` composite keys |
| Append-only tables used correctly | ✅ | `daemon_events` uses `db.add()` (append), not `UPDATE` |
| `DaemonsEvent.metadata` → `event_metadata` | ✅ | Correctly handled in both emit sites |
| No `importlib.reload(orch.config)` | ✅ | Tests use `monkeypatch.delenv()` pattern |

---

## Checklist 7 — Security & Robustness

| Check | Status | Notes |
|-------|--------|-------|
| No hardcoded URLs/ports/credentials | ✅ | All config via env vars |
| htmx `hx-confirm` NOT on abandon button | ✅ | Confirmed absent — modal pattern only |
| Endpoints return 422 (not 500) on bad input | ✅ | `abandon_merge` raises `HTTPException(status_code=422)` |
| `abandon-merge` note includes `[operator abandoned via abandon-merge]` | ✅ | `actions.py:1047` — audit trail for irreversible action |

---

## Checklist 8 — SQL / DB Migration

| Check | Status | Notes |
|-------|--------|-------|
| `ALTER TYPE ... ADD VALUE IF NOT EXISTS` — valid PostgreSQL 14+ | ✅ | Verified syntax |
| IF NOT EXISTS guard for crash-recovery replay | ✅ | Present in `migration file line 21` |
| Downgrade is documented no-op | ✅ | Comment in `migration file lines 24–34` |
| Revision chain to current head | ✅ | `561ddde7f5fb` → `48218f84b69f` (head) |

---

## Pre-Flight Gate Results

```
make lint   — FAIL (8 errors, 5 in S07-changed files)
make format — FAIL (2 files would be reformatted)
```

### NEW violations (S07 scope — fixable at S10/S11 gates)

| Severity | File | Line | Code | Description |
|----------|------|------|------|-------------|
| MEDIUM | `tests/unit/test_batch_manager.py` | 191 | E501 | Line 106 chars (limit 100) |
| MEDIUM | `tests/unit/test_batch_manager_blocking_terminal_set.py` | 12 | F401 | `typing.Any` imported but unused |
| MEDIUM | `tests/integration/test_abandon_merge_triggers_cascade.py` | 70 | E501 | Line 106 chars (limit 100) |
| MEDIUM | `tests/integration/test_merge_failure_does_not_cascade.py` | 68 | S106 | Hardcoded password — add `# noqa: S106` |
| MEDIUM | `tests/integration/test_abandon_merge_triggers_cascade.py` | 74 | S106 | Hardcoded password — add `# noqa: S106` |

### Pre-existing violations (not CRITICAL)

| File | Line | Issue | Noted in |
|------|------|-------|----------|
| `dashboard/routers/actions.py` | 1170 | E501 line too long (126 chars) | CR-00029 scope, not CR-00028 |
| `ai-dev/active/CR-00029/...` | — | format violation | Different work item |

---

## Test Verification (NON-NEGOTIABLE)

```
make test-unit  — 2306 passed, 2 skipped, 5 xfailed, 1 xpassed ✅
make test-integration — 1203 passed, 12 skipped, 0 failed ✅ (5:18)
```

**All tests pass. No regressions.**

**Note on xpassed**: `test_merge_queue.py::test_merge_error_reverts_work_item_status` was marked `xfail` in baseline but now passes because `merge_failed` is the correct new behavior. The `xfail` marker should be removed post-merge (tracked as LOW).

---

## Findings Summary

| Severity | Count | Notes |
|----------|-------|-------|
| CRITICAL | 0 | |
| HIGH | 0 | |
| MEDIUM (fixable) | 5 | S07 lint violations — fixed at S10 gate |
| MEDIUM (suggestion) | 1 | xfail marker should be removed post-merge |
| LOW | 1 | `actions.py:1170` line-length pre-existing from CR-00029 |

**mandatory_fix_count: 0** (all MEDIUM violations are code-quality, not functional correctness)

---

## Verdict

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "CR-00028",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM",
      "category": "conventions",
      "file": "tests/unit/test_batch_manager.py",
      "line": 191,
      "description": "E501 line too long (106 > 100 chars)",
      "suggested_fix": "Break line after 'execution_group=0,'"
    },
    {
      "severity": "MEDIUM",
      "category": "conventions",
      "file": "tests/unit/test_batch_manager_blocking_terminal_set.py",
      "line": 12,
      "description": "F401 typing.Any imported but unused",
      "suggested_fix": "Remove 'from typing import Any'"
    },
    {
      "severity": "MEDIUM",
      "category": "conventions",
      "file": "tests/integration/test_abandon_merge_triggers_cascade.py",
      "line": 70,
      "description": "E501 line too long (106 > 100 chars)",
      "suggested_fix": "Break line at '=' to avoid 0.0.0.0 on same line as dashboard_host"
    },
    {
      "severity": "MEDIUM",
      "category": "conventions",
      "file": "tests/integration/test_merge_failure_does_not_cascade.py",
      "line": 68,
      "description": "S106 hardcoded password 'test' — add noqa suppression per codebase convention",
      "suggested_fix": "Add # noqa: S106 to match existing test_batch_manager.py pattern"
    },
    {
      "severity": "MEDIUM",
      "category": "conventions",
      "file": "tests/integration/test_abandon_merge_triggers_cascade.py",
      "line": 74,
      "description": "S106 hardcoded password 'test' — add noqa suppression per codebase convention",
      "suggested_fix": "Add # noqa: S106 to match existing test_batch_manager.py pattern"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2306 passed (unit), 1203 passed (integration), 0 failed",
  "missing_requirements": [],
  "notes": "Chain trace: MergeError → batch_item.status=merge_failed → _current_execution_group returns group → failed_in_prior_group is False (merge_failed not in _BLOCKING_TERMINAL_STATUSES) → no cascade → restart-merge resets to completed → re-merge picks up item. All 7 ACs covered. merge_abandoned event registered in both _TOAST_EVENTS and _TOAST_SEVERITY. Both buttons use hx-get modal pattern (no hx-confirm). _ITEM_ACTION_LABELS['abandon-merge'] has danger=True. xfail marker on test_merge_error_reverts_work_item_status now passes — suggest removing marker post-merge. Pre-existing line-length violation in actions.py:1170 from CR-00029 scope, not introduced by CR-00028."
}
```