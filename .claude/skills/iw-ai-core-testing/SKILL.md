---
name: iw-ai-core-testing
version: "1.0.0"
description: IW AI Core testing standards, patterns, and quality rules for writing, reviewing, and designing tests. Covers assertion strength, the live-DB write guard and testcontainer rules, cross-project isolation, state-machine/property-test guidance, TDD with RED evidence, and the test red-flag checklist. Use when writing tests, adding test coverage, reviewing tests, strengthening tests, or designing a test plan for IW AI Core.
allowed-tools: Read, Grep, Glob
---

# IW AI Core — Testing Standards

**This skill is mandatory reading for any agent or session that writes, reviews, or designs tests for IW AI Core.** It supplements the generic `tests-impl` / `backend-impl` / `tests-review` agents with project-specific rules.

- Full strategy: [`docs/IW_AI_Core_Testing_Strategy.md`](../../docs/IW_AI_Core_Testing_Strategy.md)
- Test-suite conventions & gotchas: [`tests/CLAUDE.md`](../../tests/CLAUDE.md)
- Enhancement roadmap: [`ai-dev/work/TESTS_ENHANCEMENT.md`](../../ai-dev/work/TESTS_ENHANCEMENT.md)
- Research basis: [`docs/research/R-00068-ai-core-test-quality-strategy.md`](../../docs/research/R-00068-ai-core-test-quality-strategy.md)

---

## 0. The one rule that matters

**Nearly all of IW AI Core's production *and* test code is written by LLM agents.** AI-generated tests frequently *pass while catching nothing*. Before writing each assertion, ask:

> **"If I change the production code to return a different value, flip this comparison, or delete this line — will this test fail?"**

If the answer is *no*, the assertion is worthless. Strengthen it or delete the test. Every assertion must be one a future mutation-testing run would expect to kill a mutant with.

---

## 1. Assertion strength (NON-NEGOTIABLE)

### Anti-patterns to NEVER write

```python
# BAD — tautological; survives every mutation
assert result is not None
assert isinstance(result, dict)
assert len(result) > 0
assert "status" in result
assert result  # truthiness
```

```python
# BAD — asserting on the test's own setup, not on behaviour
mock_session.execute.assert_called_once()
mock_repo.get.assert_awaited()
# (a test whose ONLY assertion is a mock-call check is a red flag)
```

```python
# BAD — too broad; survives string/type mutations
with pytest.raises(Exception):
    do_thing()
```

### Patterns to ALWAYS use

```python
# GOOD — assert specific values; kills return/arithmetic/constant mutations
assert result["fix_cycle"] == 3
assert result["status"] == WorkItemStatus.MERGED
assert batch.items_done == 4
assert ratio == pytest.approx(0.75)
assert next_id == "I-00082"
```

```python
# GOOD — assert error type AND message; kills string mutations
with pytest.raises(LiveDbConnectionRefusedError, match=r"refusing to connect") as exc:
    safe_create_engine(...)
assert str(exc.value).startswith("Live DB")
```

```python
# GOOD — assert EVERY field of a returned structure, not just one
result = aggregate_jobs(session, project_id=p.id)
assert result.batches == 2
assert result.code_index == 1
assert result.doc_generation == 0
assert result.research_drafts == 1
assert result.total == 4
```

```python
# GOOD — assert state transitions explicitly, at boundaries
# fix-cycle cap is 5: test exactly at 4→5 and the rejected 5→6
item.fix_cycle = 5
with pytest.raises(FixCycleExhausted):
    item.start_fix_cycle()
```

### What kills which mutation (write the assertion that kills it)

| Mutation | Killed by |
|----------|-----------|
| `return x` → `return None` | assert the *specific* return value, not `is not None` |
| `>` → `>=`, `<` → `<=` | test at the exact boundary value |
| `"text"` → `"XXtextXX"` | assert `match=`, `.startswith()`, `.endswith()`, or `in` on the message |
| `and` → `or`, `or` → `and` | test cases where each condition matters independently |
| `+` → `-`, `*` → `/` | assert the specific computed value (with `pytest.approx` for floats) |
| `, `.join → `XX, XX`.join | assert the exact formatted string |
| statement deletion | assert the side effect that statement produces |

> **Statically enforced (CR-00046):** the no-assert / tautology / mock-only / `pytest.raises(Exception)`-without-`match=` bans above are checked by `scripts/check_test_assertions.py` and run as `make test-assertions`, the dedicated `assertions` daemon QV gate (right after `lint`), and a step in `.github/workflows/test-quality.yml`. A new violation in a new test file fails CI. The right fix is to *strengthen the test*; the baseline file `tests/assertion_free_baseline.txt` tracks the existing cleanup backlog only — it is **not** for silencing new violations.

---

## DB-column documentation gate (CR-00085, P4-4.5)

