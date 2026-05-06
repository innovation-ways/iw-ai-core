# I-00072 S04 Code Review — Tests

## Summary

Reviewed S03's test additions against `tests/unit/test_merge_queue_cli.py`. The two unit tests added (`TestRetryMergeParityOnly`) are sound: they verify identity (`is`) rather than equality (`==`), cover enum membership, and are correctly placed in the unit test file. No CRITICAL or HIGH findings.

The integration tests (in `tests/integration/test_merge_queue_retry.py`) were written in a prior step (S01/S02) and verified complete by S03. This review covers the unit test file only, per the step scope.

---

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_merge_queue_cli.py` | +63 lines: `TestRetryMergeParityOnly` class with 2 tests; docstring updated |

---

## Pre-Flight Gate (NON-NEGOTIABLE)

- **`make lint`** on `tests/unit/test_merge_queue_cli.py`: ✅ All checks passed (pre-existing E501 errors in `tests/integration/test_f00055_workflow_fixture.py` are out of scope for this step).
- **`make format-check`** on `tests/unit/test_merge_queue_cli.py`: ✅ Already formatted.
- Lint violations on new code in this file: **none**.

---

## Review Checklist

### 1. Semantic Correctness

**`test_i00072_cli_imports_recoverable_status_constant` (lines 39–57)**
- Identity check: `cli_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES` — **semantic, OK**.
- Enum membership assertion (lines 47–57): `frozenset({...}) == OPERATOR_RECOVERABLE_MERGE_STATUSES` — **semantic, OK**. Compares the same four members that the integration tests cover.

**`test_i00072_every_recoverable_status_has_a_regression_case` (lines 59–77)**
- Enum-coverage gate: `covered == OPERATOR_RECOVERABLE_MERGE_STATUSES` — **semantic, OK**. Adding a 5th status without a parametrised case fails loudly, exactly as designed.

### 2. Coverage Matrix

| Input | Required? | Covered by |
|-------|-----------|------------|
| `merge_failed` accepted | YES | `TestRetryMergeAcceptsRecoverableStatuses` parametrised case |
| `migration_invalid` accepted | YES | `TestRetryMergeAcceptsRecoverableStatuses` parametrised case |
| `migration_rebase_failed` accepted | YES | `TestRetryMergeAcceptsRecoverableStatuses` parametrised case |
| `migration_rolled_back` accepted | YES | `TestRetryMergeAcceptsRecoverableStatuses` parametrised case |
| Legacy `failed` + merge notes accepted | YES | `TestRetryMergeLegacyBackCompat::test_i00072_retry_merge_accepts_legacy_failed_with_merge_notes` |
| Legacy `failed` + non-merge notes rejected | YES | `TestRetryMergeLegacyBackCompat::test_i00072_retry_merge_rejects_legacy_failed_without_merge_notes` |
| Worktree-missing rejected | YES | `TestRetryMergeWorktreeMissing::test_i00072_retry_merge_rejects_missing_worktree` |
| CLI/dashboard parity (identity `is`) | YES | `TestRetryMergeParityOnly::test_i00072_cli_imports_recoverable_status_constant` + `TestRetryMergeParity::test_i00072_cli_and_dashboard_share_recoverable_status_set` |
| Enum-coverage assertion | YES | `TestRetryMergeParityOnly::test_i00072_every_recoverable_status_has_a_regression_case` |

All required cases are covered. Unit tests handle the import-only parity assertions; integration tests handle the full DB-backed semantic verification.

### 3. Falsifiability

- **`merge_failed` acceptance**: pre-S01 code would query only `failed` + `migration_rebase_failed` and exit non-zero for `merge_failed` rows. Confirmed falsifiable.
- **`migration_invalid` acceptance**: pre-S01 code would not match `migration_invalid`. Confirmed falsifiable.
- **Legacy `failed` + merge notes acceptance**: pre-S01 code already accepted `failed` blanket-style, so this is a **lock-in test** (not a falsifiability test against pre-S01). The design doc correctly notes this.
- **Legacy `failed` + non-merge notes rejection**: pre-S01 code accepted all `failed` rows, so this would have passed pre-S01 and now fails — confirmed falsifiable.
- **Identity `is` check**: pre-S01 code had no `OPERATOR_RECOVERABLE_MERGE_STATUSES` constant; the import itself would raise `ImportError` or produce a different object. Confirmed falsifiable.

### 4. Parity Test (`is`-Identity)

Both tests use `is` (identity), not `==` (equality):
- `cli_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES` (line 44)
- `dash_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES` (integration file line 345)

Both use `is` — **OK**.

### 5. Test Isolation and Determinism

- `TestRetryMergeParityOnly` uses only module-level imports and no mutable fixtures — **OK**.
- No shared mutable state between tests.
- Tests are pure import checks (no DB, no filesystem) — no isolation concerns.

### 6. Test Location

Both new tests are in `tests/unit/test_merge_queue_cli.py` — correct, per the design doc and I-00067 lesson. **OK**.

### 7. Naming and Discoverability

- `test_i00072_cli_imports_recoverable_status_constant` — starts with `test_i00072_`, states outcome in present tense. **OK**.
- `test_i00072_every_recoverable_status_has_a_regression_case` — starts with `test_i00072_`, present tense. **OK**.

### 8. No Accidental Scope Expansion

- No new test files created.
- No changes to fixtures in other modules.
- Scope is confined to `tests/unit/test_merge_queue_cli.py`. **OK**.

---

## Test Verification

```
tests/unit/test_merge_queue_cli.py: 11 passed (2 new + 9 pre-existing)
```

`make test-unit` confirms all 11 tests pass. Coverage failure is a pre-existing project-level threshold (46%) that is not reached when running a single test file in isolation — this is expected and not a test failure.

---

## Notes

1. **Placement decision was intentional**: S03 split coverage into unit (import-based parity + enum coverage) and integration (DB-backed semantic tests) files. This was a deliberate design choice to avoid the `live_db_guard` / dashboard import issue described in `tests/CLAUDE.md`. The unit tests correctly verify import identity without needing a testcontainer.

2. **Pre-existing lint/format violations** in `tests/integration/test_f00055_workflow_fixture.py` and `dashboard/app.py` are out of scope for this review — they predate I-00072.

3. **Legacy path lock-in**: The legacy back-compat acceptance test is correctly understood as a regression lock-in rather than a pre-fix falsifier. The design doc reflects this accurately.

---

## Verdict

**PASS** — zero CRITICAL, HIGH, or MEDIUM-fixable findings.

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00072",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "11 passed (tests/unit/test_merge_queue_cli.py), 0 failed",
  "notes": "Two unit tests added in TestRetryMergeParityOnly verify import identity (is) and enum membership. Integration tests in test_merge_queue_retry.py cover all DB-backed semantic outcomes. No issues found."
}
```