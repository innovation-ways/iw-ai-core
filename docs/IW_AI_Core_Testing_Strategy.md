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
| Coverage is a *floor on what's exercised*, not a measure of quality. | Coverage alone is never the only gate. We pair it with structural checks (and, per the roadmap, mutation testing). |
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
| `smoke` | fast critical-path tests; run via `make smoke` (currently ~10; an SLA is roadmap item 1.11) |
| `slow` | deselected by default unless `-m slow` is passed |
| `browser` | drives real Chromium via `playwright-cli`; **deselected by default** (`addopts` `-m 'not browser'`); run via `make test-browser` |

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
| Security — deps & SAST (basic) | `pip-audit` (`-l --strict`) + `bandit` (`-r orch dashboard executor -ll`) | advisory (currently `|| true`) | `make security-deps` (alias `make security-sast`) |
| Security — IaC | `trivy config` HIGH/CRITICAL | exit 1 on findings | `make security-iac` |
| Unit tests | pytest | 100 % pass | `make test-unit` |
| Integration + dashboard tests | pytest + testcontainers | 100 % pass | `make test-integration` |
| Coverage | `coverage.py` (`branch = true`) | `fail_under = 46` (low — raising it is roadmap item 1.2) | enforced via `pytest --cov` (config in `pyproject.toml`) |
| Migration round-trip | pytest `test_migrations_round_trip.py` | 100 % pass | `make migration-check` |
| Smoke | pytest `-m smoke --strict-markers --no-cov` | 100 % pass | `make smoke` |

Coverage is reported in four formats (`term-missing`, `html`, `xml`, `json`) under `tests/output/coverage/`. The dashboard has a coverage page that surfaces it.

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

---

## 9. Known gaps & roadmap

The full phased plan, with per-item rationale, approach, delivery vehicle, and status, lives in [`ai-dev/work/TESTS_ENHANCEMENT.md`](../ai-dev/work/TESTS_ENHANCEMENT.md); the research behind it is [R-00068](research/R-00068-ai-core-test-quality-strategy.md). Summary of where we stand:

| Area | Status |
|------|--------|
| Branch coverage enabled | ✅ (`branch = true`) |
| Coverage failure floor | ⚠️ exists but low (`fail_under = 46`) — raise & ratchet (1.2) |
| Diff/patch coverage on PRs | ❌ (1.3) |
| AST assertion scanner | ❌ (1.1) |
| `ruff` PT rules | ✅ enabled |
| Test-order randomisation (`pytest-randomly`) | ❌ (1.4) |
| Secrets scanning (`gitleaks`) | ❌ (1.6) — currently only in the `iw-oss-publish` skill |
| Semgrep SAST | ❌ (1.9) — `security-sast` is currently just a `bandit` alias |
| `vulture` / `deptry` suite-health | ❌ (1.7) |
| Allure reporting `make` targets | ❌ (1.8) — `allure-pytest` is a dep, targets are `.PHONY`-only stubs |
| Curated smoke layer with SLA | ⚠️ marker exists, no SLA (1.11) |
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
