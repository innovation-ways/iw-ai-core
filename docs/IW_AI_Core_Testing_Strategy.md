# IW AI Core — Testing Strategy

**Last updated**: 2026-05-26

This document is the single reference for *how IW AI Core is tested* — the layers, the infrastructure, the conventions, the quality gates, and the known gaps. It is **descriptive of the current state** plus a pointer to where we're heading.

- **The enhancement plan** (what we're improving, in phases, with status): [`ai-dev/work/TESTS_ENHANCEMENT.md`](../ai-dev/work/TESTS_ENHANCEMENT.md)
- **The research behind the plan**: [`docs/research/R-00068-ai-core-test-quality-strategy.md`](research/R-00068-ai-core-test-quality-strategy.md)
- **The agent-facing testing skill** (rules for writing/reviewing tests): [`skills/iw-ai-core-testing/SKILL.md`](../skills/iw-ai-core-testing/SKILL.md)
- **Test-suite conventions and gotchas**: [`tests/CLAUDE.md`](../tests/CLAUDE.md)

---

## 1. Philosophy — why this document exists

**Nearly all of IW AI Core's production *and* test code is written by LLM agents** (`backend-impl` does TDD; `tests-impl` adds coverage; `tests-review` reviews it). That changes what testing has to defend against:

- AI-generated tests routinely **pass while asserting nothing meaningful** — `assert result is not None`, `assert isinstance(x, dict)`, asserting only on their own mocks, or restating the implementation. Such tests pass today, pass after a regression is introduced, and pass forever.
- **The same agent often writes both the implementation and its tests**, so a test can encode "what the code does" rather than "what it should do" (the oracle problem).
- AI will happily generate **thousands of redundant or vacuous tests** if nothing constrains it.

So our metrics and gates are chosen accordingly:

| Principle | Consequence |
|-----------|-------------|
| Coverage is a *floor on what's exercised*, not a measure of quality. | Coverage alone is never the only gate. We pair it with structural checks (and, per the roadmap, mutation testing). The `fail_under` floor is set just below measured branch coverage and **ratchets up over time, never down** (CR-00047); a `diff-coverage` gate additionally requires new/changed lines to be well-covered (see §5). |
| Every test must be able to fail. | If deleting the corresponding production line wouldn't fail the test, the test is worthless — remove it or strengthen it. |
| Tests assert on **behaviour**, not on their own mocks. | A test whose only assertion is `mock.assert_called_*` is a red flag. |
| Write the test first; confirm it fails before implementing. | `backend-impl` follows RED-GREEN-REFACTOR; the RED run is recorded (see §6). |
| Keep the pyramid. | AI lets us afford a slightly fatter integration band, but the browser/E2E layer stays thin and curated; the bulk of behaviour is pinned by integration tests against the testcontainer DB. |
| Cheap blocking gates on every PR; expensive checks run periodically and alert on regression. | Lint/format/typecheck/unit/integration/coverage/migration block; deep audits (mutation, full security, perf) run nightly/on-demand. |

---

## 2. Test layers (current state)

IW AI Core today has **ten test layers**, all pytest-based except the browser layer which drives a real Chromium via `playwright-cli`.

```
Layer 10: Performance budgets (pytest)    — Wall-clock latency vs committed baselines (CR-00083)
Layer 9:  Daemon chaos (pytest)           — Deterministic daemon fault-injection (5 failure modes)
Layer 8:  Visual regression              — Pixel diffs for rendered HTML docs + PDF exports
Layer 7:  Cross-project isolation matrix  — Two-project seed proves project-scoped surfaces don't leak
Layer 6:  Contract tests (pytest)         — No-5xx route sweep + schemathesis OpenAPI fuzz
Layer 5:  Security tests (pytest)         — Live-DB guard regression, authz negatives,
                                                 SSRF/path-traversal, agent-context env-var
Layer 4:  Browser tests (playwright-cli)  — Real Chromium against a live Uvicorn dashboard
Layer 3:  Dashboard tests (TestClient)    — FastAPI routes/templates/htmx against testcontainer DB
Layer 2:  Integration tests (pytest)      — Models, daemon, CLI, RAG, DB behaviour against testcontainer DB
Layer 1:  Unit tests (pytest)             — Config, state-machine logic, parsers, CLI parsing, pure functions
Static:   Quality gates (ruff, mypy…)     — Enforced by `make quality` / `make check`
```

### Test inventory

| Layer | ~Tests | ~Files | Framework | Location | Execution |
|-------|-------:|-------:|-----------|----------|-----------|
| Unit | ~2,260 | 175 | pytest | `tests/unit/` | `make test-unit` |
| Integration | ~1,510 | 169 | pytest + testcontainers[postgres] | `tests/integration/` | `make test-integration` (also runs `tests/dashboard/`) |
| Dashboard | ~650 | 69 | pytest + FastAPI `TestClient` + `db_session` | `tests/dashboard/` (excl. `browser/`) | part of `make test-integration`; fast slice via `make test-dashboard` |
| **Security** | ~85 | 4 | pytest + testcontainers + subprocess | `tests/integration/security/` | `make test-security-module` (also part of `make test-integration`) |
| **E2E browser journeys** | 6 journeys | 7 modules | pytest + `playwright-cli` + isolated E2E stack | `tests/e2e/` | `make test-e2e` (all 6); `make test-e2e-smoke` (2 smoke journeys); CI: `.github/workflows/e2e.yml` |
| Browser | small | 7 | pytest + `playwright-cli` + live Uvicorn | `tests/dashboard/browser/` | `make test-browser` (not in `make test`); also the `qv-browser` workflow step |
| **Total** | **~4,470+** | **417** | | | `make test` = unit + integration (+ dashboard + security) |

(Counts are approximate — `def test_*` occurrences and `test_*.py` file counts as of 2026-05-21. Keep this row roughly current; it does not need to be exact.)

### Layer 1 — Unit tests (`tests/unit/`)

Fast, no I/O, no containers. Cover: `orch/config.py` resolution; state-machine and lifecycle logic; parsers and diffing (`orch/doc_diff.py`, `orch/doc_sections.py`); `iw` CLI argument parsing; `orch/rag/` chunking and ranking helpers; `orch/staleness/`; pure functions extracted from routers/daemon. Subdirectories mirror the package (`tests/unit/daemon/`, `tests/unit/db/`, `tests/unit/rag/`, `tests/unit/executor/`, `tests/unit/staleness/`, `tests/unit/dashboard/`, `tests/unit/orch_config/`).

`tests/unit/conftest.py` provides a `MagicMock`-based `db_session` for unit tests that need to *mock* DB calls, and re-exports `db_engine` / `pg_container` / `test_project` from the integration conftest for the rare unit test that needs a real container. **A pure function from a router module must not be unit-tested by importing `dashboard.routers.*`** — see §3 and `tests/CLAUDE.md`.

### Layer 2 — Integration tests (`tests/integration/`)

Real PostgreSQL via `testcontainers[postgres]` — never the live DB. Cover: ORM models and constraints; the daemon loop and state transitions (`tests/integration/daemon/`); the `iw` CLI end-to-end against a real DB (`tests/integration/cli/`); RAG/code-index pipeline (`tests/integration/rag/` — some tests skip when no local Ollama listener, see the conftest hook); DB behaviour including `SELECT FOR UPDATE` locking (which is *why* the DB is never mocked here); migration round-trips (`tests/integration/test_migrations_round_trip.py`, also runnable via `make migration-check`); evidence ingestion; doc service/versioning. The `tests/integration/dashboard/` and `tests/integration/api/` subdirs hold heavier DB-backed dashboard/API flows.

> **Sub-package — `tests/integration/data_layer/` (CR-00076).** A consolidated data-layer package holds three focused modules: `test_fts_trigger_invariant.py` (every `tsvector` column — `work_items.design_doc_search`, `work_items.functional_doc_search`, `project_docs.content_search` — is populated and refreshed by its FTS trigger, parametrized one case per column), `test_migration_revision_skew.py` (reproduces and pins the I-00075/I-00076 revision-skew failure: `alembic upgrade head` against a DB whose `alembic_version` names a revision absent from the migration graph must raise `CommandError: Can't locate revision identified by`), and `test_db_identity_invariants.py` (the match / mismatch / bootstrap / missing-row paths of `orch/db/identity.py`). It **extends — does not replace** — `test_migrations_round_trip.py`, `test_work_items_functional_doc_fts.py`, and `test_db_identity_integration.py`. `make data-layer-check` runs `make migration-check` then this package.

> **Sub-layer — CLI contract layer (`tests/integration/cli/` + `test_cli_spec_conformance.py`, CR-00073).** The `iw` CLI is the agent-to-DB bridge; its exit-code / stdout / DB-effect contract is load-bearing. The CLI contract layer makes that contract a tested invariant. **Per-command contract tests** live in `tests/integration/cli/test_<command>_contract.py` — one test class per priority command (`step-done`, `register`, `doc-update`, `approve`, `next-id`, plus the evidence-ingestion hooks on `approve` / `step-done`). For each command they assert: exit code 0 on every documented success path; a non-zero exit + a clear stderr message on every documented error path; the documented stdout shape (parsed JSON or pattern-matched); the DB row(s) created or mutated, queried against the testcontainer `db_session`; and idempotence / atomicity where the spec promises it (`next-id` allocation is asserted unique under a `ThreadPoolExecutor` of concurrent callers; `register` re-registration is asserted to be a no-op). **Spec-conformance** is `tests/integration/test_cli_spec_conformance.py`: it parses the §4 "Command Summary" ASCII tree of `docs/IW_AI_Core_CLI_Spec.md`, introspects the live Click command tree from `orch.cli.main`, and asserts bidirectional coverage (every documented command exists; every registered command is documented) plus that every documented command has a contract test. Two module-level allowlists make the gate a *ratchet*: `KNOWN_SPEC_DRIFT` (existence drift) and `KNOWN_UNTESTED_COMMANDS` (the pre-existing coverage gap — pre-seeded with every non-priority command). A genuine CLI bug surfaced by a contract test is `xfail`-ed with a filed Incident ID, never fixed in the test CR. `make test-cli-contract` runs the layer; it is also collected by `make test-integration`. See §5 for the gate-table entry.

### Layer 3 — Dashboard tests (`tests/dashboard/`)

FastAPI behaviour via `TestClient` with the testcontainer `db_session` injected through `app.dependency_overrides[get_db]` (see `tests/dashboard/conftest.py` and the pattern in `tests/dashboard/test_jobs_filter_ui.py`). Cover: route status/redirects/shapes; Jinja2 template rendering; htmx fragment swaps; SSE wiring (`test_code_qa_sse_wire`); chat panel a11y/security/templates; the alembic-guard banner; coverage page; staleness router; project onboarding; runtime overrides; session isolation (`test_F00077_session_isolation`). Run as part of `make test-integration`; `make test-dashboard` is a fast `--no-cov` slice for local iteration.

### Layer 4 — E2E browser journey tests (`tests/e2e/` — F-00088, 2026-05-21)

Six structured journey modules under `tests/e2e/` drive a real Chromium via **`playwright-cli` only** (never `agent-browser`, never `chromium.launch()`, never `npx playwright install` — see the root `CLAUDE.md`):

| Journey | What it exercises |
|---------|------------------|
| `test_journey_home_navigation.py` | Dashboard home → project → cross-tab navigation |
| `test_journey_queue_to_merge.py` | Queue → batch creation → batch detail |
| `test_journey_code_qa_sse.py` | Code Q&A SSE stream renders with citations |
| `test_journey_docs_export.py` | Docs HTML and PDF export round-trip |
| `test_journey_jobs_filters.py` | Jobs page multi-select filters |
| `test_journey_htmx_fragments.py` | htmx browser runtime: no dangling hx-target, no console errors |

**Markers:**
- `@pytest.mark.e2e` — all six; excluded from default `pytest` selection (`addopts`)
- `@pytest.mark.e2e_smoke` — `home_navigation` + `queue_to_merge`; **blocking** on `pull_request` / `push` via `.github/workflows/e2e.yml`

**Execution:** `make test-e2e` (all 6), `make test-e2e-smoke` (2 smoke journeys), CI workflow `.github/workflows/e2e.yml`.

**Journey conventions:** every journey asserts `pw.assert_accessibility()` on ≥1 page and `pw.assert_no_console_errors()` throughout; screenshots go to `IW_E2E_EVIDENCE_DIR` (`tests/e2e/_artifacts/`); navigation is via the UI, not hardcoded URLs; seed via `scripts/e2e_seed.py`.

**Relationship to CR-00072:** Journey 6 (`test_journey_htmx_fragments.py`) is the browser-level complement to `test_route_contract_sweep.py` — CR-00072 asserts no 5xx server-side with no JS runtime; Journey 6 asserts htmx attributes resolve, no client-side errors, and no dangling `hx-target` references in a real browser. Complementary, not redundant.

**Adding a new journey:** create `tests/e2e/test_journey_<name>.py`, mark `@pytest.mark.e2e`, assert `pw.assert_accessibility()` and `pw.assert_no_console_errors()` on at least one page, add a one-line comment naming the single assertion whose inversion proves the journey can fail. Extend `scripts/e2e_seed.py` idempotently if needed. Promote to `e2e_smoke` only if ≤30 s, covers a critical path, and there are ≤2 total in smoke.

### Layer 5 — Security tests (`tests/integration/security/` — CR-00075)

Real Chromium via **`playwright-cli` only** (never `agent-browser`, never `chromium.launch()` directly, never `npx playwright install`, never modify `.playwright/cli.config.json` — see the root `CLAUDE.md`). Marked `@pytest.mark.browser` and **deselected by default** (`addopts` has `-m 'not browser'`); run with `make test-browser` against a live Uvicorn dashboard the test data is visible to. The workflow's `qv-browser` step also exercises browser-level verification per work item, capturing screenshots into `ai-dev/active/<ITEM>/evidences/post/`.

> **Not yet a layer**: there is no structured browser/E2E *journey* suite (auth/session, queue→batch→merge, Docs export) and no isolated E2E compose stack — that's roadmap item 3.1. The current browser tests are a handful of smoke checks.

### Layer 5 — Security tests (`tests/integration/security/` — CR-00075)

Asserted regression tests for four distinct security risk classes, all against the testcontainer DB:

| Module | Target risk class | Entry point tested |
|--------|-------------------|-------------------|
| `test_live_db_write_guard.py` | Live-DB write guard regression (I-00041 class) | `orch/db/live_db_guard.py`: `is_live_db_url()`, `assert_engine_url_allowed()`, `safe_create_engine()` |
| `test_authz_negative_paths.py` | Authorization negative paths (project-scoping boundary) | Dashboard routes: items, batches, docs, jobs, code-QA, and chat tab/runtime guards |
| `test_doc_render_ssrf_path_traversal.py` | SSRF and path-traversal in doc rendering | `orch/doc_service.py`: `DocService.validate_links()`, `DocService._is_ssrf_blocked()`; `orch/doc_sections.py`: pure string functions |
| `test_agent_context_env_handling.py` | Agent-context env-var bypass | `orch/db/live_db_guard.py`: `IW_CORE_AGENT_CONTEXT` guard; CLI `iw migrations apply` with agent context |

**Execution**: `make test-security-module` (the primary convenience target); also run automatically as part of `make test-integration` via the `tests/integration/` collection. The `test-security-module` Makefile target runs **only** the security regression tests and is explicitly distinct from `make security-secrets` (gitleaks — scanner, advisory output) and `make security-sast` (Semgrep/bandit — scanner, advisory output). See §5 for the gate-table entry.

**Genuine vulnerability handling**: if a test surfaces a real SSRF, path-traversal, or a guard that does not fire, the test is written as the **failing reproduction**, marked `@pytest.mark.xfail(strict=False, reason="I-NNNNN: <one-liner>")`, and a high-priority Incident is filed. No production code is edited within the CR scope — the fix is a separate Incident. `scope.allowed_paths` enforces this at merge time.

**No real network I/O**: SSRF/path-traversal tests mock `httpx` and assert the mock is never called with an internal URL. No test reaches the live DB (port 5433).

> **Extending the security module**: add a new module under `tests/integration/security/` for each new security risk class. Do not fix vulnerabilities within the same CR — file an Incident and xfail the test instead. Run `make test-security-module` to verify the new module, then `iw sync-skills --force iw-ai-core-testing` to update the skill.

### Layer 6 — Contract tests (`tests/dashboard/test_route_contract_sweep.py`, `test_schemathesis_contract.py` — CR-00072)

Two contract-level modules that prove the dashboard's HTTP surface as a whole, rather than one targeted behaviour at a time:

| Module | What it does | Execution |
|--------|--------------|-----------|
| `test_route_contract_sweep.py` | Enumerates every route on `create_app()`; for every GET/HEAD route (minus a documented skip set — SSE/streaming, the static mount, FastAPI's OpenAPI/Swagger endpoints, the AI-runtime-gated chat endpoints) it issues a request against a seeded testcontainer `TestClient` (`raise_server_exceptions=False`) and asserts `status_code < 500`. Parametrized one case per route. Path parameters resolve from seeded data; an `UNRESOLVED` list is asserted against an explicitly-reviewed set; genuine pre-existing 5xx are recorded in an `EXPECTED_5XX` xfail allowlist. | **Blocking** — runs inside `make test-integration` (it lives under `tests/dashboard/`); convenience target `make test-route-sweep`. |
| `test_schemathesis_contract.py` | schemathesis property-fuzzes the JSON API operations (keep-alive API + runtime-overrides) against the OpenAPI schema, asserting `not_a_server_error` on every generated case. Marked `contract_fuzz`. | **Periodic** — excluded from the default selection (`addopts -m 'not … and not contract_fuzz'`); runs via `make test-contract-fuzz` and the nightly `.github/workflows/contract-fuzz.yml` (`continue-on-error` burn-in). |

The sweep introduces **no new canonical QV gate** — it is collected by the existing `integration-tests` gate. A newly-added route is swept automatically; a newly-added JSON endpoint should be considered for the schemathesis `JSON_API_PATHS` allow-list.

**Genuine pre-existing 5xx handling**: a real handler bug the sweep surfaces is recorded in `EXPECTED_5XX` (route sweep) or `KNOWN_CONTRACT_5XX` (schemathesis) with a `TODO(file-incident)` rationale, the case is `xfail`-ed / excluded, and the bug is surfaced as operator follow-up in the step report — the operator files the Incident on `main` post-merge. CR-00072 never edits production code.

### Layer 7 — Cross-project isolation matrix (`tests/integration/test_cross_project_isolation.py` — CR-00074)

Multi-project tenancy is the platform's core correctness axis: project B must never see project A's data on any project-scoped surface, and the global aggregation surfaces must span every project. The isolation matrix seeds **two** projects (the `second_project` fixture in `tests/integration/conftest.py`, backed by `tests/fixtures/dual_project_seed.py`) and runs a parametrized suite across four axes:

| Axis | Asserts |
|------|---------|
| 1 — dashboard-route isolation | every project-scoped list/index route, scoped to project B, renders B's own identifier and **none** of project A's |
| 2 — `iw`-command isolation | read commands scoped to B leak no A identifiers in their output; mutating commands leave A's rows byte-for-byte unchanged while changing B's |
| 3 — global-aggregation positive assertion | the global `/docs` surfaces aggregate **both** projects (isolation must not over-filter) |
| 4 — per-worktree-DB vs orch-DB boundary (F-00062) | `orch/config.get_db_url()` / `get_orch_db_url()` resolve `IW_CORE_DB_*` / `IW_CORE_ORCH_DB_*` to distinct databases, including the `_prefer` fallback |

A module-level **`KNOWN_LEAK`** allowlist (keyed by route path / command label) absorbs any *genuine* pre-existing leak: each entry carries a filed high-priority Incident ID and `xfail`s that case (`strict=True`). A real leak is fixed in a separate Incident — the CR stays strictly test-only. `KNOWN_LEAK` is currently empty (no genuine leaks on `main`).

**Execution**: `make test-isolation` (convenience target — runs only the matrix); also runs as part of `make test-integration` via the `tests/integration/` collection — no new daemon QV gate.

> **Extending the matrix**: a new project-scoped dashboard route or `iw` command should be added as a parametrized case (Axis 1 / Axis 2). Genuine leaks → `KNOWN_LEAK` entry + filed Incident, never an in-CR production fix.

### Layer 8 — Visual regression (`tests/visual/`)

Visual regression covers **rendered HTML document views and PDF exports**.

- **Run command**: `make visual-regression`
- **Committed baselines**: `tests/visual/baselines/`
- **Failure artefacts**: pixel-diff images under `tests/output/visual-diff/*-diff.png`

The layer compares fresh renders with committed baselines (4 PDF + 4 HTML in CR-00082) to catch CSS/template regressions that functional assertions miss.

This layer is **CI-only** (nightly + path-filtered PR/manual runs) and is **not** part of the daemon QV merge gate because of wall-clock cost.

### Layer 9 — Daemon chaos (`tests/integration/daemon_chaos/` — F-00089)

Deterministic fault-injection integration layer for the daemon poll loop, covering the five documented recovery/failure modes: worktree setup failure after clone, fix-cycle cap exhaustion, agent stall recovery, squash-merge conflict, and migration-rebase failure. This layer is **test-only** (no production daemon changes) and exists to verify daemon state/event mutations under controlled failures.

**Execution:** `make daemon-chaos-smoke` (blocking smoke subset: S02 + S03) and `make daemon-chaos-full` (full matrix, nightly/workflow-dispatch).

**Back-reference:** delivered by **F-00089**.

### Layer 10 — Performance budgets (`tests/perf/` — CR-00083, 2026-05-24)

Three modules under `tests/perf/` measure wall-clock latency against committed baselines:

- `test_daemon_poll_loop.py` — one `Daemon._poll_cycle()` iteration against a seeded testcontainer DB.
- `test_rag_query.py` — one `CodeQA.answer_stream` invocation against an in-memory LanceDB fixture with a deterministic stub embedding (no Ollama dependency — opposite stance to `tests/integration/rag/`'s skip hook).
- `test_dashboard_routes.py` — p50 over ≥10 runs (parametrized) for `/`, `/project/{id}/queue`, `/project/{id}/batches`, `/project/{id}/jobs`, `/project/{id}/code`.

**Budget methodology**: each module declares a module-level constant set to `initial_measurement × 1.5` (50% headroom). Default to `mean`; switch to `min` only when initial σ/μ > 0.3 (record the ratio in the module docstring). The pytest-benchmark `--benchmark-compare-fail=mean:25%` regression threshold is the START value — operators may ratchet it down as baselines stabilise, NEVER silently relax it.

**Baseline-update policy**: baselines live under `tests/perf/baselines/` and are committed. `make test-perf-update-baseline` regenerates them locally; committing the regenerated baselines requires a CR review (no automated baseline updates from CI). This prevents a regression from being silently absorbed into the new baseline.

**Run targets**: `make test-perf-daemon` / `make test-perf-rag` / `make test-perf-routes` for individual modules; `make test-perf` for the umbrella. Excluded from `make test-unit` / `make test-integration` via the `perf` marker + `addopts` filter.

**CI surface**: nightly only via `.github/workflows/perf-budgets.yml` (`schedule` + `workflow_dispatch`); NOT on PR per intake (runner variance makes per-PR perf measurement too noisy). On regression, the workflow appends a follow-up entry to this tracker.


## E2E browser-verification stack

### E2E OpenCode stub (CR-00054)

The chat features in F-00083 introduced a managed `opencode serve` subprocess that the production daemon spawns on the dashboard host. The per-worktree e2e stack does **not** install the real `opencode` binary because it would balloon the image with ~100 MB and an LLM-provider config the stack does not own. Instead the e2e image ships a thin shim at `/usr/local/bin/opencode` that execs a Python stub server (`scripts/e2e_opencode_stub.py`) implementing opencode v1.15.0's HTTP+SSE wire protocol.

The pattern mirrors the existing `e2e-ollama` stub: a focused, deterministic in-process server that replaces a heavier runtime for browser_verification.

**Surface implemented**

| Path | Behaviour |
|------|-----------|
| `GET /global/health` | Unauthenticated 200 (used by OpencodeRuntime's startup poll) |
| `GET /config` | Returns one stub model (`stub/echo`) + default model + default agent |
| `POST /session` · `GET /session` · `GET /session/{sid}` · `GET /session/{sid}/messages` | Process-local session CRUD |
| `POST /session/{sid}/prompt_async` | Emits a deterministic event sequence on `/event` (message → message → permission.asked → pause → message/idle) |
| `POST /session/{sid}/abort` | Emits `session.idle` with `aborted: true` |
| `POST /session/{sid}/permissions/{rid}` | Forwards the allow/deny response and emits a follow-up event |
| `GET /event` | Long-lived SSE; ring buffer (`deque(maxlen=256)`) supports `Last-Event-ID` replay |

**Auth**: HTTP Basic with username `opencode` and the per-startup `OPENCODE_SERVER_PASSWORD` env var, matching the real runtime.

**Determinism**: The stub's event sequence is a fixture, not a behaviour spec. Tests that need a richer agent surface (real tool calls reading files, multi-turn planning, etc.) must either extend the stub OR run against a real local `opencode serve` outside the e2e stack.

**Extending the stub**

When a new chat-related qv-browser step needs richer events:
1. Add the new event shape to `scripts/e2e_opencode_stub.py`'s synthetic sequence.
2. Add a matching integration test in `tests/integration/test_e2e_opencode_stub.py`.
3. Update this section's "Surface implemented" table.
4. If the wire-protocol bumps (opencode v1.16+, etc.), update both the stub and the host `opencode` binary's pinned version in the developer-docs README.

**Why a stub, not the real binary**: same trade-offs as the `e2e-ollama` stub — image size, build time, no LLM-provider config in CI, deterministic outputs for assertions.

---

## 3. Test infrastructure & isolation (NON-NEGOTIABLE)

### The live-DB write guard

IW AI Core's most important test-safety mechanism. `tests/conftest.py` arms it for the **entire session** using `os.environ` directly (not `monkeypatch`, so it persists into xdist workers, subprocesses, and testcontainers): it sets `IW_CORE_TEST_CONTEXT=true`, clears any leaked operator/daemon/agent opt-in flags, and **hijacks `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD`** to point at an unreachable address (127.0.0.1:1). Defense-in-depth: even if a code path bypasses every short-circuit, `get_db_url()` resolves to an unreachable URL and the connection fails immediately. Tests that use fixture-supplied URLs (the testcontainer's `db_engine.url`) are unaffected. Background: incident **I-00041** (a previous opt-out fixture caused a multi-hour dashboard outage) and **CR-00022 S17 R0**.

**Consequence**: never import `dashboard.routers.*` or `dashboard.dependencies` in a unit test without a testcontainer `db_session` in scope — those modules build `SessionLocal` on import via `orch.db.session.__getattr__` → `safe_create_engine()`, and the guard fires at *collection time* (`LiveDbConnectionRefusedError`) because the hijacked `IW_CORE_DB_*` makes any engine URL look "live". To unit-test a pure function from a router module: extract it to a DB-free utility module, or use the `db_session` + `app.dependency_overrides[get_db]` pattern.

### testcontainers Postgres

- `pg_container` — **session-scoped**, one PostgreSQL container per pytest run (~2 s startup).
- `db_engine` — **session-scoped**, schema created once via `Base.metadata.create_all()`, then the FTS DDL is applied (see below), reused across all tests.
- `db_session` — **function-scoped**, each test runs in a transaction that is **rolled back** at teardown. (No `test-` data-prefix cleanup convention — isolation is by transaction rollback.)
- `test_project` — **function-scoped**, a `Project` row inside the `db_session` transaction; tests that create work items/batches/docs must use this project's `id`.
- `cli_get_session` — a `get_session` factory yielding `db_session`, for CLI-command tests.

### pytest-randomly — test-order randomisation (CR-00055, 2026-05-16 — default-on)

`pytest-randomly` is **ON by default** (CR-00055, 2026-05-16). The integration + dashboard suite is robust to randomisation via per-test PostgreSQL template-clone (`pgtestdbpy>=0.0.1`): a session-scoped template database is migrated once; each test gets its own fresh clone (~25 ms via `CREATE DATABASE … TEMPLATE …` with WAL_LOG strategy override — ~10× faster than the library's default `FILE_COPY`); `IW_CORE_DB_*` env vars are monkeypatched per-test so `iw` CLI subprocesses inherit the isolated clone — closing the gap that defeated savepoint-only and per-module-TRUNCATE designs in CR-00049 (see `docs/research/R-00077-pytest-randomly-isolation-strategy.md`). 3 module-scoped `migrated_engine` tests are quarantined `@pytest.mark.xfail(strict=False)` as a carry-forward follow-up. Verified green across 4 reference seeds (12345 / 67890 / 11111 / 42424) in ~10–13 min wall-clock (≤ 12 min budget).

The per-run seed is printed at the top of every run:
```
Using --randomly-seed=<N>
```

**Reproduce a specific seed:**

```bash
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
  -p randomly --randomly-seed=<N> -q --no-cov
```

**If a test fails under random order but passes in fixed order**, it is **order-dependent** — a test isolation bug. Fix the leaking side effect or quarantine it with `@pytest.mark.order_dependent` (registered in `pyproject.toml`) + a tracking comment. A quarantined test that genuinely cannot pass under random order must also carry `@pytest.mark.xfail(strict=False, ...)` and a `# NOTE(P1-CR-C-followup-randomly):` tracking comment.

**Quarantine policy (from CR-00055):** The 3 historical `migrated_engine` quarantines — module-scoped engine tests in `test_db_identity_integration.py`, `test_pending_migration_log_migration.py`, and `test_i_00062_migration.py` — were resolved on 2026-06-15 (`P1-CR-C-followup-randomly-quarantine-cleanup`): each file's private module-scoped container/engine was replaced with the conftest function-scoped per-test `db_engine` clone, so every test gets an isolated at-head database. Two latent connection leaks (`migrated_engine.connect()` handed to a helper without a `with`) were fixed at the same time. The `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False)` markers and `# NOTE(P1-CR-C-followup-randomly):` comments were removed; verified green across the 4-seed sweep. New module-scoped engines shared across mutating tests should use the conftest `db_engine` rather than a private container.

**Earlier fallback (CR-00048):** `-p no:randomly` was in `addopts` from 2026-05-13 to 2026-05-16 after 5 fix cycles could not converge; superseded by CR-00055's per-test template-clone strategy.

Hard rules (full list in `tests/CLAUDE.md`):

1. **NEVER** connect to the live DB (port 5433) — all DB tests use testcontainers on random ports.
2. **NEVER** call `importlib.reload(orch.config)` — it re-runs `load_dotenv()`, restoring deleted env vars; use `monkeypatch.delenv()` only.
3. **NEVER** mock the database in integration tests — `SELECT FOR UPDATE` locking can't be tested with mocks.
4. **NEVER** run raw `docker` / `docker compose` / `docker-compose` from test code — the only allowed docker usage is via `testcontainers` fixtures (self-labelled under Ryuk, self-destruct). Don't stop/remove containers in teardown.
5. **NEVER** invoke `alembic` directly from test code outside the dedicated migration-round-trip test; there, downgrade to a *specific revision ID*, never `-1`.
6. **MUST** replace the psycopg2 URL from testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
7. **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` — the FTS trigger is raw SQL not captured by SQLAlchemy.
8. **CRITICAL**: `DaemonEvent.metadata` is `event_metadata` in Python (SQLAlchemy reserves `metadata`).

### Flaky/quarantine workflow (CR-00061, P2-CR-C)

A test is quarantined when it intermittently fails for a reason that hasn't been root-caused, or when it requires a specific test ordering that hasn't been fixed. **Quarantining a test is not free**: it removes the test's signal from the merge gate, so the bug it was guarding for can land unnoticed. Three surfaces exist:

1. **Merge gate deselection** — `addopts` in `pyproject.toml` contains `-m 'not browser and not quarantine'`; `--strict-markers` ensures the marker must be registered. Quarantined tests are **never run** in `make test-unit` / `make test-integration` unless `-m quarantine` is explicitly passed.

2. **`make test-quarantine`** — runs *only* quarantined tests with `pytest --reruns 1`. The single retry lets a genuinely-flaky test recover in a given run without masking the flake signal. **Recovery signal**: a quarantined test that passes `make test-quarantine` for **3 consecutive runs** (or 7 calendar days, whichever is longer) can have its marker removed.

3. **`make test-flake-detect`** — runs the **full suite 3×** and aggregates per-test outcomes; any test that disagreed across runs (some PASSED, some FAILED) is a flake. Operator-on-demand or nightly cron. Uses `pytest-rerunfailures` as a **detector**, never as an auto-fix on the merge path.

**The quarantine-requires-incident rule** (enforced in `tests/CLAUDE.md`):

Adding `@pytest.mark.quarantine` to a test requires:
1. Filing an Incident via `/iw-new-incident` before adding the marker.
2. The marker `reason` must be of the form `"I-NNNNN: <one-liner — suspected cause + date>"`.
3. The Incident's description must name the test(s) verbatim.
4. Removal: 3 consecutive `make test-quarantine` passes (or 7 days), whichever is longer.

The `quarantine` marker is the **general-purpose** flavour. `@pytest.mark.order_dependent` (CR-00055's existing narrower flavour for module-scoped `migrated_engine` issues) coexists: both are excluded from the merge gate; new entries default to `quarantine`.

### Per-worktree DB vs testcontainers

F-00062 introduced a per-worktree Postgres container for *app runtime* (started by the daemon when a project ships `ai-dev/iw-config/`). This is **separate** from `make test-integration`'s testcontainers. Tests must never assume the per-worktree DB exists — they spin up their own testcontainer. The agent's `IW_CORE_DB_*` env vars point at the per-worktree DB; `IW_CORE_ORCH_DB_*` always points at the global orch DB on 5433.

### Property-based tests (Hypothesis — CR-00060, P2-CR-B)

Five property-test modules under `tests/unit/properties/` exercise the core state machines via **Hypothesis** (property-based testing):

| Module | Target | Strategy |
|--------|--------|----------|
| `test_work_item_lifecycle_properties.py` | WorkItem lifecycle | `RuleBasedStateMachine` + 4 invariants |
| `test_batch_lifecycle_properties.py` | Batch status computation | `@given` pure-function properties |
| `test_fix_cycle_cap_properties.py` | Fix-cycle cap enforcement | `RuleBasedStateMachine` + cap invariant |
| `test_doc_diff_round_trip_properties.py` | Doc diff round-trip | `@given` parse/serialise invariants |
| `test_iw_next_id_atomicity_properties.py` | `allocate_next_id` atomicity | `RuleBasedStateMachine` + `ThreadPoolExecutor` |

**Profiles** — selected via `$IW_HYPOTHESIS_PROFILE`:

| Profile | `max_examples` | `deadline` | `derandomize` | Use |
|---------|---------------|------------|---------------|-----|
| `ci` | 20 | 2000 ms | `True` | Merge-gate default (runs as part of `make test-unit`) |
| `dev` | 200 | 5000 ms | `False` | Local development default |
| `deep` | 1000 | `None` | `False` | On-demand deep sweep (`make test-properties-deep`) |

The **`ci` profile is the merge-gate** — `derandomize=True` makes it deterministic (same seed every run); wall-clock budget is <30 s for all 5 modules combined.

The `properties` marker is **auto-applied** to every test in `tests/unit/properties/` via a `pytest_collection_modifyitems` hook in `tests/unit/properties/conftest.py` — no per-test decorator needed. The marker is registered in `pyproject.toml` `[tool.pytest.ini_options].markers`.

### Markers (`pyproject.toml`)

| Marker | Meaning |
|--------|---------|
| `integration` | requires docker/testcontainer (most `tests/integration/` rely on the dir, not the marker) |
| `smoke` | fast critical-path tests; <=15 tests, <60s wall-clock, 5 critical paths; SLA documented in `tests/CLAUDE.md` (CR-00052, 2026-05-14); run via `make smoke` |
| `slow` | deselected by default unless `-m slow` is passed |
| `browser` | drives real Chromium via `playwright-cli`; **deselected by default** (`addopts` `-m 'not browser'`); run via `make test-browser` |
| `order_dependent` | test relies on test execution order; tracked for cleanup in P1-CR-C-followup |
| `quarantine` | test intermittently failing or order-dependent without root cause; excluded from merge gate; tracked via Incident (ID in marker's `reason`); recovery = 3 consecutive `make test-quarantine` passes or 7 days (CR-00061, P2-CR-C) |
| `--strict-markers` | **default in `addopts`** — any unregistered/typo'd marker raises an error at collection time |

> `--strict-markers` is enabled by default (`pyproject.toml` `addopts`). All markers above are registered. Any new marker must be added to the `markers` list in `pyproject.toml` before use.

---

## 4. Conventions

- **AAA** — Arrange / Act / Assert, clearly separated, in every test. No logic in the Assert block (no loops, no conditionals).
- **Naming** — `test_<unit>_<scenario>_<expected_result>` (e.g. `test_next_id_with_concurrent_callers_never_reuses_an_id`). Test names describe *behaviour*, not implementation structure.
- **One behaviour per test** — multiple `assert`s are fine if they verify one behaviour (e.g. all fields of one returned dict).
- **Fixtures, not inline setup** — shared setup goes in a `conftest.py` fixture. The six conftests: `tests/conftest.py` (session guard + file-path fixtures only — **no DB/app/client**), `tests/integration/conftest.py` (testcontainer + `db_session` + `test_project`), `tests/unit/conftest.py` (mock `db_session`), `tests/dashboard/conftest.py` (TestClient + dep overrides), `tests/dashboard/browser/conftest.py`, `tests/dashboard/routers/conftest.py`.
- **No new function-scoped `app`/`client` fixtures** — use the session-scoped ones; never assign `app.state.x = mock` directly (it leaks) — use `monkeypatch.setattr(app.state, "attr", mock)` or save/restore.
- **Assertion strength** — assert specific values/shapes/messages, never just truthiness or `is not None`. See `skills/iw-ai-core-testing/SKILL.md` §1.
- **Factories** — `factory-boy` is a dependency but not yet used; there is no `tests/factories.py` yet (roadmap — a central entity factory like InnoForge's `EntityFactory` would reduce inline boilerplate).

---

## 5. Quality gates (current state)

Run by `make quality` (lint + format-check + typecheck) and `make check` (`quality` + `test` = unit + integration + dashboard). The workflow's quality-validation steps run `lint`, `format-check`, `typecheck`, and `tests` as separate gates.

| Gate | Tool | Threshold | Command |
|------|------|-----------|---------|
| Lint — Python | `ruff check` (rule sets incl. `E F W I N UP S B A C4 DTZ T20 ICN PIE PT RSE RET SLF SIM TCH ARG PTH ERA`) | 0 errors | `make lint` |
| Lint — dashboard JS | `node --check` on hand-written `dashboard/static/*.js` | 0 syntax errors | `make lint-js` (part of `make lint`) |
| Lint — Jinja2 templates | `scripts/check_templates.py` (rejects `str.format`-style `{}` passed to the `%`-style `format` filter — see I-00075) | 0 violations | `make lint-templates` (part of `make lint`) |
| Format | `ruff format --check` | 0 diffs | `make format-check` |
| Type checking | `mypy orch/ dashboard/` | 0 errors | `make typecheck` |
| Architecture | `scripts/arch_check.py` (layer-boundary import rules) | 0 violations | `make arch-check` |
| Dead-code detection | `vulture` | warnings (warn-only in Phase-1) | `make dead-code` |
| Dependency hygiene | `deptry` | warnings (warn-only in Phase-1) | `make dep-check` |
| DB-column doc gate (CR-00085, P4-4.5) | `scripts/check_db_column_docs.py` (no baseline) | blocking since CR-00092 (2026-05-28) | `make check-column-docs` (blocking in `make quality` and GH `lint-typecheck` job) |
| Security — deps & SAST (basic) | `pip-audit` (`-l --strict`) + `bandit` (`-r orch dashboard executor -ll`) | advisory (currently `|| true`) | `make security-deps` (alias `make security-sast`) |
| Security — IaC | `trivy config` HIGH/CRITICAL | exit 1 on findings | `make security-iac` |
| Security — Secret scan (gitleaks) | `gitleaks detect --no-git --config .gitleaks.toml` | 0 findings; blocking | `make security-secrets` (8th daemon QV gate); pre-commit hook; GH `secrets-scan` job |
| Security — Semgrep SAST | `semgrep --config p/python --config p/owasp-top-ten --config p/security-audit` | informational (burn-in) | GH `semgrep` job (`continue-on-error: true`); `make security-sast`; flip to blocking in `P1-CR-D-followup-semgrep-block` |
| Security — asserted regression tests (CR-00075) | pytest `tests/integration/security/` | 100 % pass (xfailed genuine vulns allowed with Incident ID) | `make test-security-module`; also runs as part of `make test-integration` |
| Unit tests | pytest | 100 % pass | `make test-unit` |
| Integration + dashboard tests | pytest + testcontainers | 100 % pass | `make test-integration` |
| Route-contract sweep (CR-00072) | pytest `test_route_contract_sweep.py` (every GET/HEAD route, `status_code < 500`) | 100 % pass (genuine pre-existing 5xx allowed via `EXPECTED_5XX` xfail + filed Incident) | `make test-route-sweep` (convenience); **blocking** — also runs inside `make test-integration`, no new daemon QV gate |
| schemathesis contract fuzz (CR-00072) | `schemathesis>=4` OpenAPI fuzz of the JSON API operations (`not_a_server_error`) | informational (nightly burn-in, `continue-on-error`) | `make test-contract-fuzz`; nightly `.github/workflows/contract-fuzz.yml`; excluded from the default suite (`contract_fuzz` marker) |
| Cross-project isolation matrix (CR-00074) | pytest `tests/integration/test_cross_project_isolation.py` (dashboard-route / `iw`-command / global-aggregation / per-worktree-DB-boundary) | 100 % pass (xfailed genuine leaks allowed with `KNOWN_LEAK` Incident ID) | `make test-isolation`; no new daemon QV gate — also runs inside `make test-integration` |
| Coverage | `coverage.py` (`branch = true`) | `fail_under = 50` — just below measured branch coverage; **ratchets up over time, never down** (CR-00047) | enforced via `pytest --cov` (config in `pyproject.toml`) at the end of *every* test run that picks up `addopts` (incl. the `unit-tests` and CI `integration` runs) |
| Diff coverage | `diff-cover` | new/changed Python lines ≥ ~90 % covered (vs `origin/main`) | `make diff-coverage` (daemon `diff-coverage` QV gate) + a `pull_request`-conditional step in `test-quality.yml`'s `unit` job |
| Migration round-trip | pytest `test_migrations_round_trip.py` | 100 % pass | `make migration-check` |
| Data-layer suite | pytest `tests/integration/data_layer/` (FTS-trigger invariant, revision-skew regression, DB-identity invariants — CR-00076) | 100 % pass | `make data-layer-check` (runs `make migration-check` first; no new daemon QV gate — the modules also run inside `make test-integration`) |
| CLI contract layer | pytest `tests/integration/cli/` per-command contract tests + `test_cli_spec_conformance.py` bidirectional spec-conformance check (CR-00073) | 100 % pass (xfailed genuine CLI bugs allowed with Incident ID) | `make test-cli-contract` (developer convenience; no new daemon QV gate — the tests also run inside `make test-integration`) |
| Smoke | pytest `-m smoke --strict-markers --no-cov` | 100 % pass | `make smoke` |
| E2E smoke (F-00088) | pytest `tests/e2e/` `-m e2e_smoke` — `home_navigation` + `queue_to_merge` | 100 % pass; **blocking** on `pull_request` / `push` | `.github/workflows/e2e.yml` `e2e-smoke` job; also `make test-e2e-smoke` |
| E2E full (F-00088) | pytest `tests/e2e/` `-m e2e` — all 6 journey modules | informational; alerts on regression; `continue-on-error` in CI | `.github/workflows/e2e.yml` `e2e-full` job (nightly cron + workflow_dispatch); also `make test-e2e` |
| Daemon chaos smoke (F-00089) | pytest `tests/integration/daemon_chaos/` smoke subset (S02 + S03) | 100 % pass; **blocking** on PR + push to `main` | `make daemon-chaos-smoke` |
| Daemon chaos full (F-00089) | pytest `tests/integration/daemon_chaos/` full matrix (S02..S06) | non-blocking; nightly + `workflow_dispatch` | `make daemon-chaos-full` |
| `perf-budgets` (nightly, CR-00083) | pytest `tests/perf/` (daemon poll-loop / RAG query / dashboard routes) | regression > 25% mean fails | `.github/workflows/perf-budgets.yml` (cron `17 3 * * *` + `workflow_dispatch`); also `make test-perf` |
| Mutation testing | `mutmut>=2.5,<3.0` | DEFERRED by CR-00080 viability guard — spike data too thin (M=0%, K=55); next step: Expand test coverage in the most-mutated modules (see per-module breakdown in evidence file), then re-run this CR. Alternatively, run a longer manual spike (`make mutation-audit` outside the 3600s budget) to gather more data before re-running. | `make mutation-check MODULE=...` / `make mutation-audit` |
| Property tests (ci profile) | hypothesis | included in `make test-unit` via `tests/unit/properties/` conftest default; `--strict-markers` via `pyproject.toml`; deterministic via `derandomize=True` | `make test-properties` (explicit); also via `make test-unit` |
| Property tests (deep profile) | hypothesis | NOT in CI; on-demand | `make test-properties-deep` |
| Quarantine deselection | `addopts` extends `-m` filter | `--strict-markers` ensures quarantine marker is registered; `quarantine` tests excluded from merge gate | automatic via `pyproject.toml` `addopts` (part of `make test-unit` / `make test-integration`) |
| Visual regression (CR-00082) | pytest visual layer (`tests/visual/`) + baseline pixel-diff artefacts | CI-only; nightly + path-filtered PR/manual workflow; burn-in non-blocking until 2026-06-01 | `make visual-regression`; `.github/workflows/visual-regression.yml` |
| Flake detector (on-demand / nightly) | `pytest-rerunfailures` + aggregator script | runs full suite 3×; any test with disagreeing outcomes across runs is a flake; NOT a CI gate | `make test-flake-detect` |

Coverage is reported in four formats (`term-missing`, `html`, `xml`, `json`) under `tests/output/coverage/`. The dashboard has a coverage page that surfaces it.

### Coverage floor & diff-coverage (CR-00047, P1-CR-B)

- **The `fail_under` floor.** `[tool.coverage.report] fail_under` is set a few points *below* the lower of the two measured branch-coverage slices — the `make test-unit` slice (covers `tests/unit/`) and the `make test-integration` slice (covers `tests/integration/ tests/dashboard/`), which cover different code and have different totals. The floor must clear the *lower* slice, because `pytest --cov` re-checks `fail_under` at the end of *every* run that picks up `addopts` (the `unit-tests` QV gate, the CI `integration` job, and `make diff-coverage`'s intermediate runs — those last ones pass `--cov-fail-under=0` to opt out). It is a **ratchet**: raise it as coverage improves, never lower it. To re-derive it, run `make test` (note both slices' branch %) and set `fail_under` ≈ (lower slice) rounded down to the nearest 5.
- **The `diff-coverage` gate** checks that new/changed Python lines are ≥ ~90 % covered, compared against `origin/main` — it forces *new* code to be covered without holding the repo hostage to legacy gaps. Run it locally with `make diff-coverage` (it re-runs the unit + integration + dashboard suites to build its own combined coverage, then `diff-cover`; it's the slow gate). It's the 7th daemon QV gate (after `integration-tests`, with a generous 1800 s timeout).
- **Coverage-source caveat.** The daemon `diff-coverage` gate builds its **own combined** unit+integration+dashboard coverage (it does not reuse the `coverage.xml` a preceding step left behind — each `pytest --cov` run overwrites it, so the leftover is the integration+dashboard slice only — nor does it depend on the `integration-tests` QV gate (`make test-integration`, flipped from the former no-op `make allure-integration` stub on 2026-05-14)). The GitHub `Run diff coverage` step in `test-quality.yml`'s `unit` job is cheaper: it diffs against the **unit** `coverage.xml` already produced by `make test-unit`. So the GH PR check may flag a changed line that the daemon gate (with integration coverage folded in) considers covered — the daemon gate is the authoritative one.

### Smoke layer SLA (CR-00052, P1-CR-E)

`make smoke` runs the curated `@pytest.mark.smoke` set. **Contract:**

- **<=15 tests** total (count by `grep -rc "@pytest.mark.smoke" tests/`).
- **<60 s** wall-clock on a clean dev environment (measured 2026-05-14: ~13s).
- **Covers 5 critical paths**: daemon-worktree-start, dashboard-main-pages, iw-next-id, work-item-queue, /healthz.

Each path has >=1 smoke test mapped to it (audit table in CR-00052's S01 report). Adding a new `@pytest.mark.smoke` decorator requires:

1. Identifying which critical path it covers (or adding a new path to the contract and updating this doc).
2. Re-auditing the count — if it would push the total over 15, **remove** a redundant existing decorator or **don't add** the new one.
3. Re-measuring wall-clock — if it would push over 60 s, profile and trim.

The contract is currently **prose-enforced** — no `make smoke-sla` command. A future follow-up may add mechanical enforcement if drift happens (see TESTS_ENHANCEMENT.md §5 / P1-CR-E-followup-sla-enforcement, not yet filed).

---

## 6. TDD & RED evidence

`backend-impl` follows **RED → GREEN → REFACTOR**: write a failing test that defines the expected behaviour, **run it and confirm it fails for the expected reason** (an `AssertionError` or `NotImplementedError`/`AttributeError`-from-missing-implementation — *not* an `ImportError`/`SyntaxError`/collection error, which would mean the test itself is broken), then write the minimal implementation to make it pass, then refactor while keeping tests green. The test is written *before* the implementation — not after, not alongside.

The captured RED failure (test id(s) + the failure line) is recorded in the Subagent Result Contract JSON as `tdd_red_evidence` — required for behavioural steps; non-behavioural steps (pure refactor, config-only, doc/template-only) record `"n/a — <one-line reason>"` instead. The Implementation / SelfAssess / CodeReview prompt templates carry matching language; SelfAssess checks the field is present and plausible, and CodeReview reasons about whether each new test would actually fail against pre-change code. `tests/unit/test_tdd_red_evidence_contract.py` is a content-guard that pins the contract strings in the agent and template files so the requirement can't quietly drift away. (Landed in **CR-00045**, 2026-05-11.)

---

## 7. AI-generated test trust — red flags

A test requires human (or `tests-review`) scrutiny if **any** of these apply:

- Its only assertion is `assert x is not None` / `isinstance(x, T)` / `len(x) > 0` / `"k" in x`.
- Its only assertion is `mock.assert_called_*` / `mock.assert_awaited_*` — it asserts on the test's own setup, not on behaviour.
- It mocks every dependency, including the unit under test.
- Its name describes implementation structure (`test_calls_repository_method`) rather than behaviour.
- It has 0–1 assertions for logic with 3+ code paths.
- It uses `time.sleep()` / hardcoded delays.
- It tests no error/exception path.
- `pytest.raises(Exception)` / `pytest.raises(...)` with no `match=` (too broad).
- Multiple statements inside a `pytest.raises` block.
- It's a snapshot/golden-file test whose baseline was regenerated rather than reviewed.

These are codified, with examples, in `skills/iw-ai-core-testing/SKILL.md`.

---

## 8. Mutation testing awareness

Mutation testing measures whether the test suite would actually fail when production code regresses. **Installed in CR-00059 (2026-05-18)** via `mutmut>=2.5,<3.0`. Four `make` targets are available: `mutation-check MODULE=<path>` (single module — quick), `mutation-audit` (widened to `orch/` in CR-00080 — slow, on-demand), `mutation-results` (re-display cached results), `mutation-show ID=<n>` (inspect one surviving mutant).

**Second spike on widened scope `orch/` (CR-00080):** CR-00080 fixed the prior runner bug by overriding pytest's coverage floor (`--cov-fail-under=0`) so mutmut could execute mutants instead of failing pre-run. The second spike then measured `orch/` with wall-clock **01:00:00**, **55** mutants generated, **0** killed, **55** survived, mutation score **M=0%**, exercised mutants **K=55** (`killed + survived`).

CR-00080 keeps mutation testing on the **nightly GH workflow** surface by design (per-batch daemon QV cost is impractical at this runtime), but gate wiring is controlled by a viability guard: wire blocking only if **M>=20% AND K>=30**. That guard **fired** in CR-00080 (`M=0%`, `K=55`), so threshold selection is **DEFERRED — viability guard fired** and no blocking threshold `T` was wired. Recommended next step (from S02): **Expand test coverage in the most-mutated modules (see per-module breakdown in evidence file), then re-run this CR. Alternatively, run a longer manual spike (`make mutation-audit` outside the 3600s budget) to gather more data before re-running.**

Ratchet rule remains the intended end-state once viable data exists: set `T` a few points below measured score, then raise `T` over time as coverage improves (same ratchet pattern as CR-00047 diff-coverage), never down.

### Assertion scanner (CR-00046, P1-CR-A)

`scripts/check_test_assertions.py` is a static AST scanner that flags four categories of vacuous test — **no-assert**, **tautology** (every `assert` is `is not None` / `isinstance` / `len > 0` / `in` / `True` / `<bare Name>` / `x == x`), **mock-only** (every assertion is `mock.assert_called*`/`assert_await*` on a mock-named receiver), and **broad-raises** (`pytest.raises(Exception)` without `match=`). It runs as `make test-assertions`, is folded into `make quality`, and is the dedicated `assertions` daemon QV gate (right after `lint`) and a step in `.github/workflows/test-quality.yml`'s `lint-typecheck` job. The committed baseline at `tests/assertion_free_baseline.txt` lists current offenders so the gate fires only on **new** violations; regenerate it with `uv run python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/`. **The right way to silence the gate is to fix the test, not to add it to the baseline** — the baseline is a cleanup backlog, not an accept-list. Local opt-out for the rare legitimate case is `# noqa: assertion-scanner` on the function `def` line (reviewers should push back).

---

## 9. Known gaps & roadmap

The full phased plan, with per-item rationale, approach, delivery vehicle, and status, lives in [`ai-dev/work/TESTS_ENHANCEMENT.md`](../ai-dev/work/TESTS_ENHANCEMENT.md); the research behind it is [R-00068](research/R-00068-ai-core-test-quality-strategy.md). Summary of where we stand:

| Area | Status |
|------|--------|
| Branch coverage enabled | ✅ (`branch = true`) |
| Coverage failure floor | ✅ (CR-00047, 2026-05-12) — `fail_under` raised from 46 to just below measured branch coverage; ratchets up, never down (1.2) |
| Diff/patch coverage on PRs | ✅ (CR-00047, 2026-05-12) — `diff-cover` dev dep + `make diff-coverage` daemon QV gate + `pull_request` step in `test-quality.yml`'s `unit` job (1.3) |
| AST assertion scanner | ✅ (CR-00046, 2026-05-11) — `make test-assertions` + baseline `tests/assertion_free_baseline.txt` |
| `ruff` PT rules | ✅ enabled |
| Test-order randomisation (`pytest-randomly`) | ✅ (CR-00055, 2026-05-16) — default-on; integration suite robust to randomisation via per-test PostgreSQL template-clone (`pgtestdbpy>=0.0.1`; WAL_LOG strategy override ~10× faster than library default); `IW_CORE_DB_*` monkeypatched per-test for subprocess isolation; 4-seed sweep green (12345/67890/11111/42424); 3 module-scoped quarantines carried forward as `xfail(strict=False)`. Earlier fallback (CR-00048, 2026-05-12): dep installed, off by default via `-p no:randomly`; superseded by CR-00055. |
| Secrets scanning (`gitleaks`) | ✅ (CR-00050, 2026-05-14) — pre-commit hook + GH `secrets-scan` job + `make security-secrets` daemon QV gate (1.6) |
| Semgrep SAST | ⚠️ (CR-00050, 2026-05-14) — managed rulesets; `continue-on-error: true` burn-in; GH `semgrep` job; flip to blocking in `P1-CR-D-followup-semgrep-block` (1.9) |
| `vulture` / `deptry` suite-health | ✅ (CR-00048, P1-CR-C, 2026-05-12) — warn-only this CR; `make dead-code` + `make dep-check` in `make quality` + GH workflow |
| Allure reporting `make` targets | ✅ (CR-00052, 2026-05-14) — 6 real Makefile recipes; `ALLURE_RESULTS`/`ALLURE_REPORT` vars; gitignored artefact dirs (1.8) |
| Curated smoke layer with SLA | ✅ (CR-00052, 2026-05-14) — 12 tests covering all 5 critical paths; <60s wall-clock; SLA in `tests/CLAUDE.md` and this doc §5 (1.11) |
| Testing strategy doc | ✅ this document (0.1) |
| Agent testing skill | ✅ `skills/iw-ai-core-testing/` (0.2) |
| TDD RED-evidence requirement | ✅ (CR-00045, 2026-05-11) — `tdd_red_evidence` field in result contract; guard test pins it |
| Mutation testing | ⚠️ (CR-00059/CR-00080) — foundation + widened-scope spike landed; gap still open (CR-00080 viability guard fired — see §8 for next step) |
| Property-based tests (Hypothesis) on state machines | ✅ (CR-00060, 2026-05-18) — five modules under `tests/unit/properties/`; ci profile in `make test-unit`; deep profile on-demand via `make test-properties-deep` |
| Flaky/quarantine workflow | ✅ (CR-00061, 2026-05-18) — quarantine marker; addopts deselection; make test-quarantine / make test-flake-detect; quarantining requires filing an Incident (rule in tests/CLAUDE.md) |
| Structured dashboard E2E layer | ✅ DONE 2026-05-21 (F-00088) — `tests/e2e/` with 6 journey modules (`home_navigation`, `queue_to_merge`, `code_qa_sse`, `docs_export`, `jobs_filters`, `htmx_fragments`); `make test-e2e` / `make test-e2e-smoke`; `.github/workflows/e2e.yml` (`e2e-smoke` blocking, `e2e-full` informational); documented in §2 Layer 4 + §5 gate table + skill (3.1) |
| Contract / no-5xx route sweep + `schemathesis` | ✅ DONE 2026-05-21 (CR-00072) — `tests/dashboard/test_route_contract_sweep.py` (every GET/HEAD route, `status_code < 500`, blocking via `make test-integration`) + `tests/dashboard/test_schemathesis_contract.py` (`schemathesis>=4` JSON-API fuzz, `contract_fuzz`-marked, nightly `contract-fuzz.yml` burn-in); genuine pre-existing 5xx → `EXPECTED_5XX`/`KNOWN_CONTRACT_5XX` allowlist + operator follow-up; documented in §2 Layer 6 + §5 gate table + skill (3.2) |
| `iw` CLI-contract layer | ✅ DONE 2026-05-21 (CR-00073) — per-command contract tests for the 6 priority commands (`step-done`, `register`, `doc-update`, `approve`, `next-id`, evidence-ingestion hooks) under `tests/integration/cli/` + bidirectional spec-conformance check `test_cli_spec_conformance.py` with `KNOWN_SPEC_DRIFT` / `KNOWN_UNTESTED_COMMANDS` allowlists; `make test-cli-contract`; documented in §2 Layer 2 sub-layer + §5 gate table + skill + TESTS_ENHANCEMENT.md (3.3) |
| Cross-project isolation matrix | ✅ DONE 2026-05-21 (CR-00074) — `tests/integration/test_cross_project_isolation.py`; `second_project` fixture + `tests/fixtures/dual_project_seed.py`; parametrized over dashboard routes / `iw` commands / global aggregation / per-worktree-DB boundary; `KNOWN_LEAK` allowlist (empty); `make test-isolation`; documented in §2 Layer 7 + §5 gate table + skill + TESTS_ENHANCEMENT.md (3.4) |
| Security test module (live-DB-guard net, authz negatives, doc-render SSRF) | ✅ DONE 2026-05-21 (CR-00075) — `tests/integration/security/` package; `test_live_db_write_guard`, `test_authz_negative_paths`, `test_doc_render_ssrf_path_traversal`, `test_agent_context_env_handling`; genuine vulns → xfail + Incident; `make test-security-module`; documented in §2 Layer 5 + §5 gate table + skill + TESTS_ENHANCEMENT.md (3.5) |
| Data-layer module (migration round-trip / FTS invariant / revision-skew / DB-identity) | ✅ (CR-00076, 2026-05-21) — `tests/integration/data_layer/` package + `make data-layer-check`; extends, does not replace, the migration round-trip (3.6) |
| DB-column doc gate (4.5) | ✅ (CR-00085, 2026-05-24; CR-00092, 2026-05-28) — baseline removed; `make check-column-docs` now blocking in `make quality` + GH `test-quality.yml` |
| Visual regression for rendered HTML/PDF docs | ✅ (CR-00082, 2026-05-25) |
| Daemon chaos / fault-injection | ✅ (F-00089, 2026-05-26) — `tests/integration/daemon_chaos/` harness + 5 scenario modules (S01–S05); `make daemon-chaos-smoke` (blocking smoke: S02 + S03); `make daemon-chaos-full` (full matrix, nightly/workflow-dispatch); documented in §2 Layer 9 + §5 gate table + TESTS_ENHANCEMENT.md (4.3) |
| Performance budgets | ✅ DONE — CR-00083 (2026-05-24) |
| `tests/factories.py` central entity factory | ❌ |
| **Self-dashboarding of test health (4.6)** | ✅ (CR-00086, 2026-05-28) — `test_health_snapshots` table + `iw test-health-capture` CLI + Test Health panel (Tests + Quality views) + `.github/workflows/test-health.yml` (self-hosted runner, push + nightly cron + workflow_dispatch) + this §10 + Database Schema DDL; see §10 below |

Update this table and the gate table in §5 as roadmap items land.

---

## 10. Self-dashboarding (CR-00086)

The platform runs other projects' test/quality gates and surfaces the results in
its Tests/Quality view — but it has not surfaced its own test-health signals.
CR-00086 closes that loop by dogfooding the platform.

### Metrics surfaced

| Metric | Source artefact | Notes |
|--------|-----------------|-------|
| `mutation_score` | `make mutation-results` JSON output (CR-00059/CR-00080) | CR-00080 widened scope to `orch/` |
| `coverage_pct` | `coverage.xml` via `orch/coverage_service.py` (CR-00047) | |
| `flaky_test_count` | `scripts/flake_detect_aggregate.py` output (CR-00061) | Parses `tests/output/flake-detect-*.log` |
| `assertion_baseline_size` | Line count of `tests/assertion_free_baseline.txt` (CR-00046) | Baseline size as a proxy for assertion quality debt |

Each capture writes one row to `test_health_snapshots` per metric, grouped by
`(project_id, metric, ts_minute)` — one capture invocation produces **one row per
metric** (4 rows total) plus **one entry in the Jobs view** (grouped by minute).

### Panel mount points

The Test Health panel (`dashboard/templates/fragments/test_health_panel.html`) is
mounted via `<div hx-get="…/test-health" hx-trigger="load">` on:

- `dashboard/templates/pages/project/tests.html` — the Tests page
- `dashboard/templates/pages/project/quality.html` — the Quality page

Both pages render under the existing gates summary. Each metric card shows:

- Latest value (with delta vs. the previous snapshot — up/down/neutral arrow)
- Inline server-rendered SVG sparkline (up to 30 snapshots, no JS library)
- Per-metric "no data yet" placeholder when the metric has no snapshots
- Combined empty state ("Test health data will appear after the first capture runs")
  when ALL four metrics lack snapshots

### Capture cadence

Three trigger paths:

1. **On push to `main`** — every successful merge to `main` runs the workflow on
   the self-hosted runner after CI gates pass.
2. **Nightly cron** (`0 3 * * *` UTC) — 03:00 UTC every day.
3. **Manual (`workflow_dispatch`)** — for operator debugging.

The command is:

```bash
uv run iw test-health-capture --project iw-ai-core
```

### Persistence model

> ⚠️ The self-hosted runner is a hard prerequisite.

The workflow runs on a **self-hosted runner** labelled `iw-core` with network
access to the orchestration DB on port 5433. Snapshots are persisted to the
live `test_health_snapshots` table — **not** to an ephemeral GH-Actions
service-container Postgres.

**Why not a service-container workflow?** The goal is a **trend over time**.
A GH-Actions service-container Postgres (`services: postgres:` in the workflow
YAML) is provisioned fresh for every run and torn down at runner exit — any rows
written to it disappear immediately. That would defeat the entire purpose of
the panel (no history → no sparkline → no trend). The `test-quality.yml` workflow
uses an ephemeral service container because it runs unit/integration tests that
need a throwaway DB. The test-health workflow uses the **live orch DB** because
it needs rows to survive across runs.

The `IW_CORE_*` GitHub secrets (`IW_CORE_DB_HOST`, `IW_CORE_DB_PORT`,
`IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD`) point at the live
orchestration DB on port 5433. No credentials are inlined in the workflow file.

### Operator prerequisites

Before this workflow will succeed, the operator must:

1. **Provision a self-hosted runner** labelled `iw-core` (or the project's
   standard label for IW-managed workflows) and keep it online.
2. **Create the `IW_CORE_*` GitHub secrets** in the repo settings:
   `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT`, `IW_CORE_DB_NAME`,
   `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD` — pointing at the live
   orchestration DB on port 5433.
3. **Verify network access**: the runner must be able to reach
   `IW_CORE_DB_HOST:5433`.

Without all three, the workflow fails at the `iw test-health-capture` step.

### Idempotency contract

One row per `(project_id, metric, ts_minute)` — `ts` is truncated to the minute
in the upsert logic (`date_trunc('minute', ts)`). Re-running within the same
minute with the same source values prints `"noop"` for unchanged metrics and
leaves existing rows intact. The command is safe to run at any frequency.

### Link to design

- CR-00086 design: `ai-dev/active/CR-00086/CR-00086_CR_Design.md`
- CR-00086 manifest: `ai-dev/active/CR-00086/workflow-manifest.json`
- Service: `orch/test_health_service.py`
- CLI command: `orch/cli/test_health_commands.py`
- Database model: `orch/db/models.py` → `TestHealthSnapshot`
- Migration: `orch/db/migrations/versions/add_test_health_snapshots_table.py`
- Panel fragment: `dashboard/templates/fragments/test_health_panel.html`
- Jobs aggregator: `orch/jobs/aggregator.py`

*last updated: 2026-05-28*

---

## 11. Regression-rate KPI (F-00090)

The regression-rate KPI is the *second half* of the quality scorecard. A
throughput metric alone (merges/week) is misleading: high velocity with
an rising regression rate is worse than steady velocity with a low one.

### How classifications are recorded

Each `WorkItem` of type `Issue` (Incident) in a project may carry five
regression-link columns (`introduced_by_work_item_id`,
`regression_classification`, `classified_at`, `classified_by`,
`introduced_by_commit_sha` — added by F-00090).

- **Operator-curated**: the operator submits a classification via the
  dashboard htmx form (Incident detail page) or the CLI
  ``iw regression-classify --accept``. The `classified_by` value records
  ``operator:<username>``.
- **Heuristic-seeded**: the operator accepts the heuristic's top suggestion
  (suggested by `regression_link_service.suggest_introducer()`). The
  `classified_by` value records ``heuristic:auto``. The heuristic *never*
  persists a classification without operator action — Invariant 3 of
  F-00090.

The `regression_classification` ENUM values are:

| Value | Meaning | Contributes to KPI? |
|-------|---------|----------------------|
| `regression` | Filed against a prior merge that introduced the bug | **Yes** — increments regressions/week |
| `pre_existing` | Bug existed before the current project's merges | No — no merge attribution |
| `unknown` | Classified but source merge undetermined | No |
| NULL | Not yet classified | No — excluded from all KPI calculations |

### How the KPI is computed

For a given project and week (Monday–Sunday UTC):

```
merges_this_week   = count(WorkItem.status='completed' AND type IN ('Feature','CR')
                           AND completed_at in [week_start, week_end])
regressions_this_week = count(Incident.regression_classification='regression'
                              AND classified_at in [week_start, week_end])
regression_rate = regressions_this_week / merges_this_week  (0.0 when merges=0)
```

The rate-guard rule (Invariant 6): when `merges == 0` in a week, the
regression rate is `0.0` — never NaN, never a division error.

The KPI is rendered on the per-project home page **and** on the dedicated
`/project/{id}/quality-kpis` route as: merges/week, regressions/week,
and the regression rate (b/a), plus a 12-week trend chart (inline SVG,
no JS library). The chart plots actual weeks only; no padding zeros for
weeks with no history.

### Backfill script and operator workflow

The operator-run backfill script
(``scripts/backfill_regression_classification.py``) does **not** auto-classify
Incidents. It calls `suggest_introducer()` on every NULL-classification
Incident and emits the top suggestion to stdout for operator review.
Classifications are confirmed via the dashboard htmx form or the CLI
``iw regression-classify --accept``. This is Invariant 3 enforced in code.

See F-00090 for the full design, acceptance criteria, and boundary
behaviour table.

---

## 12. Quick reference
# Everything before a commit
make check                 # quality (lint + format-check + typecheck) + test (unit + integration + dashboard)

# Individual layers
make test-unit             # ~2,260 unit tests, no containers
make test-integration      # ~1,510 integration + ~650 dashboard tests (testcontainer Postgres ~2s startup)
make test-dashboard        # fast --no-cov dashboard-only slice for local iteration
make test-browser          # browser tests via playwright-cli (needs a live Uvicorn dashboard)
make test-parallel         # unit+integration+dashboard with `-n auto --dist=loadfile`
make smoke                 # `-m smoke` critical-path tests

# Targeted
uv run pytest tests/unit/test_config.py -v
uv run pytest -k "test_next_id" -v
make migration-check       # Alembic round-trip on a fresh testcontainer

# Quality / security
make quality               # lint + format-check + typecheck
make lint                  # ruff + lint-js + lint-templates
make arch-check            # layer-boundary import rules
make security-deps         # pip-audit + bandit
make security-iac          # trivy config scan
```

## 13. Semgrep finding triage (CR-00051)

`make security-sast` runs Semgrep with three configs (`p/python`, `p/owasp-top-ten`, `p/security-audit`) and **must report zero blocking findings**. When a true rule misfire is unavoidable, the project follows these conventions.

**Bandit `# nosec` does NOT silence Semgrep.** The two tools share heritage but suppression markers are independent. The marker Semgrep recognises is:

- Python: a same-line `# nosemgrep: <rule-id>` on the offending statement.
- Jinja2: a `{# nosemgrep: <rule-id> — <rationale> #}` comment placed on the line immediately **before** the flagged template line.
- Project-wide: a `--exclude-rule <rule-id>` flag on the `semgrep` invocation in the `Makefile` `security-sast:` target, accompanied by a `# …`-prefixed rationale comment block immediately above the target.

**Macro-emitted findings do not propagate.** Suppressions placed `{# nosemgrep #}` inside a macro body do **not** silence findings emitted at the macro's call sites. This was verified empirically during CR-00051: an in-macro suppression on `write_button_attrs` did not silence the 26 caller-site findings. When the false-positive lives in a macro that's called from many template files, the correct tool is a project-wide Makefile `--exclude-rule`, not an in-macro comment.

**Four reasons to suppress rather than fix:**

1. *Confirmed false positive* — the rule's pattern matches a construct that is provably safe at this call site (e.g. `tojson`-filtered values inside `<script>`; a logger format string whose substituted argument is a model name, not a credential).
2. *Trusted-source rendering* — server-rendered HTML produced from internal documents (Markdown → HTML for a project doc, `| safe` on such output) where the source is not user-controlled.
3. *Deliberate-but-audited pattern* — `shell=True` on a command constructed from server-side config with no untrusted input on argv. Per-line annotation + same-line rationale documents the audit.
4. *Project-wide structural false positive* — the rule misfires across so many sites that per-line annotation would create unsustainable churn, AND every flagged site has been audited and found safe. Use `--exclude-rule` in the `Makefile` with a rationale comment block listing each excluded rule and the reason.

**Every per-line suppression carries a same-line rationale** after an em-dash, like:

```python
shell=True,  # nosec B602  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — trusted constructed command, no untrusted input on argv
```

**Every Makefile `--exclude-rule` carries a rationale comment block above the target** enumerating each excluded rule, the finding count, and why per-line annotation is not the right tool. If a future change invalidates the rationale (e.g. a macro previously known to emit constant output starts interpolating user input), the corresponding test invariant must fail loudly so the exclude flag is re-justified.

---

## 14. LLM-as-judge advisory signal (CR-00084 spike)

A stronger model (Claude Opus 4.7) scores newly-written tests against an assertion-strength rubric as an advisory signal in the CodeReview step. **Complementary to — not a replacement for — the structural assertion scanner (§8, CR-00046).** The scanner catches patterns (no-assert / tautology / mock-only / broad-raises); the judge evaluates semantic strength.

### The rubric

Three axes, each scored 1–5:

| Axis | What it measures |
|------|------------------|
| `assertion_specificity` | Does the assertion target a specific value/message/state rather than just truthiness or type? |
| `behaviour_vs_mock` | Does the test assert on real behaviour or only on its own mocks/setup? |
| `edge_coverage` | Does the test exercise edge cases and boundary values, or only the happy path? |

Bucketing: `overall >= 4` → **STRONG** · `overall == 3` → **MEDIUM** · `overall <= 2` → **WEAK**.

### Calibration outcome

The spike ran against a hand-labelled set (`tests/llm_judge/labelled_set.jsonl`). Calibration was **DEFERRED** — `ANTHROPIC_API_KEY` was not set in the worktree, so the judge script (`scripts/llm_judge_test_review.py`) could not contact the model. Full evidence at `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`.

Verdict: **DEFERRED** · Calibration bar: WEAK-recall ≥ 70% AND STRONG-FP ≤ 30%.

### Current disposition

**Advisory hook DORMANT** — the CodeReview agent spec (`agents/claude/code-review-impl.md` §6 · `agents/opencode/code-review-impl.md` §6) instructs agents **not to invoke the judge** pending re-calibration. Re-enable path: run `make llm-judge-calibrate` once `ANTHROPIC_API_KEY` is available, verify the Verdict line reads MET, then update §6 of both agent specs to the LIVE form (see the re-enable instruction in the DORMANT body).

### Cost discipline

- **Calibration budget**: < $2.00 (one-time run to generate the evidence file). The DEFERRED run cost $0.00 (no API calls made).
- **Per-review cap**: < $0.50 per CodeReview invocation (declared in the agent spec; not enforced by a hard budget).
- **No retry / no auto-loop**: if the judge fails it is skipped with a one-line log; no automatic retry.

### What's out of scope

Promoting the judge to a **blocking gate** — the tracker entry is explicit ("no judge is uniformly reliable") and this spike is explicitly an experiment. A follow-up CR that promotes the judge to a blocking gate is only possible after multiple weeks of advisory-line evidence and a re-calibration that shows stable metrics.

---

## Changelog

- **2026-05-28** — **§10 Self-dashboarding added (CR-00086).** New `.github/workflows/test-health.yml`: self-hosted runner (`runs-on: [self-hosted, iw-core]`), push + nightly cron + workflow_dispatch, `IW_CORE_*` secrets pointing at live orch DB on port 5433 (no ephemeral service-container Postgres), runs `uv run iw test-health-capture --project iw-ai-core`, uploads `test-health-summary.json` artefact. Persistence model: self-hosted runner is a hard prerequisite — rows must survive across runs for trend-over-time. Operator prerequisites documented in §10. §9 row 4.6 flipped ✅, §10 new section, Database Schema DDL appended, TESTS_ENHANCEMENT.md §8 row 4.6 → DONE + v1.4 header bump. Skill cross-reference added to `skills/iw-ai-core-testing/SKILL.md` §17. Test-only doc changes — no production code edited.
- **2026-05-24** — **Layer 10 performance budgets shipped (CR-00083).** Phase 4 first item. `tests/perf/` package with 3 modules (daemon poll-loop, RAG query, dashboard routes); committed baselines per module under `tests/perf/baselines/`; 5 Makefile targets (`test-perf-daemon`, `test-perf-rag`, `test-perf-routes`, `test-perf`, `test-perf-update-baseline`); nightly `.github/workflows/perf-budgets.yml` (cron `17 3 * * *` + `workflow_dispatch`, NOT on PR). Regression threshold `mean:25%` — start value, ratchetable. Test-only, no production code change.
- **2026-05-26** — **Layer 9 added (F-00089).** Daemon chaos / fault-injection test layer: `tests/integration/daemon_chaos/` harness + 5 scenario modules (S01–S05); `make daemon-chaos-smoke` (blocking smoke: S02 + S03) wired as PR/push gate; `make daemon-chaos-full` (full matrix S02..S06) runs nightly/workflow-dispatch. §2 Layer 9 section + §5 gate table entry + §9 roadmap item 4.3 updated. No production daemon code modified.
- **2026-05-25** — **§12 added (CR-00084 spike outcome).** LLM-as-judge advisory signal spike: judge script `scripts/llm_judge_test_review.py`, labelled set `tests/llm_judge/labelled_set.jsonl`, `make llm-judge-calibrate` target — all shipped. Calibration DEFERRED (ANTHROPIC_API_KEY unavailable in worktree; evidence at `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`). Advisory hook in CodeReview agent specs shipped DORMANT (agents instructed not to invoke the judge pending re-calibration). Item 4.4 status → DEFERRED in tracker; §11 changelog entry added. Forward link from CR-00046's §8 entry.
