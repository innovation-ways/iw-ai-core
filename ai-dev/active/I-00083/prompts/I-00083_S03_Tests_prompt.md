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

- `tests/integration/test_branch_base_drift.py` (**extend** — the file
  already exists; S01 created it with the AC1 reproduction. Add to it,
  do not rewrite or delete S01's test.)
- `ai-dev/work/I-00083/reports/I-00083_S03_Tests_report.md`

## Context

S01 already shipped the AC1 reproduction test inline as part of its
TDD cycle. This step **extends** the same file with the remaining
coverage and refactors common setup into reusable helpers.

Tests to add (do NOT remove or rename S01's AC1 test):

1. **Happy-path regression (AC3)** — single in-flight item; verify the
   daemon log line emits `in_flight_siblings=[]
   sibling_paths_without_merge=0` and that approval + worktree-create
   behavior is byte-equivalent (or at minimum behaviourally equivalent)
   to today's solo-item flow.
2. **Sibling-scope-check unit coverage** — exercise the new
   `batch_manager.py` helper directly:
   - Multiple in-flight siblings with non-overlapping `allowed_paths`
     → per-sibling counts each non-zero, total is their sum.
   - Sibling with merge commit already on `main` → count is zero.
   - Sibling whose `allowed_paths` glob matches nothing in B's tree
     → count is zero.
3. **Chore-commit allow-list coverage** — call the new narrowed
   `approve` path with a fixture `ai-dev/active/<ID>/` that contains
   a deliberate non-design file (e.g. `notes.txt`); assert the commit
   ships only the design/manifest/prompts allow-list and NOT
   `notes.txt`.

Refactor common setup (fake repo, simulated chore commit, simulated
in-flight impl) into module-level helpers at the top of the file so
S01's AC1 test and the new tests share the same fixtures. Document the
helpers with one-line docstrings.

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

S01 already captured RED → GREEN evidence for AC1. This step adds
regression and coverage tests against the already-implemented fix; all
new tests must pass at green and continue to pass under the existing
behavior. AC1's existing test must keep passing — do not modify it.

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
  "test_summary": "N passed, 0 failed (AC1 from S01 still green; AC3 + sibling-scope + chore-allow-list added)",
  "tdd_red_evidence": "n/a — extends S01's RED-proven test file with regression and coverage; AC1 RED evidence lives in the S01 report",
  "blockers": [],
  "notes": ""
}
```
