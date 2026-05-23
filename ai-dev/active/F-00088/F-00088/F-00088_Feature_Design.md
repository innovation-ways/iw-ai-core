# F-00088: Structured Dashboard E2E Test Layer

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this Feature's new tests that need them use the existing testcontainer `db_session` fixture. The E2E journey suite targets the isolated E2E stack managed by the daemon's `scripts/e2e_up.sh` / `docker-compose.e2e.yml` mechanism; the journeys themselves do not call any docker commands.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This Feature leaves migrations unchanged** — it adds no schema change and no migration file.

## Description

Add a structured E2E test layer under `tests/e2e/` that exercises whole dashboard user journeys through a real browser (via the `playwright-cli` binary) against the existing isolated E2E stack. Today the only browser tests are ad-hoc modules under `tests/dashboard/browser/` that are not seeded deterministically, cover no complete journeys, and have no accessibility or console-error assertions. F-00088 delivers six journey modules, a thin playwright-cli Python wrapper, new Makefile targets, and a two-job GitHub Actions workflow.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Especially relevant:
- **playwright-cli exclusively** — NEVER call `chromium.launch()`, NEVER use `agent-browser`, NEVER run `npx playwright install`. Binary: `~/.local/bin/playwright-cli`. Config: `.playwright/cli.config.json`.
- The existing E2E stack is `docker-compose.e2e.yml` / `scripts/e2e_up.sh`. The isolated stack is seeded by `scripts/e2e_seed.py`. The daemon manages bring-up; agents do NOT run `docker compose up`.
- `IW_BROWSER_BASE_URL` is the environment variable the daemon sets per-worktree. All browser tests must read from this env var — never hardcode ports.
- The live-DB guard forbids any test touching port 5433.
- The `addopts` `-m` expression on `main` currently excludes `browser` and `quarantine`. F-00088 extends it to also exclude `e2e` by appending `and not e2e` to whatever terms are already present — it must not hardcode the existing expression (CR-00072's `not contract_fuzz` is **not** yet on `main`; if CR-00072 merges first the term is preserved).
- This Feature is Phase 3 item 3.1 of the Testing Enhancement Plan in `ai-dev/work/TESTS_ENHANCEMENT.md`.

## Scope

### In Scope

- A new `tests/e2e/` directory with `conftest.py` and a thin Python wrapper around the `playwright-cli` binary (subprocess calls only — no direct Playwright API).
- The wrapper exposes journey helpers: open URL, go to URL, snapshot, click, fill, screenshot, read console errors, run an accessibility check.
- A `tests/e2e/test_harness_selfcheck.py` module: **unmarked** unit tests (no `e2e` marker) that feed the wrapper's pure failure-detection functions (console-error parsing, accessibility check, dangling-`hx-target` detector, SSE-timeout detector) synthetic bad input and assert each flags the failure. These need no browser or E2E stack — they are the runnable RED evidence for the harness.
- `e2e` and `e2e_smoke` pytest markers registered in `pyproject.toml`.
- The `e2e` marker added to the `addopts` `-m` exclusion expression so E2E journeys never run in the default `pytest` invocation or `make test-integration`.
- Six journey modules under `tests/e2e/`, one user journey each:
  1. `test_journey_home_navigation.py` — dashboard home → project → cross-tab navigation.
  2. `test_journey_queue_to_merge.py` — Queue → Batch → run → merge happy path.
  3. `test_journey_code_qa_sse.py` — Code Q&A: SSE answer stream renders incrementally and shows citations.
  4. `test_journey_docs_export.py` — Docs: HTML and PDF export round-trip.
  5. `test_journey_jobs_filters.py` — Jobs page multi-select filters.
  6. `test_journey_htmx_fragments.py` — htmx fragments render cleanly in a real browser (no 5xx, no console errors, no dangling `hx-target`).
- Every journey asserts (a) an accessibility check passes and (b) zero browser console errors are present at every page visited.
- An `e2e_smoke` subset designation: `test_journey_home_navigation` and `test_journey_queue_to_merge` are additionally marked `e2e_smoke`.
- `make test-e2e` and `make test-e2e-smoke` Makefile targets, both added to `.PHONY`.
- A `.github/workflows/e2e.yml` workflow with two jobs: a blocking `e2e-smoke` job (triggers on `pull_request` + `push`) and an informational `e2e-full` job (`continue-on-error: true`, triggers on `schedule` nightly + `workflow_dispatch`).
- At S03 time: updates to `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/SKILL.md` (+ sync via `iw sync-skills --force`), and `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.1 DONE + changelog entry).

### Out of Scope

- Deleting or migrating the existing `tests/dashboard/browser/` (`-m browser`) tests — those remain alongside the new layer. Migration/retirement is a possible follow-up.
- Fixing any dashboard bug a journey surfaces — these are recorded as xfail reproductions with a `TODO(file-incident)` placeholder and a one-line rationale; they are listed under an "Operator follow-up" heading in the step report, and the operator files the Incident on `main` post-merge. They are never fixed in-Feature, and no incident package is created from the worktree.
- Modifying any production code in `orch/`, `dashboard/`, or `executor/`.
- Adding a new canonical QV gate in `skills/iw-workflow/SKILL.md` — the new Makefile targets are convenience targets; the QV suite is unchanged except for the S14 qv-browser step.
- Sweeping mutating POST routes (covered by the route-contract sweep in CR-00072 and existing action tests).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `tests/e2e/` dir + `conftest.py` + playwright-cli wrapper; `e2e` + `e2e_smoke` markers + `addopts` exclusion; `make test-e2e` + `make test-e2e-smoke` Makefile targets; `test_journey_home_navigation.py` as proof-of-harness with a11y + no-console-error assertions | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | backend-impl | Remaining 5 journeys; `e2e_smoke` subset designation; `.github/workflows/e2e.yml`; docs/skill/plan updates | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Global cross-agent review; runs full unit + integration suites | — |
| S06 | qv-gate | `lint` → `make lint` | — |
| S07 | qv-gate | `assertions` → `make test-assertions` | — |
| S08 | qv-gate | `format` → `make format-check` | — |
| S09 | qv-gate | `typecheck` → `make type-check` | — |
| S10 | qv-gate | `unit-tests` → `make test-unit` | — |
| S11 | qv-gate | `integration-tests` → `make test-integration` | — |
| S12 | qv-gate | `diff-coverage` → `make diff-coverage` | — |
| S13 | qv-gate | `security-secrets` → `make security-secrets` | — |
| S14 | qv-browser | Run the full E2E matrix (`make test-e2e`) in the daemon's isolated worktree stack | — |
| S15 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

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

All design files for this work item live under `ai-dev/active/F-00088/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00088_Feature_Design.md` | Design | This document |
| `F-00088_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/F-00088_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/F-00088_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/F-00088_S03_Backend_prompt.md` | Prompt | S03 implementation instructions |
| `prompts/F-00088_S04_CodeReview_prompt.md` | Prompt | S04 per-agent review instructions |
| `prompts/F-00088_S05_CodeReview_Final_prompt.md` | Prompt | S05 final cross-agent review instructions |
| `prompts/F-00088_S14_BrowserVerification_prompt.md` | Prompt | S14 browser verification instructions |
| `prompts/F-00088_S15_SelfAssess_prompt.md` | Prompt | S15 self-assessment instructions |

Reports are created during execution in `ai-dev/work/F-00088/reports/`.

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `tests/e2e/__init__.py` | Create | Package marker |
| `tests/e2e/conftest.py` | Create | E2E fixtures: base URL, wrapper instance, journey helpers, artifact dir |
| `tests/e2e/.gitignore` | Create | Ignores the `_artifacts/` journey-screenshot dir |
| `tests/e2e/playwright_wrapper.py` | Create | Thin subprocess wrapper around the `playwright-cli` binary |
| `tests/e2e/test_journey_home_navigation.py` | Create | Journey 1: dashboard home → project → cross-tab navigation |
| `tests/e2e/test_journey_queue_to_merge.py` | Create | Journey 2: Queue → Batch → run → merge |
| `tests/e2e/test_journey_code_qa_sse.py` | Create | Journey 3: Code Q&A SSE stream |
| `tests/e2e/test_journey_docs_export.py` | Create | Journey 4: HTML + PDF export round-trip |
| `tests/e2e/test_journey_jobs_filters.py` | Create | Journey 5: Jobs page multi-select filters |
| `tests/e2e/test_journey_htmx_fragments.py` | Create | Journey 6: htmx fragment browser runtime |
| `tests/e2e/test_harness_selfcheck.py` | Create | Unmarked unit tests proving the wrapper's failure detectors flag synthetic bad input (RED evidence) |
| `.github/workflows/e2e.yml` | Create | Two-job E2E CI workflow |
| `pyproject.toml` | Modify | `e2e` + `e2e_smoke` markers; `addopts` exclusion |
| `Makefile` | Modify | `test-e2e` + `test-e2e-smoke` targets, `.PHONY` |
| `scripts/e2e_seed.py` | Modify (if needed) | Extend seed data if a journey needs extra rows |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | Document E2E layer (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Note the E2E layer + how to extend it |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (`iw sync-skills --force iw-ai-core-testing`) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Mark item 3.1 DONE; §11 changelog entry |

## Acceptance Criteria

### AC1: The playwright-cli wrapper exists and uses the binary exclusively

```
Given the tests/e2e/ directory and playwright_wrapper.py are created
When the wrapper's helpers are inspected
Then all browser interactions are implemented via subprocess calls to
     the playwright-cli binary at ~/.local/bin/playwright-cli
And chromium.launch(), agent-browser, and npx playwright install
     are absent from the entire tests/e2e/ tree
And the wrapper exposes at minimum: open_url, goto, snapshot, click,
     fill, screenshot, read_console_errors, and accessibility_check
```

### AC2: Six journey modules exist, each asserting a11y and no console errors

```
Given the six journey modules under tests/e2e/ exist
When make test-e2e runs against a live E2E stack
Then each of the six journeys passes
And every journey asserts that an accessibility check passes on
     at least one page visited during the journey
And every journey asserts that zero browser console errors were
     observed on every page visited during the journey
```

### AC3: The e2e marker excludes the layer from the default suite and make test-integration

```
Given the e2e marker is registered in pyproject.toml and added to
      the addopts -m exclusion expression
When uv run pytest --collect-only -q runs (the default selection)
Then no e2e-marked journey test from tests/e2e/ is collected
     (the unmarked harness self-check unit tests ARE collected — intended:
      they are fast and need no stack)
When make test-integration runs
Then no e2e-marked journey test from tests/e2e/ is collected
```

### AC4: make test-e2e and make test-e2e-smoke run the correct subsets

```
Given the two Makefile targets exist and are in .PHONY
When make test-e2e runs
Then all six journey modules are collected and executed
When make test-e2e-smoke runs
Then exactly the e2e_smoke-marked journeys are collected and executed
     (test_journey_home_navigation and test_journey_queue_to_merge)
```

### AC5: The e2e.yml workflow has a blocking smoke job and a nightly full job

```
Given .github/workflows/e2e.yml exists
When a pull_request or push event fires
Then the e2e-smoke job runs make test-e2e-smoke (blocking, no continue-on-error)
When the nightly cron fires or the workflow is dispatched manually
Then the e2e-full job runs make test-e2e with continue-on-error: true
And neither job triggers on the other's events
```

### AC6: The E2E layer targets the isolated stack and never the live DB

```
Given the tests/e2e/conftest.py reads the base URL from $IW_BROWSER_BASE_URL
When a journey runs
Then the E2E stack's PostgreSQL is the only DB the journey touches
And no connection to port 5433 is made
And running tests/e2e/ without IW_BROWSER_BASE_URL set causes every journey
     test to skip with a clear E2E_STACK_MISSING message — the skip is
     fixture-scoped (the harness self-check unit tests, which use no stack
     fixture, still run) rather than silently connecting to the live DB
```

### AC7: Docs, skill, and plan updated and synced

```
Given the E2E test layer now exists
When S03 completes
Then docs/IW_AI_Core_Testing_Strategy.md describes the E2E layer
     (§3 layers, §5 gate table, §9 gap rows — replaces the ad-hoc
     -m browser description)
And skills/iw-ai-core-testing/SKILL.md notes the E2E layer and
     how to extend it (a new journey, adding a route to the htmx sweep)
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical
     to its master (iw sync-skills --force iw-ai-core-testing was run)
And ai-dev/work/TESTS_ENHANCEMENT.md marks item 3.1 DONE with a
     §11 changelog entry
```

## Boundary Behavior

Define edge cases. **Every row becomes a mandatory test case.**

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Journey run with no seed data | E2E DB is empty (no project, no work items) | Journeys that need seed data skip via `pytest.skip` with `ENV_DATA_MISSING:` reason, never raising an uncaught exception |
| A journey hits a 5xx from the dashboard | A route returns HTTP 500 during journey execution | The journey fails with a clear assertion error naming the route; it is written as a failing reproduction, marked `xfail` with a `# NOTE` containing a `TODO(file-incident)` placeholder and a one-line rationale, listed as operator follow-up in the step report, and NOT fixed in-Feature; the operator files the Incident on `main` post-merge |
| Console error present on any page | Browser console receives an error during page load or user interaction | The journey fails at the `assert_no_console_errors()` call; the error text is included in the failure message |
| `IW_BROWSER_BASE_URL` env var is unset | A journey requests the `base_url`/`pw` fixture | Every journey test skips with a clear message (`E2E_STACK_MISSING: IW_BROWSER_BASE_URL is not set`); the skip is fixture-scoped so the harness self-check unit tests still run |
| `playwright-cli` binary is absent | `~/.local/bin/playwright-cli` does not exist | The wrapper raises a clear `RuntimeError` at import time, not a cryptic `FileNotFoundError` at first call |
| A journey's htmx fragment has a dangling `hx-target` | A rendered page references a DOM id that does not exist in the same HTML response | `test_journey_htmx_fragments` detects and fails on the dangling reference |
| The SSE stream in Code Q&A never emits a first chunk | Server sends no data within the stream timeout | `test_journey_code_qa_sse` fails with a timeout assertion, not a hang |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. The E2E layer never connects to port 5433 — all database I/O in journeys goes through the isolated E2E stack.
2. Every journey asserts zero browser console errors at every page visited during the journey.
3. Every journey asserts that an accessibility check passes on at least one page visited.
4. The default `pytest` run never collects an `e2e`-marked test (verified via `--collect-only`).
5. `make test-integration` never collects an `e2e`-marked test.
6. The `playwright-cli` binary is the only browser automation mechanism used anywhere in `tests/e2e/` — no direct Playwright API calls.
7. If a journey surfaces a genuine dashboard bug, the journey is written as a failing reproduction and marked `xfail` with a `# NOTE` containing a `TODO(file-incident)` placeholder and a one-line rationale; the finding is listed under an "Operator follow-up" heading in the step report so the operator files the Incident on `main` post-merge. The bug is never fixed inside F-00088, and no `ai-dev/active/I-NNNNN/` package is created from the worktree.
8. The `e2e_smoke` subset consists of exactly two journeys: `test_journey_home_navigation` and `test_journey_queue_to_merge`.

## Dependencies

- **Depends on**: None functionally. The `pgtestdbpy` per-test DB isolation (CR-00055) and the existing E2E stack mechanism (`docker-compose.e2e.yml` / `scripts/e2e_up.sh`) are already on `main` and are relied upon, but no in-flight item is required.
- **Shared-file serialization**: F-00088 modifies `pyproject.toml`, `Makefile`, `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, and `ai-dev/work/TESTS_ENHANCEMENT.md`, which are ALSO modified by CR-00072, CR-00073, CR-00074, CR-00075, and CR-00076 (the Phase 3 testing CRs). F-00088 therefore **must NOT run in the same parallel batch** as those CRs — the batch executor must serialize them.
- **Blocks**: None.

## Impacted Paths

- `tests/e2e/**`
- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `scripts/e2e_seed.py`
- `.github/workflows/e2e.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is a test-infrastructure Feature — the six journeys ARE the deliverable. Classic RED-GREEN does not apply to browser journeys. The "every test must be able to fail" requirement is satisfied **entirely within `tests/e2e/**`** — no production code is edited, at design time or at runtime.

- **Harness self-check unit tests (S01 + S03 — the runnable RED evidence)**: The wrapper's failure-detection logic — console-error parsing, the accessibility check, the dangling-`hx-target` detector, and the SSE-timeout detector — are pure functions over in-memory input. S01 creates `tests/e2e/test_harness_selfcheck.py` (**unmarked** — no `e2e` marker) with unit tests that feed each function **synthetic bad input** (a console log containing an `error` line; a snapshot with no landmark region; an HTML fragment with `hx-target="#missing"`; a stream source that emits no chunk) and assert it flags the failure. These are written RED-first, need no browser or E2E stack, and are run directly in S01/S03 via `uv run pytest tests/e2e/test_harness_selfcheck.py -v`. The RED run (test failing before the helper is implemented) is recorded as `tdd_red_evidence`. S03 extends this module as it adds the dangling-reference and SSE-timeout detectors.
- **Journey assertion-inversion (in-scope, confirmed at S14)**: Each journey can be shown to fail by temporarily inverting one of its own behavioural assertions **in its own `tests/e2e/test_journey_*.py` file** to a known-false expectation, then reverting. Because S01/S03 have no live E2E stack, the RED run of an inverted journey assertion is confirmed at S14 (where the stack is up); each journey module documents — in a one-line comment — which assertion to invert for this check.
- **Production code is never touched.** Injecting `raise`/`console.error` into `dashboard/` handlers or templates is out of `scope.allowed_paths`, would trip the merge-time scope gate, and is forbidden — including "temporary" edits that are reverted. The fail-detection machinery is proven against synthetic input instead.
- **Unit tests**: `tests/e2e/test_harness_selfcheck.py` (above) — the only pure logic in this Feature.
- **Integration tests**: none in the classical sense — the journeys require a live browser and the E2E stack; they are collected and run via `make test-e2e` / `make test-e2e-smoke`, not `make test-integration`.
- **Updated tests**: none — no existing test changes behaviour. The existing `tests/dashboard/browser/` modules are untouched.

## Notes

- **Journey 1 scope — no authentication**: The IW AI Core dashboard has no login/auth (verified: no auth routes or middleware in `dashboard/app.py`, no login templates, no `e2e_user`/`e2e_password` in `projects.toml`). Journey 1 (`test_journey_home_navigation`) verifies the dashboard home → project → cross-tab navigation path, not an auth/session boundary. It stays in the `e2e_smoke` blocking subset as a fast, critical-path check. `IW_BROWSER_E2E_USER` / `IW_BROWSER_E2E_PASSWORD` are NOT set for this project and no journey reads them.
- **Relationship to CR-00072 (`test_journey_htmx_fragments`)**: CR-00072 sweeps every dashboard route via a `TestClient` to assert no 5xx — a server-side check with no JS or HTMX runtime. `test_journey_htmx_fragments` is the browser-level complement: it exercises the same routes in a real browser and asserts that htmx attributes resolve correctly, no client-side errors occur, and no dangling `hx-target` references exist. These two checks are **complementary, not redundant** — CR-00072 has no JS/HTMX runtime; this journey does.
- **Relationship to existing `-m browser` tests**: F-00088 adds the new structured layer alongside the existing `tests/dashboard/browser/` ad-hoc tests. Those tests are NOT deleted or modified. They remain collected only when explicitly run with `-m browser`. Migrating or retiring them is explicitly Out of Scope.
- **Risk — SSE journey timing**: `test_journey_code_qa_sse` may be sensitive to the speed of the in-stack Ollama stub. If the stub is slow the journey should fail with a clear timeout assertion, never hang. The wrapper's accessibility helper must respect a configurable timeout.
- **Risk — `make test-e2e-smoke` as blocking CI gate**: The `e2e-smoke` job in `e2e.yml` is blocking. If the E2E stack is flaky, every PR is blocked. The implementer should ensure the `e2e_smoke` journeys are as deterministic as possible — seeded data only, no real LLM calls.
- **`e2e_smoke` is a subset of `e2e`**: Excluding `e2e` from the default `addopts` covers `e2e_smoke` automatically — no need to separately exclude `e2e_smoke`. The `make test-e2e-smoke` target selects the smoke subset via `-m e2e_smoke`.
- **No new canonical QV gate**: F-00088 introduces S14 as a `qv-browser` step (not a `qv-gate` step). The canonical QV gate list in `skills/iw-workflow/SKILL.md` is NOT modified — qv-browser steps are a separate agent class.
