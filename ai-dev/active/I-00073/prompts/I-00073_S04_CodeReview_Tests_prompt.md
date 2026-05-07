# I-00073_S04_CodeReview_Tests_prompt

**Work Item**: I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Allowed exceptions: testcontainers spun up by pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Read-only `alembic history|current|show` only. **If S03 added a migration file, that is an automatic CRITICAL finding** — the test scenario depends on simulating drift, which means there must NOT be a migration.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00073 --json`.
- `ai-dev/active/I-00073/I-00073_Issue_Design.md`
- `ai-dev/active/I-00073/reports/I-00073_S03_Tests_report.md` — S03 report
- All files listed in S03's `files_changed`
- `tests/CLAUDE.md` — project test conventions

## Output Files

- `ai-dev/active/I-00073/reports/I-00073_S04_CodeReview_report.md` — Review report

## Context

You are reviewing the regression test suite written in S03 for **I-00073**.

The suite must (1) reproduce the pre-fix bug shape, (2) cover every patched callsite from S01, and (3) assert semantic correctness — not just exit codes.

Read S03's report — pay special attention to the `notes` field which should describe what S03 observed when they reverted S01's patches and re-ran the suite (the manual RED-check). If that paragraph is missing, vague, or implausible, that is at minimum a HIGH finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files → CRITICAL finding (`category: conventions`).

## Review Checklist

### 1. Coverage of Patched Callsites

S01 patched these CLI commands (per the design's Root Cause Analysis): `step-done`, `step-fail`, `step-restart`, `step-restart-from`, `step-skip`, `step-kill`, `step-start`, plus reads in `item-status`. S01 also patched both query shapes (Shape A — `select(Model)`; Shape B — `session.get(Model, key)`). The suite MUST have:

- One regression scenario per command, each driving the command against a column-drifted DB.
- For `item-status`, **two separate scenarios** — one drift on `work_items` (pins the Shape B `session.get(WorkItem, ...)` rewrite at item_commands.py:718) and one drift on `workflow_steps` (pins the Shape A `select(WorkflowStep)` rewrite at item_commands.py:724). A single combined scenario is NOT acceptable: it would still pass even if the agent only fixed one of the two shapes.
- One scenario that drops a `workflow_steps` column (covers `step_commands.py:141, 622, 730`).

Cross-reference S01's `files_changed` with S03's test names. Any uncovered command → **CRITICAL** finding (`category: testing`). A single combined `item-status` scenario instead of the two separate ones → **CRITICAL** finding (testing — the bug shapes are not pinned).

### 2. Semantic Correctness of Assertions

Every test must assert **both** (a) the command exited 0 (or the appropriate code) AND (b) the intended side-effect actually landed in the DB. A test that only asserts `result.returncode == 0` is shape-checking — that is the I003 lesson the design explicitly warned about.

For each test, walk the assertions and confirm they verify a specific expected DB state. Examples:
- `step-done` test must assert `step.status == "completed"` AND `latest_run.status == "completed"`.
- `step-fail` test must assert `step.status == "failed"` AND error_message contains the reason.
- `step-restart` test must assert `step.status == "pending"`.
- `item-status` test must assert specific JSON keys carry expected values, not just that JSON parses.

Any test that only checks exit code (or shape) → **CRITICAL** finding (`category: testing`).

### 3. Drift Simulation Is Real

The suite simulates drift by `ALTER TABLE ... DROP COLUMN ...` after `create_all`. Confirm:
- The dropped columns ARE declared on the in-process ORM (`orch.db.models`). Otherwise the simulation is vacuous.
- The drop is performed against the testcontainer DB, NOT the live DB on 5433.
- The dropped columns include at least one on `step_runs` and one on `work_items` (covering both affected tables).

If the simulation is fake (drops a column the ORM no longer declares, or doesn't actually drop anything), → **CRITICAL** finding (`category: testing`).

### 4. Subprocess Invocation

The reproduction test invokes `iw step-done` as a subprocess (via `subprocess.run` or similar). Confirm the test does NOT call `step_done()` directly — direct calls would bypass the real CLI process startup and could pass even with broken projection.

If any test calls the click function directly instead of as a subprocess → **HIGH** finding (`category: testing`).

### 5. Testcontainer Conventions

Per the project's CLAUDE.md and `tests/CLAUDE.md`:
- **MUST** replace `postgresql+psycopg2://` → `postgresql+psycopg://` on the testcontainer URL.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- **MUST NOT** mock the DB.
- **MUST NOT** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- **MUST NOT** connect to port 5433 (the live DB).

Any violation → **CRITICAL** finding (`category: conventions`).

### 6. Test Isolation

- Each test must spin up its own DB or use a fixture that resets state. No test should depend on state another test left behind.
- The dropped-column simulation must not leak into other test files (the testcontainer should be ephemeral).

### 7. Manual RED-Check Plausibility

S03's report `notes` field should describe what they observed when they reverted S01's patches and re-ran the suite. Confirm:
- The narrative mentions `UndefinedColumn` (the actual error from the bug).
- The narrative mentions a specific test that failed (the reproduction test, ideally).
- The narrative isn't generic boilerplate.

A missing or implausible RED-check description → **HIGH** finding (`category: testing`) — the suite may not actually pin the bug.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-integration` — every test must pass, including all new drift scenarios.
2. Run `make test-unit` — must still pass.
3. Optionally re-do the RED-check yourself if you doubt S03's report.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Missing coverage for a patched command, shape-only assertion, fake drift simulation, broken testcontainer convention, migration file added | Must fix before merge |
| **HIGH** | Direct function call instead of subprocess, missing/implausible RED-check description | Must fix before merge |
| **MEDIUM (fixable)** | Test naming, assertion clarity, helper extraction | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Style/structural improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00073",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X integration passed, 0 failed",
  "notes": ""
}
```
