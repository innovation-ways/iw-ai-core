# CR-00028_S08_CodeReview_Tests_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — AC1–AC7
- `ai-dev/active/CR-00028/reports/CR-00028_S07_Tests_report.md`
- All files in S07's `files_changed`

## Output Files

- `ai-dev/active/CR-00028/reports/CR-00028_S08_CodeReview_Tests_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings.

## Review Checklist

### 1. Coverage

Build an AC-coverage matrix and verify EVERY AC has at least one test:

| AC | Description | Test File(s) |
|----|-------------|--------------|
| AC1 | merge_failed on MergeError | `test_merge_queue_merge_failed_status.py::test_merge_error_writes_merge_failed_not_failed` |
| AC2 | merge_failed doesn't cascade | `test_merge_failure_does_not_cascade.py` |
| AC3 | migration_invalid/rebase don't cascade | `test_merge_failure_does_not_cascade.py` (parametrized) |
| AC4 | no-worktree-path still produces failed | `test_merge_queue_merge_failed_status.py::test_no_worktree_path_still_writes_failed` |
| AC5 | restart-merge resumes queue | `test_actions_restart_merge_preconditions.py` |
| AC6 | abandon-merge triggers cascade | `test_abandon_merge_triggers_cascade.py` |
| AC7 | dashboard renders new badge/buttons | DEFERRED to S15 (browser) |

If any AC is uncovered, that's a HIGH finding.

### 2. Test Isolation

- No live-DB connections (port 5433)
- Testcontainer fixtures used for integration tests
- FTS triggers installed after `create_all()`
- `psycopg://` URL (not `psycopg2://`) — `tests/CLAUDE.md`
- No `importlib.reload(orch.config)` — `monkeypatch.delenv()` instead

### 3. Test Determinism

- No flaky `time.sleep`s
- No reliance on filesystem state from other tests
- Mocks are surgical, not blanket — see if any test mocks `BatchItem` directly when it should use a real testcontainer row

### 4. Test Naming & Clarity

- Test function names describe the assertion ("test_X_when_Y_then_Z")
- One assertion focus per test (parametrize for related cases)
- No `assert True` placeholders
- Comments only where the WHY is non-obvious

### 5. Updated Existing Tests

S07 was asked to identify existing tests that asserted `BatchItemStatus.failed` after a merge error and update them. Verify the list in S07's report covers all relevant cases. Spot-check by `grep -r "BatchItemStatus.failed" tests/` for tests adjacent to merge-error paths.

### 6. Project Conventions

Read `tests/CLAUDE.md`. Verify all critical rules are followed.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass with zero failures.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "CR-00028",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "AC coverage matrix attached"
}
```
