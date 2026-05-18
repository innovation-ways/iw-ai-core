# tests/ — Test Suite

pytest-based tests with strict DB isolation rules.

## Required reading (agents writing or reviewing tests)

- **`skills/iw-ai-core-testing/SKILL.md` — MUST read before writing, reviewing, or designing any test.** Assertion-strength rules, the live-DB-guard / testcontainer rules, cross-project isolation, state-machine/property guidance, the test red-flag checklist.
- **`docs/IW_AI_Core_Testing_Strategy.md`** — the full strategy: layers, infrastructure, conventions, quality gates, known gaps, roadmap.
- **`ai-dev/work/TESTS_ENHANCEMENT.md`** — the phased plan for improving testing here (status of each item).

## TDD & test quality (NON-NEGOTIABLE)

- **TDD = RED → GREEN → REFACTOR.** `backend-impl` writes the failing test first, *runs it and confirms it fails for the right reason*, records the RED output in its execution report, then writes the minimal implementation, then refactors with tests green. Tests are written *before* the implementation — not after, not alongside.
- **Coverage is a floor on what's exercised, not the gate.** A high coverage number with weak assertions is the failure mode, not the goal. Coverage has a `fail_under` floor (`pyproject.toml`); never drop it — but passing it is necessary, not sufficient. Every assertion must be one that would fail if the production code regressed (the "mutation test question" in the testing skill §0).
- **Every test must be able to fail.** If deleting the production line it covers wouldn't fail the test, the test is worthless — strengthen or remove it. Tests assert on *behaviour*, never only on their own mocks.

## Structure

| Path | Purpose |
|------|---------|
| `conftest.py` | Root fixtures: `pg_engine`, `db_session`, `test_project` |
| `unit/` | Fast, no I/O — config, state machine, logic, CLI parsing |
| `integration/` | Real PostgreSQL via testcontainers — models, DB behavior, CLI e2e |
| `dashboard/` | FastAPI TestClient tests — chat a11y/security/templates, code layout/SSE wiring, project onboarding |
| `fixtures/` | Shared test data helpers |

## Testing Rules (NON-NEGOTIABLE)

1. **NEVER** connect to live DB (port 5433) — all DB tests use testcontainers on random ports
2. **NEVER** call `importlib.reload(orch.config)` — it re-runs `load_dotenv()` restoring deleted env vars from `.env`; use `monkeypatch.delenv()` only
3. **NEVER** mock the database in integration tests — `SELECT FOR UPDATE` locking can't be tested with mocks
4. **NEVER** run raw `docker` / `docker compose` / `docker-compose` from test code. The ONLY allowed docker usage in tests is via `testcontainers` fixtures (which self-label under Ryuk and self-destruct). Never stop/remove containers from test teardown — let the fixture lifecycle handle it. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.
4a. **NEVER** invoke `alembic` directly from test code outside of dedicated migration-round-trip tests. In those tests, downgrade to a *specific revision ID*, never `-1`, so the test stays stable as new migrations land on top. Migrations are daemon-driven in production — agents generate, daemon applies. See `docs/IW_AI_Core_Agent_Constraints.md`.
5. **MUST** replace psycopg2 URL from testcontainers before use:
   ```python
   url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
   ```
5. **MUST** run FTS DDL after `Base.metadata.create_all()` — the trigger is raw SQL not captured by SQLAlchemy:
   ```python
   from orch.db.models import FTS_FUNCTION_SQL, FTS_TRIGGER_SQL
   with engine.connect() as conn:
       conn.execute(text(FTS_FUNCTION_SQL))
       conn.execute(text(FTS_TRIGGER_SQL))
       conn.commit()
   ```

## testcontainers Pattern

```python
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_engine():
    with PostgresContainer("postgres:15") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        engine = create_engine(url)
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            conn.commit()
        yield engine
```

## Running Tests

```bash
make test-unit                              # Fast, no containers
make test-integration                       # Starts PostgreSQL testcontainer (~3s)
make quality                                # ruff check + ruff format --check + mypy
make check                                  # quality + all tests

uv run pytest tests/unit/test_config.py -v
uv run pytest tests/integration/test_models.py -v
uv run pytest -k "test_next_id" -v         # Match by test name
```

## Gotchas