`scripts/check_db_column_docs.py` is a static SQLAlchemy-mapper-walking
scanner that flags every `Column` declaration missing a `doc=` description.
It runs as `make check-column-docs`, folded into `make quality` warn-first
during the burn-in period, and as a step in `.github/workflows/test-quality.yml`'s
`lint-typecheck` job (also warn-first).

**The rule when you add a new column.** Every new `Column(...)` declaration
on a SQLAlchemy model under `orch/db/` MUST carry a `doc="<one-line description>"`
argument. Example:

```python
class WorkItem(Base):
    foo = Column(Integer, nullable=False, doc="What this column means in one line.")
```

**The committed baseline at `orch/db/column_docs_baseline.txt`** lists today's
undocumented columns so the gate fires only on **NEW** violations. Regenerate
with:

```bash
uv run python scripts/check_db_column_docs.py \\
    --write-baseline orch/db/column_docs_baseline.txt
```

**The right way to silence the gate is to write a `doc=` on the column, not
to add the FQN to the baseline.** The baseline is a cleanup backlog, not an
accept-list — reviewers should push back on baseline growth.

**Reserved-name trap.** Because SQLAlchemy reserves `metadata` on the
declarative base, the `DaemonEvent` table's `metadata` column is bound to
the python attribute `event_metadata`. The scanner walks the SQL columns
via `Base.registry.mappers` → `mapper.local_table.columns`, so it reports
the SQL column name (`metadata`), not the python attribute name. If you
encounter a similar SQLAlchemy-reserved-name collision, follow the same
pattern.

---

## 2. IW AI Core test infrastructure rules (NON-NEGOTIABLE)

### The live-DB write guard — do not fight it

`tests/conftest.py` arms a session-wide guard: it sets `IW_CORE_TEST_CONTEXT=true`, clears leaked operator/daemon/agent flags, and **hijacks `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD`** to an unreachable address. This is defense-in-depth after incident **I-00041** (an opt-out fixture caused a multi-hour outage).

- **NEVER** add a fixture that unsets `IW_CORE_TEST_CONTEXT` or restores `IW_CORE_DB_*` to anything reachable.
- **NEVER** import `dashboard.routers.*` or `dashboard.dependencies` in a **unit** test — those modules build `SessionLocal` on import (`orch.db.session.__getattr__` → `safe_create_engine()`), the guard fires at *collection time* (`LiveDbConnectionRefusedError`), and **every test in the file fails before any test body runs**. To unit-test a pure function from a router module: (a) extract it to a DB-free utility module, or (b) use a testcontainer `db_session` + `app.dependency_overrides[get_db]` (see `tests/dashboard/test_jobs_filter_ui.py`).
- A test that *needs* to monkeypatch `IW_CORE_DB_*` (e.g. `test_db_identity_integration.py`) is fine — its per-test `monkeypatch` overrides the session default within scope.

### testcontainers Postgres — the fixtures

| Fixture | Scope | What |
|---------|-------|------|
| `pg_container` | session | one PostgreSQL container per pytest run |
| `db_engine` | session | schema via `Base.metadata.create_all()` + FTS DDL, reused |
| `db_session` | function | each test in a transaction, **rolled back** at teardown |
| `test_project` | function | a `Project` row inside `db_session`; use its `id` for any work item / batch / doc |
| `cli_get_session` | function | a `get_session` factory yielding `db_session` |

Unit tests that just need to *mock* DB calls get a `MagicMock` `db_session` from `tests/unit/conftest.py`.

### Data-layer test package — `tests/integration/data_layer/` (CR-00076)

A consolidated package for the hard-won data-layer invariants. Three modules:

| Module | Asserts | Extends (does not replace) |
|--------|---------|----------------------------|
| `test_fts_trigger_invariant.py` | every `tsvector` column is populated on INSERT and refreshed on UPDATE by its FTS trigger — parametrized one case per column | `test_work_items_functional_doc_fts.py` |
| `test_migration_revision_skew.py` | `alembic upgrade head` against a DB whose `alembic_version` names a revision absent from the graph raises `CommandError: Can't locate revision identified by` — the I-00075/76 failure, pinned as a regression | `test_migrations_round_trip.py` |
| `test_db_identity_invariants.py` | the match / mismatch / bootstrap / missing-row paths of `orch/db/identity.py` | `test_db_identity_integration.py` |

`make data-layer-check` runs `make migration-check` then the package.

**Extending it:**
- New `tsvector` column → add one `(table, tsvector_column, [searchable_text_columns])` tuple to `TSVECTOR_COLUMNS` in `test_fts_trigger_invariant.py`; a parametrized case is generated automatically.
- New DB-identity edge case → add a test to `test_db_identity_invariants.py`.
- The skew module is **test-only** — it pins the failure, it adds no runtime skew guard. Any `alembic downgrade` here targets a specific revision ID, never `-1` (`tests/CLAUDE.md` rule 4a). To exercise a "behind head" DB, `command.upgrade` to a specific old revision — never rewrite `alembic_version` under a head-schema DB (the second upgrade would re-run already-applied `CREATE TABLE`s).

