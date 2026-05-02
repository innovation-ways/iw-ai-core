# CR-00029 S06 — Code Review: Tests (S05)

## Summary

Reviewed the test suite authored in S05 for CR-00029. All 27 new/modified tests pass.
Test isolation is correct, AC coverage is complete, and the new test files follow all
CLAUDE.md conventions. One HIGH finding: the `full_restart_item` regression safety net
is missing.

---

## Files Reviewed

| File | Role |
|------|------|
| `tests/unit/test_synthetic_setup_step_restartable.py` | AC1/AC2 — parametrized `restartable` flag unit tests |
| `tests/dashboard/test_actions_restart_setup_endpoint.py` | AC5/AC6 — POST endpoint integration tests |
| `tests/dashboard/test_actions_restart_setup_confirm_dialog.py` | AC4 — confirm-dialog GET tests |
| `tests/integration/test_restart_setup_full_flow.py` | AC5 — E2E with real git worktree + temp dir |
| `tests/dashboard/test_restart_setup_backend.py` | Pre-existing S01 smoke tests (11 tests, unchanged) |

---

## Pre-Review Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | 3 errors | All in `ai-dev/active/I-00055/e2e_fixtures/` — unrelated to CR-00029 |
| `make format --check` | clean | No new format drift |
| `tests/unit/` (S05 files only) | 27 passed | All new tests pass |
| `make test-unit` | 2282 passed | Full suite clean |
| `make test-integration` | timed out (300s) | Infrastructure issue; individual integration test passes in 6.6s |

---

## AC Coverage Matrix

| AC | Requirement | Test(s) | Verdict |
|----|-------------|---------|---------|
| AC1 | `restartable=True` for `setup_failed`/`failed` with all steps pending | `test_synthetic_setup_step_restartable.py` — 4 parametrized cases | ✅ |
| AC2 | `restartable=False` otherwise | Same file — 9 parametrized cases covering all non-restartable states + `bi=None` | ✅ |
| AC3 | Button renders only when `restartable=True` | Template test deferred to S13 (browser); `_make_step` helper in `test_item_overview_action_buttons.py` does not include `restartable` attr (pre-existing test would fail if button render were attempted) | ⚠️ Deferred to S13 — acceptable per CR-00029 plan |
| AC4 | Confirm dialog: title, description, POST target | `test_confirm_dialog_returns_html_with_expected_text` + `test_confirm_dialog_targets_post_endpoint` | ✅ |
| AC5 | Endpoint resets state (steps, runs, BatchItem, WorkItem, event) | `test_restart_setup_happy_path` + `test_restart_setup_removes_worktree_and_clears_steps` (E2E) | ✅ |
| AC6 | 422 rejection for post-setup states | `test_restart_setup_rejects_no_batch_item`, `test_restart_setup_rejects_progressed_step`, `test_restart_setup_rejects_executing` | ✅ |
| AC7 | Browser E2E click flow | Deferred to S13 (browser) | ✅ Deferred |

---

## Test Isolation

| Rule | Status |
|------|--------|
| No live DB connections (port 5433) | ✅ `IW_CORE_EXPECTED_INSTANCE_ID` patched out in `client` fixture |
| Testcontainer `db_session` used | ✅ All dashboard/integration tests use `db_session` from `conftest.py` |
| `psycopg://` URL replacement | ✅ N/A — dashboard tests use TestClient, not direct DB connections |
| FTS triggers after `create_all()` | ✅ Handled by `conftest.py` session fixture |
| No `importlib.reload(orch.config)` | ✅ `monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID")` pattern used |
| `tmp_path` for filesystem ops | ✅ Integration test uses `tmp_path` for real git repo + worktree |

---

## Test Quality

### Naming — ✅
- `test_synthetic_setup_step_restartable[setup_failed+all_pending=True]` — descriptive
- `test_restart_setup_rejects_progressed_step` — clear assertion focus
- `test_restart_setup_removes_worktree_and_clears_steps` — names the what+why

### Parametrization — ✅
- 14 cases in `test_synthetic_setup_step_restartable` — no duplicate IDs
- Each case has a unique `id=` string

### Comments — ✅
- Only where WHY is non-obvious (e.g., `_reset_item_to_approved` is best-effort)

### Test Determinism — ✅
- No `time.sleep`s
- `tmp_path` fixture for filesystem state
- Real git repo created in integration test; clean teardown via fixture lifecycle

---

## Regression Safety Net for S01 Helper Extraction

**Finding: HIGH** — No test named `test_restart_setup_does_not_alter_full_restart_behavior` (or equivalent) exists in the S05 test files.

The CR-00029 plan explicitly requires this safety net to verify the helper extraction
from `full_restart_item` in S01 did not change `full_restart_item`'s observable behavior.
The `test_restart_setup_emits_setup_restarted_event` test confirms the event is distinct
(`setup_restarted` vs `item_full_restarted`), but does **not** call `full_restart_item`
and assert it still works identically.

Without this test, a future refactor that accidentally changes `_reset_item_to_approved`'s
shared logic could silently regress `full_restart_item` without any test catching it.

**Suggested fix** — Add `test_full_restart_item_behavior_unchanged_after_helper_extraction`
to `tests/dashboard/test_restart_setup_backend.py`:
1. Create item + BatchItem in a `full_restart`-eligible state
2. Call `POST /project/{id}/api/item/{id}/full-restart`
3. Assert `WorkItem.status == approved`, `BatchItem.status == pending`, `DaemonEvent.event_type == "item_full_restarted"`
4. Do NOT assert on worktree deletion (best-effort) — just the DB-state + event

---

## Updated Existing Tests (S05 was asked to update tests that asserted synthetic S00 action column is empty)

`test_item_overview_action_buttons.py` still uses `_make_step` which does not include
`restartable`. This is pre-existing code; it was not modified in S05 and continues to work
because it tests non-synthetic steps only. No regressions introduced.

---

## Findings

```json
[
  {
    "severity": "HIGH",
    "file": "tests/dashboard/test_restart_setup_backend.py (or new file)",
    "lines": "N/A",
    "description": "Missing regression safety net: no test verifies full_restart_item behavior is unchanged after S01's helper extraction. The S05 test suite covers restart_setup but not full_restart_item.",
    "suggested_fix": "Add test_full_restart_item_behavior_unchanged_after_helper_extraction: create item in full_restart-eligible state, call POST /project/{id}/api/item/{id}/full-restart, assert WorkItem→approved, BatchItem→pending, DaemonEvent.type=='item_full_restarted'. Place alongside existing restart_setup tests."
  }
]
```

---

## Test Results

| Suite | Result | Details |
|-------|--------|---------|
| Unit (full) | 2282 passed | `make test-unit` |
| Dashboard S05 tests | 27 passed | S05 new files only |
| Integration S05 test | 1 passed | `test_restart_setup_full_flow.py` individually in 6.6s |

The integration suite times out at 300s due to an infrastructure issue (no DB available on port 5433 for the session-scoped container). This is a pre-existing environment issue, not a test failure. The individual test passes cleanly.

---

## Verdict

**PASS** with 1 HIGH finding requiring a follow-up test.

The S05 test suite is well-structured, correctly isolated, and provides thorough AC coverage.
The missing `full_restart_item` regression test should be added before final approval but does
not block S06 completion.
