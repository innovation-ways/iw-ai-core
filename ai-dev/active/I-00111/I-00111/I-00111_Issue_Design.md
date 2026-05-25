# I-00111: `GET /openapi.json` returns HTTP 500 — `create_app().openapi()` raises Pydantic `ForwardRef('Response')` error; app-wide OpenAPI schema generation is broken

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-24
**Reported By**: CR-00072 (Contract / No-5xx Route Sweep + schemathesis, merged 2026-05-22) — surfaced while wiring schemathesis. Filed from `ai-dev/work/TESTS_ENHANCEMENT.md` §10 "Phase 3 operator-follow-up incidents".
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This incident does **not** touch any Alembic migration — no schema change involved.)

## Description

`create_app()` returns a FastAPI app whose `app.openapi()` method (which builds the OpenAPI schema lazily on first call to `/openapi.json` and on Swagger UI loads) raises a Pydantic `ForwardRef('Response')` resolution error. Net effect: `GET /openapi.json` 500s app-wide, `GET /docs` (Swagger UI) does not load, and any tooling that consumes the OpenAPI schema (schemathesis, generated clients, external docs) is broken.

The defect is documented in the test-module header docstring of `tests/dashboard/test_schemathesis_contract.py:23-30` and worked around for the Phase-3 contract fuzz tests by building a partial OpenAPI schema from only the JSON-API routes whose annotations resolve cleanly (`tests/dashboard/test_schemathesis_contract.py:163-173`). The workaround is what enables Phase-3 contract fuzzing to run at all; this incident is the underlying fix.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules — in particular the live-DB guard rules and the testcontainer pattern used in `tests/dashboard/conftest.py` (the new direct OpenAPI integration test in S03 must follow the same import-ordering rules to avoid tripping the live-DB guard at collection time).

## Steps to Reproduce

1. Start the dashboard locally (`./ai-core.sh start` or equivalent).
2. `curl http://localhost:9900/openapi.json` → HTTP 500.
3. `curl http://localhost:9900/docs` (Swagger UI) → renders an empty schema / surfaces 500.
4. Logs show a Pydantic `ForwardRef('Response')` resolution failure raised from inside `FastAPI.openapi()` → `pydantic` schema-generation.

In-process reproduction (no HTTP needed):

```bash
uv run python -c 'from dashboard.app import create_app; print(create_app().openapi())'
```

**Expected**: `GET /openapi.json` returns a valid OpenAPI 3.x JSON document covering every route the app exposes (or, if some routes are intentionally excluded, the schema must still load without erroring). The in-process call returns a dict with at minimum `openapi`, `info`, and `paths` keys, and `paths` is non-empty.

**Actual**: HTTP 500 from the route; the in-process call raises a Pydantic `ForwardRef('Response')` resolution failure during schema generation.

## Evidence (from CR-00072)

Browser-evidence capture is **deferred — not applicable**. The evidence is in-tree, recorded by CR-00072:

