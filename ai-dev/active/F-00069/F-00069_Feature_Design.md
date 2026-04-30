# F-00069: Test Execution, Coverage Gate, Reports, and Coverage Dashboard View

**Type**: Feature
**Priority**: High
**Created**: 2026-04-29
**Status**: Draft

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

This feature does NOT add or modify any migration. There is no Database
step. No alembic invocations are required.

## Description

Make AI Core's test suite faster (parallel execution), enforce a coverage
floor that prevents silent regression, surface coverage data visually in
the dashboard so the gap to the threshold is obvious without leaving the
UI, and add ergonomic Make targets for E2E debugging and Allure report
viewing. This is the foundation feature of the testing/quality batch
sourced from the podforger comparison; F-00070 (Smoke + CI) depends on
it.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard
rules. Specifically:

- `tests/CLAUDE.md` — strict live-DB-guard rules; coverage runs MUST
  inherit them (no env override).
- `dashboard/CLAUDE.md` — htmx fragment + Jinja base-template pattern
  for the new `/coverage` page.

## Scope

### In Scope

1. **Parallel test execution**
   - Add `pytest-xdist>=3.5.0` to the dev dependency group in
     `pyproject.toml`.
   - Configure `[tool.pytest.ini_options]` so the parallel runner uses
     `-n auto --dist=loadfile` (file-level distribution; required because
     integration tests share a session-scope `pg_engine` testcontainer
     fixture in `tests/conftest.py` — fixture-scope races are observed
     under the default `loadgroup` distribution).
   - Add `make test-parallel` Makefile target that runs `tests/unit/`
     and `tests/integration/` under xdist. Default `make test`,
     `make test-unit`, `make test-integration` MUST continue to behave
     exactly as today (serial); xdist is opt-in via the new target.

2. **Coverage gate (measure-then-enforce)**
   - Wire `pytest-cov` into the existing `make test-unit` and
     `make test-integration` invocations. Coverage scope: `orch/`,
     `dashboard/`, `executor/`. Exclusions (configured under
     `[tool.coverage.run]` in pyproject.toml):
     `orch/db/migrations/versions/*`, `tests/*`, `scripts/*`, `bin/*`,
     `*/__init__.py`-only files only if they have no statements.
   - Reports written to `tests/output/coverage/`:
     - terminal `term-missing:skip-covered`
     - HTML at `tests/output/coverage/htmlcov/`
     - XML at `tests/output/coverage/coverage.xml`
     - JSON at `tests/output/coverage/coverage.json`
   - **Baseline measurement** (executed during S01 implementation): run
     the full suite once on a clean checkout, read the resulting
     `coverage.json` `totals.percent_covered`, take `floor(value)` and
     subtract 5 to derive the threshold. Persist this number into
     `[tool.coverage.report] fail_under = N` in `pyproject.toml`. Record
     the measured baseline AND the chosen floor in the S01 report and
     append a **"Baseline Coverage Snapshot"** section to this design
     doc post-implementation. The floor is one-way: future work may
     ratchet it up but never down.
   - Add `tests/output/` to `.gitignore` (verify it is not already
     covered by `.gitignore` first).

3. **Allure / HTML report Make targets**
   - The repo already has `make allure-unit`, `make allure-integration`,
     `make allure-all`, `make allure-serve`, `make allure-clean`. Keep
     them. Add:
     - `make allure-report` — generate a static HTML report at
       `allure-report/` from `allure-results/` (uses `allure generate
       --clean`).
   - Wrap `allure-serve` and `allure-report` so that if the `allure`
     CLI is not on PATH the target prints clear install instructions
     (npm/brew/manual) and exits non-zero, instead of silently failing
     via `npx`.

