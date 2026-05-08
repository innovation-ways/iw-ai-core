# I-00073_S01_Backend_prompt

**Work Item**: I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items
**Step**: S01
**Agent**: Backend

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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

**This incident MUST NOT add or modify migrations.** The whole point of the
fix is to make the agent-facing CLI tolerate the gap between an in-worktree
ORM that has unmerged column additions and the live orchestration DB whose
schema is still at the prior head. Adding a migration would defeat the
test scenario. If you find yourself wanting to write a migration, STOP and
re-read the design — your fix should live entirely in
`orch/cli/step_commands.py`, `orch/cli/item_commands.py`, and the docs.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for current step list, status, prompt paths, gate commands, prefer `uv run iw item-status I-00073 --json`. The `workflow-manifest.json` is a design-time snapshot and may be out of date.
- `ai-dev/active/I-00073/I-00073_Issue_Design.md` — Design document
- `orch/cli/step_commands.py` — primary patch target
- `orch/cli/item_commands.py` — secondary patch target
- `docs/IW_AI_Core_Agent_Constraints.md` — append the resilience subsection here
- `orch/db/models.py` — to confirm column names per Mapped class

## Output Files

- `ai-dev/active/I-00073/reports/I-00073_S01_Backend_report.md` — Step report

## Context

You are implementing the fix for **I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items**.

Read `ai-dev/active/I-00073/I-00073_Issue_Design.md` first — the Root Cause Analysis section enumerates every callsite that needs patching and tells you exactly which `select(Model)` queries are full-ORM (broken) and which are already column-projected (the reference pattern at `orch/cli/step_commands.py:649-654`). Then read `CLAUDE.md` and `orch/CLAUDE.md` for project conventions.

The drift this fix tolerates is structural and intentional — it follows from agent constraint R2 ("agents write migrations, daemon applies") and cannot be eliminated. The CLI must accept it, not resolve it.

## Requirements

### 1. Pin a "core column set" per affected ORM model

For each of `StepRun`, `WorkItem`, `WorkflowStep`, decide which columns the agent-facing CLI commands actually read or write. Define those at module scope as a tuple of `Mapped` attribute references — e.g.:

```python
# orch/cli/step_commands.py — module top, near the imports
_STEP_RUN_CLI_COLUMNS = (
    StepRun.id,
    StepRun.step_id,
    StepRun.run_number,
    StepRun.status,
    StepRun.pid,
    StepRun.pid_alive,
    StepRun.last_heartbeat,
    StepRun.error_message,
    StepRun.exit_code,
    StepRun.log_file,
    StepRun.log_content,
    StepRun.report_file,
    StepRun.worktree_path,
    StepRun.started_at,
    StepRun.completed_at,
    StepRun.duration_secs,
)
```

(That is illustrative — derive the *actual* set from the live code by walking every CLI callsite and listing every attribute it reads or writes on the loaded entity. Err on the side of including known columns rather than under-projecting; the goal is "no SELECT mentions a column the live DB might not have", not "smallest possible projection".)

Do the same for `WorkItem` and `WorkflowStep` if any agent-facing command reads them via full ORM SELECT. Add the pinned sets to `orch/cli/item_commands.py` if needed there too — keep each module's pinned set local to that module to avoid cross-module coupling.

### 2. Replace every full-ORM agent-facing SELECT with a column-projected one

In **`orch/cli/step_commands.py`** and **`orch/cli/item_commands.py`** patch every callsite enumerated in the design's Root Cause Analysis table. The table covers TWO shapes — handle both:

**Shape A — `select(Model).where(...)`**: rewrite with `load_only`. The idiomatic SQLAlchemy 2.0 way:

```python
from sqlalchemy.orm import load_only

step_run = session.execute(
    select(StepRun)
    .options(load_only(*_STEP_RUN_CLI_COLUMNS))
    .where(StepRun.step_id == step.id, StepRun.status == RunStatus.running)
    .order_by(StepRun.run_number.desc())
    .limit(1)
).scalar_one_or_none()
```

