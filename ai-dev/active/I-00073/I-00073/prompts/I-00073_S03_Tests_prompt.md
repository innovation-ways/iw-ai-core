# I-00073_S03_Tests_prompt

**Work Item**: I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Allowed exceptions: testcontainers spun up by pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This incident MUST NOT add or modify migrations** (any new file under `orch/db/migrations/versions/` would be a CRITICAL regression — the test scenario depends on simulating drift, which means there is intentionally NO migration). Read-only `alembic history|current|show` is fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00073 --json`.
- `ai-dev/active/I-00073/I-00073_Issue_Design.md` — Design document (read the "Test to Reproduce" and "TDD Approach" sections carefully)
- `ai-dev/active/I-00073/reports/I-00073_S01_Backend_report.md` — S01 report (knows which callsites were patched)
- `tests/conftest.py` — testcontainer fixtures, FTS DDL setup, URL replacement rules
- `tests/CLAUDE.md` — project test conventions
- `orch/cli/step_commands.py` and `orch/cli/item_commands.py` — patched files

## Output Files

- `tests/integration/cli/test_step_commands_drift.py` — NEW reproduction + regression tests
- `ai-dev/active/I-00073/reports/I-00073_S03_Tests_report.md` — Step report

## Context

You are writing the regression suite that proves I-00073 is fixed and prevents it from regressing. The bug: agent-facing CLI commands (`iw step-done`, `step-fail`, `step-restart`, `step-skip`, `step-kill`, `step-start`, `item-status`) crash with `psycopg.errors.UndefinedColumn` when the worktree's ORM declares a column on `step_runs` or `work_items` that the live orchestration DB has not yet acquired (because the relevant migration is unapplied).

The fix in S01 narrowed every such read to use a column-projected SELECT (via `load_only(...)`). Your job is to write tests that:

1. **Reproduce the bug shape** — fail against the unpatched code, pass against the patched code.
2. **Cover every patched callsite** — one regression scenario per CLI command listed in the Root Cause Analysis table of the design.
3. **Assert semantic correctness** — not just exit code 0, but that the intended side-effect actually landed in the DB.

## Requirements

### 1. New test file: `tests/integration/cli/test_step_commands_drift.py`

Use the existing testcontainer fixture from `tests/conftest.py`. Per the rules in `tests/CLAUDE.md` and the project's CLAUDE.md:

- **MUST** replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- **MUST NOT** mock the database.
- **MUST NOT** connect tests to the live DB on port 5433.

The test pattern: build a fresh testcontainer DB with the full current schema, then drop a specific column to simulate "the live orch DB hasn't received this feature's migration yet". Use `ALTER TABLE step_runs DROP COLUMN diff_text` (and friends) in a setup helper. The dropped columns must be ones the in-process ORM still declares — that is the simulated drift.

### 2. Reproduction test (`test_step_done_tolerates_missing_step_runs_column`)

The canonical reproduction. Invoke `iw step-done` as a subprocess (so we exercise the real CLI process, not just the function), against the drifted DB. Assertions (semantic correctness — see the warning below):

```python
# 1. The command succeeded
assert result.returncode == 0, f"step-done exited {result.returncode}: {result.stderr}"
# 2. The exact error that fired before the fix is absent
assert "UndefinedColumn" not in result.stderr
assert "step_runs.diff_text" not in result.stderr
# 3. The step actually advanced to completed (not a silent no-op)
assert _step_status(db_url, "F-99999", "S01") == "completed"
# 4. The running StepRun was actually marked completed
assert _latest_step_run_status(db_url, "F-99999", "S01") == "completed"
```

**Critical**: do NOT replace the subprocess invocation with a direct call into `step_done()`. The subprocess form is what proves the drift is tolerated end-to-end (driver, ORM session creation, full SELECT projection, full UPDATE projection). A direct function call could pass even if the projection was still wrong.

### 3. Regression scenarios — one per patched command

| Test name | Command exercised | Drift |
|-----------|-------------------|-------|
| `test_step_done_tolerates_missing_step_runs_column` | `iw step-done` | drop `step_runs.diff_text` |
| `test_step_fail_tolerates_missing_step_runs_column` | `iw step-fail` | drop `step_runs.diff_text` |
| `test_step_restart_tolerates_missing_work_items_column` | `iw step-restart` | drop `work_items.diff_text` |
| `test_step_restart_from_tolerates_missing_workflow_steps_column` | `iw step-restart-from` | drop one column from `workflow_steps` (covers the WorkflowStep `select(...)` paths at step_commands.py:622, 730) |
| `test_step_skip_tolerates_missing_step_runs_column` | `iw step-skip` | drop `step_runs.diff_text` |
| `test_step_kill_tolerates_missing_step_runs_column` | `iw step-kill` | drop `step_runs.diff_text` |
| `test_step_start_tolerates_missing_work_items_column` | `iw step-start` | drop `work_items.diff_text` (also exercises `_get_workflow_step` helper at step_commands.py:141, so a missing WorkflowStep column would surface here too) |
| `test_item_status_tolerates_missing_work_items_column` | `iw item-status` | drop ONLY a `work_items` column. **This scenario specifically covers the `session.get(WorkItem, ...)` path at item_commands.py:718** — `session.get` emits a full-column SELECT just like `select(WorkItem)`, so a fix that only rewrote the `select(WorkflowStep)` line at item_commands.py:724 would still let this test fail. |
| `test_item_status_tolerates_missing_workflow_steps_column` | `iw item-status` | drop ONLY a `workflow_steps` column |

For each scenario, after asserting the command succeeded, **also** assert the side-effect:

| Command | Side-effect to verify |
|---------|----------------------|
| step-done | step.status == completed AND latest StepRun.status == completed |
| step-fail | step.status == failed AND latest StepRun.status == failed AND error_message contains the reason |
| step-restart | step.status == pending AND new StepRun row count incremented |
| step-restart-from | target step + every subsequent step is reset to pending; runs for the cleared steps marked superseded or removed per the command's existing semantics |
| step-skip | step.status == skipped |
| step-kill | step.status == failed AND active run.status == killed (no real PID needed — seed `pid=None`) |
| step-start | step.status == in_progress AND work_item.status == in_progress |
| item-status | exit 0 AND JSON output has the expected work_item fields (id, status, steps[]) — verify SPECIFIC values, not just key presence |

**Why the two `item-status` scenarios are split**: the WorkItem-only drift specifically pins the `session.get(WorkItem, ...)` rewrite from S01 (Shape B). The `workflow_steps`-only drift pins the `select(WorkflowStep)` rewrite (Shape A). A combined "drop on both tables" test would still pass even if the agent only fixed one of the two shapes.

### 4. Drift simulation helper

Create a small helper inside the test module:

```python
def _drop_column(engine, table: str, column: str) -> None:
    """Simulate worktree-vs-live-DB drift by dropping a column the in-process
    ORM still declares. Used to reproduce I-00073."""
    with engine.begin() as conn:
        conn.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}"))