- Unit tests must not import `orch.config` at module level if env vars are being patched — import inside the test function or use `importlib` carefully
- **NEVER import `dashboard.routers.*` or `dashboard.dependencies` in a unit test unless a testcontainer `db_session` is in scope.** These modules load `SessionLocal` on import via `orch.db.session.__getattr__`, which calls `safe_create_engine()`. The live-DB guard fires immediately because `tests/conftest.py` redirects `IW_CORE_DB_HOST:PORT` to a blocked address — making any engine URL look like the "live" DB to `is_live_db_url()`. You will see `LiveDbConnectionRefusedError` at *collection time*, before any test body runs, and every test in the file will fail. To unit-test a pure function from a router module (e.g. `_preprocess_mermaid`): either (a) extract it to a utility module with no DB in its import chain, or (b) use the testcontainer-backed `db_session` fixture + `app.dependency_overrides[get_db]` pattern shown in `tests/dashboard/test_jobs_filter_ui.py`.
- Integration test fixtures are `scope="session"` for the container, `scope="function"` for DB transactions (rollback after each test)
- `test_project` fixture creates a `Project` row; tests that create work items must use this project's `id`
- E2E browser-verification fixtures live under `ai-dev/{active,archive}/<item>/e2e_fixtures/*.py` (loaded by `scripts/e2e_seed.py`, NOT pytest). The regression net is `tests/integration/test_e2e_seed.py` — when you add a new fixture or a new model with cross-mapper FKs, run `pytest tests/integration/test_e2e_seed.py` before merging. See the docstring in `scripts/e2e_seed.py` for the parent/child insert-order gotcha.

## Per-worktree DB vs testcontainers (F-00062)

Feature F-00062 introduces a per-worktree Postgres container for app runtime
(started by the daemon when the project ships `ai-dev/iw-config/`).
This is separate from `make test-integration`'s testcontainers.

- `make test-integration` **MUST** continue to use testcontainers (existing rule).
- The per-worktree DB is for the agent's app runtime (e.g., dashboard exercising
  Backend step changes), NOT for tests.
- Tests must NEVER assume the per-worktree DB exists — they spin up their own
  testcontainer.

## pytest-randomly — test-order randomisation

