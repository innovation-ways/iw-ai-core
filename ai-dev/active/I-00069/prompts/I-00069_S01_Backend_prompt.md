# I-00069_S01_Backend_prompt

**Work Item**: I-00069 -- Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch migrations. Do not run alembic upgrade /
downgrade / stamp commands. Read-only `alembic history|current|show` is
fine if you need to investigate.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for current step list, prefer `uv run iw item-status I-00069 --json`. The `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00069/I-00069_Issue_Design.md` — Design document
- `dashboard/app.py` — file to modify (target lines 142-150)
- `orch/db/live_db_guard.py` — defines `LiveDbConnectionRefusedError` (read-only — DO NOT modify)
- `orch/db/alembic_guard.py` — defines `check_db_at_head()` (read-only — DO NOT modify)
- `dashboard/middlewares/alembic_guard.py` — already silent via `contextlib.suppress(Exception)`; reference only
- `orch/daemon/main.py:147` — daemon path; do NOT touch

## Output Files

- `dashboard/app.py` — modified
- `ai-dev/active/I-00069/reports/I-00069_S01_Backend_report.md` — Step report

## Context

You are implementing the only production-code change for **I-00069**.

Read the design document first (`ai-dev/active/I-00069/I-00069_Issue_Design.md`),
specifically the **Description**, **Root Cause Analysis**, **Code Changes**,
and **Acceptance Criteria** sections. Then read the project's `CLAUDE.md`
and `dashboard/CLAUDE.md` for conventions.

The bug: `dashboard/app.py:146-149` catches the alembic-guard startup probe
with a bare `except Exception` and logs every failure via
`logger.exception(...)` (ERROR + traceback). Under `IW_CORE_TEST_CONTEXT=true`,
the guard at `orch/db/live_db_guard.py:134-141` correctly raises
`LiveDbConnectionRefusedError` to *prevent* test code from reaching the live
DB — but the dashboard then logs that intentional refusal as a loud ERROR.

## Requirements

### 1. Narrow the exception handling at `dashboard/app.py:142-150`

Replace the current bare `except Exception` with a structure that:

1. Catches `LiveDbConnectionRefusedError` **first**, before the generic branch.
2. In that branch:
   - If `os.environ.get("IW_CORE_TEST_CONTEXT") == "true"`: log at **DEBUG**
     with a single-line message — e.g. `logger.debug("alembic guard skipped: live DB connection refused under IW_CORE_TEST_CONTEXT=true")`. Do NOT use `logger.exception` and do NOT include a traceback.
   - Otherwise: log at **WARNING** with a single-line message — e.g.
     `logger.warning("alembic guard skipped: live DB connection refused: %s", exc)`. No traceback.
3. Keep the existing `logger.exception("alembic guard check failed at startup; continuing")` call for the generic `except Exception` branch so genuine boot failures (DB unreachable, mis-config, etc.) are still loud at ERROR with a traceback.
4. In **all** branches, `app.state.alembic_guard_status = None` MUST still be set — preserving the existing contract that any failure leaves the banner hidden.

### 2. Import handling

`LiveDbConnectionRefusedError` lives in `orch.db.live_db_guard`. Import it at
the top of `dashboard/app.py` (alongside the existing `orch.db.alembic_guard`
import on line 56). Use a normal top-of-file import; do **not** import inside
the `try` block.

### 3. Do NOT change

- `orch/db/live_db_guard.py` — the guard's contract is correct.
- `orch/db/alembic_guard.py` — `check_db_at_head()` itself is unaffected.
- `dashboard/middlewares/alembic_guard.py` — already silent.
- `orch/daemon/main.py` — daemon path is correct (real DB target).
- The startup probe's *control flow* — it must still set
  `app.state.alembic_guard_status` to either the `GuardStatus` (success)
  or `None` (any failure).

### 4. Style and brevity

The change is ~5–8 lines. No refactoring of the surrounding code. No
helper functions. No comments explaining what the code does — only a
short comment if the *why* is non-obvious (the existing `# R3` comment
already explains the behaviour).

## Project Conventions

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for:

- FastAPI factory + middleware patterns (`dashboard/CLAUDE.md`)
- Logging conventions (use `logger = logging.getLogger(__name__)` already established)
- Layer boundaries — `dashboard/` may import from `orch/`, never the reverse
- `make format` / `make typecheck` / `make lint` are the project quality gates

Follow all rules defined there exactly. Match the existing import style and
comment style in `dashboard/app.py`.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: The failing test already lives in S03's prompt
   (`tests/dashboard/test_live_db_guard_log_level.py`). For S01, write a
   minimal local repro using `caplog` to confirm the bug exists before
   you change `dashboard/app.py`. Do NOT commit your local repro — S03
   adds the canonical regression test.
2. **GREEN**: Make the minimal change described above.
3. **REFACTOR**: Only if the new exception structure is awkward; otherwise
   leave it.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving `dashboard/app.py`.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the `preflight` object with
`"ok"` / `"fixed"` / `"skipped:<reason>"` for each command.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` and confirm zero failures.
2. Run `make typecheck` and `make lint` per pre-flight.
3. Do **NOT** report `tests_passed: true` unless all unit tests pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/app.py"
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
