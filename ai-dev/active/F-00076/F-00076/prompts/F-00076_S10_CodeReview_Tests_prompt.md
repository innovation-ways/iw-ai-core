# F-00076_S10_CodeReview_Tests_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S10
**Agent**: code-review-impl
**Reviewing**: S09 (tests-impl)

---

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- `ai-dev/active/F-00076/reports/F-00076_S09_Tests_report.md`
- All test files added in S09

## Review Scope

1. **Coverage**:
   - Every Boundary Behavior row in the design has at least one mapping test.
   - All six Acceptance Criteria have at least one E2E or integration test asserting them.
   - All eight Invariants are testable via the test files (note in your report which test asserts which Invariant).

2. **Isolation**:
   - Each test creates and tears down its own data; no cross-test state leakage.
   - Tests follow `tests/CLAUDE.md` rules (no `importlib.reload`, FTS triggers, psycopg URLs).

3. **Robustness**:
   - Tests don't rely on wall-clock timing beyond reasonable bounds.
   - Performance smoke test has a sane threshold (100ms claimed in design — verify it's defensible on the daemon's typical hardware).
   - Held-event cadence test asserts EXACTLY 3 events (Invariant: one per cycle).

4. **No implementation changes** (this step's contract): S09 must NOT have modified S01–S07 files. Verify via git diff.

## Severity Levels

(Same as S02.)

## Output

`ai-dev/active/F-00076/reports/F-00076_S10_CodeReview_Tests_report.md`. Re-run `make test-unit` and `make test-integration`.

## Subagent Result Contract

(Same shape as S02.)
