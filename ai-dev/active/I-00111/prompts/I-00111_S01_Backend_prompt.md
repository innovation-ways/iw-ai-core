# I-00111_S01_Backend_prompt

**Work Item**: I-00111 -- `GET /openapi.json` returns HTTP 500 — `create_app().openapi()` raises Pydantic `ForwardRef('Response')` error; app-wide OpenAPI schema generation is broken
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

This incident does NOT touch any Alembic migration — there is no schema change. You MUST NOT generate, edit, or run any alembic command for this step.

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00111 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00111/I-00111_Issue_Design.md` -- Design document (read in full; the Root Cause Analysis section names the three candidate fault locations)
- `tests/dashboard/test_schemathesis_contract.py` (lines 21-30 and 163-173) -- the test-module docstring that documents the bug and the workaround function — read these to confirm the bug shape before reproducing.
- `dashboard/app.py` -- the `create_app()` entry point that builds the FastAPI app
- `dashboard/routers/**` -- candidate location for the offending route handler
- `orch/**` -- candidate location for a Pydantic response model with a `Response`-typed field

## Output Files

- `ai-dev/work/I-00111/reports/I-00111_S01_Backend_report.md` -- Step report (MUST include the captured ForwardRef traceback verbatim, a one-line statement of the actual fault location, the exact lines changed, and the post-fix verification output)

## Context

You are implementing the fix for **I-00111**: `create_app().openapi()` raises a Pydantic `ForwardRef('Response')` error, so `GET /openapi.json` returns HTTP 500 app-wide and `GET /docs` (Swagger UI) does not load. This was surfaced by CR-00072 (Phase-3 schemathesis contract fuzzing), which installed a workaround to fuzz only the JSON-API subset. Your job is the underlying fix.

Read `ai-dev/active/I-00111/I-00111_Issue_Design.md` first to understand the full scope, the three candidate root causes, and the acceptance criteria. Then read `CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. Reproduce the bug locally and capture the exact traceback

Before touching any production code, run:

```bash
uv run python -c 'from dashboard.app import create_app; create_app().openapi()' 2>&1 | tee /tmp/i-00111-reproduce.txt
```

The output MUST show a Pydantic `ForwardRef` resolution failure mentioning `Response`. **Copy the traceback verbatim into your step report**, including the chain of `pydantic._internal._generate_schema` / `fastapi.openapi.utils.get_openapi` frames — this is the canonical evidence that locates the offending route handler or response model. If the script exits 0 (no error), STOP and raise a blocker: either the bug has already been fixed on `main` (in which case you only need to do S03's workaround removal — but file a blocker first so the operator can decide), or your worktree state is wrong.

### 2. Bisect to the offending annotation

The traceback will name a specific route function or Pydantic model class. With that name in hand:

```bash
git grep -nE "(-> *['\"]?Response['\"]?|: *['\"]Response['\"])" dashboard/ orch/
git grep -nE "response_model|response_class" dashboard/routers/
```

Identify the **single** line where a `Response` annotation is a string ForwardRef that Pydantic cannot resolve. The three candidate fault patterns (from the design doc's Root Cause Analysis):

1. **Route-handler return annotation** — a handler returning the `fastapi.Response` / `starlette.responses.Response` class with a string-quoted `-> "Response"` annotation and no explicit `response_class=…` on the decorator.
2. **Pydantic response model** with a `Response`-typed field that's a string ForwardRef and was never `model_rebuild()`-ed.
3. **`from __future__ import annotations`** in the same module turning every annotation into a string ForwardRef while `Response` is only imported under `TYPE_CHECKING:`.

State in your report which of these three patterns was the actual fault, with the specific file and line number.

### 3. Apply the SMALLEST possible fix

Once located, the fix is intentionally tiny — typically 1-3 lines of code. Pick the smallest change that resolves the ForwardRef and does NOT alter the route's observed behaviour:

- **If route signature**: either (a) add the missing import outside `TYPE_CHECKING` so `Response` is in the module's runtime namespace, OR (b) replace the string-quoted return annotation with the actual class, OR (c) set `response_class=Response` on the decorator and drop the return annotation entirely (FastAPI's documented escape hatch for handlers that build their own `Response`).
- **If Pydantic model**: add `model_rebuild()` at module load (after the import of `Response`) — or replace the string ForwardRef with the actual class.

**DO NOT** refactor adjacent code, rename things, add new tests in this step (S03 owns the tests), or "improve" anything else. The fix's blast radius MUST be contained to the one or two lines you change.

### 4. Verify the fix in-process and via TestClient

```bash
uv run python -c 'from dashboard.app import create_app; app = create_app(); s = app.openapi(); assert "paths" in s and len(s["paths"]) > 0, "paths empty"; print("OK:", len(s["paths"]), "paths")'
```

Then run a quick TestClient probe:

```bash
uv run python -c '
from fastapi.testclient import TestClient
from dashboard.app import create_app
r = TestClient(create_app()).get("/openapi.json")
print("status:", r.status_code, "paths:", len(r.json().get("paths", {})))
assert r.status_code == 200
'
```

Both MUST print non-zero path counts and `status: 200`. **Copy both lines of output into your step report**.

### 5. Do NOT remove the schemathesis workaround in this step

S03 (Tests agent) removes the `_json_api_openapi()` closure and the `monkeypatch.setattr(app, "openapi", …)` at `tests/dashboard/test_schemathesis_contract.py:163-173` and switches `contract_schema` to load via `from_asgi` against the real schema. Your S01 work stays out of `tests/`.

### 6. Do NOT add the new regression test file in this step

S03 owns `tests/dashboard/test_openapi_schema.py`. S01 only fixes the production defect.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries (dashboard / orch separation)
- Coding conventions and naming rules
- The live-DB guard rules (do NOT import `dashboard.routers.*` in test code without a testcontainer in scope)
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

The reproducing tests for this bug live in S03 (`tests/dashboard/test_openapi_schema.py`) — not S01. This S01 step is a "fix an observable defect" step, where the RED evidence is the **reproduction script in Requirement #1** (the `uv run python -c '… create_app().openapi()'` raising a `ForwardRef` error) rather than a new pytest test.

For your `tdd_red_evidence` field: record the test-script command and the captured `ForwardRef` traceback line, e.g.:

```
tdd_red_evidence: "uv run python -c 'from dashboard.app import create_app; create_app().openapi()' raised: pydantic.errors.PydanticUndefinedAnnotation: name 'Response' is not defined  // captured in /tmp/i-00111-reproduce.txt before fix; same command exits 0 after fix"
```

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full test suite**. Full-suite execution is owned by the dedicated QV gate steps downstream (`unit-tests`, `integration-tests`); duplicating them here burns this step's budget.

For this S01 step:

1. Run the in-process reproduction script + TestClient probe from Requirement #4. Both must succeed.
2. Optionally run a narrow targeted unit suite for whichever module you changed (e.g. `uv run pytest tests/unit/routers/test_<your_module>.py -v` if such a file exists).
3. Do NOT run `make test-integration` or `make test-unit`.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00111",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "path/to/file_with_the_fix.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "in-process reproduction script: OK (N paths); TestClient probe: status 200 (N paths)",
  "tdd_red_evidence": "uv run python -c 'from dashboard.app import create_app; create_app().openapi()' raised pydantic.errors.PydanticUndefinedAnnotation: name 'Response' is not defined // captured pre-fix; same script exits 0 post-fix",
  "blockers": [],
  "notes": "Fault pattern: <one of: route-signature ForwardRef / response-model ForwardRef / __future__ annotations + TYPE_CHECKING import>. Offending location: <path/to/file.py:NN>. Fix: <one-line summary of the 1-3 LOC change>."
}
```

- `tdd_red_evidence`: MUST include the captured `ForwardRef` error line from the in-process reproduction script (Requirement #1) — that script IS the RED evidence for this step. Do NOT use `"n/a — …"`; this is a behaviour-implementing step with a concrete observable defect.
- `notes`: MUST name the fault pattern (one of the three candidates) and the offending file:line so S02 reviewer can verify the bisect was sound.
- `blockers`: if the reproduction script exits 0 against pre-fix code, raise a blocker (the bug may already be fixed on `main`).