### pytest-randomly — test-order randomisation (CR-00055, 2026-05-16 — default-on)

`pytest-randomly` is **ON by default** (CR-00055, 2026-05-16). The integration + dashboard suite is robust to randomisation via per-test PostgreSQL template-clone (`pgtestdbpy>=0.0.1`): a session-scoped template DB is migrated once; each test gets its own fresh clone (~25 ms via `CREATE DATABASE … TEMPLATE …` with WAL_LOG strategy override); `IW_CORE_DB_*` env vars are monkeypatched per-test so `iw` CLI subprocesses inherit the isolated clone. 3 module-scoped `migrated_engine` tests are quarantined `@pytest.mark.xfail(strict=False)` as carry-forward. Verified green across 4 reference seeds (12345/67890/11111/42424).

The seed is printed at the top of every run: `Using --randomly-seed=<N>`.

**Reproduce a specific seed:**

```bash
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
  -p randomly --randomly-seed=<N> -q --no-cov
```

**If a test fails under random order but passes in fixed order**, it is **order-dependent** — a test isolation bug. Fix the leaking side effect or quarantine it with `@pytest.mark.order_dependent` (registered in `pyproject.toml`) + a tracking comment. A quarantined test that genuinely cannot pass under random order must also carry `@pytest.mark.xfail(strict=False, ...)` and a `# NOTE(P1-CR-C-followup-randomly):` tracking comment.

**Quarantine policy:** The 3 known quarantines are module-scoped `migrated_engine` tests. A follow-up CR (`P1-CR-C-followup-randomly-quarantine-cleanup`) will scope those engines down to function level.

**Earlier fallback (CR-00048):** `-p no:randomly` was in `addopts` 2026-05-13 → 2026-05-16; superseded by CR-00055's per-test template-clone strategy.

### Quarantine workflow (CR-00061, P2-CR-C)

A test is quarantined when it intermittently fails for a reason we haven't root-caused,
**OR** when it requires a specific test ordering we haven't fixed. **Quarantining a test
is not free**: it removes the test's signal from the merge gate.

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

The three surfaces: (a) `addopts` deselects `quarantine` on the merge gate; (b) `make test-quarantine` runs only quarantined tests with `--reruns 1`; (c) `make test-flake-detect` runs the full suite 3× and reports any test whose outcome disagreed across runs (a flake).

### Hard rules (also in `tests/CLAUDE.md`)