```

The columns to drop in this test (the F-00079 columns) MUST exist on the current model — confirm by reading `orch/db/models.py` first. If by the time this test runs F-00079 has been merged but a different in-flight feature has added different columns, switch the dropped columns to whatever the model now declares that did NOT exist 2 migrations ago. The test needs at least one column on `step_runs`, one on `work_items`, and one on `workflow_steps` to drop (one per affected table — the design's RCA covers all three).

### 5. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- **BAD**: `assert "permissions" in data` (shape only)
- **BAD**: `assert result.returncode == 0` *alone* (does not prove the side-effect happened)
- **GOOD**: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- **GOOD**: `assert _step_status(db_url, item, step) == "completed"` (semantic — verifies the DB actually advanced)
- **GOOD**: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Every assertion in this suite must verify the bug-actually-fixed condition, not just that the command exited cleanly.

### 6. Verify the suite ACTUALLY catches the bug

Before declaring done, do this manual sanity check (do NOT commit the revert):

1. `git stash` your test file.
2. `git checkout HEAD~1 -- orch/cli/step_commands.py orch/cli/item_commands.py` (restore the broken pre-S01 versions).
3. `git stash pop`.
4. Run `make test-integration -- tests/integration/cli/test_step_commands_drift.py`.
5. Confirm AT LEAST the reproduction test (`test_step_done_tolerates_missing_step_runs_column`) FAILS with an error mentioning `UndefinedColumn`.
6. `git checkout HEAD -- orch/cli/step_commands.py orch/cli/item_commands.py` (restore the fixed versions).
7. Re-run the suite — all tests must now pass.

Write a short paragraph in your report describing what you observed in steps 5 and 7. **If the suite passes against the broken code, the test does not actually pin the bug** — go back and tighten it (most likely you forgot the side-effect assertion, or the subprocess didn't pick up the patched files).

## Project Conventions

Read `tests/CLAUDE.md` carefully — testcontainer URL replacement, FTS DDL execution after `create_all`, `monkeypatch.delenv()` (NEVER `importlib.reload(orch.config)`), append-only invariant on `step_runs`.

Match the style of existing integration tests under `tests/integration/cli/` (or wherever the CLI tests live — `grep -r "uv run iw" tests/integration/` to find them).

## TDD Requirement

This step IS the RED phase for the regression. The implementation already happened in S01. Your job:

1. **RED check**: confirm S01's pre-fix state would have failed your tests (the manual revert exercise above).
2. **GREEN**: confirm S01's actual code makes them pass.
3. No REFACTOR — these are tests.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving touched files.
3. **`make lint`** — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-integration` — your new tests AND every existing test must pass.
2. Run `make test-unit` — must still pass.
3. Do **NOT** report `tests_passed: true` unless ALL tests pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/cli/test_step_commands_drift.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X integration passed, 0 failed (including N new drift scenarios)",
  "blockers": [],
  "notes": "Manual RED-check observation: <what you observed when you reverted S01's patches and re-ran the suite>"
}
```
