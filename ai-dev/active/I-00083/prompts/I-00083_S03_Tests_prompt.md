# I-00083_S03_Tests_prompt

**Work Item**: I-00083 — Branch-base drift across in-flight items
**Step**: S03
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/I-00083/I-00083_Issue_Design.md` — see "Test to Reproduce" and 3 ACs
- `ai-dev/work/I-00083/reports/I-00083_S01_Pipeline_report.md`
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- `tests/integration/test_branch_base_drift.py` (new file)
- `ai-dev/work/I-00083/reports/I-00083_S03_Tests_report.md`

## Context

Two tests minimum:

1. **Reproduction test (AC1, AC2)** — simulate items A and B both in
   flight; verify B's worktree does not inherit A's broken-state test
   files.
2. **Happy-path regression (AC3)** — single item; verify approval and
   worktree creation are byte-equivalent (or at least behaviourally
   equivalent) to today.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "in_flight_siblings" in log_line` (shape only)
- GOOD: `assert "in_flight_siblings=[A-99001]" in log_line` (semantic)
- BAD: `assert b_worktree.exists()`
- GOOD: `assert not (b_worktree / "tests" / "test_drift.py").exists()`

### Fixture pattern

Use a fake git repo under `tmp_path` with helpers to: (a) initialize a
"main" branch, (b) simulate a chore commit, (c) simulate an in-progress
unmerged impl, (d) call the new approve / worktree-create entry points
directly. Do not shell out to the real `iw` command — use the
underlying functions for speed and isolation.

If a real DB session is needed, use the testcontainer-backed `db_session`
fixture.

## TDD Requirement

This step is the test step. The reproduction test must FAIL against
pre-S01 code and PASS after S01.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_branch_base_drift.py -v
```

Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/test_branch_base_drift.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "tdd_red_evidence": "n/a — S01 implementation already applied; tests are the regression suite",
  "blockers": [],
  "notes": ""
}
```