- Test-module header docstring quoting the bug verbatim (`tests/dashboard/test_schemathesis_contract.py:22-30`):

  > **OpenAPI generation work-around** — `create_app().openapi()` raises a pre-existing Pydantic `ForwardRef` error (a handler elsewhere in the app has an unresolved `-> Response` annotation), so `GET /openapi.json` 500s app-wide. To fuzz the JSON operations we override `app.openapi` on the *test* app instance with a schema built (via FastAPI's `get_openapi`) from only the JSON-API routes, whose annotations resolve cleanly. The override touches only the test app — no production code is modified. The broken full-app `/openapi.json` is surfaced as operator follow-up in the S01 step report.

- Workaround function the fix must dismantle (`tests/dashboard/test_schemathesis_contract.py:163-173`): the `_json_api_openapi()` closure built via `fastapi.openapi.utils.get_openapi` from a hand-filtered list of JSON-API routes, installed via `monkeypatch.setattr(app, "openapi", _json_api_openapi, raising=False)`.

No new browser screenshots are required for this incident — verification is the in-process `create_app().openapi()` call returning a dict, plus `client.get("/openapi.json")` returning HTTP 200 via TestClient.

## Root Cause Analysis

**TBD — requires investigation in S01.** The Pydantic `ForwardRef('Response')` error means somewhere in the app's route signatures or response models, a `Response` type annotation is a string ForwardRef that Pydantic cannot resolve at schema-generation time. The most likely candidates (S01 must bisect, not guess):

1. **Route-handler return annotation.** A route handler returns `Response` (the `fastapi.Response` / `starlette.responses.Response` class) with no explicit `response_class=…` on the decorator, and the return-type annotation is a string `"Response"` that Pydantic tries to introspect for the response schema. Combined with `from __future__ import annotations` in the same module, every annotation is a string ForwardRef at runtime — FastAPI passes it to Pydantic, which fails to resolve `Response` in the local namespace.
2. **Pydantic response model with a `Response`-typed field.** A response model has an attribute typed as `Response` that's a string ForwardRef and was never `model_rebuild()`-ed after `Response` became importable in its module.
3. **`from __future__ import annotations` interaction with FastAPI route registration.** FastAPI walks signatures eagerly at app construction, but the type-evaluation can be deferred to `openapi()` call time — the symbol resolution happens against the module's `__globals__`, and if `Response` is only imported under `TYPE_CHECKING:` the ForwardRef has no real class to resolve to.

S01's first job is **reproduce + bisect**, not pre-commit to a fix shape. Reproduce via `uv run python -c 'from dashboard.app import create_app; create_app().openapi()'` to capture the exact `ForwardRef` traceback (which model / which field / which route function will be in the error chain). Then `git grep` for `Response` annotations across `dashboard/routers/**` and `orch/**` response models. Apply the **smallest** fix — likely 1-3 LOC:

- If a route signature: add the missing import outside `TYPE_CHECKING`, drop the string-quoted annotation, or set `response_class=Response` on the decorator and remove the return-type annotation entirely (FastAPI's documented escape hatch for handlers that build their own `Response`).
- If a Pydantic model: add an explicit `model_rebuild()` call at module load after the relevant import; or replace the string ForwardRef with the actual class.

## Affected Components

| Component | Files (suspected) | Impact |
|-----------|-------------------|--------|
| Dashboard FastAPI app | `dashboard/app.py`, `dashboard/routers/**` (specific file TBD by S01 bisect) | `GET /openapi.json` returns HTTP 500 app-wide |
| Swagger UI | `dashboard/app.py` (mounted at `/docs`) | `GET /docs` loads empty / errors |
| Contract-fuzz tests | `tests/dashboard/test_schemathesis_contract.py` | Forced to build a partial schema from only JSON-API routes; full-app fuzz target is unreachable |
| External tooling | n/a (consumer-side) | Schemathesis (without workaround), generated clients, external docs all broken |
| Pydantic response model (alternative root cause) | TBD — `orch/**` response models with `Response` fields | `openapi()` schema generation raises |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. This is a small-to-medium fix: the diagnosis (S01) is the hard part; once located, the fix is 1-3 LOC + a regression test + removing the schemathesis workaround. A single Backend step covers diagnosis + minimal fix; a separate Tests step covers the regression net and the workaround removal.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Reproduce the ForwardRef error in-process; bisect to the offending route/model; apply the smallest fix; verify `app.openapi()` returns a valid schema; verify `client.get("/openapi.json")` returns HTTP 200 via TestClient | — |
| S02 | CodeReview | Per-agent review of S01 (correct root cause located? smallest possible fix? no scope creep into refactors?) | — |
| S03 | Tests | Add `tests/dashboard/test_openapi_schema.py` (new file): integration test asserting `app.openapi()` returns a dict with `openapi`/`info`/`paths` keys and a non-empty `paths`; and `client.get("/openapi.json")` returns HTTP 200 with a valid OpenAPI envelope. Remove the workaround at `tests/dashboard/test_schemathesis_contract.py:163-173` (the `_json_api_openapi()` closure and the `monkeypatch.setattr(app, "openapi", …)` line) and switch the `contract_schema` fixture to `schemathesis.openapi.from_asgi("/openapi.json", contract_app)` against the real app schema. Update the module docstring at `tests/dashboard/test_schemathesis_contract.py:21-30` accordingly (note that I-00111 fixed the ForwardRef and the workaround is no longer needed). Targeted verification only: `uv run pytest tests/dashboard/test_openapi_schema.py -v --no-cov` and a targeted re-run of the contract-fuzz module to confirm the schema-loading path still works (`uv run pytest tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema -v --no-cov -m contract_fuzz`). | — |
| S04 | CodeReview | Per-agent review of S03 (semantic asserts, not shape; workaround removal complete; docstring updated; no full-suite runs in the step) | — |
| S05 | CodeReview_Final | Global cross-agent review of S01..S04; AC1 + AC2 + AC3 verified end-to-end | — |
| S06..S13 | QV Gates | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment of the just-completed item via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `tests-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A — no schema change

### Code Changes

- **Files to modify** (production): one or two files under `dashboard/routers/**`, `dashboard/app.py`, or `orch/**` response models (exact target TBD by S01 bisect). The fix is intentionally scoped to the smallest possible change — typically a single import addition, a single annotation correction, or a single `response_class=` argument on a route decorator.
- **Files to modify** (tests): `tests/dashboard/test_schemathesis_contract.py` (remove workaround, switch fixture to real app schema, update docstring).
- **Files to create** (tests): `tests/dashboard/test_openapi_schema.py` (new direct integration test for OpenAPI schema generation).
- **Nature of change**: fix a Pydantic ForwardRef resolution error in a route signature or response model; add a regression test that pins the `app.openapi()` contract; restore the contract-fuzz tests to fuzz against the **real** full-app OpenAPI schema.

## File Manifest

All files for this work item live under `ai-dev/active/I-00111/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00111_Issue_Design.md` | Design | This document |
| `I-00111_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00111_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00111_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00111_S03_Tests_prompt.md` | Prompt | S03 regression tests + workaround removal |
| `prompts/I-00111_S04_CodeReview_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00111_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent final review |
| `prompts/I-00111_S14_SelfAssess_prompt.md` | Prompt | S14 self-assessment |

Reports are created during execution in `ai-dev/work/I-00111/reports/`.

## Test to Reproduce

A failing test that demonstrates the bug **before** the fix and passes **after**. Lives at `tests/dashboard/test_openapi_schema.py` (new file). Uses the dashboard TestClient pattern already wired in `tests/dashboard/conftest.py` (a testcontainer-backed `client` fixture).

**Test-file location** — `tests/dashboard/` is mandatory because the test drives a FastAPI route via the dashboard `client` fixture and calls `app.openapi()` on the same `create_app()`-built instance. Placing it in `tests/unit/` or `tests/integration/` would fail with `fixture 'client' not found` (the live-DB guard would also fire at import time — see `tests/CLAUDE.md`).

```python
# tests/dashboard/test_openapi_schema.py
"""I-00111 regression — GET /openapi.json must return a valid OpenAPI schema.

Pre-fix, create_app().openapi() raised a Pydantic ForwardRef('Response')
resolution error and /openapi.json returned HTTP 500. This test fails RED
against pre-fix code and passes GREEN after the fix.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_i_00111_openapi_endpoint_returns_valid_schema(client: TestClient) -> None:
    """GET /openapi.json must return HTTP 200 with a valid OpenAPI envelope."""
    response = client.get("/openapi.json")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Pre-I-00111 this was 500 from a Pydantic ForwardRef('Response') error. "
        f"Body: {response.text[:500]}"
    )
    schema = response.json()
    # Semantic asserts: every required OpenAPI 3.x top-level key is present
    # AND has non-empty content (shape-only checks pass vacuously against a
    # half-built schema — assert the real contract).
    assert "openapi" in schema and schema["openapi"].startswith("3."), schema.get("openapi")
    assert "info" in schema and schema["info"].get("title"), schema.get("info")
    assert "paths" in schema and len(schema["paths"]) > 0, (
        "OpenAPI 'paths' is empty — the schema generator silently produced a "
        "stub; the fix must restore real route coverage."
    )


def test_i_00111_app_openapi_callable_returns_dict() -> None:
    """In-process: create_app().openapi() must return a dict, not raise.

    This is the lowest-level reproduction of the bug — calling .openapi()
    on a freshly-built app, without going through HTTP. Pre-fix this raised
    a Pydantic ForwardRef resolution error from inside FastAPI's schema
    generation.
    """
    # Import lazily inside the function so the live-DB guard test-mode
    # plumbing in tests/dashboard/conftest.py is in effect when create_app
    # runs.
    from dashboard.app import create_app

    app = create_app()
    schema = app.openapi()
    assert isinstance(schema, dict), type(schema)
    assert "paths" in schema and len(schema["paths"]) > 0
```

## Acceptance Criteria

### AC1: `GET /openapi.json` returns a valid OpenAPI 3.x schema

```
Given the dashboard app built by create_app()
When GET /openapi.json is called (via TestClient or curl)
Then the response status is 200
 And the body is a JSON dict containing keys "openapi" (starting with "3."), "info", and "paths"
 And "paths" is non-empty
```

### AC2: Regression test exists and is enforced by CI

```
Given the fix is applied
When the test suite runs (make test-integration → tests/dashboard/)
Then tests/dashboard/test_openapi_schema.py::test_i_00111_openapi_endpoint_returns_valid_schema passes
 And tests/dashboard/test_openapi_schema.py::test_i_00111_app_openapi_callable_returns_dict passes
```

### AC3: The schemathesis contract-fuzz workaround is removed

```
Given the ForwardRef bug is fixed
When tests/dashboard/test_schemathesis_contract.py is read
Then the _json_api_openapi() closure at the former lines 163-173 is gone
 And the monkeypatch.setattr(app, "openapi", _json_api_openapi, raising=False) line is gone
 And the contract_schema fixture loads via schemathesis.openapi.from_asgi("/openapi.json", contract_app) against the real app schema
 And the module docstring at lines 21-30 is updated to note that I-00111 fixed the underlying bug
```

## Regression Prevention

- **Direct OpenAPI integration test** (`tests/dashboard/test_openapi_schema.py`) pins `app.openapi()` to "must return a dict with non-empty `paths`" — any future change that re-introduces a ForwardRef breakage trips this test in `make test-integration` before merge.
- **Contract-fuzz tests now run against the real app schema** (no workaround), so any new JSON-API route that introduces a ForwardRef breakage will surface as a schemathesis failure in the nightly `make test-contract-fuzz` workflow rather than silently passing through a hand-filtered subset.
- **No structural rule** is added — this is a localised type-annotation fix, not a class-of-bug that warrants a project-wide lint rule. If a similar ForwardRef breakage recurs after this fix, that justifies promoting it to a `scripts/check_openapi_schema.py` lint gate; not now.

## Dependencies

- **Depends on**: None
- **Blocks**: None (downstream improvement: the Phase-3 contract-fuzz tests gain real-schema coverage once AC3 lands, but no other work item is blocked on this)

## Impacted Paths

The S01 bisect may land the production fix in any one of: a router under `dashboard/routers/**`, `dashboard/app.py`, or a Pydantic response model under `orch/**`. The scope is deliberately permissive on production code so the fix is not forced to expand `scope.allowed_paths` mid-flight; the QV final review (S05) verifies the actual diff is minimal.

- `dashboard/routers/**`
- `dashboard/app.py`
- `orch/**`
- `tests/dashboard/test_schemathesis_contract.py`
- `tests/dashboard/test_openapi_schema.py`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_openapi_schema.py::test_i_00111_openapi_endpoint_returns_valid_schema` (HTTP-level) and `::test_i_00111_app_openapi_callable_returns_dict` (in-process). Both fail RED against pre-fix code (status 500 / `ForwardRef` raise) and pass GREEN after.
- **Unit tests**: None — the bug lives at the FastAPI route-registration / Pydantic schema-generation boundary, which is intrinsically integration-shaped. A pure unit test of an internal helper would not catch it.
- **Integration tests**: The two tests above, plus the restored schemathesis fuzz target (`tests/dashboard/test_schemathesis_contract.py`) which after AC3 loads the real full-app schema.

## Notes

- **Single Backend step with generous S01 timeout (~1800s)** to cover the bisect. Most of the work is reading the traceback and `git grep`-ing for `Response` annotations — the actual code change is small.
- **Do NOT refactor adjacent code** while doing the bisect. The fix is intentionally minimal (1-3 LOC) so the diff is reviewable and the blast radius is contained. If S01 encounters other latent OpenAPI generation issues during the bisect, file follow-up incidents — do not bundle them here.
- **S03 must not silently widen the JSON_API_PATHS allow-list** in `tests/dashboard/test_schemathesis_contract.py`. The allow-list intentionally narrows the fuzz surface to JSON endpoints; this incident only removes the *workaround* that built a fake `openapi()`, it does not change which routes the fuzzer targets.
- **No browser verification step** (`browser_verification: false`) — the bug is reproducible via `curl` / TestClient and the evidence is already on-disk as the CR-00072 test-module docstring. Adding a Playwright Swagger-UI screenshot would not improve signal.
