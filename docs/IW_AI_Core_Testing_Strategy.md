# IW AI Core — Testing Strategy

**Last updated**: 2026-05-11

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

IW AI Core today has **four test layers**, all pytest-based except the browser layer which drives a real Chromium via `playwright-cli`.

```
Layer 4:  Browser tests (playwright-cli)   — Real Chromium against a live Uvicorn dashboard
Layer 3:  Dashboard tests (TestClient)     — FastAPI routes/templates/htmx against testcontainer DB
Layer 2:  Integration tests (pytest)       — Models, daemon, CLI, RAG, DB behaviour against testcontainer DB
Layer 1:  Unit tests (pytest)              — Config, state-machine logic, parsers, CLI parsing, pure functions
Static:   Quality gates (ruff, mypy, ...)  — Enforced by `make quality` / `make check`
```

### Test inventory

| Layer | ~Tests | ~Files | Framework | Location | Execution |
|-------|-------:|-------:|-----------|----------|-----------|
| Unit | ~2,260 | 175 | pytest | `tests/unit/` | `make test-unit` |
| Integration | ~1,510 | 169 | pytest + testcontainers[postgres] | `tests/integration/` | `make test-integration` (also runs `tests/dashboard/`) |
| Dashboard | ~650 | 69 | pytest + FastAPI `TestClient` + `db_session` | `tests/dashboard/` (excl. `browser/`) | part of `make test-integration`; fast slice via `make test-dashboard` |
| Browser | small | 7 | pytest + `playwright-cli` + live Uvicorn | `tests/dashboard/browser/` | `make test-browser` (not in `make test`); also the `qv-browser` workflow step |
| **Total** | **~4,420** | **413** | | | `make test` = unit + integration (+ dashboard) |

(Counts are approximate — `def test_*` occurrences and `test_*.py` file counts as of 2026-05-11. Keep this row roughly current; it does not need to be exact.)

### Layer 1 — Unit tests (`tests/unit/`)

Fast, no I/O, no containers. Cover: `orch/config.py` resolution; state-machine and lifecycle logic; parsers and diffing (`orch/doc_diff.py`, `orch/doc_sections.py`); `iw` CLI argument parsing; `orch/rag/` chunking and ranking helpers; `orch/staleness/`; pure functions extracted from routers/daemon. Subdirectories mirror the package (`tests/unit/daemon/`, `tests/unit/db/`, `tests/unit/rag/`, `tests/unit/executor/`, `tests/unit/staleness/`, `tests/unit/dashboard/`, `tests/unit/orch_config/`).

`tests/unit/conftest.py` provides a `MagicMock`-based `db_session` for unit tests that need to *mock* DB calls, and re-exports `db_engine` / `pg_container` / `test_project` from the integration conftest for the rare unit test that needs a real container. **A pure function from a router module must not be unit-tested by importing `dashboard.routers.*`** — see §3 and `tests/CLAUDE.md`.

### Layer 2 — Integration tests (`tests/integration/`)

Real PostgreSQL via `testcontainers[postgres]` — never the live DB. Cover: ORM models and constraints; the daemon loop and state transitions (`tests/integration/daemon/`); the `iw` CLI end-to-end against a real DB (`tests/integration/cli/`); RAG/code-index pipeline (`tests/integration/rag/` — some tests skip when no local Ollama listener, see the conftest hook); DB behaviour including `SELECT FOR UPDATE` locking (which is *why* the DB is never mocked here); migration round-trips (`tests/integration/test_migrations_round_trip.py`, also runnable via `make migration-check`); evidence ingestion; doc service/versioning. The `tests/integration/dashboard/` and `tests/integration/api/` subdirs hold heavier DB-backed dashboard/API flows.

### Layer 3 — Dashboard tests (`tests/dashboard/`)

FastAPI behaviour via `TestClient` with the testcontainer `db_session` injected through `app.dependency_overrides[get_db]` (see `tests/dashboard/conftest.py` and the pattern in `tests/dashboard/test_jobs_filter_ui.py`). Cover: route status/redirects/shapes; Jinja2 template rendering; htmx fragment swaps; SSE wiring (`test_code_qa_sse_wire`); chat panel a11y/security/templates; the alembic-guard banner; coverage page; staleness router; project onboarding; runtime overrides; session isolation (`test_F00077_session_isolation`). Run as part of `make test-integration`; `make test-dashboard` is a fast `--no-cov` slice for local iteration.

### Layer 4 — Browser tests (`tests/dashboard/browser/`)

Real Chromium via **`playwright-cli` only** (never `agent-browser`, never `chromium.launch()` directly, never `npx playwright install`, never modify `.playwright/cli.config.json` — see the root `CLAUDE.md`). Marked `@pytest.mark.browser` and **deselected by default** (`addopts` has `-m 'not browser'`); run with `make test-browser` against a live Uvicorn dashboard the test data is visible to. The workflow's `qv-browser` step also exercises browser-level verification per work item, capturing screenshots into `ai-dev/active/<ITEM>/evidences/post/`.

> **Not yet a layer**: there is no structured browser/E2E *journey* suite (auth/session, queue→batch→merge, Docs export) and no isolated E2E compose stack — that's roadmap item 3.1. The current browser tests are a handful of smoke checks.

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

