# F-00073_S04_CodeReview_Tests_prompt

**Work Item**: F-00073 -- Smoke Gate + Active Test CI + Logging Tests
**Step Being Reviewed**: S03
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00073/F-00073_Feature_Design.md`
- `ai-dev/active/F-00073/reports/F-00073_S03_Tests_report.md`
- `tests/unit/test_make_targets.py`

## Output Files

- `ai-dev/active/F-00073/reports/F-00073_S04_CodeReview_report.md`

## Review Checklist

### 1. Coverage

- [ ] Smoke marker registration asserted.
- [ ] `make smoke` target presence asserted.
- [ ] `make smoke` uses `--strict-markers` asserted.
- [ ] `test-quality.yml` existence asserted.
- [ ] All four jobs (`lint-typecheck`, `unit`, `integration`, `smoke`) asserted via parametrize.
- [ ] Action SHA-pin assertion via 40-char regex.
- [ ] Permissions minimality asserted.
- [ ] At-least-10-smoke-tests assertion via `pytest --collect-only`.

### 2. Test quality

- [ ] No live-DB calls.
- [ ] Subprocess invocation of pytest is `--collect-only` only — no test execution; no fixture spin-up.
- [ ] No flaky network or timing.
- [ ] mypy-clean.

### 3. F-00069 coexistence

- [ ] New tests appended to existing `test_make_targets.py` without breaking existing F-00069 assertions.

### 4. Negative path

- [ ] Removing `make smoke` target makes `test_make_smoke_target_exists` fail clearly.
- [ ] Removing the `smoke` marker from pyproject makes `test_smoke_marker_registered` fail.
- [ ] Stripping a job from the workflow makes the parametrize case fail.

## Test Verification

- `uv run pytest tests/unit/test_make_targets.py -v`
- `make lint`, `make typecheck`, `make test-unit`

## Severity Levels (standard)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00073",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
