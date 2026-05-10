# I-00075_S03_Tests_prompt

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (Ryuk-managed; self-destruct).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT generate or modify any alembic migration. The integration
test relies on the existing testcontainer fixtures (`tests/integration/conftest.py`)
which already run `Base.metadata.create_all()` + `FTS_FUNCTION_SQL` +
`FTS_TRIGGER_SQL` on a fresh container. Do NOT introduce a migration here.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00075 --json`
- `ai-dev/active/I-00075/I-00075_Issue_Design.md` -- Design document, especially **§ Test to Reproduce**, **§ TDD Approach**, and **§ Acceptance Criteria**
- `ai-dev/active/I-00075/reports/I-00075_S01_Backend_report.md` -- S01 implementation report
- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` -- The fixture under test
- `tests/CLAUDE.md` -- Test-suite conventions (READ FIRST — covers FTS DDL, testcontainer rules, conftest layout)
- `tests/conftest.py` and `tests/integration/conftest.py` -- Existing fixtures (find the canonical session-yielding fixture name; do NOT invent a new one)
- `tests/integration/test_e2e_seed.py` -- The reference test that exercises the broader e2e_seed flow; useful for fixture-loader patterns

## Output Files

- `tests/integration/test_i00075_fix_cycle_fixture.py` -- The new integration test file
- `ai-dev/active/I-00075/reports/I-00075_S03_Tests_report.md` -- Step report

## Context

You are writing the regression net for I-00075's fix.

The fix in S01 is a single fixture file. Without a regression test, that file can drift silently — a future refactor of `scripts/e2e_seed.py:_run_fixture` could break fixture loading semantics, or someone could rename the file and break the discovery. Your tests are the static guarantee that:

1. The fixture file exists at the expected path (file-presence guard).
2. When loaded, it produces ≥1 `FixCycle` row attached to a `WorkflowStep` whose `work_item_id == "I-99001"` (semantic guarantee — verifies the actual data the qv-browser step needs is there).
3. Re-running the fixture in the same session does not raise `IntegrityError` (idempotency guarantee).

These three checks together encode AC1, AC2, and AC3 of the design doc into the test suite.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "fix_cycles" in result` (shape only)
- GOOD: `assert fix_cycle_count == 2` (semantic — verifies the design-mandated 2 cycles)
- GOOD: `assert any(fc.cycle_number == 2 for fc in cycles)` (semantic — proves the second cycle row landed)
- GOOD: `assert all(fc.trigger_type == FixTrigger.code_review for fc in cycles)` (semantic)

Apply this rule to every assertion. The fixture's value comes from rendering exactly what the design requires. A test that only proves "≥1 fix cycle exists" would technically pass even if the fixture seeded the wrong trigger type or wrong cycle numbers, masking a real defect.

## Requirements

### 1. Test file location and naming

Create exactly one new test file at:

```
tests/integration/test_i00075_fix_cycle_fixture.py
```

The `tests/integration/` directory is correct because the test needs a real Postgres testcontainer (the fixture inserts ORM rows). Per `tests/CLAUDE.md`, this test MUST NOT be placed under `tests/dashboard/` (no dashboard `client` fixture in scope) or `tests/unit/` (unit tests do not get the `integration_db` session — they would fail with `fixture not found`).

### 2. Mandatory test functions

Author exactly the following four test functions:

#### 2a. `test_i00075_fixture_file_exists`

```python
def test_i00075_fixture_file_exists():
    """Pre-fix this assertion FAILS (file is absent); post-fix it PASSES.

    Reproduction test for I-00075 — proves the fixture file is present at the
    exact path the daemon's _apply_per_item_fixtures resolves at browser-
    verification time.
    """
    assert FIXTURE_PATH.is_file(), (
        f"Fixture {FIXTURE_PATH} must exist so qv-browser can render fix-cycle "
        f"amber pills against a seeded item — see I-00075 root cause analysis."
    )
```

`FIXTURE_PATH` is a module-level `pathlib.Path` constant computed from `Path(__file__)` so it is robust against the test runner's CWD.

#### 2b. `test_i00075_fixture_seeds_at_least_one_fix_cycle`

```python
def test_i00075_fixture_seeds_at_least_one_fix_cycle(<session_fixture>):
    """Semantic assertion: after the fixture runs, the DB MUST contain
    ≥1 FixCycle row attached to a WorkflowStep belonging to I-99001."""