`load_only` produces a SELECT that emits only the listed columns (plus the primary key, which SQLAlchemy always projects). The returned entity is a real `StepRun` instance — every existing call site that mutates it (`step_run.status = ...`, `step_run.completed_at = ...`, etc.) keeps working unchanged.

**Shape B — `session.get(Model, key)`**: this looks like a primary-key lookup but SQLAlchemy still emits a full-column SELECT (with all `Mapped[]` attributes) when the entity is not in the identity map. The fix is to rewrite each `session.get` with an explicit `select(...).options(load_only(...))` against the composite primary key:

```python
# BEFORE — column-drift sensitive:
item = session.get(WorkItem, (project_id, item_id))

# AFTER — column-projected:
item = session.execute(
    select(WorkItem)
    .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
    .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
).scalar_one_or_none()
```

Apply Shape B everywhere `session.get(WorkItem, ...)` appears in `orch/cli/item_commands.py` (the design's RCA lists every line). Verify the rewrite preserves identity-map behavior — if a prior `session.get` in the same transaction returned the entity from the cache, the new `select()` form will still hit the cache via SQLAlchemy's "loader options" path. If you're unsure, add an inline comment pointing at I-00073.

**Do NOT** modify any file under `orch/daemon/` — see AC3 in the design. Daemon-side callsites run from `main` where ORM ↔ DB are always in sync; narrowing them is churn without justification.

### 3. Document the rule

Add a short module docstring at the top of `orch/cli/step_commands.py` (and update the existing one in `orch/cli/item_commands.py` if any) explaining why these reads use `load_only` — point to incident I-00073 and to agent constraint R2.

Then append a new subsection to `docs/IW_AI_Core_Agent_Constraints.md`, after the existing R1/R2 sections, titled **"CLI resilience to in-flight schema drift"**. Body: 4–8 sentences explaining the structural cause (R2 implies worktree ORM ↔ live DB drift on schema-modifying features), the rule (agent-facing CLI reads must use column-projected SELECTs against orchestration tables), the reference pattern (`load_only` with a per-module pinned column set), and a pointer to incident `I-00073` and the regression test path.

### 4. Behavior preservation

- Every existing test under `tests/unit/cli/` and `tests/integration/cli/` MUST continue to pass — the column-projected reads must return entities that behave identically for every existing caller. If something breaks, the projection is missing a column the caller needs.
- Do NOT change the public surface of any CLI command. JSON output schemas, exit codes, error messages, and click options must remain identical.
- Do NOT add error handling for `UndefinedColumn` (option (b) in the design — explicitly rejected as too magical).

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 `Mapped[]` declarative style
- psycopg v3 driver — never psycopg2
- Click 8.1+ CLI patterns
- Append-only invariants on `step_runs`, `daemon_events`
- The `DaemonEvent.metadata` → `event_metadata` Python rename gotcha (do not "fix" it)

Match existing code in `orch/cli/`. The line at `orch/cli/step_commands.py:649-654` (`select(StepRun.run_number)`) is the reference pattern for column-projected reads — use the same idiom (or `load_only` if you load the entity).

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: The reproduction test in S03 will fail against the pre-fix code. You do not write it — `tests-impl` does. But before declaring this step done, run `tests/unit/cli/` and `tests/integration/cli/` to confirm you haven't regressed existing coverage.
2. **GREEN**: Apply the column-projection patches.
3. **REFACTOR**: Once green, look once for duplication across `step_commands.py` callsites — if the same `select(...).options(load_only(...)).where(...).order_by(...).limit(1)` shape appears 5+ times, consider a single helper function. Otherwise leave the explicit form.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

Populate the `preflight` object in your result contract:
- `"ok"` — ran cleanly
- `"fixed"` — applies to `format` only
- `"skipped:<reason>"` — only with a blocker

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — all unit tests must pass.
2. Run `make test-integration` if changes touch CLI command code — at minimum the existing CLI integration tests must still pass.
3. Do **NOT** report `tests_passed: true` unless ALL applicable tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/step_commands.py",
    "orch/cli/item_commands.py",
    "docs/IW_AI_Core_Agent_Constraints.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
