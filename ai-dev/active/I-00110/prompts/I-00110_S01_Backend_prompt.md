# I-00110_S01_Backend_prompt

**Work Item**: I-00110 -- Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id path param
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

**This step does not generate any migration.** The fix is purely at the
FastAPI route boundary; the BIGINT column is correct.

Allowed for agents:
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00110 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00110/I-00110_Issue_Design.md` -- Design document (READ THIS FIRST)
- `dashboard/routers/keep_alive.py` (lines 175-204) -- The two handlers being fixed
- `orch/keep_alive_service.py` (lines 102-130) -- The downstream service (read-only; do NOT modify)

## Output Files

- `ai-dev/work/I-00110/reports/I-00110_S01_Backend_report.md` -- Step report
- Modified: `dashboard/routers/keep_alive.py`

## Context

You are implementing the route-boundary fix for **I-00110 — Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id**.

Read the design document `ai-dev/active/I-00110/I-00110_Issue_Design.md` in full before touching any code. It contains the root cause, the exact fix plan, the rationale for choosing 422 over 404, and the acceptance criteria.

Then read `CLAUDE.md` and `dashboard/CLAUDE.md` for project-specific patterns and conventions.

**Your job in S01 is the route-boundary fix only.** Do NOT create test files in this step — the regression test suite is the deliverable of S03 (tests-impl), which runs after S02 reviews this step.

## Requirements

### 1. Capture pre-fix RED evidence (design-time reproduction)

Before applying any code change to `dashboard/routers/keep_alive.py`, run a one-shot in-process reproduction script to capture the bug exactly as it manifests today. Use `uv run python -c '…'` (or write a throwaway script under `/tmp/` if multi-line is easier) along these lines:

```python
from fastapi.testclient import TestClient
from dashboard.app import create_app

OVERFLOW = 2**63  # one above BIGINT max

app = create_app()
client = TestClient(app, raise_server_exceptions=False)

resp = client.delete(f"/api/keep-alive/slots/{OVERFLOW}")
print("DELETE status:", resp.status_code)
print("DELETE body:", resp.text[:500])

resp = client.patch(f"/api/keep-alive/slots/{OVERFLOW}/toggle")
print("PATCH status:", resp.status_code)
print("PATCH body:", resp.text[:500])
```

You should observe HTTP 500 on both calls, with a `psycopg.errors.NumericValueOutOfRange` trace surfacing in the dashboard logs (the `raise_server_exceptions=False` flag prevents TestClient from re-raising; the response is the genuine 500 the dashboard would emit to a real client).

**Capture both status codes and a one-line summary of the exception** for your step report's `tdd_red_evidence` field. The expected snippet looks like:

```
DELETE status: 500   PATCH status: 500   psycopg.errors.NumericValueOutOfRange: value "9223372036854775808" is out of range for type bigint
```

If the reproduction does NOT show 500 on both endpoints, STOP and raise a blocker — either the bug has already been fixed in a parallel branch (verify with `git log -- dashboard/routers/keep_alive.py`) or the reproduction script is wrong.

### 2. Apply the fix to `dashboard/routers/keep_alive.py` (GREEN)

Modify ONLY the two handler signatures (lines 175-176 and 187-188). Add a module-level constant explaining the magic number, then apply it via FastAPI's `Path` using the modern `Annotated` form:

```python
from typing import Annotated  # add to imports if not already present
from fastapi import Path      # add to imports if not already present (existing `from fastapi import ...` line)

# BIGINT max — PostgreSQL's signed 64-bit integer upper bound.
# slot_id is stored in a BIGINT column; values above this raise
# psycopg.errors.NumericValueOutOfRange at query time (I-00110).
_BIGINT_MAX = 2**63 - 1