**Quarantine policy (from CR-00055):** The 3 known quarantines are module-scoped `migrated_engine` tests where the per-test clone cannot help (the engine is shared across the whole module). Each carries `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False)` + a `# NOTE(P1-CR-C-followup-randomly):` comment. A follow-up CR (`P1-CR-C-followup-randomly-quarantine-cleanup`) will scope those engines down to function level.

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

### Per-worktree DB vs testcontainers

F-00062 introduced a per-worktree Postgres container for *app runtime* (started by the daemon when a project ships `ai-dev/iw-config/`). This is **separate** from `make test-integration`'s testcontainers. Tests must never assume the per-worktree DB exists — they spin up their own testcontainer. The agent's `IW_CORE_DB_*` env vars point at the per-worktree DB; `IW_CORE_ORCH_DB_*` always points at the global orch DB on 5433.

### Markers (`pyproject.toml`)

| Marker | Meaning |
|--------|---------|
| `integration` | requires docker/testcontainer (most `tests/integration/` rely on the dir, not the marker) |
| `smoke` | fast critical-path tests; <=15 tests, <60s wall-clock, 5 critical paths; SLA documented in `tests/CLAUDE.md` (CR-00052, 2026-05-14); run via `make smoke` |
| `slow` | deselected by default unless `-m slow` is passed |
| `browser` | drives real Chromium via `playwright-cli`; **deselected by default** (`addopts` `-m 'not browser'`); run via `make test-browser` |
| `order_dependent` | test relies on test execution order; tracked for cleanup in P1-CR-C-followup |
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
| Security — deps & SAST (basic) | `pip-audit` (`-l --strict`) + `bandit` (`-r orch dashboard executor -ll`) | advisory (currently `|| true`) | `make security-deps` (alias `make security-sast`) |
| Security — IaC | `trivy config` HIGH/CRITICAL | exit 1 on findings | `make security-iac` |
| Security — Secret scan (gitleaks) | `gitleaks detect --no-git --config .gitleaks.toml` | 0 findings; blocking | `make security-secrets` (8th daemon QV gate); pre-commit hook; GH `secrets-scan` job |
| Security — Semgrep SAST | `semgrep --config p/python --config p/owasp-top-ten --config p/security-audit` | informational (burn-in) | GH `semgrep` job (`continue-on-error: true`); `make security-sast`; flip to blocking in `P1-CR-D-followup-semgrep-block` |
| Unit tests | pytest | 100 % pass | `make test-unit` |
| Integration + dashboard tests | pytest + testcontainers | 100 % pass | `make test-integration` |
| Coverage | `coverage.py` (`branch = true`) | `fail_under = 50` — just below measured branch coverage; **ratchets up over time, never down** (CR-00047) | enforced via `pytest --cov` (config in `pyproject.toml`) at the end of *every* test run that picks up `addopts` (incl. the `unit-tests` and CI `integration` runs) |
| Diff coverage | `diff-cover` | new/changed Python lines ≥ ~90 % covered (vs `origin/main`) | `make diff-coverage` (daemon `diff-coverage` QV gate) + a `pull_request`-conditional step in `test-quality.yml`'s `unit` job |
| Migration round-trip | pytest `test_migrations_round_trip.py` | 100 % pass | `make migration-check` |
| Smoke | pytest `-m smoke --strict-markers --no-cov` | 100 % pass | `make smoke` |

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

Mutation testing (introduce a small bug — a "mutant" — into production code; check that some test fails) is the only direct measure of whether our tests catch regressions: line coverage cannot tell a strong assertion from `assert x is not None`. **It is not yet set up** — it's roadmap item 2.1 (`mutmut`, scoped to changed files as a PR gate plus a periodic full audit over `orch/`). Until then, write every assertion as if a mutant were coming: *"if I change the production code to return a different value / flip this comparison, will this test fail?"* If the answer is no, the assertion is too weak.

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
| Mutation testing | ❌ (2.1) |
| Property-based tests (Hypothesis) on state machines | ❌ (2.2) |
| Flaky/quarantine workflow | ❌ (2.3) |
| Structured dashboard E2E layer | ❌ (3.1) — only ad-hoc `-m browser` tests today |
| Contract / no-5xx route sweep + `schemathesis` | ❌ (3.2) |
| `iw` CLI-contract layer | ⚠️ piecemeal in `tests/integration/cli/` (3.3) |
| Cross-project isolation matrix | ❌ (3.4) |
| Security test module (live-DB-guard net, authz negatives, doc-render SSRF) | ⚠️ partial (`test_chat_security`, the guard fixture) (3.5) |
| Data-layer module (migration round-trip / FTS invariant / per-worktree-DB skew) | ⚠️ partial (`migration-check` exists) (3.6) |
| Visual regression for rendered HTML/PDF docs | ❌ (4.1) |
| Performance budgets | ❌ (4.2) |
| Daemon chaos / fault-injection | ❌ (4.3) |
| `tests/factories.py` central entity factory | ❌ |

Update this table and the gate table in §5 as roadmap items land.

---

## 10. Quick reference

```bash
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

## 11. Semgrep finding triage (CR-00051)

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