1. **NEVER** connect to the live DB (port 5433) — testcontainers only, random ports.
2. **NEVER** `importlib.reload(orch.config)` — it re-runs `load_dotenv()`, restoring deleted env vars. Use `monkeypatch.delenv()`.
3. **NEVER** mock the database in integration tests — `SELECT FOR UPDATE` locking cannot be tested with mocks.
4. **NEVER** run raw `docker` / `docker compose` / `docker-compose` from test code — only `testcontainers` fixtures. Don't stop/remove containers in teardown; let the fixture lifecycle handle it.
5. **NEVER** invoke `alembic` directly from test code outside the dedicated migration-round-trip test; there, downgrade to a *specific revision ID*, never `-1`.
6. **MUST** replace the psycopg2 URL: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
7. **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` — the FTS trigger is raw SQL.
8. `DaemonEvent.metadata` is `event_metadata` in Python (SQLAlchemy reserves `metadata`).
9. The per-worktree DB (F-00062, present when a project ships `ai-dev/iw-config/`) is **not** the test DB — tests spin up their own testcontainer and must never assume it exists.

### Session-scoped app/client (dashboard tests)

- **NEVER** create new function-scoped `app` or `client` fixtures — use the session-scoped ones from `tests/dashboard/conftest.py`.
- **NEVER** assign `app.state.x = mock` directly — it leaks to other tests. Use `monkeypatch.setattr(app.state, "attr", mock)` or save/restore in `finally`.
- Inject the test DB via `app.dependency_overrides[get_db]` — never reach for the live session.

---

## 3. Cross-project isolation (IW AI Core's "tenancy")

IW AI Core is **multi-project** (`projects.toml` → `Project` rows). Project A's data must never appear in Project B's dashboard pages, RAG answers, job lists, or worktrees; project-scoped `iw` commands must never touch another project's rows; and the *global* views (`/docs`, `/jobs`) must aggregate *across* projects.

When you add or change a project-scoped route, query, or `iw` command, add an isolation assertion: create two `Project` rows, populate one, assert the other's scoped view is empty and the global view aggregates.

Also keep the two DBs separate in tests: the agent runtime uses `IW_CORE_DB_*` (per-worktree DB); the orch DB is `IW_CORE_ORCH_DB_*` on 5433. Never let a test assume they're the same.

### The cross-project isolation matrix (CR-00074)

`tests/integration/test_cross_project_isolation.py` is the systematic matrix that proves tenancy isolation. It seeds two fully-populated projects via the **`second_project`** fixture (`tests/integration/conftest.py`, backed by `tests/fixtures/dual_project_seed.py` — both projects get a work item, a batch, an architecture doc, a research doc, a code-index row and a doc-generation row with guaranteed-distinct identifiers), then runs a parametrized suite across four axes:

- **Axis 1 — dashboard-route isolation**: each project-scoped list/index route, scoped to project B, renders B's own identifier and **none** of project A's.
- **Axis 2 — `iw`-command isolation**: read commands leak no A identifiers in their output; mutating commands leave A's rows byte-for-byte unchanged while changing B's.
- **Axis 3 — global-aggregation positive assertion**: the global `/docs` surfaces aggregate **both** projects.
- **Axis 4 — per-worktree-DB vs orch-DB boundary (F-00062)**: `orch/config.get_db_url()` / `get_orch_db_url()` resolve `IW_CORE_DB_*` / `IW_CORE_ORCH_DB_*` to distinct databases, including the `_prefer` fallback.

A module-level **`KNOWN_LEAK`** dict (keyed by route path / command label) absorbs any *genuine* pre-existing leak — each entry carries a filed high-priority Incident ID and `xfail`s that case. A real leak is fixed in a separate Incident; the matrix CR stays test-only.

**How to extend it**: when you add a new project-scoped dashboard route or `iw` command, consider it for the matrix — add a parametrized case to Axis 1 (`_AXIS1_ROUTES`) or Axis 2 (`_AXIS2_COMMANDS`). If the matrix surfaces a genuine leak, add a `KNOWN_LEAK` entry + file a high-priority Incident — never fix production code inside the test CR. Run `make test-isolation` to verify.

---

## 4. State machines & property testing

IW AI Core is full of state machines and parsers — the natural targets for invariant-style and Hypothesis property tests:

- **Work-item lifecycle** — invariants: never reach a terminal state with an open fix cycle; never exceed the fix-cycle cap (5); a merged item is never re-queued.
- **Batch lifecycle** — invariant: batch status is a pure function of its items' statuses; a held/paused batch launches no new items.
- **`iw next-id`** — monotonic, never reuses an ID, atomic under concurrency (needs a real testcontainer).
- **Doc versioning / diff** (`orch/doc_diff.py`, `orch/doc_sections.py`) — round-trip and idempotence: split→merge is identity; re-diffing is stable.
- **RAG chunking** (`orch/rag/`) — chunk boundaries partition the source; re-chunking is stable.

### Property-based tests (Hypothesis — CR-00060, P2-CR-B)

Five property-test modules are implemented under `tests/unit/properties/`:

| Module | Target | Pattern |
|--------|--------|---------|
| `test_work_item_lifecycle_properties.py` | WorkItem lifecycle | `RuleBasedStateMachine` + 4 invariants |
| `test_batch_lifecycle_properties.py` | Batch status | `@given` pure-function properties |
| `test_fix_cycle_cap_properties.py` | Fix-cycle cap | `RuleBasedStateMachine` |
| `test_doc_diff_round_trip_properties.py` | Doc diff round-trip | `@given` with `assume()` for pathological inputs |
| `test_iw_next_id_atomicity_properties.py` | `allocate_next_id` concurrency | `RuleBasedStateMachine` + `ThreadPoolExecutor` |

**When to add a new property module:** the target is an invariant violation across a large input space that example tests can't enumerate. The five above are the canonical targets for this project.

**Choosing RuleBasedStateMachine vs `@given`:** use `RuleBasedStateMachine` when modelling a stateful entity with multiple allowed transitions (work-item lifecycle, fix-cycle counter). Use `@given` when testing a pure function with arbitrary inputs (batch status, doc-diff round-trip). Use `assume()` to skip pathological inputs rather than silently passing — a test that accepts everything passes everything.

**The `properties` marker** is auto-applied to every test in `tests/unit/properties/` by `pytest_collection_modifyitems` in `tests/unit/properties/conftest.py` — no per-test decorator needed.

**Profiles:** the `ci` profile (`derandomize=True`, 20 examples, 2000 ms deadline) is the merge gate and runs as part of `make test-unit`. The `dev` profile (200 examples, 5000 ms deadline) is the local default. The `deep` profile (1000 examples, no deadline) is on-demand via `make test-properties-deep`. Select via `$IW_HYPOTHESIS_PROFILE`.

---

## 5. TDD — RED, GREEN, REFACTOR (and record the RED)

`backend-impl` writes the test **first**:

1. **RED** — write a failing test that defines the expected behaviour. *Run it; confirm it fails for the right reason.* Record the failing-test output in your execution report.
2. **GREEN** — write the minimal implementation to make it pass.
3. **REFACTOR** — clean up while keeping every test green.

The test is written before the implementation — not after, not alongside. A test added *after* the code tends to confirm "what the code does" rather than "what it should do". (Recording RED evidence is being formalised — roadmap item 0.4.)

---

## 8. Quality gates you must leave green

`make check` = `make quality` (`lint` → ruff + `lint-js` + `lint-templates`; `format-check`; `typecheck` → mypy; `test-assertions` → assertion scanner) + `make test` (unit + integration + dashboard). `make quality` also runs `make dead-code` (`vulture`) and `make dep-check` (`deptry`) — **informational / warn-only this CR**; they flip to hard gates after a burn-in follow-up. Also keep `make migration-check` and `make smoke` passing if your change touches migrations or critical paths. Coverage has a `[tool.coverage.report] fail_under` floor (set just below measured branch coverage and **ratcheted up over time, never down** — CR-00047, roadmap 1.2): don't drop it; `make diff-coverage` is the dedicated diff-coverage QV gate (new/changed Python lines must be ≥~90% covered vs `origin/main` — CR-00047, roadmap 1.3). The browser layer (`make test-browser`) is not in `make test` — run it when you touch browser flows. The **8** daemon QV gates: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests` → `diff-coverage` → `security-secrets` (gitleaks, CR-00050). The pre-commit hook is the developer's first line of defense — `gitleaks/gitleaks` at `v8.30.1` is wired in `.pre-commit-config.yaml`. Semgrep (`security-sast`) runs `uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor` locally; the GH `semgrep` job uses `continue-on-error: true` during burn-in (informational only; findings are visible in Code Scanning but never block a merge — flip to blocking in `P1-CR-D-followup-semgrep-block`).

