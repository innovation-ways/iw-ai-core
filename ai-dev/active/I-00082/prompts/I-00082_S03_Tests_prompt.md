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
- `ai-dev/work/I-00082/reports/I-00082_S01_Pipeline_report.md` — names the helpers (`_scope_match`, `_implicit_allows`, `_captured_paths`) and confirms `FixStatus.escalated` is the outcome to assert on
- `tests/integration/test_fix_cycle_scope_enforcement.py` — already exists; S01 authored the AC1 reproduction test in it. You will **extend**, not overwrite.
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — test rules
- `tests/conftest.py` — root fixtures

## Output Files

- `tests/integration/test_fix_cycle_scope_enforcement.py` — **modified** (S01 created it with one `def test_i00082_fix_cycle_escalates_on_out_of_scope_edit`; you append two more tests below)
- `ai-dev/work/I-00082/reports/I-00082_S03_Tests_report.md`

## Context

S01 already authored the AC1 reproduction test as part of its RED-first
TDD step (see S01 report). Your job is to extend the same file with the
two remaining regression tests so all 4 ACs are covered:

1. **Reproduction test (AC1, AC2)** — **already present from S01**, do not
   re-write. You may rename or refactor for clarity but the assertion
   semantics (`assert cycle.status == FixStatus.escalated`,
   `assert "out_of_scope.py" in cycle.fix_metadata["scope_violations"]`,
   agent's edit preserved verbatim) must remain.
2. **Operator-preservation test (AC3)** — **new, you author it**. Operator
   pre-edits a file outside `allowed_paths` *before* the cycle starts;
   the agent then edits only in-scope files. Assert: cycle status is
   `FixStatus.completed` (NOT `escalated`); the operator's file is
   untouched; `fix_metadata.get("scope_violations", [])` is empty.
3. **Happy-path regression test (AC4)** — **new, you author it**. Agent
   edits only files inside `allowed_paths`. Assert: cycle status is
   `FixStatus.completed`; step advances normally; no
   `scope_violation_escalation` DaemonEvent emitted for the cycle.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Every assertion must verify a specific expected value, not just shape:

- BAD: `assert "status" in cycle.__dict__` (shape only)
- GOOD: `assert cycle.status == FixStatus.escalated` (semantic — uses the existing enum value)
- BAD: `assert len(cycle.fix_metadata.get("scope_violations", [])) > 0`
- GOOD: `assert "out_of_scope.py" in cycle.fix_metadata["scope_violations"]`

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

S01 already captured RED → GREEN evidence for the AC1 reproduction test
when it implemented the fix. Your two new tests (AC3, AC4) are written
against the GREEN tree — they must pass on first run. **Do NOT** revert,
stash, or `git checkout` any S01 file at runtime to artificially produce
RED — this is forbidden by the project's test prompt rules (causes thrash
and timeouts). Pre-fix reproduction was done at design time; runtime is
GREEN-only.

If you suspect an AC is uncovered by your new tests, OR that the
reproduction test from S01 has a weak/shape-only assertion, raise it as a
`blockers` entry — do NOT silently pass.

```bash
# All three tests must pass:
uv run pytest tests/integration/test_fix_cycle_scope_enforcement.py -v
```

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
  "test_summary": "3 passed, 0 failed (AC1 from S01 + AC3/AC4 added here)",
  "tdd_red_evidence": "AC1 RED→GREEN captured by S01; AC3/AC4 are regression tests added on top of the implemented fix — no runtime RED check (forbidden by project policy)",
  "blockers": [],
  "notes": ""
}
```
