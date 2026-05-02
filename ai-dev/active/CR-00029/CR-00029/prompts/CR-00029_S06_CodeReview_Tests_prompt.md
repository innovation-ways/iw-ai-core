# CR-00029_S06_CodeReview_Tests_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md` — AC1–AC7
- `ai-dev/active/CR-00029/reports/CR-00029_S05_Tests_report.md`
- All files in S05's `files_changed`

## Output Files

- `ai-dev/active/CR-00029/reports/CR-00029_S06_CodeReview_Tests_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings.

## Review Checklist

### 1. Coverage matrix

Build an AC-coverage matrix:

| AC | Test |
|----|------|
| AC1 (restartable=True for setup-only) | `test_synthetic_setup_step_restartable.py` parametrized |
| AC2 (restartable=False otherwise) | same file, parametrized |
| AC3 (button renders only when restartable) | NOTE: AC3 is template-level; verify a template-rendering test covers it OR confirm S13 (browser) covers it |
| AC4 (confirm-dialog) | `test_actions_restart_setup_confirm_dialog.py` |
| AC5 (endpoint resets state) | `test_actions_restart_setup_endpoint.py::test_restart_setup_happy_path` + `test_restart_setup_full_flow.py` |
| AC6 (precondition rejects post-setup) | `test_actions_restart_setup_endpoint.py::test_restart_setup_rejects_*` |
| AC7 (E2E click flow) | DEFERRED to S13 (browser) |

Any uncovered AC = HIGH finding (or CRITICAL if it's not even in the deferred list).

### 2. Test isolation

- No live-DB connections (port 5433)
- Testcontainer fixtures for integration tests
- FTS triggers installed after `create_all()`
- `psycopg://` URL (not `psycopg2://`)
- No `importlib.reload(orch.config)` — `monkeypatch.delenv()` instead

### 3. Test determinism

- No flaky `time.sleep`s
- No reliance on filesystem state from sibling tests
- Parametrization is correct (no duplicate IDs)
- The integration test creates a real temp dir for the worktree and asserts cleanup — `tmp_path` fixture used

### 4. `full_restart_item` regression check

The `test_restart_setup_does_not_alter_full_restart_behavior` test (or equivalent) verifies the helper extraction did NOT change `full_restart_item`'s observable behavior. This is a critical safety net for the S01 helper refactor.

If this test is missing, that's a HIGH finding — without it, S01's refactor risks silent regression.

### 5. Test naming and clarity

- Names describe the assertion ("test_X_when_Y_then_Z")
- One assertion focus per test (parametrize for related cases)
- Comments only where the WHY is non-obvious

### 6. Updated existing tests

S05 was asked to update existing tests that asserted the action column for synthetic S00 was empty. Verify those updates are present and correct.

`grep -r "is_synthetic" tests/` to spot-check.

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
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00029",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "AC coverage matrix attached"
}
```
