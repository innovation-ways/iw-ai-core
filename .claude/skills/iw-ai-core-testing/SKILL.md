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

IW AI Core is full of state machines and parsers — the natural targets for invariant-style and (per the roadmap) Hypothesis property tests:

- **Work-item lifecycle** — invariants: never reach a terminal state with an open fix cycle; never exceed the fix-cycle cap (5); a merged item is never re-queued.
- **Batch lifecycle** — invariant: batch status is a pure function of its items' statuses; a held/paused batch launches no new items.
- **`iw next-id`** — monotonic, never reuses an ID, atomic under concurrency (needs a real testcontainer).
- **Doc versioning / diff** (`orch/doc_diff.py`, `orch/doc_sections.py`) — round-trip and idempotence: split→merge is identity; re-diffing is stable.
- **RAG chunking** (`orch/rag/`) — chunk boundaries partition the source; re-chunking is stable.

For now, write these as explicit boundary/transition tests with strong assertions. Use `@pytest.mark.parametrize` for known-important cases (boundaries, each error code); reserve broad random exploration for the forthcoming Hypothesis layer (roadmap 2.2). Do **not** add `hypothesis` or `mutmut` as dependencies on your own — those land via dedicated roadmap items.

---

## 5. TDD — RED, GREEN, REFACTOR (and record the RED)

`backend-impl` writes the test **first**:

1. **RED** — write a failing test that defines the expected behaviour. *Run it; confirm it fails for the right reason.* Record the failing-test output in your execution report.
2. **GREEN** — write the minimal implementation to make it pass.
3. **REFACTOR** — clean up while keeping every test green.

The test is written before the implementation — not after, not alongside. A test added *after* the code tends to confirm "what the code does" rather than "what it should do". (Recording RED evidence is being formalised — roadmap item 0.4.)

---

## 6. Test red-flag checklist (for `tests-review` and any reviewer)

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

---

## 7. Naming, structure, and scope

- `test_<unit>_<scenario>_<expected_result>` — e.g. `test_aggregate_jobs_with_two_batches_returns_total_four`, `test_start_fix_cycle_when_cap_reached_raises_fix_cycle_exhausted`.
- AAA blocks, clearly separated; no logic in Assert.
- One behaviour per test (multiple `assert`s OK if they verify one behaviour).
- Match existing patterns in the nearest test file/directory — fixtures, assertion style, organisation. Don't invent conventions.
- Tests live next to their layer: `tests/unit/` (no I/O), `tests/integration/` (testcontainer DB), `tests/dashboard/` (TestClient), `tests/dashboard/browser/` (`playwright-cli` only — never `agent-browser`, never `chromium.launch()`, never `npx playwright install`, never modify `.playwright/cli.config.json`).
- No new dependencies, no production-code changes from `tests-impl`, no out-of-scope changes — stick to the prompt.

---

## 8. Quality gates you must leave green

`make check` = `make quality` (`lint` → ruff + `lint-js` + `lint-templates`; `format-check`; `typecheck` → mypy) + `make test` (unit + integration + dashboard). Also keep `make migration-check` and `make smoke` passing if your change touches migrations or critical paths. Coverage has a `fail_under` floor (currently low; being raised — roadmap 1.2): don't drop it. The browser layer (`make test-browser`) is not in `make test` — run it when you touch browser flows. Full gate table: `docs/IW_AI_Core_Testing_Strategy.md` §5.