**Mutmut (CR-00080 status):** scope is widened to `orch/` (whole backend) — config widened, gate wiring deferred. Keep using on-demand runs via `make mutation-check MODULE=...` / `make mutation-audit`. CR-00080 attempted a blocking nightly GH workflow gate, but the viability guard fired (**M=0%**, **K=55**); wiring is deferred until this next step is done: **Expand test coverage in the most-mutated modules (see per-module breakdown in evidence file), then re-run this CR. Alternatively, run a longer manual spike (`make mutation-audit` outside the 3600s budget) to gather more data before re-running.** Earlier behaviour (CR-00059): daemon-only scope (`orch/daemon/`), informational/on-demand only.

Full gate table: `docs/IW_AI_Core_Testing_Strategy.md` §5.

---

## 9. Test red-flag checklist (for `tests-review` and any reviewer)

Flag a test for scrutiny / rework if **any** apply:

- [ ] Its only assertion is `is not None` / `isinstance(...)` / `len(...) > 0` / `"k" in x` / truthiness.
- [ ] Its only assertion is a `mock.assert_called_*` / `mock.assert_awaited_*`.
- [ ] It mocks every dependency, including the unit under test (no real logic exercised).
- [ ] Its name describes implementation structure (`test_calls_X`, `test_uses_Y`) not behaviour.
- [ ] It has 0–1 assertions for logic with 3+ code paths.
- [ ] It uses `time.sleep()` / a hardcoded delay.
- [ ] It tests no error/exception path for code that has one.
- [ ] `pytest.raises(Exception)` or `pytest.raises(...)` with no `match=`.
- [ ] Multiple statements inside a `pytest.raises` block.
- [ ] A snapshot/golden-file test whose baseline was regenerated rather than reviewed.
- [ ] It imports `dashboard.routers.*` / `dashboard.dependencies` in a unit test without a `db_session` in scope (will fail at collection).
- [ ] It would still pass if you deleted the production line it's supposed to cover.
- [ ] **It only passes in fixed order** — this is an order-dependence smell: the test (or a fixture it uses) leaks state to other tests. Fix the leak or mark it `@pytest.mark.order_dependent` with a tracking comment.

---

## 10. Security test module (CR-00075)

A dedicated security regression package lives at `tests/integration/security/`:

| Module | Target risk class |
|--------|-------------------|
| `test_live_db_write_guard.py` | Live-DB write guard regression (I-00041 class) — guard fires in test/agent contexts |
| `test_authz_negative_paths.py` | Authorization negative paths — protected routes return 4xx for unauthenticated/cross-project access |
| `test_doc_render_ssrf_path_traversal.py` | SSRF and path-traversal in doc rendering — `file://`, `../../etc/passwd`, `http://localhost` all blocked |
| `test_agent_context_env_handling.py` | Agent-context env-var bypass — `IW_CORE_AGENT_CONTEXT` blocks operator-only commands; bypass attempts blocked |

**How to extend:** add a new module under `tests/integration/security/` for each new security risk class. The module name describes the risk class, not the entry point. Every test must have a meaningful behavioural assertion — see §1.

