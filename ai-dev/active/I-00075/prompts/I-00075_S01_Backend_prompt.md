# I-00075_S01_Backend_prompt

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step**: S01
**Agent**: backend-impl

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
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT generate or modify any alembic migration. The fixture you
write inserts at runtime against an already-existing schema (the per-worktree
DB seeded from production via pg_dump, or the integration testcontainer).
Do NOT run any alembic command. If you find yourself reaching for one, STOP
and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00075 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00075/I-00075_Issue_Design.md` -- Design document (read every section, especially **Root Cause Analysis**, **Fix Plan → S01 row**, **Notes**, and **Acceptance Criteria → AC1**)
- `ai-dev/archive/F-00055/e2e_fixtures/001_f00055_workflow.py` -- Reference implementation; copy its idempotency guard, insert-order discipline, and use of `db.flush()` between parent/child inserts
- `scripts/e2e_seed.py` -- Read the **Per-item fixtures** docstring section (lines 19–48) to understand the contract: `def seed(db: Session) -> None`, idempotent, lexical load order
- `scripts/e2e_apply_item_fixtures.py` -- Read to understand exactly how the fixture will be invoked at browser-verification time
- `orch/db/models.py` -- All ORM models you will instantiate: `WorkItem`, `WorkItemType`, `WorkflowStep`, `StepType`, `StepStatus`, `StepRun`, `RunStatus`, `FixCycle`, `FixTrigger`, `FixStatus`, `Batch`, `BatchStatus`, `BatchItem`, `BatchItemStatus`

## Output Files

- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` -- The new fixture file
- `ai-dev/active/I-00075/reports/I-00075_S01_Backend_report.md` -- Step report

## Context

You are implementing the only code-producing step of **I-00075**.

The bug: browser verification of `dashboard/templates/components/step_pipeline.html:33-41` (the amber `↺SXX` fix-cycle pill branch) cannot be verified because no item in the per-worktree E2E DB has `fix_cycle_count > 0`. CR-00039 S08 V3 was forced to return `n/a / env_data_missing` for this reason.

Your fix: author a **single** fixture file that, when loaded by `scripts/e2e_apply_item_fixtures.py I-00075` inside the per-worktree compose stack (or by `_run_fixture(...)` from `scripts/e2e_seed.py` in the integration test), seeds a synthetic completed item whose step pipeline meaningfully exercises the amber pill render branch.

This is a **test-data fixture**, not production code. It is loaded only when `IW_E2E_SEED=1` (the production guardrail in `orch/db/identity.py` blocks production execution).

## Requirements

### 1. File location and naming

Create exactly one file at:

```
ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py
```

The `001_` prefix is REQUIRED — `scripts/e2e_seed.py:_discover_fixture_files` loads files in lexical order; do not break that pattern by skipping the prefix. The file MUST NOT start with `_` (private/init modules are skipped by the discoverer — see `scripts/e2e_seed.py:_discover_fixture_files` and `scripts/e2e_apply_item_fixtures.py:main`).

### 2. Module shape: top-level docstring + `seed(db: Session)` callable

The file MUST export a **single** top-level callable named `seed` with the signature:

```python
def seed(db: Session) -> None:
    ...
```

`scripts/e2e_seed.py:_run_fixture` will fail with `RuntimeError("... has no callable seed(db: Session) -> None")` if the symbol is missing, mis-typed, or not callable. Do NOT also expose any other public top-level symbols beyond `seed` and the module-level constants you use; the F-00055 reference fixture is the canonical shape — match it.

The module-level docstring MUST briefly state:
- What rows it seeds (item, step count, fix-cycle count)
- That it is idempotent
- The work-item ID `I-99001` it uses
- A pointer back to `ai-dev/active/I-00075/I-00075_Issue_Design.md` for the rationale

### 3. Synthetic data shape

Insert exactly the following rows under `project_id = "iw-ai-core"`:

**Batch** (1 row):
- `id="BATCH-I00075DEMO"` (uppercase, no spaces — keeps it visually distinct from real `BATCH-D-####` IDs)
- `status=BatchStatus.completed`
- `max_parallel=4`
- `cli_tool="opencode"`
- `auto_publish=False`

**BatchItem** (1 row):
- `batch_id="BATCH-I00075DEMO"`
- `work_item_id="I-99001"`
- `execution_group=0`
- `status=BatchItemStatus.merged`

**WorkItem** (1 row):
- `id="I-99001"` (chosen well outside the live `iw next-id` allocation range — DO NOT change to a smaller number)
- `type=WorkItemType.Issue`
- `title="Fix-cycle demo (I-00075 fixture)"`
- `status="completed"`
- `phase="done"`
- `summary="Synthetic item seeded by I-00075 fixture so qv-browser can render fix-cycle amber pills."`
- `design_doc_content="Synthetic demo item created by ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py for fix-cycle UI verification. See I-00075_Issue_Design.md."`
- `created_at=datetime.now(UTC)`

**WorkflowStep** (3 rows): `S01`, `S02`, `S03` with `step_number=1, 2, 3`, `agent_label="opencode"`, `step_type=StepType.implementation` for S01, `StepType.code_review` for S02, `StepType.quality_validation` for S03, all with `status=StepStatus.completed` and identical `started_at`/`completed_at = datetime.now(UTC)`.

