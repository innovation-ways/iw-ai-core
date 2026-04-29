# F-00070_S04_CodeReview_Tests_prompt

**Work Item**: F-00070 -- Pre-commit Hardening
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00070/F-00070_Feature_Design.md`
- `ai-dev/active/F-00070/reports/F-00070_S03_Tests_report.md`
- `tests/unit/test_precommit_config.py`

## Output Files

- `ai-dev/active/F-00070/reports/F-00070_S04_CodeReview_report.md`

## Review Checklist

### 1. Coverage of design

- [ ] All 12 expected hook IDs (3 existing + 8 new) are listed in `EXPECTED_HOOK_IDS`.
- [ ] Each ID is asserted via parametrize so failure messages identify which hook is missing.
- [ ] Rev-pin assertion rejects `HEAD`, `latest`, `main`, `master`.
- [ ] `--maxkb=<n>` assertion present.

### 2. Test quality

- [ ] Test file location: `tests/unit/test_precommit_config.py` (correct directory).
- [ ] No live-DB connections (filesystem-only).
- [ ] Uses `pyyaml`, which is verified to be in dev deps.
- [ ] Test names describe what they verify.
- [ ] No flaky timing or network calls.

### 3. Negative path

- [ ] If a hook is removed from the config, the corresponding parametrized test should fail clearly. Verify by manually removing one hook in a temp copy and re-running the test (the agent does this in TDD; the reviewer confirms test design).

### 4. Conventions

- Read `tests/CLAUDE.md`.
- File passes lint/typecheck.

## Test Verification

- `uv run pytest tests/unit/test_precommit_config.py -v`
- `make lint`, `make typecheck`, `make test-unit`

## Severity Levels (standard)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00070",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