**Genuine vulnerability handling:** if a test surfaces a real SSRF, path-traversal, or a guard that does not fire, do NOT fix it within the current CR:
1. Write the test as the **failing reproduction** (it fails on current `main`).
2. Mark it `@pytest.mark.xfail(strict=False, reason="I-NNNNN: <one-liner>")` with a `# NOTE: genuine vulnerability — tracked in I-NNNNN` comment.
3. File a **high-priority security Incident** via `/iw-new-incident`.
4. Report it as a blocker in your step report's `blockers` section. The fix is a separate CR.
5. `scope.allowed_paths` enforces this at merge time — production code under `orch/` / `dashboard/` is excluded.

**Run the security module:**
```bash
make test-security-module   # convenience target — runs only security tests
# also runs as part of:
make test-integration       # all integration tests including security
```

**No real network I/O:** SSRF/path-traversal tests mock `httpx` and assert the mock is never called with an internal URL. No test touches the live DB (port 5433).

---

## 11. Contract test layer (CR-00072)

Two contract-level modules under `tests/dashboard/` prove the dashboard's HTTP surface *as a whole* — a broken router import, a typo'd template, or an unhandled exception is caught the moment any route 5xx's, instead of when a human hits the page.

| Module | What it does | Runs when |
|--------|--------------|-----------|
| `test_route_contract_sweep.py` | Enumerates every route on `create_app()`; requests each GET/HEAD route against a seeded testcontainer `TestClient` (`raise_server_exceptions=False`) and asserts `status_code < 500`. Parametrized one case per route. | **Blocking** — inside `make test-integration`; convenience `make test-route-sweep`. |
| `test_schemathesis_contract.py` | `schemathesis` property-fuzzes the JSON API operations against the OpenAPI schema, asserting `not_a_server_error`. Marked `contract_fuzz`. | **Periodic** — `make test-contract-fuzz` + nightly `contract-fuzz.yml`; excluded from the default suite. |

**How the sweep stays honest:**
- **Skip set** (`SKIP_ROUTES`) — SSE/streaming routes, the static mount, FastAPI's OpenAPI/Swagger endpoints, AI-runtime-gated chat endpoints. Each entry carries a one-line rationale.
- **Path parameters** resolve from a seeded dataset (`seed_contract_test_data` in `tests/dashboard/conftest.py`); a route whose parameters cannot all be resolved goes into `UNRESOLVED`, asserted against an explicitly-reviewed `EXPECTED_UNRESOLVED` set.
- **`EXPECTED_5XX`** — a genuine pre-existing handler bug is allowlisted (route → `TODO(file-incident)` rationale), the case `xfail`-ed; the operator files the Incident on `main` post-merge. **Never fix production code to make the sweep pass** — investigate, and allowlist only genuine bugs (most 5xx are harness artefacts: better seed data / a resolvable parameter).

**Extending it:**
- A **newly-added route is swept automatically** — no test change needed. If the new route needs a path parameter the sweep can't resolve, `test_unresolved_routes_match_expected` fails — seed the entity (so it resolves) or add the route to `EXPECTED_UNRESOLVED` with a rationale.
- A **newly-added JSON endpoint** (handler returning `JSONResponse` / a pydantic model) should be added to `JSON_API_PATHS` in `test_schemathesis_contract.py` so schemathesis fuzzes it. HTML/htmx routes are *not* fuzzed — the route sweep covers those.
- A genuine 5xx schemathesis surfaces goes in `KNOWN_CONTRACT_5XX` (excluded from the fuzz, surfaced as operator follow-up) — same "never fix production code in-CR" rule.

## 12. CLI contract layer (CR-00073)

The `iw` CLI is the agent-to-DB bridge — every agent call passes through it. The **CLI contract layer** makes its exit-code / stdout / DB-effect contract a tested invariant.

**Per-command contract tests** live in `tests/integration/cli/test_<command>_contract.py` — one file (a test class or grouped functions) per priority command. For each command they assert, against the testcontainer `db_session`:

| Assertion | What it checks |
|-----------|----------------|
| Exit code 0 | every documented success path |
| Non-zero exit + stderr | every documented error path, with a clear message asserted via `in` / `match=` |
| stdout shape | the documented format — `json.loads` the output and assert specific fields, or pattern-match |
| DB effect | the row(s) created or mutated — query the model after the command and assert the changed fields |
| Idempotence / atomicity | where the spec promises it (`next-id` unique under a `ThreadPoolExecutor`; `register` re-registration is a no-op) |

Use Click's `CliRunner` for in-process commands — inject the test session via `obj={"get_session": cli_get_session}` so the command never touches `orch.db.session`. Use `subprocess` invocation where a command spawns subprocesses or relies on process-level env vars (the `db_engine` fixture monkeypatches `IW_CORE_DB_*` so a subprocess inherits the per-test clone). Match the existing files under `tests/integration/cli/`.

