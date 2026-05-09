# I-00075_S04_CodeReview_Tests_prompt

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy — see I-00075_S02_CodeReview_Backend_prompt.md for the full text.) S03 produces only an integration test file; no docker commands are in scope.

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.) S03 does NOT generate any migration. If a migration appears in the diff, that is a CRITICAL out-of-scope finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00075 --json`
- `ai-dev/active/I-00075/I-00075_Issue_Design.md` -- Design document, especially **§ Test to Reproduce**, **§ TDD Approach**, **§ Acceptance Criteria**
- `ai-dev/active/I-00075/reports/I-00075_S03_Tests_report.md` -- Implementation report
- `tests/integration/test_i00075_fix_cycle_fixture.py` -- The new test file
- `tests/CLAUDE.md` -- Test-suite conventions
- `tests/integration/conftest.py` -- To verify the session fixture name S03 chose is the canonical one

## Output Files

- `ai-dev/active/I-00075/reports/I-00075_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the integration tests written by S03 for the I-00075 fixture. The review focus:

1. **Semantic correctness** — every assertion checks specific values, not just shape (per the I003 lesson).
2. **Coverage of all four mandated test functions** — file-presence, semantic FixCycle, idempotency, WorkflowStep shape.
3. **Use of the canonical session fixture** — not a new ad-hoc one.
4. **Use of `_run_fixture` from `scripts.e2e_seed`** — not a manual `importlib.spec_from_file_location` call (which would bypass the daemon's loader path).

**Read the design doc BEFORE reading the test file.**

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in `tests/integration/test_i00075_fix_cycle_fixture.py` (vs. `main`) is a **CRITICAL** finding with `category: "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. All four mandatory tests are present

Per design's § TDD Approach and the S03 prompt § Requirements 2:

- [ ] `test_i00075_fixture_file_exists`
- [ ] `test_i00075_fixture_seeds_at_least_one_fix_cycle`
- [ ] `test_i00075_fixture_idempotent`
- [ ] `test_i00075_fixture_seeds_workflow_steps`

Missing any of the four is a HIGH finding.

### 2. Semantic correctness — assertion-by-assertion

Read each assertion. The bar is: "does this assertion fail when the fixture seeds the wrong data?"

For `test_i00075_fixture_seeds_at_least_one_fix_cycle`:
- [ ] Asserts **exactly 2** FixCycle rows (not `>= 1`, not `> 0`)
- [ ] Asserts cycle_numbers `{1, 2}` (set comparison) — catches duplicate-cycle bug
- [ ] Asserts step the cycles attach to has `step_id == "S02"` (string ID, not the autoincrement integer) — catches "wrong step" bug
- [ ] Asserts `trigger_type == FixTrigger.code_review`
- [ ] Asserts `status == FixStatus.completed`

For `test_i00075_fixture_idempotent`:
- [ ] Counts rows BEFORE and AFTER the second `_run_fixture` call
- [ ] Counts at least 3 tables (WorkItem, WorkflowStep, FixCycle) — catches partial idempotency
- [ ] Second call does NOT raise (wrapped in pytest.raises only if it should raise — it should NOT)

For `test_i00075_fixture_seeds_workflow_steps`:
- [ ] Asserts exactly 3 rows
- [ ] Asserts step_ids = `["S01", "S02", "S03"]` sorted
- [ ] Asserts step_types per step_number match `[implementation, code_review, quality_validation]`
- [ ] Asserts all `status == StepStatus.completed`

A test that uses `>= 1` or `> 0` where the design specifies an exact count is a HIGH finding tagged `testing` — it's the I003 anti-pattern.

### 3. Use of `_run_fixture` from `scripts.e2e_seed`

The S03 prompt explicitly requires this. If S03 instead used `importlib.util.spec_from_file_location` directly to import the fixture, that bypasses the production loader path and provides false coverage — flag as HIGH (`testing`) with suggestion to swap in `_run_fixture`.

### 4. Session fixture name

Verify the session fixture S03 used is one defined in `tests/integration/conftest.py` (or a parent conftest). A made-up name will fail at runtime with `fixture 'X' not found` — flag as CRITICAL.

### 5. Path-resolution discipline

`FIXTURE_PATH` MUST be derived from `Path(__file__).resolve().parents[2]` (or equivalent). Hardcoded absolute paths or `os.getcwd()` calls are HIGH findings — they break in CI and in worktree-relative test runs.

### 6. Project Conventions — `tests/CLAUDE.md`

- [ ] Test file is under `tests/integration/` (not `tests/dashboard/` or `tests/unit/`)
- [ ] No `importlib.reload(orch.config)` calls
- [ ] No live DB connection (port 5433); only the testcontainer session
- [ ] No `db.commit()` in the tests (the session fixture owns transaction lifecycle)

### 7. Out-of-scope changes

Per `workflow-manifest.json:scope.allowed_paths`, S03 may ONLY create `tests/integration/test_i00075_fix_cycle_fixture.py`. Any other file modified is a CRITICAL out-of-scope finding.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_i00075_fix_cycle_fixture.py -v 2>&1 | tail -30
```

All four tests MUST pass. Report results in the contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Wrong session fixture (test won't run), out-of-scope file modified | Must fix before merge |
| **HIGH** | Missing mandatory test, shape-only assertion, manual importlib bypassing `_run_fixture` | Must fix before merge |
| **MEDIUM (fixable)** | Lint violation, missing assertion message, hardcoded path | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Improved assertion phrasing, parametrize candidate | Optional |
| **LOW** | Nitpicks | Informational only |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00075",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed",
  "notes": ""
}
```
