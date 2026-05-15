# I-00082_S03_Tests_prompt

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Input Files

- `ai-dev/active/I-00082/I-00082_Issue_Design.md` — see "Test to Reproduce" and the 4 ACs
- `ai-dev/work/I-00082/reports/I-00082_S01_Pipeline_report.md` — to know which helpers / new outcome enum exist
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — test rules
- `tests/conftest.py` — root fixtures

## Output Files

- `tests/integration/test_fix_cycle_scope_enforcement.py` (new file)
- `ai-dev/work/I-00082/reports/I-00082_S03_Tests_report.md`

## Context

Author the regression suite for I-00082. Three tests minimum, one per
acceptance criterion plus the operator-preservation case:

1. **Reproduction test (AC1, AC2)** — out-of-scope edit triggers
   `escalate-to-operator`; the agent's edits are preserved verbatim.
2. **Operator-preservation test (AC3)** — operator pre-edit on an
   out-of-scope file is NOT counted as a violation when the agent only
   edits in-scope files.
3. **Happy-path regression test (AC4)** — agent edits only in-scope files;
   cycle outcome is `pass` (or whatever the existing success enum value
   is); step advances normally.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Every assertion must verify a specific expected value, not just shape:

- BAD: `assert "outcome" in result` (shape only)
- GOOD: `assert result.outcome == "escalate-to-operator"` (semantic)
- BAD: `assert len(result.violation_paths) > 0`
- GOOD: `assert "out_of_scope.py" in result.violation_paths`

### Test fixture pattern

Use `tmp_path` for the worktree, monkeypatch the LLM agent runner to a
fake function that performs the desired edits, and call `run_fix_cycle()`
(or whatever entry point S01 exposes) directly. Do NOT shell out to the
real daemon — that is far too slow and brittle for a regression test.

If the cycle entry point requires a real DB session, use the
testcontainer-backed `db_session` fixture from `tests/conftest.py`. Do
NOT use sqlite (FOR UPDATE locking is part of the daemon contract — see
`tests/CLAUDE.md`).

## TDD Requirement

This step IS the test step. The reproduction test must FAIL against
pre-S01 code and PASS after S01. Confirm both directions before reporting:

```bash
# Should pass with S01 applied:
uv run pytest tests/integration/test_fix_cycle_scope_enforcement.py -v
```

If S01 is already applied (working tree state), record in your report
the test-id list and the passing summary. If you suspect S01 missed an
AC, raise it as a `blockers` entry — do NOT silently pass with weak
assertions.

## Test Verification (NON-NEGOTIABLE)

Run only the new test file:

```bash
uv run pytest tests/integration/test_fix_cycle_scope_enforcement.py -v
```

Do NOT run `make test-integration` — that is the S11 QV gate.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/test_fix_cycle_scope_enforcement.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "3 passed, 0 failed",
  "tdd_red_evidence": "n/a — S01 implementation already applied; tests are the regression suite",
  "blockers": [],
  "notes": ""
}
```