```

The test MUST:

1. Look up the canonical session-yielding fixture name in `tests/integration/conftest.py` and use it (do NOT invent a new fixture name).
2. Call `_run_fixture(FIXTURE_PATH, session)` — `from scripts.e2e_seed import _run_fixture`.
3. Call `session.flush()` (NOT `commit`).
4. Issue a SELECT joining `FixCycle` and `WorkflowStep` filtered by `WorkflowStep.work_item_id == "I-99001"` AND `WorkflowStep.project_id == "iw-ai-core"`.
5. Assert **exactly 2 rows** (per design's deliberate 2-cycle count, see Issue_Design.md § Notes and § Requirements 3).
6. Assert the cycle_numbers are `{1, 2}` (set comparison) — proves the loop generated both cycles, not the same cycle twice.
7. Assert the FixCycle.step_id resolves to a WorkflowStep with `step_id == "S02"` — proves the cycles attached to the right step.
8. Assert all rows have `trigger_type == FixTrigger.code_review` and `status == FixStatus.completed`.

#### 2c. `test_i00075_fixture_idempotent`

```python
def test_i00075_fixture_idempotent(<session_fixture>):
    """Running the fixture a second time on the same session is a safe no-op."""
```

The test MUST:

1. Run `_run_fixture` once, `session.flush()`, count rows.
2. Run `_run_fixture` a second time on the same session — must NOT raise.
3. `session.flush()`.
4. Count rows again — must equal the first count (no duplicate inserts).

Cover three tables in the count: `WorkItem`, `WorkflowStep`, `FixCycle` (semantic — checks that the idempotency guard short-circuits correctly without partial re-insertion).

#### 2d. `test_i00075_fixture_seeds_workflow_steps`

```python
def test_i00075_fixture_seeds_workflow_steps(<session_fixture>):
    """The fixture seeds exactly 3 WorkflowStep rows so the pipeline strip
    is meaningfully wide (the qv-browser V1 verifies a multi-step pipeline)."""
```

The test MUST assert:

1. Exactly 3 `WorkflowStep` rows for `(project_id="iw-ai-core", work_item_id="I-99001")`.
2. Their `step_id` values, sorted, equal `["S01", "S02", "S03"]`.
3. Their `step_type` values match `[StepType.implementation, StepType.code_review, StepType.quality_validation]` in step_number order.
4. All rows have `status == StepStatus.completed`.

### 3. Imports

Use the same import discipline as the rest of the integration suite. The minimum set:

```python
from __future__ import annotations
from pathlib import Path

from sqlalchemy import select

from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
)
from scripts.e2e_seed import _run_fixture
```

`_run_fixture` is the canonical fixture-loader; the integration test MUST use it (do not import the fixture file directly with `importlib` — that bypasses the same loader path the daemon uses, defeating the regression guarantee).

### 4. Module-level constants

Match the path-resolution pattern used by `tests/integration/test_e2e_seed.py` (read it first):

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "ai-dev" / "active" / "I-00075" / "e2e_fixtures" / "001_fix_cycle_demo.py"
```

Do NOT hardcode the absolute path. Do NOT use `os.getcwd()`.

### 5. Allow-list — files you may touch

Per `workflow-manifest.json:scope.allowed_paths`, S03 may ONLY create:

- `tests/integration/test_i00075_fix_cycle_fixture.py`

Do NOT modify `tests/conftest.py`, `tests/integration/conftest.py`, the fixture file from S01, or any other file. If a test fixture you need does not exist, that is a blocker — STOP and raise it.

## Project Conventions

Read the project's `CLAUDE.md` and `tests/CLAUDE.md`:

- **NEVER** connect tests to live DB (port 5433) — use testcontainers only. The `<session_fixture>` you reference MUST resolve to a testcontainer-backed session.
- **NEVER** call `importlib.reload(orch.config)` in tests — use `monkeypatch.delenv()` instead.
- **MUST** replace psycopg2 URLs in testcontainers: handled by existing fixtures.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests — handled by existing fixtures (don't re-issue).

When in doubt, mirror `tests/integration/test_e2e_seed.py`'s structure.

## TDD Requirement

You write tests AFTER the S01 implementation. The reproduction guarantee is preserved by:

1. Mentally reverting S01 (`git stash` the fixture file in your scratch session — DO NOT actually commit a revert) to confirm `test_i00075_fixture_file_exists` fails.
2. Restoring the fixture and re-running — it passes.

Per CLAUDE.md updates, **do NOT actually run `git stash` / `git checkout` to revert S01's file at runtime** — that is a thrash-prone manual revert RED-check that the project policy disallows. The conceptual revert is the design-time argument; your job is to ship the test that *would have* failed pre-fix.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the new test file.
3. **`make lint`** — must report zero errors.

If a tool isn't available, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

After writing the tests, run **only** the new test file:

```bash
uv run pytest tests/integration/test_i00075_fix_cycle_fixture.py -v
```

ALL FOUR tests MUST pass. Do **NOT** run `make test-integration` or `make test-unit` — full-suite execution is owned by the S11/S12 QV gates downstream and would burn this step's timeout budget (see I-00073/S03 post-mortem, 2026-05-08).

Do NOT report `tests_passed: true` unless all four targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_i00075_fix_cycle_fixture.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
