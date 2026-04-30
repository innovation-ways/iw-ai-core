# F-00072_S04_CodeReview_Tests_prompt

**Work Item**: F-00072 -- Pragmatic Migration Safety + Schema Validation
**Step Being Reviewed**: S03
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00072/F-00072_Feature_Design.md`
- `ai-dev/active/F-00072/reports/F-00072_S03_Tests_report.md`
- `tests/unit/test_migration_roundtrip_targets.py`

## Output Files

- `ai-dev/active/F-00072/reports/F-00072_S04_CodeReview_report.md`

## Review Checklist

### 1. Coverage

- [ ] Roundtrip test file existence asserted.
- [ ] `@pytest.mark.integration` presence asserted.
- [ ] Parametrize-over-revisions asserted.
- [ ] Hardcoded-revision detection in test file (regex for 12-char hex strings).
- [ ] Rule 4a compliance: `downgrade -1` NOT present in the roundtrip test file.
- [ ] Workflow file existence asserted.
- [ ] `alembic check` string asserted.
- [ ] Action SHA-pin assertion via 40-char regex.
- [ ] Permissions minimality asserted.
- [ ] Postgres service container declaration asserted.

### 2. Test quality

- [ ] No live-DB calls.
- [ ] No flaky timing or network calls.
- [ ] Type hints + mypy clean.

### 3. Negative path

- [ ] Removing `alembic check` from the workflow makes `test_workflow_runs_alembic_check` fail clearly.
- [ ] Removing `@pytest.mark.integration` from the roundtrip test makes the corresponding assertion fail.

## Test Verification

- `uv run pytest tests/unit/test_migration_roundtrip_targets.py -v`
- `make lint`, `make typecheck`, `make test-unit`

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Test asserts wrong file path; SHA regex wrong (passes non-SHAs); test can pass when files are missing |
| HIGH | Missing key assertion (alembic check, integration marker, permissions check); negative path not verified |
| MEDIUM (fixable) | Regex too loose; missing assertion for parametrize check; assertion message not helpful |
| MEDIUM (suggestion) | Refactor / DRY opportunity |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00072",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
