# CR-00010 S06 Code Review Report

## Summary

**Reviewed**: S05 (tests-impl)  
**Verdict**: PASS  
**Mandatory fixes**: 0

## Test Results

| Suite | Result |
|-------|--------|
| Unit tests | 850 passed, 5 warnings |
| Integration tests | 513 passed, 8 failed |
| ruff check | All passed |
| ruff format | All passed |

The 8 integration failures are all `TestGlobalSearch::*` in `test_doc_polish.py` — confirmed pre-existing (fail on clean checkout, unrelated to CR-00010).

## AC Coverage Map

| AC | Test(s) | Status |
|----|---------|--------|
| AC1: `iw approve` rejects research | `test_validate_approve_transition_rejects_research` (unit) + `test_research_auto_complete_end_to_end` (integration) | COVERED |
| AC2: `iw unapprove` rejects research | `test_validate_unapprove_transition_rejects_research` (unit) + `test_research_unapprove_errors` (integration) | COVERED |
| AC3: `iw doc-update` auto-completes | `test_research_auto_complete_end_to_end` — verifies `work_item_auto_completed: true`, status=completed, phase=done, completed_at set | COVERED |
| AC4: idempotent on completed | `test_research_doc_update_idempotent` — verifies `work_item_auto_completed: false` on second call | COVERED |
| AC5: non-research untouched | `test_doc_update_non_research_does_not_autocomplete` — F-00001 stays draft | COVERED |
| AC6: batch-create rejects research | `test_batch_create_rejects_research_item` — correct error substring + no Batch row | COVERED |
| AC7: state machine transitions | `test_work_item_status_transitions_type_aware` (18 param) + `test_validate_work_item_status_type_aware` (9 param) | COVERED |
| AC8: dashboard hides approve/unapprove | S14 browser verification (not S05 scope); `test_research_item_detail_hides_approve` noted as template guard verification in S05 | DELEGATED |
| AC9: batch-queue excludes research | `test_batch_queue_excludes_research_items` + `test_batch_queue_draft_items_excludes_research` | COVERED |
| AC10: skill docs new flow | Manual read of `skills/iw-research/SKILL.md` | DELEGATED |

## Review Checklist Findings

### 1. AC Coverage Map ✅
All ACs verified against actual test code. No test claims to cover an AC without exercising the required behavior.

### 2. Test Quality ✅
- **Isolation**: All integration tests use testcontainer via `db_session` fixture, not live DB port 5433.
- **No DB mocking**: No `mock` usage in integration tests.
- **No `importlib.reload(orch.config)`**: Not found in any changed test file.
- **psycopg driver**: testcontainer URLs use `postgresql+psycopg://` — via fixtures, not hardcoded.
- **Test names**: Follow `test_<behavior>_<condition>` pattern throughout.
- **Assertions**: Exact AC substrings used — `"Cannot approve research items"`, `"Cannot unapprove research items"`, `"research item"` + `"cannot be added to a batch"`.

### 3. Pre-Existing Test Updates ✅
- S01 report listed `TestGlobalSearch` failures. All 8 remain — confirmed pre-existing and unrelated to CR-00010.
- No other pre-existing tests were modified to fit new fixtures.

### 4. No Skipped / xfail Tests ✅
The only `xfail` found is in `test_code_qa_sse_wire.py:342` (pre-existing, unrelated to CR-00010). No skip/xfail markers added by S05.

### 5. Regression Surface ✅
No non-research tests were modified by S05. Existing tests remain unchanged.

### 6. Idempotency & Edge Cases
- AC4 (idempotent): COVERED
- AC5 (non-research untouched): COVERED
- **Ad-hoc research doc edge case** (doc_id with no matching work item): NOT TESTED — MEDIUM finding, not a CRITICAL gap as it is not an AC.

### 7. Test Code Quality ✅
- Helpers reused from `conftest.py` via fixtures (`db_session`, `test_project`, `cli_get_session`).
- No hardcoded project IDs — uses `test_project` fixture.
- No `sleep()` calls.
- No unused imports.

### 8. Conventions ✅
- Unit tests under `tests/unit/` have no DB session.
- Integration tests use the `db_session` fixture correctly.
- No test creates its own schema without FTS trigger.

## Findings

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00010",
  "step_reviewed": "S05",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM",
      "category": "edge_case_coverage",
      "description": "Ad-hoc research doc path (doc-update on research doc_id with no matching work item) has no test. Design notes call this out explicitly.",
      "location": "tests/integration/test_cli_core.py"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "850 unit passed, 513 integration passed, 8 failed (pre-existing GlobalSearch failures)",
  "missing_requirements": [],
  "notes": "AC8 and AC10 are correctly delegated to S14 and manual review respectively per the S05 report. The 8 integration failures are pre-existing and unrelated to CR-00010. All new tests for CR-00010 pass."
}
```

## Files Changed (by S05)

| File | Changes |
|------|---------|
| `tests/unit/test_state_machine.py` | +18 parameterized cases for research transitions (AC7) |
| `tests/unit/test_cli_core.py` | +6 unit tests for validate_approve/unapprove research rejection (AC1, AC2) |
| `tests/integration/test_cli_core.py` | +4 integration tests: e2e auto-complete (AC1+AC3), idempotent (AC4), unapprove rejection (AC2), non-research untouched (AC5) |
| `tests/integration/test_cli_batches.py` | +1 test for batch-create research rejection (AC6) |
| `tests/integration/test_dashboard_pages.py` | +2 tests for batch-queue research exclusion (AC9); extended `make_item` with `item_type` param |