4. **E2E ergonomics Make targets** (folded in from tier-2)
   - `make e2e-health` — reads the service ports defined in
     `docker-compose.e2e.yml`, curls `/healthz` (or service-appropriate
     path) for each one, prints a PASS/FAIL line per service, and exits
     non-zero if any service fails.
   - `make e2e-logs` — `docker compose -f docker-compose.e2e.yml -p
     "$$COMPOSE_PROJECT_NAME" logs --tail=200 -f` (exits cleanly on
     Ctrl-C).
   - `make e2e-stats` — `docker stats --no-stream` filtered to the
     project's containers (use `docker ps --filter
     "label=com.docker.compose.project=$$COMPOSE_PROJECT_NAME" -q`).

5. **Coverage dashboard view** (`/system/coverage`)
   - New FastAPI router `dashboard/routers/coverage.py` registered in
     `dashboard/app.py`. Single route: `GET /system/coverage` returning
     the rendered template; one htmx fragment route
     `GET /system/coverage/files/{package}` returning the per-file
     drill-down fragment.
   - New service `dashboard/services/coverage_service.py` — pure
     function reading `tests/output/coverage/coverage.json` and
     normalising it into a typed view-model (overall %, per-package
     rows, per-file rows, threshold, mtime, missing-file flag). NO DB.
     NO history. NO background job.
   - Threshold sourced from `[tool.coverage.report] fail_under` in
     `pyproject.toml` (read once at request time using `tomllib`).
   - New page template
     `dashboard/templates/pages/system/coverage.html` extending
     `base.html`. New htmx fragment template
     `dashboard/templates/fragments/coverage_files.html`.
   - Page sections, top-to-bottom:
     - **Header card**: overall line %, branch %, gap to threshold,
       `coverage.json` mtime (human-readable + ISO), test count if
       present.
     - **Per-package table**: rows for `orch`, `dashboard`, `executor`
       — line %, branch %, missing-line count, color-coded badge
       (green ≥ threshold; amber threshold-10 ≤ x < threshold; red <
       threshold-10).
     - **Drill-down**: clicking a package row swaps in the file-level
       table via htmx; same column set.
     - **Empty state**: when `coverage.json` is missing or unreadable,
       render a card explaining "Run `make test-unit` or
       `make test-parallel` to generate coverage data" and show the
       last-known mtime if any artefact lives at the path.
   - **Nav entry**: add `('/system/coverage', 'Test Coverage')` to the
     `system_links` list in `dashboard/templates/base.html`. Place it
     after `/system/status` and before `/system/all-active`.

### Out of Scope

- `@smoke` pytest marker and `make smoke` target — owned by F-00073.
- The `test-quality` GitHub Actions workflow — owned by F-00073.
- Logging configuration tests under `tests/unit/` — owned by F-00073.
- Pre-commit hook additions — owned by F-00070.
- Migration roundtrip tests / `schema-validation` workflow — owned by F-00072.
- Codecov upload (explicitly skipped per user decision 2026-04-29).
- ERD auto-regeneration (explicitly skipped per user decision
  2026-04-29).
- Coverage trend-over-time / DB persistence / time-series chart — out
  of scope for this feature; could be a future CR.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | pyproject.toml (xdist + pytest-cov + coverage config + threshold), Makefile additions, baseline measurement, coverage_service.py, /coverage router registration | — |
| S02 | frontend-impl | /system/coverage Jinja templates, fragment template, base.html nav entry, dashboard CSS if needed | — |
| S03 | code-review-impl | Review S01 (backend + Makefile + config) | — |
| S04 | code-review-impl | Review S02 (frontend templates + nav) | — |
| S05 | tests-impl | Unit tests for coverage_service.py; dashboard tests for /system/coverage page (rendered, empty-state, fragment); Makefile target smoke-check | — |
| S06 | code-review-impl | Review S05 (tests) | — |
| S07 | code-review-final-impl | Cross-layer global review | — |
| S08 | qv-gate | `make lint` | — |
| S09 | qv-gate | `make format` | — |
| S10 | qv-gate | `make typecheck` | — |
| S11 | qv-gate | `make test-unit` | — |
| S12 | qv-gate | `make allure-integration` | — |
| S13 | qv-browser | Browser verification — render `/system/coverage`, drill-down, empty state | — |

S01 and S02 are listed sequentially; the orchestrator may parallelize
them since they touch disjoint files (S01 owns Python/Makefile, S02
owns templates/CSS), with the exception that S02's nav entry is in
`base.html` which S01 does not touch — non-conflict.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no DB changes whatsoever.

### API Changes

- **New endpoints**:
  - `GET /system/coverage` — HTML page
  - `GET /system/coverage/files/{package}` — htmx fragment
- **Modified endpoints**: None

### Frontend Changes

- **New components**:
  - Page template `dashboard/templates/pages/system/coverage.html`
  - Fragment template `dashboard/templates/fragments/coverage_files.html`
- **Modified components**:
  - `dashboard/templates/base.html` — one new nav entry under System

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00069/F-00069_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00069/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00069/prompts/F-00069_S01_Backend_prompt.md` | Prompt | S01 backend implementation |
| `ai-dev/active/F-00069/prompts/F-00069_S02_Frontend_prompt.md` | Prompt | S02 frontend implementation |
| `ai-dev/active/F-00069/prompts/F-00069_S03_CodeReview_Backend_prompt.md` | Prompt | Review of S01 |
| `ai-dev/active/F-00069/prompts/F-00069_S04_CodeReview_Frontend_prompt.md` | Prompt | Review of S02 |
| `ai-dev/active/F-00069/prompts/F-00069_S05_Tests_prompt.md` | Prompt | Test step |
| `ai-dev/active/F-00069/prompts/F-00069_S06_CodeReview_Tests_prompt.md` | Prompt | Review of S05 |
| `ai-dev/active/F-00069/prompts/F-00069_S07_CodeReview_Final_prompt.md` | Prompt | Final cross-layer review |
| `ai-dev/active/F-00069/prompts/F-00069_S13_BrowserVerification_prompt.md` | Prompt | QV browser verification |
| `pyproject.toml` | Modified | Add pytest-xdist, pytest-cov config, coverage config, fail_under |
| `Makefile` | Modified | Add `test-parallel`, `allure-report`, `e2e-health`, `e2e-logs`, `e2e-stats`; wrap `allure-serve` with install hint |
| `.gitignore` | Modified | Add `tests/output/` if not already covered |
| `dashboard/services/coverage_service.py` | New | Pure function reading coverage.json into view-model |
| `dashboard/routers/coverage.py` | New | FastAPI router for /system/coverage and fragment |
| `dashboard/app.py` | Modified | Register `coverage` router |
| `dashboard/templates/pages/system/coverage.html` | New | Coverage page template |
| `dashboard/templates/fragments/coverage_files.html` | New | Per-file drill-down fragment |
| `dashboard/templates/base.html` | Modified | Add `('/system/coverage', 'Test Coverage')` nav entry |
| `tests/unit/dashboard/test_coverage_service.py` | New | Unit tests for service |
| `tests/dashboard/test_coverage_page.py` | New | Dashboard tests (rendered, empty state, fragment) |

