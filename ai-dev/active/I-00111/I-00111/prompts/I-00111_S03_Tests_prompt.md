# I-00111_S03_Tests_prompt

**Work Item**: I-00111 -- `GET /openapi.json` returns HTTP 500 — `create_app().openapi()` raises Pydantic `ForwardRef('Response')` error
**Step**: S03
**Agent**: Tests

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
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch any Alembic migration.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00111 --json` is canonical.
- `ai-dev/active/I-00111/I-00111_Issue_Design.md` -- Design document (`## Test to Reproduce` section has the full draft test bodies; `## Acceptance Criteria` AC2 and AC3 are this step's contract)
- `ai-dev/work/I-00111/reports/I-00111_S01_Backend_report.md` -- S01 report (confirms the production fix landed; `files_changed` tells you which production file to expect a working schema from)
- `tests/dashboard/test_schemathesis_contract.py` -- the test file you will MODIFY (remove the workaround at the former lines 163-173, switch the fixture to load via `from_asgi` against the real app schema, update the docstring at lines 21-30)
- `tests/dashboard/conftest.py` -- the dashboard `client` fixture you will USE in the new regression test
- `tests/CLAUDE.md` -- testing rules (live-DB guard, testcontainer pattern, test-file location rules — read before writing the new test file)

## Output Files

- `tests/dashboard/test_openapi_schema.py` -- NEW regression test file (two tests for AC2)
- `tests/dashboard/test_schemathesis_contract.py` -- MODIFIED (workaround removed for AC3, docstring updated)
- `ai-dev/work/I-00111/reports/I-00111_S03_Tests_report.md` -- Step report

## Context

You are adding the regression test net AND restoring the schemathesis contract-fuzz tests to fuzz the **real** full-app OpenAPI schema, now that S01 has fixed the underlying Pydantic ForwardRef bug.

Read the design document FIRST. The `## Test to Reproduce` section has the full draft bodies of both regression tests — copy them as the starting point, adapt to match the project's existing test conventions in `tests/dashboard/`, and verify they pass against the post-S01 code.

## Requirements

### 1. CREATE `tests/dashboard/test_openapi_schema.py` — two regression tests

Use the draft from the design document's `## Test to Reproduce` section as the starting point. The file MUST contain:

**Test A — `test_i_00111_openapi_endpoint_returns_valid_schema(client: TestClient)`**

- Uses the dashboard `client` fixture (registered in `tests/dashboard/conftest.py` — see `tests/CLAUDE.md` "test-file location" rule).
- Calls `client.get("/openapi.json")`.
- Asserts status code `== 200` with a failure message that quotes the response body's first 500 chars (so a regression's error message is diagnosable).
- Parses the JSON body and asserts:
  - `"openapi" in schema and schema["openapi"].startswith("3.")` — specific value, not just "key exists".
  - `"info" in schema and schema["info"].get("title")` — specific value, not empty info block.
  - `"paths" in schema and len(schema["paths"]) > 0` — specific value, not just "key exists".

**Test B — `test_i_00111_app_openapi_callable_returns_dict()`**

- No fixture argument — purely in-process.
- Imports `create_app` lazily inside the function body (so the test-mode live-DB guard plumbing in `tests/dashboard/conftest.py` is in effect when `create_app` runs — see `tests/CLAUDE.md`).
- Builds `app = create_app()`, calls `schema = app.openapi()`.
- Asserts `isinstance(schema, dict)` and `len(schema["paths"]) > 0` — both with diagnostic failure messages.

Both tests MUST have a module-level docstring that names I-00111 and explains the contract being pinned ("pre-fix, this raised a `ForwardRef('Response')` error; post-fix, this is the regression net").

### 2. MODIFY `tests/dashboard/test_schemathesis_contract.py` — remove the workaround (AC3)

The file currently builds a partial OpenAPI schema from a hand-filtered subset of JSON-API routes because the full-app `openapi()` raised. With S01 fixed, the workaround is no longer needed.

