# F-00071_S04_CodeReview_Tests_prompt

**Work Item**: F-00071 -- Local + CI Security Scanning
**Step Being Reviewed**: S03
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00071/F-00071_Feature_Design.md`
- `ai-dev/active/F-00071/reports/F-00071_S03_Tests_report.md`
- `tests/unit/test_security_targets.py`

## Output Files

- `ai-dev/active/F-00071/reports/F-00071_S04_CodeReview_report.md`

## Review Checklist

### 1. Test coverage of design

- [ ] Each of the 5 required Make targets is asserted (with prefix-match for `security-image-*`).
- [ ] Each required dev dep (`pip-audit`, `bandit`) is asserted.
- [ ] Workflow file existence asserted.
- [ ] Required workflow jobs asserted (`deps-audit`, `iac-scan`).
- [ ] Permissions minimality asserted (only `contents: read` + `security-events: write`).
- [ ] Action SHA pinning asserted via 40-char regex.
- [ ] Trigger types asserted (PR + push + schedule).
- [ ] Bandit `exclude_dirs` asserted.
- [ ] `.trivyignore` exists and has no active ignores.

### 2. Test quality

- [ ] Filesystem-only; no live-DB.
- [ ] Each parametrize case fails clearly when its target is removed.
- [ ] No flaky timing or network calls.
- [ ] Type hints + mypy clean.

### 3. Negative path

- [ ] Manually verify: stripping `security-deps` from the Makefile makes one parametrized case fail; restoring fixes it.
- [ ] Manually verify: changing an action pin to `@v4` makes `test_workflow_actions_pinned_to_sha` fail.

### 4. YAML parsing gotcha

- [ ] PyYAML parses `on:` as the boolean `True` (yaml's truthy aliasing). The test file handles both `data["on"]` and `data[True]` — confirm.

## Test Verification

- `uv run pytest tests/unit/test_security_targets.py -v`
- `make lint`, `make typecheck`, `make test-unit`

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Tests don't actually fail when the thing they guard is removed |
| HIGH | Missing a required assertion from the design (uncovered invariant or AC) |
| MEDIUM | Flaky assertion (timing, environment-dependent), poor error messages |
| LOW | Style, naming, minor coverage gaps |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00071",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