**Spec-conformance** is `tests/integration/test_cli_spec_conformance.py`: it parses the §4 "Command Summary" ASCII tree of `docs/IW_AI_Core_CLI_Spec.md`, introspects the live Click command tree (`orch.cli.main`), and asserts bidirectional coverage plus contract-test coverage. Two module-level allowlists make it a *ratchet*: `KNOWN_SPEC_DRIFT` (existence drift — each entry carries an Incident ID or rationale + a `"direction"`) and `KNOWN_UNTESTED_COMMANDS` (the coverage gap — pre-seeded with every non-priority command).

**How to extend:**

- **Adding contract coverage for a new command** → create `tests/integration/cli/test_<command>_contract.py` with the five assertion classes above, then **remove that command from `KNOWN_UNTESTED_COMMANDS`** in `test_cli_spec_conformance.py` (shrinking that allowlist is the explicit follow-up).
- **Adding a new CLI command** → document it in `docs/IW_AI_Core_CLI_Spec.md` §4, then re-run `make test-cli-contract`; the conformance test fails until §4 and the contract-test (or `KNOWN_UNTESTED_COMMANDS`) coverage are both in place.
- **Updating the spec** → after editing §4, re-run the conformance test to verify bidirectional coverage still holds.
- **A genuine CLI bug surfaced by a contract test** → mark the test `@pytest.mark.xfail` (or record it in a `KNOWN_CLI_BUG` allowlist in that contract file) with a filed Incident ID — never fix production code in a test CR. A CLI bug is neither spec drift nor a coverage gap, so it does **not** belong in `KNOWN_SPEC_DRIFT` or `KNOWN_UNTESTED_COMMANDS`.

**Run the layer:**
```bash
make test-cli-contract      # per-command contract tests + conformance check
# also runs as part of:
make test-integration       # all integration tests including the CLI contract layer
```

## 13. E2E browser journey layer (F-00088)

Six structured journey modules under `tests/e2e/` drive a real Chromium via `playwright-cli` (never `agent-browser`, `chromium.launch()`, or `npx playwright install` — per the root `CLAUDE.md`):

| Journey module | What it exercises |
|----------------|-------------------|
| `test_journey_home_navigation.py` | Dashboard home → project → cross-tab navigation (Queue / Code / Docs / Jobs) |
| `test_journey_queue_to_merge.py` | Queue → approved item → batch creation → batch detail |
| `test_journey_code_qa_sse.py` | Code Q&A: SSE stream renders incrementally with citations |
| `test_journey_docs_export.py` | Docs: HTML and PDF export round-trip |
| `test_journey_jobs_filters.py` | Jobs page multi-select filter interactions |
| `test_journey_htmx_fragments.py` | htmx browser runtime: no dangling hx-target, no console errors, interactive swaps |

**Markers:**
- `@pytest.mark.e2e` — all six; excluded from default `pytest` selection (`addopts`)
- `@pytest.mark.e2e_smoke` — `home_navigation` + `queue_to_merge` only; **blocking** on `pull_request` / `push` via `.github/workflows/e2e.yml`

**Execution:** `make test-e2e` (all 6), `make test-e2e-smoke` (2 smoke), CI `.github/workflows/e2e.yml`.

**Journey conventions:**
- Every journey asserts `pw.assert_accessibility()` on ≥1 page and `pw.assert_no_console_errors()` throughout.
- Screenshots go to `IW_E2E_EVIDENCE_DIR` (default: `tests/e2e/_artifacts/`).
- Navigation is via the UI (snapshot + click), never hardcoded URLs (except the initial `goto`).
- Seed via `scripts/e2e_seed.py` — extend idempotently if a journey needs rows.
- Every module carries a one-line comment naming the single assertion whose inversion proves the journey can fail (RED run executed at S14 against the live stack).

**Adding a new journey:**
1. Create `tests/e2e/test_journey_<name>.py`.
2. Mark `@pytest.mark.e2e` (promote to `e2e_smoke` only if <30 s, covers a critical path, ≤2 total in smoke).
3. Assert `pw.assert_accessibility()` and `pw.assert_no_console_errors()` on at least one page.
4. Add the one-line assertion-inversion comment.
5. Extend `scripts/e2e_seed.py` idempotently if needed. Document the extension in the step report.

**Relationship to CR-00072:** `test_journey_htmx_fragments.py` (Journey 6) is the browser-level complement to `test_route_contract_sweep.py`. CR-00072 exercises every GET route via TestClient with no JS/HTMX runtime — it asserts no 5xx. Journey 6 exercises the same routes in a real browser and asserts htmx attributes resolve, no client-side errors, and no dangling `hx-target` references. They are complementary, not redundant.