@router.delete("/api/keep-alive/slots/{slot_id}")
def delete_slot(
    slot_id: Annotated[int, Path(ge=1, le=_BIGINT_MAX)],
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ...


@router.patch("/api/keep-alive/slots/{slot_id}/toggle")
def toggle_slot(
    slot_id: Annotated[int, Path(ge=1, le=_BIGINT_MAX)],
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    ...
```

The `Annotated[int, Path(...)]` form is the modern FastAPI idiom — it sidesteps the default-parameter ordering rules so you don't need to reshuffle `request: Request` or `db: Session = Depends(get_db)`. Preserve the existing handler bodies verbatim — only the `slot_id` parameter declaration changes.

Do NOT touch any other line in `dashboard/routers/keep_alive.py`. Do NOT add a try/except in `orch/keep_alive_service.py` — the design explicitly rejects the service-layer defensive catch.

### 3. Verify GREEN via the same in-process reproduction script

Re-run the script from step 1. Both `DELETE` and `PATCH` calls should now return HTTP 422, with the FastAPI validation envelope mentioning `slot_id` in `detail[].loc`. Capture the post-fix output for your step report.

Expected snippet:

```
DELETE status: 422
DELETE body: {"detail":[{"type":"less_than_equal","loc":["path","slot_id"],...}]}
PATCH status: 422
PATCH body: {"detail":[{"type":"less_than_equal","loc":["path","slot_id"],...}]}
```

If either status code is anything other than 422 (especially still 500), STOP and raise a blocker.

### 4. Test Verification — TARGETED ONLY

This step does NOT create or modify test files. The dedicated coverage step S03 (tests-impl) writes the regression test suite.

For S01's own verification, the in-process reproduction script from step 3 is sufficient. Do NOT run `make test-integration`, `make test-unit`, `make test-dashboard`, or `make allure-integration` — full-suite execution belongs to the QV gate steps downstream (`unit-tests`, `frontend-tests` via `test-dashboard`, `integration-tests`). Duplicating them here blows the step's timeout budget (see I-00073/S03 post-mortem, 2026-05-08).

## Project Conventions

Read the project's `CLAUDE.md` for:

- Routers are thin (`dashboard/CLAUDE.md`): validation belongs at the route boundary, not in the service or template layer.
- Coding conventions: `ruff format` is the formatter, `ruff check` is the linter, `mypy` is the type checker. `make lint`, `make format`, `make typecheck` are the entry points.

## TDD Requirement

This step is a **behaviour-implementing** step (it changes route validation) AND it is the step that owns the RED evidence under the Backend → Tests split (because S03 is a dedicated coverage step, RED-exempt by the workflow contract).

1. **RED**: Run the in-process reproduction (step 1 above) BEFORE applying the fix. Confirm HTTP 500 on both endpoints. Capture the status codes + the `NumericValueOutOfRange` traceback summary in `tdd_red_evidence`.
2. **GREEN**: Apply the `Path(...)` bound (step 2 above). Re-run the reproduction; both endpoints must return HTTP 422 with `slot_id` in `detail[].loc`.
3. **REFACTOR**: None — the change is minimal by design.

**Do not skip the RED phase.** The bug must be reproduced before the fix is applied. If your `tdd_red_evidence` field is empty or contains a stale/fabricated snippet, S02 review will fail this step.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched (`dashboard/routers/keep_alive.py`). Errors elsewhere are pre-existing — note them in your report but do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Even though S01 does not write test files, its **verification** must be semantic, not shape-only:

- BAD: `assert "detail" in resp.json()` (shape only — every FastAPI error has a `detail`)
- GOOD: `assert resp.status_code == 422` (semantic — specific expected status)
- GOOD: `assert any("slot_id" in str(err.get("loc", ())) for err in body["detail"])` (semantic — verifies the validator names the right field)

Both your RED probe and your GREEN probe must observe the SPECIFIC status code (500 vs 422) and quote it in your report.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00110",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/keep_alive.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "n/a — S01 verifies via in-process reproduction; regression test file is S03's deliverable",
  "tdd_red_evidence": "Pre-fix in-process probe: DELETE /api/keep-alive/slots/9223372036854775808 -> 500; PATCH /api/keep-alive/slots/9223372036854775808/toggle -> 500; psycopg.errors.NumericValueOutOfRange: value \"9223372036854775808\" is out of range for type bigint. Post-fix probe: both -> 422 with slot_id in detail[].loc.",
  "blockers": [],
  "notes": ""
}
```

- `tdd_red_evidence`: **Required.** Record the pre-fix probe output (both status codes + a one-line `NumericValueOutOfRange` summary) AND the post-fix probe output (both 422 + `slot_id` in `loc`).
- `completion_status`: Use `complete` when `dashboard/routers/keep_alive.py` is modified, the pre-flight gates pass, and the in-process probe shows 422 on both endpoints. Use `blocked` if FastAPI's `Annotated[int, Path(...)]` cannot be applied without a wider refactor (it should not — this is the canonical FastAPI idiom).
- `blockers`: List any issues that prevented full completion.
- `notes`: Any context the next step or reviewer should know — e.g., if you needed to import `Annotated` from `typing`, note the additional import.