Make exactly these three edits:

**Edit 2.1 — remove the `_json_api_openapi` closure and the monkeypatch line.** Inside the `contract_app` fixture (currently around lines 160-173), delete the block that builds `json_api_routes` from `app.routes`, defines `_json_api_openapi`, and calls `monkeypatch.setattr(app, "openapi", _json_api_openapi, raising=False)`. The fixture's body should now end with `yield app` directly after `app.dependency_overrides[get_db] = _override_get_db`.

**Edit 2.2 — switch the `contract_schema` fixture (currently around lines 180-183) to load from the real app's `/openapi.json`.**

The fixture currently calls `schemathesis.openapi.from_asgi("/openapi.json", contract_app)` — which now loads the real app schema directly because the workaround is gone. Verify the call site is unchanged but document via a fixture docstring update that it now loads the FULL app schema (not the hand-built partial). If the existing line is already correct, the only change is the docstring text from "Load the app's OpenAPI schema (built from the JSON_API_PATHS routes)" to "Load the app's full OpenAPI schema (I-00111 restored full-app schema generation; the JSON_API_FUZZ_PATHS filter narrows the fuzz target downstream)".

**Edit 2.3 — update the module docstring at lines 21-30.** Replace the "OpenAPI generation work-around" section with a note that I-00111 (link by ID) fixed the underlying Pydantic ForwardRef bug and the workaround was removed. Keep the rest of the module docstring (Fuzz target, Marker, Live-DB guard sections) intact. Suggested replacement text:

```
OpenAPI generation
──────────────────
``create_app().openapi()`` now generates the full app's OpenAPI schema cleanly
(I-00111, 2026-05-24, fixed the Pydantic ForwardRef('Response') resolution
error in the offending route handler). The ``contract_schema`` fixture loads
the real full-app schema via ``schemathesis.openapi.from_asgi``; the fuzz
target is narrowed downstream by the ``JSON_API_FUZZ_PATHS`` filter on the
lazy schema. No production code override is needed.
```

### 3. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident, apply that lesson concretely:

- BAD: `assert "paths" in schema` (the buggy `_json_api_openapi` workaround would have passed this too — it returned a partial schema with `paths` present but only the JSON-API subset)
- GOOD: `assert len(schema["paths"]) > 0` (must have at least one route — but the partial workaround had this too, so still not strong enough on its own)
- BEST: combine `len(schema["paths"]) > 0` AND `schema["openapi"].startswith("3.")` AND `schema["info"].get("title")` — three independent checks that the schema is a real, populated OpenAPI 3.x document. The compound assertion is what makes the test diagnostic of the actual fix.

Do NOT add `assert isinstance(schema["paths"], dict)` as your only path-related check — that is shape-only and would pass against an empty `{}`.

### 4. Targeted verification only

Run ONLY the test files you wrote / modified. Do NOT call `make test-integration` or `make test-unit` — those are S10/S11 QV gates with their own (longer) timeout budgets and will run with full coverage. Duplicating them inside this Tests step routinely blows the step's timeout budget (see I-00073/S03 post-mortem, 2026-05-08).

```bash
# Verify the new regression test file
uv run pytest tests/dashboard/test_openapi_schema.py -v --no-cov

# Verify the contract-fuzz schema-loading still works post-workaround-removal
uv run pytest tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema -v --no-cov -m contract_fuzz
```

Both commands MUST exit 0. **Copy the final summary line of each command's output into your step report's `test_summary` field.**

### 5. Do NOT manually revert the S01 fix to "verify RED"

Do NOT instruct yourself to `git checkout HEAD~1 -- <file>`, `git stash`, or otherwise revert source files at runtime to "confirm the test would have failed pre-fix". That is a thrash-prone operation. The RED evidence is already in S01's report (the in-process reproduction script raising `ForwardRef`); your job is to write tests that codify the GREEN contract going forward.

### 6. Do NOT widen the JSON_API_PATHS allow-list