`pytest-randomly` is **ON by default** (CR-00055, 2026-05-16). The integration +
dashboard suite is robust to randomisation via per-test PostgreSQL template-clone
(`pgtestdbpy>=0.0.1`): a session-scoped template DB is migrated once; each test
gets its own fresh clone (~25 ms via `CREATE DATABASE … TEMPLATE …` with WAL_LOG
strategy override — ~10× faster than the library's default `FILE_COPY`);
`IW_CORE_DB_*` env vars are monkeypatched per-test so `iw` CLI subprocesses
inherit the isolated clone — closing the gap that defeated savepoint-only and
per-module-TRUNCATE designs in CR-00049. See
`docs/research/R-00077-pytest-randomly-isolation-strategy.md`.

The per-run seed is printed at the top of every run:

```
Using --randomly-seed=<N>
```

**Reproduce a specific seed:**

```bash
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
  -p randomly --randomly-seed=<N> -q --no-cov
```

**4-seed sweep (verified green on 2026-05-16):**

```bash
for seed in 12345 67890 11111 42424; do
  echo "=== seed $seed ==="
  uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
    -p randomly --randomly-seed=$seed -q --no-cov 2>&1 | tail -3
done
```

**If a test fails under random order but passes in fixed order**, it is
**order-dependent** — a test isolation bug (state leaking between tests).
Fix the leaking side effect (or quarantine it with `@pytest.mark.order_dependent`
+ a tracking comment). A quarantined test that genuinely cannot pass under
random order must also carry `@pytest.mark.xfail(strict=False, ...)` and a
`# NOTE(P1-CR-C-followup-randomly):` tracking comment.

**Quarantine policy:** The 3 known quarantines are module-scoped `migrated_engine`
tests in `test_db_identity_integration.py`, `test_pending_migration_log_migration.py`,
and `test_i_00062_migration.py`. A follow-up CR (`P1-CR-C-followup-randomly-quarantine-cleanup`)
will scope those engines down to function level.

**Earlier fallback (CR-00048):** `-p no:randomly` was in `addopts` from 2026-05-13
to 2026-05-16 after 5 fix cycles could not converge; superseded by CR-00055's
per-test template-clone strategy.

## Quarantine workflow (CR-00061, P2-CR-C)

A test is quarantined when it intermittently fails for a reason we haven't root-caused,
**OR** when it requires a specific test ordering we haven't fixed. **Quarantining a test
is not free**: it removes the test's signal from the merge gate, so the bug it was
guarding for can land unnoticed.

**The rules:**

1. Before adding `@pytest.mark.quarantine`, run `/iw-new-incident` and file an Incident
   describing the suspected cause and the test name(s). Use the Incident ID in the
   marker's `reason` argument.
2. The marker MUST carry a `reason` string of the form `"I-NNNNN: <one-liner — suspected
   cause + when added>"`. Example:
   ```python
   @pytest.mark.quarantine(reason="I-00099: race in foo() when bar is concurrent; added 2026-05-18")
   ```
3. The Incident's `Description` field must name the test(s) verbatim so a `git grep`
   from the test name finds the tracking ticket.
4. To remove the marker: run `make test-quarantine` for 3 consecutive runs (or 7 calendar
   days, whichever is more); if the test passed all of them, the marker can come off and
   the Incident can be closed with `verdict: not-reproducible`. (If it failed any run,
   root-cause it first.)
5. The existing `@pytest.mark.order_dependent` is a narrower flavour of `quarantine` —
   both are excluded from the merge gate; pre-existing `order_dependent`-marked tests
   are NOT migrated by CR-00061 (they carry their own tracking from CR-00048/55); new
   quarantines default to `quarantine`.

## Property tests (CR-00060, P2-CR-B)

Five Hypothesis property-based test modules live under `tests/unit/properties/`:

| Module | Target | Pattern |
|--------|--------|---------|
| `test_work_item_lifecycle_properties.py` | WorkItem lifecycle invariants | `RuleBasedStateMachine` |
| `test_batch_lifecycle_properties.py` | Batch status pure-function properties | `@given` |
| `test_fix_cycle_cap_properties.py` | Fix-cycle cap enforcement | `RuleBasedStateMachine` |
| `test_doc_diff_round_trip_properties.py` | Doc diff round-trip | `@given` |
| `test_iw_next_id_atomicity_properties.py` | `allocate_next_id` concurrency | `RuleBasedStateMachine` + `ThreadPoolExecutor` |

**When to add a new property test:** when the class of bug is an *invariant violation* across a state space too large to enumerate exhaustively with example tests (e.g. "a merged work item never transitions back to in-progress"). If a property test already exists for the same target, add cases to it rather than creating a new file.

**RuleBasedStateMachine vs `@given`:** use `RuleBasedStateMachine` when modelling a multi-step state machine (the work item and fix-cycle modules); use `@given` when testing a pure function with arbitrary inputs (the batch status and doc-diff modules). Use `assume()` inside a `@given` to skip pathological inputs — never silently pass.

**The `properties` marker is auto-applied** to every test in `tests/unit/properties/` by a `pytest_collection_modifyitems` hook in `tests/unit/properties/conftest.py` — no per-test `@pytest.mark.properties` decorator is needed.

**CI profile (`ci`):** runs as part of `make test-unit` via the conftest default (`IW_HYPOTHESIS_PROFILE=ci`). Must be <30 s wall-clock. `derandomize=True` makes it deterministic.

**Deep profile:** `make test-properties-deep` for on-demand thorough sweeps (1000 examples, full shrinking).

## Smoke layer SLA (CR-00052, P1-CR-E)

`make smoke` runs the curated `@pytest.mark.smoke` set. **Contract:**

- **<=15 tests** total (count by `grep -rc "@pytest.mark.smoke" tests/`).
- **<60 s** wall-clock on a clean dev environment (measured 2026-05-14: ~13s).
- **Covers 5 critical paths**: daemon-worktree-start, dashboard-main-pages, iw-next-id, work-item-queue, /healthz.

Each path has >=1 smoke test mapped to it (audit table in CR-00052's S01 report). Adding a new `@pytest.mark.smoke` decorator requires:

1. Identifying which critical path it covers (or adding a new path to the contract and updating this doc).
2. Re-auditing the count — if it would push the total over 15, **remove** a redundant existing decorator or **don't add** the new one.
3. Re-measuring wall-clock — if it would push over 60 s, profile and trim.

The contract is currently **prose-enforced** — no `make smoke-sla` command. A future follow-up may add mechanical enforcement if drift happens (see TESTS_ENHANCEMENT.md §5 / P1-CR-E-followup-sla-enforcement, not yet filed).
