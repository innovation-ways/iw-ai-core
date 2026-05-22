# CR-00072 — S01 Backend Report

**Work item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
**Step**: S01 (backend-impl)
**Status**: complete
**Date**: 2026-05-21

---

## What was done

Implemented the full contract test layer for CR-00072 — a **test-only** change.
No production code (`orch/`, `dashboard/`, `executor/`, `scripts/`) was modified;
`git diff origin/main -- dashboard/ orch/ executor/ scripts/` is empty.

1. **Route-contract sweep** — `tests/dashboard/test_route_contract_sweep.py`
   - Enumerates every route on `create_app()`; for each GET/HEAD route it issues
     a request against a seeded testcontainer `TestClient`
     (`raise_server_exceptions=False`) and asserts `status_code < 500`.
   - **Parametrized one case per route** (`pytest_generate_tests`), the param id
     is the route path so a failure names the offending route.
   - `SKIP_ROUTES` (14 entries, one-line rationale each): SSE/streaming routes,
     the static mount, FastAPI's OpenAPI/Swagger endpoints, and the AI-runtime
     -gated chat endpoints (their 503 is correct behaviour when no runtime is up).
   - Path parameters resolve from a seeded dataset via a substitution map
     (`project_id`, `item_id`, `batch_id`, `doc_id`, `job_id`, `step_id`,
     `run_id`). Routes with unresolvable parameters go into `UNRESOLVED`, asserted
     against the explicitly-reviewed `EXPECTED_UNRESOLVED` set (20 routes).
   - `EXPECTED_5XX` allowlist: genuine pre-existing 5xx → `xfail(strict=True)` +
     `TODO(file-incident)` rationale.

2. **schemathesis fuzz module** — `tests/dashboard/test_schemathesis_contract.py`
   - `schemathesis>=4` property-fuzzes the JSON API operations (keep-alive API +
     runtime-overrides) against the OpenAPI schema, asserting `not_a_server_error`
     (`status_code < 500`) on every generated case.
   - Module marked `contract_fuzz` (`pytestmark`) — excluded from the default
     suite, runs only via `make test-contract-fuzz` / the nightly workflow.
   - Work-around: `create_app().openapi()` raises a pre-existing Pydantic
     `ForwardRef('Response')` error, so the test app's `app.openapi` is overridden
     (test app only) with a schema built from just the JSON-API routes.

3. **Shared seed helper** — `seed_contract_test_data` added to
   `tests/dashboard/conftest.py` (project, work item + steps, batch + batch item,
   catalogue doc + research doc, doc-generation job, test run, daemon event).

4. **`pyproject.toml`** — `schemathesis>=4.19,<5` (current major) in
   `[dependency-groups] dev`; `uv.lock` regenerated (`uv sync --frozen` passes).
   The `contract_fuzz` marker + `addopts` `-m '... and not contract_fuzz'`
   exclusion were already present.

5. **Makefile** — `test-route-sweep` + `test-contract-fuzz` targets added to the
   `.PHONY` line (the recipes were already present).

6. **Nightly workflow** — `.github/workflows/contract-fuzz.yml`: `schedule` cron
   (`17 3 * * *`) + `workflow_dispatch`; **never** push/pull_request; runs
   `make test-contract-fuzz`; `continue-on-error: true` (burn-in). Environment
   setup mirrors `test-quality.yml`'s `integration` job.

7. **Docs / skill / plan**:
   - `docs/IW_AI_Core_Testing_Strategy.md` — §2 new "Layer 6 — Contract tests",
     §5 two new gate-table rows, §9 row 3.2 flipped to ✅.
   - `skills/iw-ai-core-testing/SKILL.md` — new §11 "Contract test layer";
     `iw sync-skills --force iw-ai-core-testing` ran — `.claude/skills/` copy is
     byte-identical (verified with `diff`).
   - `ai-dev/work/TESTS_ENHANCEMENT.md` — item 3.2 → `DONE 2026-05-21 (CR-00072)`;
     §11 changelog entry added.

## Files changed

- `tests/dashboard/test_route_contract_sweep.py` (new)
- `tests/dashboard/test_schemathesis_contract.py` (new)
- `tests/dashboard/conftest.py` (seed helper added)
- `.github/workflows/contract-fuzz.yml` (new)
- `pyproject.toml` (schemathesis pin)
- `uv.lock` (regenerated)
- `Makefile` (`.PHONY`)
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## Test results

- **Route sweep** (`make test-route-sweep`): **124 passed, 1 xfailed** —
  123 GET/HEAD route cases swept (122 pass + 1 xfail) + 2 meta tests pass.
- **schemathesis** (`make test-contract-fuzz`): **2 passed, 5 subtests passed** —
  5 JSON-API operations fuzzed green; the schema-existence guard passes.
