# I-00062_S06_CodeReview_Tests_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Step Being Reviewed**: S05 (Tests)
**Review Step**: S06

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Read-only
introspection allowed. Testcontainers spawned by pytest fixtures are
exempt — Ryuk-managed. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB. **Do NOT run bare `make`.** `alembic history/current/show` is allowed.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- For runtime step state, prefer `uv run iw item-status I-00062 --json`.
- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document, ACs
- `ai-dev/active/I-00062/reports/I-00062_S05_Tests_report.md` — S05 report
- All four new test files listed in S05's `files_changed`:
  - `tests/unit/daemon/test_agent_subprocess_env.py`
  - `tests/integration/daemon/test_launch_step_env_isolation.py`
  - `tests/unit/orch_config/test_agent_context_failfast.py`
  - `tests/integration/db/test_i_00062_migration.py`

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S06_CodeReview_report.md` — review

## Context

S05 wrote four test files covering env stripping, env injection,
fail-fast guard, and migration round-trip. Verify the tests verify
**semantic correctness** (not just shape), cover all six ACs, and would
have caught the original bug.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the four test files:

```bash
make lint
make format
```

NEW violations → **CRITICAL** with `"category": "conventions"`.

## Review Checklist (I-00062-specific)

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

For EVERY assertion in the new tests, classify it:

- **Shape-only** (BAD): `assert "X" in dict`, `assert dict.get("X")`,
  `assert len(list) > 0` → flag as **CRITICAL** with `"category":
  "testing"`.
- **Semantic** (GOOD): `assert dict["X"] == "specific_value"`,
  `assert "X" not in dict`, `assert "specific_value" not in list` → OK.

If any assertion is shape-only AND that assertion is the primary check
for the AC it covers, flag CRITICAL. Auxiliary shape checks alongside a
semantic check are acceptable.

### 1. AC coverage (must be complete)

Confirm each AC from the design doc has at least one test that asserts
its specific behavior:

| AC | Description | Test that covers it (file → test) |
|----|-------------|------------------------------------|
| AC1 | Compose path injects per-worktree DB vars | `test_launch_step_env_isolation.py::TestLaunchStepInjectsWorktreeDBEnv::test_compose_stack_injects_all_five_db_vars` |
| AC2 | Snapshot orch creds, then strip baseline path | `test_agent_subprocess_env.py::test_snapshots_orch_creds_before_strip` AND `::test_strips_inherited_orch_db_vars` AND `::test_snapshot_does_not_overwrite_existing_orch_creds` |
| AC3 | Fail-fast in agent context with orch port | `test_agent_context_failfast.py::test_agent_context_with_orch_port_raises` AND `::test_legacy_worktree_with_inherited_orch_port_raises` |
| AC4 | Reproduction tests exist & pass | All four files |
| AC5 | Migration adds 4 columns, reversible | `test_i_00062_migration.py::test_upgrade_adds_four_columns` + `::test_downgrade_drops_four_columns` |
| AC6 | Browser-verification env injection still wins | `test_agent_subprocess_env.py::TestBrowserVerificationEnvStillWins::test_bv_env_overrides_strip` |

Note: tests for `_agent_subprocess_env` (a pure function — snapshot,
strip, extra merge) live in the **unit** file
`tests/unit/daemon/test_agent_subprocess_env.py`, NOT in the integration
file. The integration file
`tests/integration/daemon/test_launch_step_env_isolation.py` is
reserved for `_launch_step` interactions with a fake `BatchItem` /
`worktree_info`. If S05 placed `_agent_subprocess_env` tests in the
integration file, flag **MEDIUM (fixable)** with `"category":
"testing"`.

If any AC has no test, flag **HIGH** with `"category": "testing"`.

### 2. Pre-fix vs post-fix behavior

The S05 report should document, per test, whether it FAILS on pre-fix
code and PASSES on post-fix code. Tests that pass both before and after
the fix do not regress against the bug — flag **HIGH** with
`"category": "testing"` if the report doesn't establish this.

You can spot-check by reading the test logic and asking: "if I revert
S03's strip block, does this test still pass?" If yes, the test isn't
guarding the regression.

### 3. Test isolation

- No use of `importlib.reload(orch.config)` (project rule — see
  `CLAUDE.md`). Use `monkeypatch.delenv()` instead.
- No connection to live DB on port 5433 — testcontainers only.
- Testcontainer URLs replace `postgresql+psycopg2://` with
  `postgresql+psycopg://` (project rule).
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` runs after `Base.metadata.
  create_all()` in tests that don't go through alembic (only relevant
  if any new test bypasses alembic).

### 4. Test naming & organization

- File paths follow project convention:
  `tests/unit/<area>/test_<topic>.py` and
  `tests/integration/<area>/test_<topic>.py`.
- Class names describe the behavior under test, not the function under
  test.
- Test method names start with `test_` and read as a sentence.
- `@pytest.mark.integration` is on integration tests.

### 5. Fixtures & conftest

- New tests reuse existing fixtures from `tests/conftest.py`
  where applicable (don't reinvent testcontainer setup).
- No new fixtures added to global conftest unless reused by ≥2 tests.

### 6. Migration round-trip test

`tests/integration/db/test_i_00062_migration.py` must:
- Use a testcontainer (NOT 5433).
- Verify the four columns exist after upgrade.
- Verify the four columns are gone after downgrade -1.
- Verify all four are nullable.

If any of these are missing, flag **HIGH**.

### 7. Coverage of edge cases

- Operator context (no `IW_CORE_AGENT_CONTEXT`) bypasses the guard.
- `IW_CORE_ORCH_DB_PORT` unset: guard does nothing.
- `get_orch_db_url()` is NOT guarded (legitimate operator path).
- bv_env merge ordering: extra wins over strip.

If any edge case is uncovered, flag **MEDIUM (fixable)**.

### 8. NO live-DB writes from tests

Tests must NOT connect to port 5433. Testcontainers only. Any
hardcoded `localhost:5433` in test files → **CRITICAL** with
`"category": "architecture"`.

## Test Verification (NON-NEGOTIABLE)

Run all four new test files individually and the full unit + integration
suites. Confirm green. Pre-existing failures (if any) must be flagged
but not classified as new findings.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Shape-only primary assertion, live-DB connection, missing AC coverage |
| **HIGH** | Test doesn't differentiate pre-fix from post-fix, missing AC test, missing migration round-trip |
| **MEDIUM (fixable)** | Convention drift, missing edge case, weak test name |
| **MEDIUM (suggestion)** | Better fixture reuse, additional assertion |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00062",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/test_file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM (fixable) findings.