**StepRun** (4 rows): one run for S01 (`run_number=1`), one run for S03, and **three runs** for S02 (`run_number=1, 2, 3`) — this gives S02 a `run_count > 1` so the History page's runs column shows non-trivial data alongside the fix cycles. All with `status=RunStatus.completed`, `cli_tool="opencode"`.

**FixCycle** (2 rows on S02 only): `cycle_number=1` and `cycle_number=2`, `trigger_type=FixTrigger.code_review`, `status=FixStatus.completed`. This is the key data — these two rows are what makes `step_pipeline.html` render two amber `↺S02` pills with title attributes "↺S02: fix cycle 1" and "↺S02: fix cycle 2".

The exact 2-cycle count is deliberate: it exercises both `loop.index` formatting and the multi-pill connector chain (one `iw-pipeline-connector--fixcycle` div per pill) in `step_pipeline.html:35`.

### 4. Idempotency

Mirror the F-00055 reference fixture's idempotency guard:

```python
existing = db.execute(
    select(WorkflowStep).where(
        WorkflowStep.project_id == PROJECT_ID,
        WorkflowStep.work_item_id == WORK_ITEM_ID,
    )
).scalars().first()
if existing is not None:
    return
```

This is intentionally a coarse guard: it short-circuits the entire fixture if the WorkflowStep rows are already present, which (per F-00055) is sufficient because the WorkflowStep insert is the first child write that would conflict.

### 5. Insert order discipline (read the e2e_seed.py docstring)

`scripts/e2e_seed.py` lines 32–43 explain the FK insert-order gotcha. `BatchItem→Batch` and `BatchItem→WorkItem` have ORM `relationship()` declarations, so SQLAlchemy will sort their INSERTs correctly. **However**, `WorkflowStep`, `StepRun`, and `FixCycle` rely on you explicitly calling `db.flush()` after each parent insert before child inserts reference its autoincrement `id`. Do NOT skip these `db.flush()` calls — they are what make the fixture work without `ForeignKeyViolation`.

The recommended insert sequence (mirrors F-00055):
1. `db.add(batch); db.flush()`
2. `db.add(batch_item); db.flush()`
3. `db.add(work_item); db.flush()`
4. For each step: `db.add(workflow_step); db.flush()` and store the resulting object in a `dict[str, WorkflowStep]` so step IDs can be looked up by their string ID for run/cycle FK references.
5. For each StepRun: `db.add(run)` then `db.flush()` after the loop.
6. For each FixCycle: `db.add(cycle)` then `db.flush()` after the loop.

Do NOT call `db.commit()` — the caller (`scripts/e2e_seed.py:seed` and `scripts/e2e_apply_item_fixtures.py:main`) owns the commit.

### 6. Module-level constants

Match the F-00055 fixture's style:

```python
PROJECT_ID = "iw-ai-core"
WORK_ITEM_ID = "I-99001"
AGENT_LABEL = "opencode"
```

Hardcode these. Do NOT read them from environment variables — the fixture must be deterministic across every worktree.

### 7. Imports

Use the same import discipline as `ai-dev/archive/F-00055/e2e_fixtures/001_f00055_workflow.py`:

```python
from __future__ import annotations
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    FixCycle,
    FixStatus,
    FixTrigger,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
```

The `TYPE_CHECKING` guard around `Session` is intentional — the fixture is not meant to import sqlalchemy.orm at runtime.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries (this fixture lives outside the `orch/` and `dashboard/` layers — it's test-data, not production code)
- Coding conventions and naming rules (ruff config in `pyproject.toml`)
- The append-only nature of `step_runs`, `fix_cycles`, `daemon_events` (you are writing fresh rows; never `UPDATE`)
- The composite-PK convention `(project_id, id)` for `work_items` and `batches`

Follow all rules defined there exactly. When in doubt, match the F-00055 reference fixture.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: The reproducing assertion is `tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_file_exists` (S03 will write it). Pre-fix the file does not exist; that test fails. Your S01 work makes it pass.
2. **GREEN**: Write the minimal fixture that satisfies AC1 + AC2 + AC3 in the design document.
3. **REFACTOR**: Confirm the fixture matches the F-00055 reference style. Do NOT add helper functions, classes, or abstractions — keep the file shape symmetrical with F-00055.

Do not skip the RED phase. The S03 test author will write the failing test BEFORE running this fixture for verification, then re-run after.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report. Skipping any of these wastes a fix-cycle slot
when the QV gate steps catch the same issue downstream.

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the new fixture
   file. Errors elsewhere are pre-existing — note them in your report but do
   not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the `preflight` object recording
the result of each command (`"ok" | "fixed" | "skipped:<reason>"`).

## Test Verification (NON-NEGOTIABLE)

After implementing the fixture, verify ONLY the integration test that exercises
your file. Do NOT run the full suite — `make test-integration` is the S12 QV
gate's job.

```bash
uv run pytest tests/integration/test_i00075_fix_cycle_fixture.py -v
```

If S03 has not yet authored that test (it runs AFTER you), do a static lint of
your fixture by importing it under a python REPL one-liner instead — that
proves the file parses and `seed` is callable:

```bash
uv run python -c "import importlib.util; \
spec = importlib.util.spec_from_file_location('demo', 'ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py'); \
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); \
assert callable(m.seed), 'seed must be callable'"
```

Do NOT report `tests_passed: true` if either the targeted test or this
import-shape probe fails.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "import-shape probe passed (S03 not yet authored)",
  "blockers": [],
  "notes": ""
}
```
