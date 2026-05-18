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

When you add or change a project-scoped route, query, or `iw` command, add an isolation assertion: create two `Project` rows, populate one, assert the other's scoped view is empty and the global view aggregates. (A systematic cross-project isolation matrix is roadmap item 3.4 — until it exists, do this inline.)

Also keep the two DBs separate in tests: the agent runtime uses `IW_CORE_DB_*` (per-worktree DB); the orch DB is `IW_CORE_ORCH_DB_*` on 5433. Never let a test assume they're the same.

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

`make check` = `make quality` (`lint` → ruff + `lint-js` + `lint-templates`; `format-check`; `typecheck` → mypy; `test-assertions` → assertion scanner) + `make test` (unit + integration + dashboard). `make quality` also runs `make dead-code` (`vulture`) and `make dep-check` (`deptry`) — **informational / warn-only this CR**; they flip to hard gates after a burn-in follow-up. Also keep `make migration-check` and `make smoke` passing if your change touches migrations or critical paths. Coverage has a `[tool.coverage.report] fail_under` floor (set just below measured branch coverage and **ratcheted up over time, never down** — CR-00047, roadmap 1.2): don't drop it; `make diff-coverage` is the dedicated diff-coverage QV gate (new/changed Python lines must be ≥~90% covered vs `origin/main` — CR-00047, roadmap 1.3). The browser layer (`make test-browser`) is not in `make test` — run it when you touch browser flows. The **8** daemon QV gates: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests` → `diff-coverage` → `security-secrets` (gitleaks, CR-00050). The pre-commit hook is the developer's first line of defense — `gitleaks/gitleaks` at `v8.30.1` is wired in `.pre-commit-config.yaml`. Semgrep (`security-sast`) runs `uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor` locally; the GH `semgrep` job uses `continue-on-error: true` during burn-in (informational only; findings are visible in Code Scanning but never block a merge — flip to blocking in `P1-CR-D-followup-semgrep-block`). Full gate table: `docs/IW_AI_Core_Testing_Strategy.md` §5.

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