**TDD for the E2E layer:** Browser journeys are not subject to classic RED-GREEN (they require a live stack). The "every test can fail" requirement is satisfied via two in-scope mechanisms:
- **Harness self-check unit tests** (`tests/e2e/test_harness_selfcheck.py` — unmarked, run as normal unit tests): pure failure-detection logic (console-error parsing, accessibility check, dangling-`hx-target` detector, SSE-timeout detector) is fed synthetic bad input and asserted to flag the failure. RED evidence is recorded in the step report.
- **Per-journey assertion inversion:** each journey module contains a one-line comment naming the single behavioural assertion whose inversion proves the journey can fail. The actual RED run is executed at S14 (`qv-browser`) against the live stack — not in this step.

**Scope discipline:** the E2E layer is strictly test-infrastructure. No production code in `orch/` / `dashboard/` / `executor/` may be edited. The merge-time `scope.allowed_paths` gate enforces this.

## 14. Visual regression — patterns and baseline-management rules

The visual layer (`make visual-regression`) protects rendered docs (HTML + PDF) from CSS/template regressions.

- Add a baseline for every new editorial category shipped under `doc-system/`.
- Intentional baseline updates must be review-gated PRs that touch `tests/visual/baselines/**`.
- Never auto-accept diffs in tests (forbidden pattern: "if diff > threshold, overwrite baseline").
- Follow the Playwright CLI rules in the repository `CLAUDE.md` (use `playwright-cli` only; no `agent-browser`, no direct Playwright API).
- Keep pixel tolerance disciplined: one shared constant per layer; do not inflate tolerances per test to force green.

---

## 15. Advisory: LLM-as-judge signal (CR-00084)

A judge utility (`scripts/llm_judge_test_review.py`) scores newly-written tests against a three-axis rubric (assertion specificity, behaviour-vs-mock, edge coverage — each 1–5, bucketed STRONG ≥4 / MEDIUM ==3 / WEAK ≤2) and is referenced in the CodeReview step.

### Hook form: DORMANT

The judge exists at `scripts/llm_judge_test_review.py` but **is not invoked** in the current CodeReview step because calibration was **DEFERRED** (ANTHROPIC_API_KEY was unavailable in the worktree during the CR-00084 spike). The hook will be in the DORMANT state until a re-calibration run produces a MET verdict.

**If the hook were LIVE** (after re-calibration produces MET):
- Your newly added test files may be sampled by the judge.
- A per-test advisory JSON line (scores + rationale) may appear in the review report under an "Advisory: LLM-judge scores" subsection.
- **This advisory score never raises the verdict to fail and never increments `mandatory_fix_count`.** It is informational only and never blocks merge.

**If the hook is DORMANT (current state):** the judge exists but the CodeReview agent is instructed not to invoke it pending re-calibration. Full evidence at `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`.

**Re-enable path:** run `make llm-judge-calibrate` once `ANTHROPIC_API_KEY` is available; if the Verdict line reads MET, update §6 of `agents/claude/code-review-impl.md` and `agents/opencode/code-review-impl.md` to the LIVE form.

## 16. Daemon chaos / fault-injection harness (F-00089)

The daemon-chaos harness is a **deterministic fault-injection** layer for daemon poll-loop integration tests. It is not a chaos-monkey system: no random failure, no `kill -9`, no wall-clock flake injection. It gives reproducible failure-mode simulations so recovery paths can be asserted from daemon-mutated DB/event state.

Hook API (source of truth: `tests/integration/daemon_chaos/harness.py` docstring):

- `inject_worktree_setup_failure_after_clone(stage: str = "after_clone") -> None`
- `inject_fix_cycle_always_fails() -> None`
- `inject_agent_stall_after_seconds(seconds: int) -> None`
- `inject_squash_merge_conflict_on_main() -> None`
- `inject_migration_rebase_conflict_revision() -> None`

Scenario-addition checklist:

- Read the harness module docstring first; treat it as the canonical contract.
- Reuse an existing hook when possible; add a new hook to `harness.py` only when no existing hook can model the failure.
- Keep hooks deterministic: no `kill -9`, no `random.*`, no wall-clock-driven race timing.
- Hooks must be idempotent (arming the same hook twice must not corrupt harness state).
- Scenario assertions must target daemon-mutated DB rows and/or daemon-event rows, not only "hook fired" flags.
- If a scenario reveals a genuine daemon bug, mark it `xfail(strict=True)` and file an Incident; do **not** fix daemon production code inside the test CR.
- Keep the determinism meta-test passing (`tests/integration/daemon_chaos/test_harness_is_deterministic.py`).
- If the smoke subset changes (currently S02 + S03), update `Makefile` and `.github/workflows/daemon-chaos.yml` together.

Source of truth: `tests/integration/daemon_chaos/harness.py` docstring and the package-level tests under `tests/integration/daemon_chaos/`.
