# CR-00072: Contract / No-5xx Route Sweep + schemathesis Fuzzing

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 3 item 3.2 of the Testing Enhancement Plan — there is no contract-level test today, so a broken router import or an unhandled exception on any dashboard route ships silently until a human hits it in the browser.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this CR's new tests use the existing testcontainer `db_session` fixture and nothing else.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item leaves migrations unchanged** — it adds no schema change and no migration file.

## Description

Add a contract test layer that proves no FastAPI route on the dashboard returns a 5xx. A **route-contract sweep** enumerates every registered `app.route`, requests each GET/HEAD route (including htmx GET fragments) against a seeded `TestClient`, and asserts the response status is never a server error. A separate **schemathesis** module property-fuzzes the JSON API endpoints against the generated OpenAPI schema. The sweep is a blocking gate; schemathesis runs nightly during a burn-in period.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the dashboard is a FastAPI app assembled in `dashboard/app.py` via `create_app()`; routers live in `dashboard/routers/`; dashboard tests use a `TestClient` with `app.dependency_overrides[get_db]` pointing at a testcontainer `db_session` (see `tests/dashboard/test_jobs_filter_ui.py` for the canonical pattern); the live-DB guard forbids any test touching port 5433. This CR is part of the phased plan in `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.2).

## Current Behavior

- There is no test that exercises every dashboard route. Coverage of routes is incidental — a route is only tested if someone wrote a targeted test for it.
- A broken router import, a typo'd template name, a `%`-format bug in a shared Jinja2 fragment (the I-00075 class), or an unhandled exception in a handler is only discovered when a human navigates to the affected page, or — at best — when an unrelated targeted test happens to touch the route.
- `tests/dashboard/` holds ~60 `TestClient` test files, each pinning one specific behaviour; none of them sweeps the route table.
- There is no contract/fuzz testing against the app's OpenAPI schema. `schemathesis` is not a dependency.
- The `pytest` default selection (`addopts`) excludes `browser` and `quarantine` markers; there is no `contract_fuzz` marker.

## Desired Behavior

- A **route-contract sweep** (`tests/dashboard/test_route_contract_sweep.py`) enumerates `create_app().routes`, and for every route that serves GET (or HEAD), issues a request against a `TestClient` backed by a seeded testcontainer DB and asserts `response.status_code < 500`. Routes with path parameters get real IDs substituted from the seeded data. The sweep is parametrized one-case-per-route so a failure names the offending route.
- Because the sweep lives under `tests/dashboard/`, the existing **`integration-tests` daemon QV gate** (`make test-integration`) and the `integration` job in `test-quality.yml` run it automatically on every work item and every PR — **no new canonical QV gate** is introduced.
- A **schemathesis module** (`tests/dashboard/test_schemathesis_contract.py`, marked `contract_fuzz`) property-fuzzes the app's **JSON API operations** against the generated OpenAPI schema, asserting schemathesis's `not_a_server_error` check. The fuzz target is defined precisely as *operations whose OpenAPI response declares an `application/json` media type* (handlers returning `JSONResponse` or a pydantic model — not `HTMLResponse`); in today's dashboard that is the keep-alive API (`/api/keep-alive/*`), the runtime-overrides endpoint, and the JSON job endpoints. The dashboard is predominantly HTML/htmx, so this surface is deliberately narrow — the HTML/htmx routes are covered by the route sweep, not the fuzzer. The `contract_fuzz` marker is **excluded from the default `pytest` selection**, so it never runs in the blocking suite.
- A new **nightly GitHub Actions workflow** (`.github/workflows/contract-fuzz.yml`) runs `make test-contract-fuzz` on a cron schedule with `continue-on-error` (burn-in), matching the periodic/informational bucket in the plan's §9 CI matrix.
- If the sweep finds a *genuine* 5xx on current `main`, it is recorded in an explicit `EXPECTED_5XX` allowlist in the test file — keyed by route, each entry carrying a `TODO(file-incident)` placeholder and a one-line rationale — and the corresponding parametrized case is `xfail`-ed. The implementer does **not** file the Incident from inside the worktree (an incident package would land outside `scope.allowed_paths`); each placeholder is surfaced as operator follow-up in the S01 report, and the operator files the Incident on `main` post-merge. The gate then fires only on **new** 5xx regressions. This keeps CR-00072 strictly test-only: it never edits production code.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/dashboard/` | ~60 targeted `TestClient` files; no route sweep | + route-contract sweep + schemathesis module |
| `pytest` marker set | `browser`, `quarantine`, `smoke`, `order_dependent`, `properties` | + `contract_fuzz` (excluded from default `addopts` selection) |
| `Makefile` | no contract targets | + `test-route-sweep`, `test-contract-fuzz` |
| GitHub Actions | `test-quality.yml`, `security-scan.yml`, `codeql.yml`, … | + nightly `contract-fuzz.yml` |
| Dev dependencies | no `schemathesis` | + `schemathesis` (dev group) |

### Breaking Changes

- None. This CR adds tests, a marker, two Makefile targets, one CI workflow, and one dev dependency. No production code, no API, no schema, no behaviour change.

### Data Migration

- None. No schema change, no migration file, nothing to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Route-contract sweep + schemathesis module; `schemathesis` dev dep; `contract_fuzz` marker; `addopts` exclusion; Makefile targets; nightly workflow; strategy-doc + skill + plan updates | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global cross-agent review of all work | — |
| S04 | qv-gate | `lint` → `make lint` | — |
| S05 | qv-gate | `assertions` → `make test-assertions` | — |
| S06 | qv-gate | `format` → `make format-check` | — |
| S07 | qv-gate | `typecheck` → `make type-check` | — |
| S08 | qv-gate | `unit-tests` → `make test-unit` | — |
| S09 | qv-gate | `integration-tests` → `make test-integration` (this runs the new route sweep) | — |
| S10 | qv-gate | `diff-coverage` → `make diff-coverage` | — |
| S11 | qv-gate | `security-secrets` → `make security-secrets` | — |
| S12 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no migration file is added.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00072_CR_Design.md` | Design | This document |
| `CR-00072_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00072_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00072_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/CR-00072_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review instructions |
| `prompts/CR-00072_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00072/reports/`.

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `tests/dashboard/test_route_contract_sweep.py` | Create | The no-5xx route sweep |
| `tests/dashboard/test_schemathesis_contract.py` | Create | schemathesis OpenAPI fuzzing of JSON endpoints |
| `tests/dashboard/conftest.py` | Modify (if needed) | Shared seeded-`TestClient` fixture |
| `tests/fixtures/**` | Create (if needed) | Shared seed helper for the sweep |
| `.github/workflows/contract-fuzz.yml` | Create | Nightly schemathesis workflow |
| `pyproject.toml` | Modify | `schemathesis` dev dep; `contract_fuzz` marker; `addopts` exclusion |
| `uv.lock` | Modify | Regenerated after adding the dep |
| `Makefile` | Modify | `test-route-sweep` + `test-contract-fuzz` targets, `.PHONY` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | Document the contract layer (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Note the contract sweep layer + how to extend it |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (`iw sync-skills --force iw-ai-core-testing`) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Mark item 3.2 DONE; §11 changelog; §9 row |

## Acceptance Criteria

### AC1: Route sweep exercises every GET route and asserts no 5xx

```
Given the dashboard app assembled by create_app()
When tests/dashboard/test_route_contract_sweep.py runs
Then every route on app.routes that serves GET or HEAD — minus a small, explicitly
     documented skip set (streaming/SSE endpoints, the static-files mount) — is
     requested against a seeded TestClient (raise_server_exceptions=False)
And each request asserts response.status_code < 500
And the sweep is parametrized one case per route so a failure names the route
```

### AC2: The sweep is picked up by the existing blocking gate — no new QV gate

```
Given the route sweep lives under tests/dashboard/
When the integration-tests QV gate (make test-integration) or the test-quality.yml
     integration job runs
Then test_route_contract_sweep.py is collected and executed
And no new entry is added to the canonical QV-gate list in skills/iw-workflow/SKILL.md
```

### AC3: schemathesis fuzzing exists and is excluded from the default suite

```
Given the contract_fuzz marker is registered in pyproject.toml and added to the
      addopts -m exclusion expression
When make test-unit or make test-integration runs
Then tests/dashboard/test_schemathesis_contract.py is NOT collected
When make test-contract-fuzz runs
Then schemathesis loads the app's OpenAPI schema, generates cases for the JSON
     API operations (those whose OpenAPI response declares an application/json
     media type — the keep-alive API, runtime-overrides, JSON job endpoints —
     never the HTML/htmx routes), and asserts the not_a_server_error check on
     every generated response
```

### AC4: Nightly schemathesis workflow

```
Given .github/workflows/contract-fuzz.yml exists
When the nightly cron fires (or the workflow is dispatched manually)
Then it runs make test-contract-fuzz with continue-on-error / a non-failing job
     status during the burn-in period
And it does not run on ordinary pushes or pull requests
```

### AC5: Genuine pre-existing 5xx are allowlisted, not fixed — the CR stays test-only

```
Given S01 runs the route sweep against current main
When a route returns a genuine 5xx (not a test-harness artefact such as a missing
     seed row or an unresolved path parameter)
Then that route is recorded in an EXPECTED_5XX allowlist in the test file, keyed by
     route, with a TODO(file-incident) placeholder and a one-line rationale, and
     its parametrized case is xfail-ed
And each placeholder is surfaced as operator follow-up in the S01 report — the
     operator files the Incident on main post-merge; S01 never runs /iw-new-incident
     or creates an incident package inside the worktree
And no file outside this CR's scope.allowed_paths is modified
And the route sweep exits 0 on current main
```

### AC6: Docs, skill, and plan updated and synced

```
Given the contract test layer now exists
When S01 completes
Then docs/IW_AI_Core_Testing_Strategy.md describes the contract layer (§3 layers,
     §5 gate table, §9 gap rows)
And skills/iw-ai-core-testing/SKILL.md notes the sweep layer and how to extend it
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to its master
     (iw sync-skills --force iw-ai-core-testing was run)
And ai-dev/work/TESTS_ENHANCEMENT.md marks item 3.2 DONE with a §11 changelog entry
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the squash-merge commit. The CR adds only tests, a marker, two Makefile targets, one CI workflow, one dev dependency, and doc updates — reverting removes them cleanly with no residue.
- **Data**: No data loss on rollback — nothing in the CR writes to any persistent store.

## Dependencies

- **Depends on**: None. The `pgtestdbpy` per-test DB isolation (CR-00055) and the `integration-tests` gate flip to `make test-integration` (direct change, 2026-05-14) are already on `main` and are relied upon, but no in-flight item is required.
- **Blocks**: None. Sibling Phase 3 items (3.1, 3.3–3.6) are logically independent — no item depends on another's code.
- **Cannot share a parallel batch with the siblings**: CR-00072 modifies `Makefile`, `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, and `ai-dev/work/TESTS_ENHANCEMENT.md` — every one of which is also in the impacted-paths of the sibling Phase 3 CRs (CR-00073/74/75/76) — plus `pyproject.toml` and `uv.lock`, shared with F-00088. These are non-test paths, so the cross-batch launch-time overlap gate (F-00076) will flag a conflict. The Phase 3 items must therefore be **sequenced** (one batch each, or run individually), not launched as a single parallel batch.

## Impacted Paths

- `tests/dashboard/test_route_contract_sweep.py`
- `tests/dashboard/test_schemathesis_contract.py`
- `tests/dashboard/conftest.py`
- `tests/fixtures/**`
- `.github/workflows/contract-fuzz.yml`
- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is a test-infrastructure CR — the new tests *are* the deliverable, so classic RED-GREEN does not apply to production code. The "every test must be able to fail" requirement is satisfied differently:

- **Route sweep — prove it can fail.** Before reporting completion, S01 must demonstrate the sweep catches a regression — **entirely within the test file**, no production code touched: register a throwaway, deliberately-5xx route on the test's own `create_app()` instance (e.g. a `GET /__cr72_selfcheck__` handler that raises). The sweep enumerates `app.routes`, so it picks the throwaway route up; run the sweep, confirm that route's parametrized case fails with a 5xx, then remove the throwaway route. The captured failing output is recorded as `tdd_red_evidence`. Do **not** inject a `raise` into a production `dashboard/` handler — that file is out of scope.
- **schemathesis — prove it can fail.** Similarly, and again entirely within the test file: register a throwaway JSON route on the test app that 5xx's and falls inside the fuzz filter, confirm `make test-contract-fuzz` reports the `not_a_server_error` failure, then remove the throwaway route. No production code is touched.
- **Unit tests**: none — there is no pure logic to unit-test; the deliverable is integration-level `TestClient` sweeps.
- **Integration tests**: `test_route_contract_sweep.py` (the sweep itself) and `test_schemathesis_contract.py` (the fuzz module). Both use the testcontainer `db_session` fixture; neither touches the live DB.
- **Updated tests**: none — no existing test changes behaviour. If the sweep surfaces a genuine 5xx, it is allowlisted (AC5), not fixed.

## Notes

- **Risk — the sweep finds real 5xx on `main`.** Expected and acceptable. AC5's `EXPECTED_5XX` allowlist absorbs them so the CR can merge without expanding into a production fix; each allowlisted route carries a `TODO(file-incident)` placeholder and is surfaced as operator follow-up in the S01 report, and the operator files the Incident on `main` post-merge so the bug is tracked. The implementer must NOT edit production code, and must NOT create an incident package inside the worktree (it would land outside `scope.allowed_paths`) — the merge-time scope gate enforces this.
- **`raise_server_exceptions=False` is mandatory for the sweep client.** The common dashboard-test fixture uses `raise_server_exceptions=True`, which *raises* on a 500 instead of returning it. The sweep must observe the 500 as a response to assert on it.
- **Streaming/SSE routes must be skipped.** Routes under `dashboard/routers/sse.py` (and any other streaming endpoint) hold the connection open; a blind GET hangs the sweep. They go in the documented skip set with a rationale. SSE behaviour is covered separately by existing targeted tests.
- **Path-parameter resolution.** Routes like `/projects/{project_id}/...` need real IDs. The sweep builds a substitution map from the seeded dataset (project, work item, batch, doc, job, …). A route whose parameters cannot be resolved is recorded in an explicit `UNRESOLVED` list the test asserts against, so a newly-added unresolvable route surfaces rather than being silently skipped.
- **schemathesis version.** Pin to the current major at implementation time (consult the library docs); restrict generated operations to the JSON API paths only — fuzzing the HTML/htmx routes is out of scope for this CR.
- **Out of scope**: fixing any 5xx the sweep finds; sweeping mutating POST routes (covered by schemathesis for JSON endpoints + existing action tests); flipping schemathesis to a blocking gate (a later follow-up after burn-in); porting the layer to sibling repos.
