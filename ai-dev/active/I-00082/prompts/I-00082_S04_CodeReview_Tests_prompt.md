# I-00082_S04_CodeReview_Tests_prompt

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00082/I-00082_Issue_Design.md`
- `ai-dev/work/I-00082/reports/I-00082_S03_Tests_report.md`
- `tests/integration/test_fix_cycle_scope_enforcement.py`

## Output Files

- `ai-dev/work/I-00082/reports/I-00082_S04_CodeReview_report.md`

## Review Checklist

### CRITICAL

- **Reproduction test (AC1) would fail pre-fix.** Sanity-check by reading
  the test logic against the pre-S01 fix-cycle behaviour (drift / silent
  pass). The test was authored in S01 and the file now contains S01's
  AC1 test plus S03's AC3 and AC4 additions. If AC1 would have passed
  against pre-fix code too, it is not actually a regression test —
  flag it.
- **Correct enum value asserted.** The cycle outcome is
  `FixStatus.escalated` (existing value at `orch/db/models.py:165`), NOT
  a new string `escalate-to-operator`. Flag CRITICAL if any test
  asserts against a fabricated outcome string.
- **Semantic assertions only.** No `len(...) > 0` / `"status" in result`
  shape checks. Each assertion must pin a specific expected value.

### HIGH

- All 4 ACs covered by the file's 3 tests: AC1 (escalation — from S01),
  AC2 (regression test exists — meta; the file's existence is the proof),
  AC3 (operator-preservation — from S03), AC4 (in-scope happy path —
  from S03).
- No live DB usage (port 5433); only testcontainer or `tmp_path`.
- No `agent-browser` / direct `chromium.launch()` (this step is non-UI
  but the rule is project-wide).
- No runtime source-revert RED-checks (`git stash`, `git checkout HEAD~1`,
  etc.) — flag CRITICAL if any test (or test fixture) reverts S01's code
  to manufacture a RED state.

### MEDIUM

- Test naming: `test_i00082_<scenario>` style.
- Fixture cleanup: `tmp_path` is auto-cleaned by pytest, fine.
- Monkeypatch teardown uses pytest's auto-restore.

## Verdict

`pass` or `needs-fix` with grouped findings.

## Subagent Result Contract

Standard `code-review-impl` JSON.
