# F-00070_S05_CodeReview_Final_prompt

**Work Item**: F-00070 -- Pre-commit Hardening
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00070/F-00070_Feature_Design.md`
- All step reports under `ai-dev/active/F-00070/reports/`
- `.pre-commit-config.yaml`
- `tests/unit/test_precommit_config.py`
- All files modified by S01's auto-fix (cross-reference S01 report)

## Output Files

- `ai-dev/active/F-00070/reports/F-00070_S05_CodeReview_Final_report.md`

## Review Checklist

### 1. Completeness vs Design

- [ ] All 4 ACs satisfied (hooks present, smoke catches deletion, repo hygienic, suite green).
- [ ] All 6 invariants hold (rev pinning, idempotent run, hook ID match, no new deps, gitignore intact, mypy compatible).

### 2. Cross-Step Consistency

- [ ] `EXPECTED_HOOK_IDS` in the test matches the actual hook list in the config.
- [ ] No hook in the config that the test doesn't assert (allowable — but flag MEDIUM_SUGGESTION if so).

### 3. Integration

- [ ] `pre-commit run --all-files` exits 0 on a fresh checkout.
- [ ] `make test-unit` passes including the new test.
- [ ] No file in `.env`, `.iw/`, `tests/output/`, `node_modules/`, `.venv/`, or any gitignored path was modified by S01.

### 4. Architecture

- No layer changes; this is a tooling/config feature only.

### 5. Security

- [ ] `detect-private-key` hook present and effective (verified by manually pasting a `-----BEGIN PRIVATE KEY-----\n...` test string into a temp file and running `pre-commit run detect-private-key --files <tmp>`; should fail). This is a sanity check for the reviewer; do NOT commit the temp file.

## Test Verification (NON-NEGOTIABLE)

1. `make lint`
2. `make format-check`
3. `make typecheck`
4. `make test-unit`
5. `make test-integration` — should pass (no integration logic changed)
6. `uv run pre-commit run --all-files` — exits 0

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "F-00070",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