- **Marker exclusion**: `pytest tests/dashboard/test_schemathesis_contract.py
  --collect-only` → `no tests collected (2 deselected)` — `contract_fuzz` is not
  collected by the default selection.
- Preflight: `make format` clean · `make lint` "All checks passed" ·
  `make typecheck` "Success: no issues found" · `make test-assertions`
  "No new assertion-scanner violations".

## "Every test can fail" — deliberate-break demonstration (tdd_red_evidence)

- **Route sweep**: a throwaway `GET /__cr72_selfcheck__` handler raising
  `RuntimeError` was registered on the test's `create_app()` instance. The sweep
  picked it up and its parametrized case failed:
  `AssertionError: Route GET /__cr72_selfcheck__ ... returned HTTP 500. assert 500 < 500`.
  Throwaway route removed.
- **schemathesis**: a throwaway JSON `GET /__cr72_jsonfuzz__` route raising
  `RuntimeError` was added to the fuzz target. schemathesis reported the
  `not_a_server_error` failure (`SUBFAILED ...[GET /__cr72_jsonfuzz__]`).
  Throwaway route removed.
- Verified `git diff origin/main -- dashboard/ orch/` is empty and no
  `__cr72_*` route remains in the committed test files.

## EXPECTED_5XX / KNOWN_CONTRACT_5XX summary

- **Total GET/HEAD routes swept**: 123 (parametrized cases).
- **Skipped** (`SKIP_ROUTES`): 14 — SSE/streaming (7), static mount (1), FastAPI
  OpenAPI/Swagger endpoints (4), AI-runtime-gated chat endpoints (2).
- **UNRESOLVED** (`EXPECTED_UNRESOLVED`): 20 routes with path parameters the
  sweep cannot resolve from seeded data (free-text `action`/`job_type`/`phase`
  discriminators, chat tab/conversation ids, RAG module slugs, service names,
  file-path parameters, etc.).
- **`EXPECTED_5XX`**: **1** route.
- **schemathesis `KNOWN_CONTRACT_5XX`**: **1 bug class / 2 operations**.

## Operator follow-up — file these Incidents on `main` post-merge

CR-00072 is strictly test-only; the implementer does not run `/iw-new-incident`
from the worktree (the incident package would land outside `scope.allowed_paths`).
The operator should file an Incident for each genuine pre-existing bug below.

1. **`GET /project/{project_id}/docs/{doc_id}/pdf` → HTTP 500** (route sweep
   `EXPECTED_5XX`). `docs_pdf()` in `dashboard/routers/docs.py` raises an
   unhandled `PermissionError` when the optional on-disk PDF cache directory
   under `project.repo_root` is not writable — the PDF itself was already
   generated successfully; only the optional cache write fails. The sibling
   handler `docs_pdf_view()` guards the identical cache write in `try/except`
   and degrades gracefully; `docs_pdf()` must do the same. Failing snippet:
   `Timing middleware error: [Errno 13] Permission denied: '/repos'` →
   `Internal Server Error` (HTTP 500).

2. **Keep-alive slot endpoints 500 on a BIGINT-overflow `slot_id`**
   (schemathesis `KNOWN_CONTRACT_5XX`). `DELETE /api/keep-alive/slots/{slot_id}`
   and `PATCH /api/keep-alive/slots/{slot_id}/toggle` take an unbounded `int`
   path parameter and pass it straight to a `BIGINT`-keyed query; a value above
   `2**63-1` raises `psycopg.errors.NumericValueOutOfRange` → HTTP 500 instead
   of a 404/422. Failing snippet:
   `(psycopg.errors.NumericValueOutOfRange) bigint out of range
   [parameters: {'pk_1': 9223372036854775808}]`.

3. **`GET /openapi.json` 500s app-wide** (discovered while wiring schemathesis).
   `create_app().openapi()` raises
   `PydanticUserError: TypeAdapter[Annotated[ForwardRef('Response'), ...]] is not
   fully defined` — a handler elsewhere in the app has an unresolved `-> Response`
   return annotation that breaks full-app OpenAPI generation. Worked around in
   the schemathesis module by building the fuzz schema from only the JSON-API
   routes. The route sweep skips `/openapi.json` per the documented skip set.

## Observations

- The route sweep is collected automatically by `make test-integration` (it
  lives under `tests/dashboard/`) — **no new canonical QV gate** is introduced
  (AC2).
- The full app's `app.openapi()` being broken meant schemathesis could not load
  the schema from `create_app()` directly; the JSON-API-routes-only schema
  override (test app only, no production change) is the work-around.
- schemathesis handlers raise `HTTPException` on a DB error without rolling
  back; the fuzz `get_db` override rolls the shared session back before each
  request so a poisoned session does not leak `InFailedSqlTransaction` across
  generated cases.