Reports are created during execution in `ai-dev/active/F-00069/reports/`.

## Acceptance Criteria

### AC1: Parallel runner works without fixture races

```
Given pytest-xdist is installed and `[tool.pytest.ini_options]` is configured
When the developer runs `make test-parallel`
Then the unit and integration suites run under xdist with -n auto --dist=loadfile
And every test that passes under serial `make test` also passes under `make test-parallel`
And no testcontainer fixture-race errors are observed across at least 3 consecutive runs
```

### AC2: Coverage threshold enforced

```
Given the coverage threshold is set to floor(baseline) - 5 in pyproject.toml
When the developer runs `make test-unit` or `make test-integration`
Then a coverage.json, coverage.xml, and HTML report are written under tests/output/coverage/
And if the suite achieves >= threshold the command exits 0
And if a hypothetical change drops coverage below threshold the command exits non-zero with a clear "FAIL Required test coverage of N% not reached" message
```

### AC3: Coverage dashboard page renders

```
Given coverage.json exists at tests/output/coverage/coverage.json
When the user opens http://localhost:9900/system/coverage
Then the page renders with HTTP 200
And the header card shows the overall line %, branch %, gap to threshold, and the file mtime
And the per-package table shows one row each for orch, dashboard, executor
And each row shows a green/amber/red badge based on its line % vs the threshold
And the page extends base.html with the standard System nav visible
```

### AC4: Coverage dashboard drill-down works

```
Given coverage.json contains per-file data for the orch package
When the user clicks the orch package row on /system/coverage
Then htmx fetches /system/coverage/files/orch
And the response is the file-level fragment showing one row per file with line %, branch %, missing lines
And no full page reload occurs
```

### AC5: Empty state renders when coverage.json is missing

```
Given tests/output/coverage/coverage.json does not exist
When the user opens /system/coverage
Then the page renders with HTTP 200 (not an error)
And shows a card with the message "Run `make test-unit` or `make test-parallel` to generate coverage data"
And does not show any package rows
```

### AC6: Make targets behave correctly

```
Given the e2e stack is up
When the developer runs `make e2e-health`
Then the target curls each service in docker-compose.e2e.yml and prints PASS/FAIL per service
And exits non-zero if any service is unhealthy

Given allure CLI is not installed on PATH
When the developer runs `make allure-serve` or `make allure-report`
Then the target prints clear install instructions (npm/brew) and exits non-zero
And does not silently no-op or attempt to install
```

### AC7: Existing test commands unchanged in behavior