`JSON_API_PATHS` in `tests/dashboard/test_schemathesis_contract.py` intentionally narrows the fuzz surface to JSON endpoints. This incident only removes the workaround that built a fake `openapi()`; it does NOT change which routes the fuzzer targets. Leave `JSON_API_PATHS`, `KNOWN_CONTRACT_5XX`, and `JSON_API_FUZZ_PATHS` untouched.

## Project Conventions

Read the project's `CLAUDE.md` AND `tests/CLAUDE.md` for:

- **Test-file location rules** — tests that drive a FastAPI route via the dashboard `client` fixture MUST live under `tests/dashboard/` (the `client` fixture is registered only in `tests/dashboard/conftest.py`). Placing the new test under `tests/unit/` or `tests/integration/` will fail with `fixture 'client' not found` (I-00067).
- **Live-DB guard** — NEVER import `dashboard.routers.*` or `dashboard.dependencies` at module level in a unit test without a testcontainer `db_session` in scope. The dashboard `client` fixture wires this correctly; using the fixture (rather than importing `dashboard.app` at module top-level) is the safe pattern.
- **Lazy imports inside test functions** — Test B (`test_i_00111_app_openapi_callable_returns_dict`) MUST `from dashboard.app import create_app` inside the function body, not at module top, so the test-mode plumbing in `tests/dashboard/conftest.py` is in effect.
- **Type-checker friendliness** — gate `from fastapi.testclient import TestClient` behind `if TYPE_CHECKING:` for the import-only annotation.

## TDD Requirement

The RED phase was performed by S01 (the in-process reproduction script raising `ForwardRef`). Your S03 job is to codify the GREEN contract — tests that pass against the post-S01 code and would FAIL against any future regression of the same class.

For each new test:

1. **Write the test.**
2. **Run it (targeted) and confirm it PASSES against the current (post-S01) code.** A test that fails GREEN means either S01 didn't actually fix the bug (escalate immediately) or the test is wrong (fix the test).
3. **Reason about whether the test would fail against pre-S01 code.** Document this reasoning in your step report's `notes` field — e.g. "test_i_00111_app_openapi_callable_returns_dict would have raised `pydantic.errors.PydanticUndefinedAnnotation` at the `app.openapi()` call line, satisfying RED-first semantics retroactively". Do NOT actually revert S01 to test this (Requirement #5).

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order:

1. **`make format`** — auto-fixes formatting drift in your new and modified test files.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run ONLY `uv run pytest tests/dashboard/test_openapi_schema.py -v --no-cov` AND `uv run pytest tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema -v --no-cov -m contract_fuzz`.
2. Both must exit 0.
3. Do NOT run `make test-integration` or `make test-unit` — those are S10/S11 gates.
4. Do NOT report `tests_passed: true` unless both targeted runs pass cleanly.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00111",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_openapi_schema.py",
    "tests/dashboard/test_schemathesis_contract.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "test_openapi_schema.py: 2 passed; test_schemathesis_contract.py::test_json_api_paths_exist_in_schema: 1 passed",
  "tdd_red_evidence": "n/a — dedicated coverage step; RED evidence is in S01 report (in-process create_app().openapi() raised ForwardRef pre-fix)",
  "blockers": [],
  "notes": "Workaround removal at tests/dashboard/test_schemathesis_contract.py:163-173 complete; contract_schema fixture now loads via from_asgi against the real full-app schema; module docstring at lines 21-30 updated to reference I-00111. Pre-S01 RED semantics: test_i_00111_app_openapi_callable_returns_dict would have raised pydantic.errors.PydanticUndefinedAnnotation at the app.openapi() call against pre-fix code."
}
```

- `tdd_red_evidence`: use the `"n/a — …"` form — this is a dedicated coverage step (`tests-impl`), exempt from RED-first by design (see `skills/iw-workflow/SKILL.md`).
- `completion_status`: `complete` only if both target runs are green AND the workaround is fully removed (not partially).
- `notes`: MUST mention that the workaround removal is complete and the module docstring is updated.