```
Given a developer runs `make test-unit` or `make test-integration` (without -parallel)
Then the suites run serially as before, with no xdist worker spawning
And the only behavioral change is that coverage data is collected and the threshold is enforced
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| `coverage.json` missing | File deleted or never generated | `/system/coverage` renders empty state, HTTP 200 |
| `coverage.json` malformed | Invalid JSON or schema mismatch | `/system/coverage` renders empty state with a "could not parse" hint, HTTP 200, error logged |
| `coverage.json` partial | Has overall totals but no per-file data | Header renders; per-package table renders zeroes; drill-down fragment renders empty file list |
| Threshold not yet set in pyproject.toml | `[tool.coverage.report] fail_under` absent | `coverage_service` falls back to threshold=0; "gap" displayed as N/A; package badges all green |
| Coverage exactly at threshold | `total == threshold` | Badge is green; `--cov-fail-under` exit 0 |
| Coverage below threshold | `total < threshold` | `pytest --cov-fail-under` exits non-zero; dashboard renders red badge for affected package |
| `tests/output/coverage/` directory missing | Directory not yet created | Service treats as "missing coverage.json"; tests must create the dir before writing |
| xdist worker count = 1 (`-n 1`) | CI / forced serial | Tests still pass; no behavioral diff vs serial run |
| Allure CLI absent | `command -v allure` returns non-zero | Make targets print install hint and exit non-zero |
| `docker-compose.e2e.yml` not running | No services up | `make e2e-health` reports all FAIL and exits non-zero; `make e2e-logs` errors with a clear "no compose project" message |

## Invariants

1. `make test-unit` and `make test-integration` (without `-parallel`) must run serially — never spawn xdist workers.
2. The coverage threshold floor only ratchets upward; no implementation step may lower it below the value persisted by S01.
3. `coverage_service` MUST NOT raise on a missing or malformed `coverage.json` — always returns a view-model, with the empty-state flag set.
4. `/system/coverage` MUST NOT touch the database, spawn background jobs, or invoke pytest. It is a read-only view of an artefact file.
5. The `/system/coverage` route uses the standard `base.html` template and the htmx pattern documented in `dashboard/CLAUDE.md` — no client-side JS framework introduced.
6. xdist distribution mode MUST be `loadfile` (file-level isolation) to avoid `pg_engine` session-scope fixture races.
7. No new external dependencies are introduced beyond `pytest-xdist`. `pytest-cov` is already in deps.
8. The threshold value, the measured baseline, and the measurement date are recorded in both the S01 report and an appended "Baseline Coverage Snapshot" section of this design doc.

## Dependencies

- **Depends on**: None
- **Blocks**: F-00073 (Smoke + active test CI) — F-00073's `test-quality.yml` invokes `make test-parallel` and consumes the coverage gate established here.

## TDD Approach

- **Unit tests** (`tests/unit/dashboard/test_coverage_service.py`):
  - Parses a sample `coverage.json` fixture into the expected view-model.
  - Returns empty-state view-model when file is missing.
  - Returns empty-state view-model with parse-error flag when JSON is malformed.
  - Computes threshold gap correctly (positive when above, zero when at, negative when below).
  - Reads `fail_under` from a fixture pyproject.toml string.
  - Color-codes correctly at threshold boundary, threshold-1, threshold-10, threshold-11.
- **Integration / dashboard tests** (`tests/dashboard/test_coverage_page.py`):
  - GET `/system/coverage` with a fixture coverage.json present — assert 200, header values, table rows.
  - GET `/system/coverage` with file missing — assert 200, empty state element present.
  - GET `/system/coverage/files/orch` — fragment renders with per-file rows.
  - GET `/system/coverage/files/unknown` — 404.
- **Edge cases**:
  - Coverage exactly at threshold (boundary).
  - Per-package rollup from per-file rows when overall totals absent.
  - Make targets: `make test-parallel` smoke check via subprocess that the target exists and `make -n test-parallel` (dry-run) prints the expected command.

## Notes

- **Baseline measurement is part of S01.** Do not skip it. The S01 report
  must include `baseline_percent`, `floor_percent`, and the
  `[tool.coverage.report]` snippet committed to pyproject.toml.
- The dashboard already has Tailwind classes for status badges (see
  existing System pages); reuse `bg-green-*`, `bg-amber-*`, `bg-red-*`
  classes rather than introducing new ones.
- `make e2e-health` should derive the list of services from
  `docker-compose.e2e.yml` rather than hardcoding service names — read
  the file at runtime so adding services later doesn't break the target.
- This is the foundation feature of a 5-feature batch (F-A through F-E
  in the planning conversation). F-00070 (the next batch member, F-B)
  is the only one with a hard dependency on this feature.

## Baseline Coverage Snapshot

- **Measured on**: 2026-04-29
- **Baseline line coverage**: 51.25%
- **Threshold floor (`fail_under`)**: 46%
- **Notes**: Baseline measured via `make test-unit` (2064 passed, 9 pre-existing failures unrelated to F-00069 changes). The `executor/` package has low absolute coverage due to shell-script coverage tracking limitations; `orch/` and `dashboard/` drive the average. The floor (46%) allows a ~5% buffer before the gate fails.
