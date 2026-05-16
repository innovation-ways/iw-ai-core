# Re-enabling pytest-randomly by default: test-isolation strategy for IW AI Core

**Research ID**: R-00077
**Date**: 2026-05-16
**Mode**: deep
**Depth**: deep
**Primary Question**: What pytest test-isolation pattern keeps `make test-integration` close to its ~10 min unrandomised baseline AND green under `pytest-randomly`, given that ~5–10 % of integration tests invoke `iw` CLI subprocesses that commit through their own engine connection (bypassing outer-transaction rollback and SQLAlchemy savepoint sessions)?

---

## Executive Summary

The CR-00048 / CR-00049 cycle proved that two of the obvious isolation patterns are insufficient for this codebase: outer-transaction rollback + savepoint sessions miss commits made by subprocess-owned engine connections (271 failures on seed 12345), and global TRUNCATE-CASCADE-per-test fixes correctness but adds an 18-minute (3×) regression to every `make test-integration` run. The recommended pattern is **per-test PostgreSQL template-clone**: a session-scoped template database is migrated once, then each test gets a fresh `CREATE DATABASE … TEMPLATE …` clone (~10 ms each) and exports its URL via the existing `IW_CORE_DB_*` env vars so `iw` CLI subprocesses inherit it transparently. The Python port [`pgtestdbpy`](https://pypi.org/project/pgtestdbpy/) implements this pattern directly; for a 2 500-test suite the projected wall-clock is ~10–11 min (baseline ~10 min + ~25 s of clone overhead), well under the 12-min budget. Trigger-based dirty-table tracking ([`pytest-clean-database`](https://pypi.org/project/pytest-clean-database/)) is a viable Plan B but is less battle-tested and the per-write trigger overhead is not officially benchmarked.

---

## Background

IW AI Core ships [P1-CR-C (CR-00048) with `pytest-randomly` off-by-default](../research/R-00068-ai-core-test-quality-strategy.md) — `-p no:randomly` in `pyproject.toml` `[tool.pytest.ini_options] addopts` was the design's explicit AC1 escape clause after S10 (`make diff-coverage`) burned 5 fix cycles on order-dependent integration failures. The cleanup follow-up CR-00049 (P1-CR-C-followup-randomly) was filed to re-enable randomisation by default; its daemon-launched S01 attempt timed out at 80 m, and a subsequent operator manual completion on 2026-05-16 explored two fixture designs before abandoning. The batch was cancelled (`iw batch-cancel BATCH-00106`), the work item marked `cancelled`, and this research filed to determine the right pattern before another implementation attempt. The integration + dashboard suite is ~2 500 tests across ~150 modules; ~20 modules invoke `iw` CLI subprocesses or use [Click's `CliRunner`](https://click.palletsprojects.com/en/stable/testing/) without going through the bound test session, and ~7–10 modules define their own `pg_container` testcontainer for migration-round-trip-style tests.

---

## Findings

### Savepoint-only isolation cannot catch commits from subprocess-owned connections [HIGH confidence]

SQLAlchemy's canonical "joining a Session into an External Transaction" recipe pairs a session-scoped outer transaction on a bound `Connection` with `join_transaction_mode="create_savepoint"`. When the test's Session calls `.commit()`, the call releases a savepoint instead of committing to the outer transaction, and the outer transaction's eventual `rollback()` undoes everything. This is the [pattern SQLAlchemy 2.0 explicitly recommends for tests](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html): *"When the context manager yielded by `Session.begin_nested()` completes, it 'commits' the savepoint, which includes the usual behavior of flushing all pending state."* It is also the pattern used by [`pytest-flask-sqlalchemy`](https://pypi.org/project/pytest-flask-sqlalchemy/) and many in-process test recipes.

The recipe has a fundamental limitation, however: it only catches commits **that go through the bound Connection**. A subprocess (`subprocess.run(["iw", "item-cancel", ...])`) opens its own engine via `safe_create_engine()`, which is a brand-new `Connection` on the same engine URL but **not** bound to the test's outer transaction. Its commits land in the real database. This was the root cause of CR-00049's seed-12345 sweep producing 271 failures + 12 errors when the operator tried savepoint-only mode without any TRUNCATE.

The same SQLAlchemy docs note this limitation obliquely: *"For some components (such as external binaries) [single-connection isolation] is may be impossible"* ([Eric Radman, "Database Test Isolation"](https://eradman.com/posts/database-test-isolation.html)), which is precisely IW AI Core's situation — the integration suite invokes `iw` (which boots an entirely separate process with its own engine) as a feature, not an accident.

### Per-test TRUNCATE-CASCADE catches subprocess writes but inflicts a 3× perf regression [HIGH confidence]

The operator's manual CR-00049 completion implemented per-test TRUNCATE-CASCADE in `_db_test_connection` (function-scoped) along with savepoint sessions. Correctness was solid: only 2 tests needed quarantines, all four seeds (12345 / 67890 / 11111 / 42424) ended green. **Wall-clock was the problem:** `pytest -p randomly --randomly-seed=12345 --no-cov` produced a 28-min 35-s sweep (`/tmp/cr49_seed12345_v3.log`) vs the suite's pre-CR-00049 baseline of ~10 min — a 2.85× regression on every `make test-integration` invocation, applied to CI, local dev, and the daemon's `integration-tests` QV gate on every work item.

The cost decomposes as: ~30 public tables × ~5–10 ms per TRUNCATE-CASCADE (PostgreSQL acquires `AccessExclusiveLock` per cascading table) × ~2 500 tests = ~10–15 min of pure overhead. This is consistent with [Eric Radman's benchmark](https://eradman.com/posts/database-test-isolation.html) of ~30 ms per "Truncate" reset on a similar-shape schema. Conditional TRUNCATE — only the dirty tables, see the trigger-based section below — could reduce this to seconds, but the conservative full TRUNCATE is what the manual completion shipped because identifying "dirty" tables requires either triggers or `pg_stat_user_tables` deltas.

### Per-module TRUNCATE eliminates the perf regression but doesn't catch within-module subprocess leaks [HIGH confidence]

When the operator refactored to **module-scoped autouse** TRUNCATE (~30 calls per sweep instead of ~2 500), wall-clock dropped to **8 min 29 s** (faster than baseline, per `/tmp/cr49_seed12345_v3.log` and the seed-table-exclusion variant `/tmp/cr49_seed12345_v4.log`), but seed-12345 still surfaced ~230 failures concentrated in modules that invoke `iw` CLI subprocesses (`test_cli_cancel.py` × 9, `test_phantom_gate_auto_skip.py`, `test_batch_item_approval.py`, `test_oss_finding_details.py`, …). Each module starts clean, but a CLI subprocess fired from test N commits rows that persist into test N+1 of the same module. Savepoint sessions don't catch this either — the subprocess never touched the bound session.

The pytest community's general guidance corroborates the limitation: [pytest-postgresql's own documentation notes](https://pypi.org/project/pytest-postgresql/) that *"SQL query tracking does not work properly if your test runs subprocesses,"* and [pytest-pgsql highlights](https://pytest-pgsql.readthedocs.io/) that *"you can't call execute a COMMIT statement anywhere in your tests, or you'll risk causing nondeterministic bugs."* IW AI Core's tests legitimately do commit (via the subprocess), so a transaction-rollback-only approach is structurally incompatible with the suite's shape.

### Per-test template-clone (`CREATE DATABASE … TEMPLATE …`) is fast and subprocess-safe [HIGH confidence]

PostgreSQL natively supports cloning a database with [`CREATE DATABASE new TEMPLATE old`](https://www.postgresql.org/docs/current/sql-createdatabase.html), and the clone is on the order of **~10 ms per test** for a typical migration-shaped template on RAM-backed hardware ([pgtestdb README](https://github.com/peterldowns/pgtestdb), [Eric Radman benchmark — "Option 3 (Copy Database) … approximately 30ms setup time while supporting full transactional capabilities and external utilities"](https://eradman.com/posts/database-test-isolation.html)). Each test gets a brand-new, fully migrated database; the test's `IW_CORE_DB_NAME` env var points to the clone, so any `iw` CLI subprocess invoked from the test inherits the per-test DB and its commits are confined to that clone. When the test ends, the clone is dropped.

PostgreSQL 18 made this even better with [`CREATE DATABASE … STRATEGY = FILE_COPY`](https://boringsql.com/posts/instant-database-clones/) for large templates, but the default `WAL_LOG` strategy is already fast enough for IW AI Core's schema size. The well-known caveat — *"CREATE DATABASE will fail if any other connection exists on the source database"* ([PostgreSQL docs](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html)) — is handled by the canonical pattern: the template database is created once at session start, no test ever connects to it, and clones are made FROM it (the template is read-only as far as tests are concerned).

For a 2 500-test suite, the overhead budget is: ~500 ms one-time template build (alembic upgrade) + ~10 ms × 2 500 = **~25 s of cloning overhead**. Total expected sweep: ~10 min 25 s, well inside the 12-min budget the operator set.

### `pgtestdbpy` is a maintained Python implementation of the template-clone pattern [HIGH confidence]

[`pgtestdbpy`](https://pypi.org/project/pgtestdbpy/) is a direct Python port of the well-established Go library [`pgtestdb`](https://github.com/peterldowns/pgtestdb) (which is used in production by multiple Go shops; see [Lobste.rs discussion](https://lobste.rs/s/i5xnsj/testing_with_go_postgresql_ephemeral_dbs)). The Python version exposes two primitives: a `templates` context manager (session-scoped — runs migrations once, marks the result as a template) and a `clone` context manager (function-scoped — `CREATE DATABASE … TEMPLATE …`, yields the URL, drops the database on exit). The library uses PostgreSQL advisory locks to make migration application idempotent across `pytest-xdist` workers, so the pattern composes correctly with parallel test execution.

A minimal fixture wiring for IW AI Core would look approximately like:

```python
import pgtestdbpy, psycopg, pytest
from sqlalchemy import create_engine

def migrate(url: str) -> None:
    """Apply alembic head migrations + FTS DDL to the template database."""
    cfg = _build_alembic_config(url)
    _run_alembic_upgrade(cfg)
    with psycopg.connect(url) as conn:
        conn.execute(FTS_FUNCTION_SQL)
        conn.execute(FTS_TRIGGER_SQL)
        conn.commit()

migrator = pgtestdbpy.Migrator(migrate)
config = pgtestdbpy.Config(...)  # host/port/superuser/etc.

@pytest.fixture(scope="session")
def _template_db():
    with pgtestdbpy.templates(config, migrator):
        yield

@pytest.fixture
def db_url(_template_db, monkeypatch):
    """Per-test cloned DB. Exports IW_CORE_DB_NAME so subprocesses inherit."""
    with pgtestdbpy.clone(config, migrator) as url:
        # Set the per-test DB name in env so safe_create_engine() in iw
        # subprocesses connects to THIS clone, not the template.
        monkeypatch.setenv("IW_CORE_DB_NAME", _extract_dbname(url))
        yield url

@pytest.fixture
def db_engine(db_url):
    return create_engine(db_url, pool_pre_ping=True)
```

This composes correctly with the 7–10 modules that define their own `pg_container` fixture — those modules keep their existing module-scoped container override and aren't affected by the conftest-level fixtures. (The CR-00049 manual completion ran into a [`ScopeMismatch` error](https://docs.pytest.org/en/stable/reference/fixtures.html) here because the autouse module-scoped TRUNCATE fixture depended on session-scoped `db_engine` which couldn't resolve `pg_container` against module-scoped overrides. The template-clone pattern's autouse fixture only takes `request: pytest.FixtureRequest` and uses `request.getfixturevalue`, side-stepping the issue. The CR-00049 abandoned-completion report documents the workaround at `/tmp/cr49_abandoned_report.md`.)

### Trigger-based "dirty table" tracking is a viable Plan B [MEDIUM confidence]

[`pytest-clean-database`](https://pypi.org/project/pytest-clean-database/) installs an `INSERT` trigger on every user table that records the table name in a tracking table; after each test, only the tables with new entries are TRUNCATEd. This catches subprocess commits because **triggers fire on every INSERT regardless of which session/connection makes the change** — the very gap savepoint mode leaves open. The package's docs describe the mechanism: *"For every user table, create an INSERT trigger that will execute the function that marks this table as dirty."*

The downsides:
- **Less mature**: the package is far less widely deployed than the template-clone pattern; the PyPI page does not publish per-write overhead benchmarks, though a [general PostgreSQL trigger benchmark from Infinite Lambda](https://infinitelambda.com/postgresql-triggers/) measured *"a join-based trigger introduced only a 0.17% increase in latency compared to insert-only operations"* — suggestive but not directly applicable to a dirty-table tracker trigger.
- **Schema-scoped**: defaults to the `public` schema; multi-schema setups need `--clean-db-pg-schema` and the docs lack examples. IW AI Core only uses `public` today, so this is moot.
- **DDL is not tracked**: the `migrated_engine`-scoped quarantines this research recommends keeping (see Limitations) would still apply.

If template-clone is rejected for any reason (e.g. testcontainer permissioning), `pytest-clean-database` is the next-best option.

### Eliminating subprocesses in favour of `CliRunner` is a non-starter at this scale [HIGH confidence]

Click's own testing guide recommends [`CliRunner` over `subprocess`](https://click.palletsprojects.com/en/stable/testing/) precisely because it runs in-process and shares the test's DB session (via the existing `cli_get_session` fixture in `tests/integration/conftest.py`, which 17 test files already use). However, ~20 IW AI Core test files use `subprocess.run` directly (covering CLI invocations that need the full process boot — `iw approve`, `iw item-cancel`, `iw batch-create`, end-to-end pipeline tests), and ~926 total subprocess+CLI references appear across `tests/integration/` and `tests/dashboard/`. Refactoring all of them to `CliRunner` would:

1. Lose end-to-end coverage of CLI process startup, env-var handling, and the safe_create_engine code path — the latter being exactly the thing IW's live-DB guard (`tests/conftest.py:28`) defends against and that I-00041 surfaced as a production-incident class.
2. Take an estimated 1–2 weeks of refactor work across ~20 modules, with significant risk of behaviour drift.

The template-clone pattern lets these subprocess tests work correctly **without any refactor** because the subprocess inherits `IW_CORE_DB_*` from the test's monkeypatched env. This is the decisive advantage over the Plan B (`pytest-clean-database`) — both work, but template-clone is the only one that requires no test-code changes outside `tests/integration/conftest.py`.

### Industry-wide pattern: per-test ephemeral DB is the consensus for subprocess-bearing test suites [MEDIUM confidence]

The state-of-the-art surveyed across [pytest-postgresql](https://pypi.org/project/pytest-postgresql/) (which already provides a [`client` fixture that clones a session-scoped template](https://github.com/dbfixtures/pytest-postgresql) — *"the process fixture pre-populates the database once per session into a template database; the client fixture then clones this template for each test"*), [pgtestdb / pgtestdbpy](https://github.com/peterldowns/pgtestdb), [Apache Airflow's pytest pipeline](https://github.com/apache/airflow/blob/main/contributing-docs/testing/unit_tests.rst) (per-worker dedicated metadata DB), and the [pg_tmp HN discussion](https://news.ycombinator.com/item?id=26947964) consistently lands on the same answer when subprocesses are in scope: **clone a template per test, accept the ~10 ms overhead, get true isolation**. The transaction-rollback approach is preferred only in pure in-process Django / Flask / FastAPI scenarios where no test forks a child process.

[Cal Paterson's contrarian "don't clean the database between tests"](https://calpaterson.com/against-database-teardown.html) argument is interesting but inapplicable: it relies on tests being written to tolerate dirty data, which the existing 2 500 IW AI Core tests are not (they assert exact row counts, IDs, etc.). Retrofitting that would require rewriting every assertion.

---

## Recommendations

1. **Primary — Adopt the per-test template-clone pattern via `pgtestdbpy`.** Replace the current `_db_test_connection` outer-transaction-rollback fixture with a session-scoped `pgtestdbpy.templates` + function-scoped `pgtestdbpy.clone`. Each test's `IW_CORE_DB_NAME` is monkeypatched to the clone so subprocess-invoked `iw` commands inherit the per-test database via `safe_create_engine()`. **Expected wall-clock impact**: ~10 min 25 s for the integration + dashboard suite (baseline ~10 min + ~25 s of clone overhead at ~10 ms × 2 500 tests), well inside the operator-set 12-min budget. **Expected correctness**: all four seeds (12345/67890/11111/42424) green, modulo a small set of `xfail(strict=False)` quarantines for the 3 module-scoped `migrated_engine` tests (`test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`, `test_pending_migration_log_migration.py::test_valid_enum_values_accepted`, `test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade` — these are orthogonal cleanups, see Limitations). **Migration plan**: a CR with two impacted-paths slices — `tests/integration/conftest.py` (replace fixtures) and `pyproject.toml` (`-p no:randomly` removed from addopts + `pgtestdbpy` added to `[dependency-groups] dev`).

2. **Alternative — `pytest-clean-database` with INSERT triggers** if template-clone is blocked (e.g. the testcontainer's superuser doesn't have CREATEDB, or the template can't be locked exclusively for cloning). It catches subprocess commits via the trigger, only TRUNCATEs dirty tables (so wall-clock should be similar to baseline), and requires no test-code changes outside conftest. Lower confidence because the per-write trigger overhead is not officially benchmarked and the package is less battle-tested.

3. **Avoid — Per-test global TRUNCATE-CASCADE.** Adds an 18-minute / 3× regression to every `make test-integration` run (CI, local dev, every daemon QV-gate run). The CR-00049 sweep log `/tmp/cr49_seed12345_v3.log` documents this empirically: 28 min 35 s vs the ~10 min unrandomised baseline.

4. **Avoid — Bulk migrating 20+ tests from `subprocess.run` to `CliRunner`.** Loses end-to-end coverage of the safe-create-engine live-DB guard path (the I-00041 incident class) and represents weeks of refactor work with significant behaviour-drift risk. Template-clone makes this refactor unnecessary.

5. **Avoid — Snapshot-based testcontainer images (e.g. [`metaloom/postgresql-snapshot-testcontainer`](https://github.com/metaloom/postgresql-snapshot-testcontainer))**. Java-only; per-test restore requires a database restart (tmpfs copy + container restart); measured gains were modest (16 s vs 26 s in the project's own benchmark). Template-clone is faster and language-neutral.

---

## Limitations

- **Per-test overhead is an estimate, not a measurement on IW AI Core's hardware.** The 10 ms figure comes from pgtestdb's README and Eric Radman's bench on a similar-shape schema; actual hardware (the developer's dev box + GitHub Actions runner) may diverge. The implementation CR should measure this on the real testcontainer + dev machine before claiming the 12-min target.
- **The 3 `migrated_engine` quarantines (CR-00049) remain orthogonal.** Even with template-clone, tests that downgrade the schema mid-module on a module-scoped engine will still leak intra-module. A follow-up CR should scope these fixtures down to function-level OR add explicit per-test restore — the quarantines documented in `/tmp/cr49_abandoned_report.md` (3 tests) should be carried forward into the next CR with the same `@pytest.mark.order_dependent` + `xfail(strict=False)` triad.
- **The 7–10 modules with their own `pg_container` override are out of scope** for the conftest changes. They have their own testcontainer and their own isolation discipline; the template-clone pattern doesn't touch them. The `ScopeMismatch` gotcha from CR-00049 must still be avoided by writing the new autouse fixture to take `request` and call `request.getfixturevalue` lazily.
- **`pytest-clean-database` trigger overhead is unbenchmarked at IW AI Core's write volume.** If template-clone is rejected, a quick spike (run unit + integration with the package installed, measure wall-clock) is needed before committing.
- **No production data on `pgtestdbpy` adoption.** Unlike the Go `pgtestdb` which is widely used, the Python port is newer and the maintenance trajectory should be verified before adoption — fork-feasibility is a fallback (the codebase is small, ~a few hundred lines).
- **This research did not investigate parallelism (`pytest-xdist`)**, which is currently disabled in IW AI Core's pipeline. Both template-clone and trigger-based approaches support parallelism natively, but the per-worker DB scheme has subtle interactions with the existing live-DB guard that should be confirmed before P1-CR-F (the parallelism CR, not yet filed).
- **Sentry-specific patterns were not located.** Sentry's test infrastructure documentation is not publicly indexed under the search queries tried; the patterns above represent the broader pytest+PostgreSQL+subprocess ecosystem (pgtestdb, pytest-postgresql, dbt, Airflow). Direct Sentry confirmation would require reading the [getsentry/sentry repo's conftest](https://github.com/getsentry/sentry) directly.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | SQLAlchemy 2.0 — Transactions and Connection Management | HIGH | https://docs.sqlalchemy.org/en/20/orm/session_transaction.html |
| 2 | pgtestdb (Go, original) — README | HIGH | https://github.com/peterldowns/pgtestdb |
| 3 | pgtestdb — testdb.go (implementation reference) | HIGH | https://github.com/peterldowns/pgtestdb/blob/main/testdb.go |
| 4 | pgtestdbpy (Python port) — PyPI | HIGH | https://pypi.org/project/pgtestdbpy/ |
| 5 | pytest-postgresql — PyPI + GitHub | HIGH | https://pypi.org/project/pytest-postgresql/ |
| 6 | pytest-postgresql — GitHub (dbfixtures org) | HIGH | https://github.com/dbfixtures/pytest-postgresql |
| 7 | PostgreSQL docs — CREATE DATABASE | HIGH | https://www.postgresql.org/docs/current/sql-createdatabase.html |
| 8 | PostgreSQL docs — Template Databases (22.3) | HIGH | https://www.postgresql.org/docs/current/manage-ag-templatedbs.html |
| 9 | Eric Radman — "Database Test Isolation" (benchmarks for 4 strategies) | HIGH | https://eradman.com/posts/database-test-isolation.html |
| 10 | pytest-clean-database — PyPI | MEDIUM | https://pypi.org/project/pytest-clean-database/ |
| 11 | pytest-flask-sqlalchemy — PyPI (canonical savepoint recipe) | HIGH | https://pypi.org/project/pytest-flask-sqlalchemy/ |
| 12 | Click testing docs — CliRunner | HIGH | https://click.palletsprojects.com/en/stable/testing/ |
| 13 | Cal Paterson — "The argument against clearing the database between tests" | MEDIUM | https://calpaterson.com/against-database-teardown.html |
| 14 | metaloom/postgresql-snapshot-testcontainer (Java, tmpfs snapshots) | MEDIUM | https://github.com/metaloom/postgresql-snapshot-testcontainer |
| 15 | Apache Airflow — testing/unit_tests.rst | HIGH | https://github.com/apache/airflow/blob/main/contributing-docs/testing/unit_tests.rst |
| 16 | pytest_pgsql — Clean PostgreSQL Databases for Your Tests | MEDIUM | https://pytest-pgsql.readthedocs.io/ |
| 17 | boringSQL — "Instant database clones with PostgreSQL 18" (FILE_COPY strategy) | MEDIUM | https://boringsql.com/posts/instant-database-clones/ |
| 18 | Infinite Lambda — "PostgreSQL Triggers' Performance Impact" | MEDIUM | https://infinitelambda.com/postgresql-triggers/ |
| 19 | Advanced Python Development — "Finding test isolation issues with PyTest" | MEDIUM | https://advancedpython.dev/articles/pytest-randomisation/ |
| 20 | pg_tmp — Hacker News discussion | MEDIUM | https://news.ycombinator.com/item?id=26947964 |
| 21 | CR-00049 abandoned-completion report (local, this session) | HIGH | /tmp/cr49_abandoned_report.md |
| 22 | CR-00049 sweep logs (per-test vs per-module TRUNCATE, local) | HIGH | /tmp/cr49_seed12345_v3.log, v4.log, v5.log |

---

## Appendix A: Implementation outline the next CR can quote verbatim

### Acceptance criteria

- AC1: `grep -n 'no:randomly' pyproject.toml` returns nothing.
- AC2: `make test-integration` wall-clock on the reference dev box is ≤ 12 min (target ~10 min 30 s).
- AC3: `pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=<N> -q --no-cov` exits 0 across seeds 12345 / 67890 / 11111 / 42424 / 99999, with at most the 3 carried-forward `xfail(strict=False)` quarantines.
- AC4: tests/CLAUDE.md §7, docs/IW_AI_Core_Testing_Strategy.md §3 + §9 row, skills/iw-ai-core-testing/SKILL.md §2 flipped to default-on with the CR-00048 fallback preserved as an "Earlier fallback" historical note.
- AC5: `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row P1-CR-C-followup-randomly → DONE; item 1.4 row → DONE; §11 changelog entry.

### Impacted paths (allowed_paths)

- `pyproject.toml` (drop `-p no:randomly`, add `pgtestdbpy>=<version>` to `[dependency-groups] dev`, rewrite addopts comment block).
- `tests/integration/conftest.py` (rewrite `_db_test_connection` → template-clone fixture; preserve the `db_session` / `db_session_factory` / `test_project` / `cli_get_session` API the existing tests use).
- `tests/integration/db/test_i_00062_migration.py`, `tests/integration/test_db_identity_integration.py`, `tests/integration/test_pending_migration_log_migration.py` (carry forward the 3 CR-00049 quarantines).
- `tests/CLAUDE.md` §7 (doc flip).
- `docs/IW_AI_Core_Testing_Strategy.md` §3 + §9 row (doc flip).
- `skills/iw-ai-core-testing/SKILL.md` §2 (doc flip).
- `.claude/skills/iw-ai-core-testing/SKILL.md` (re-synced).
- `ai-dev/work/TESTS_ENHANCEMENT.md` (§5 row, item 1.4, §11 changelog).
- `uv.lock` (regenerated for `pgtestdbpy`).

### S01 budget recommendation

- **Timeout**: 4 800 s (80 min). The 4-seed sweep at ~10 min each = ~40 min; plus diagnosis, fixture rewrite, docs, plan, sync, and preflight = 60–70 min total.
- **Bounded sweep recipe**: bake `--no-cov` into the design's verification command. The coverage flag adds 30–40 % overhead and is exercised by S10 `diff-coverage` anyway — running `--cov` four times in S01 is wasted work and was a major contributor to CR-00049's attempt-1 timeout.

### Sequencing within the implementation step

1. Wire `pgtestdbpy` template + clone fixtures in `tests/integration/conftest.py`. Keep the existing `db_session` / `db_session_factory` / `test_project` / `cli_get_session` API: rebind them to engine sessions on the per-test clone URL. Monkeypatch `IW_CORE_DB_HOST` / `IW_CORE_DB_PORT` / `IW_CORE_DB_NAME` / `IW_CORE_DB_USER` / `IW_CORE_DB_PASSWORD` in the per-test fixture so any `iw` subprocess spawned by the test inherits the clone's URL.
2. Carry forward the 3 CR-00049 quarantines (`migrated_engine`-bound tests) with the same `@pytest.mark.order_dependent` + `xfail(strict=False, reason="…")` triad and `# NOTE(P1-CR-C-followup-randomly):` tracking comments. Do not attempt to fix the underlying scope-down-`migrated_engine` issue in this CR — file as a separate follow-up.
3. Carry forward the 2 module-scoped test-class teardowns in `test_oss_migration.py::TestOssMigrationDowngrade` and `test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade` (they restore migrated schema after intentional downgrades).
4. RED reproduction: run `pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q --no-cov` BEFORE the fixture rewrite; capture the failure count as `tdd_red_evidence`.
5. After implementation, run the 4-seed sweep; expect all green modulo the 3 quarantines.
6. Drop `-p no:randomly` from `addopts`; rewrite the comment block.
7. Flip the 4 doc locations (§7 + §3 + §9 + skill §2) with the historical-note pattern.
8. Update `TESTS_ENHANCEMENT.md` §5 + item 1.4 + §11 changelog.
9. `uv run iw sync-skills --force iw-ai-core-testing`.
10. Preflight: `make format` + `make typecheck` + `make lint`. All must be green.

---

## Appendix B: Gotchas from the cancelled CR-00049 attempt

- **`ScopeMismatch` from autouse + `db_engine` dependency**: a module-scoped autouse fixture that takes `db_engine` (session-scoped) as a parameter will fail with `ScopeMismatch: You tried to access the module scoped fixture pg_container with a session scoped request object` in any module that overrides `pg_container` at module scope (10+ such modules exist in IW AI Core's integration suite). **Fix**: take `request: pytest.FixtureRequest`, branch on `hasattr(request.module, "pg_container")`, and resolve `db_engine` lazily via `request.getfixturevalue("db_engine")` only when the module does NOT override.
- **Seed-data tables that must not be TRUNCATEd** (only relevant if Plan B / trigger-based or per-test TRUNCATE is chosen; template-clone makes this moot since each test gets a fully-migrated fresh DB): `alembic_version`, `agent_runtime_options`, `id_sequences` (critical — `iw next-id` reads this; wiping breaks every test that registers a work item), `iw_core_instance` (daemon identity gate row), `keep_alive_config` (F-00074 seed), `doc_type_guides` (seed doc-type rows). Grep `INSERT INTO` across `orch/db/migrations/versions/` to catch any new ones added after this research.
- **Daemon S01 timeout budget**: the CR-00049 design's 2 400 s timeout was set assuming a 4-seed sweep with `--cov`. Each `--cov` sweep ran ~12 min; 4 × 12 = 48 min, plus diagnosis = budget overrun. Either bump S01's timeout or drop `--cov` from the bounded-sweep recipe. The implementation CR (recommendation 1) bakes `--no-cov` into the design.
- **Existing pre-merge fixture for `test_db_identity_integration.py`**: the file already defines `TestDashboardHealthzIdentity::ensure_instance_row` at class scope. With template-clone every test gets a fresh fully-migrated DB, so this fixture becomes redundant — but leaving it in place is harmless and reduces diff churn for the implementation CR.
- **`db_session_factory` consumers**: ~5 tests use this fixture to construct sessions for poller/daemon threads. With template-clone, the factory simply binds to the per-test clone engine; the existing API (`sessionmaker(bind=...)`) stays the same.
- **The `pytest-randomly` order_dependent marker** is already registered in `pyproject.toml` `markers` from CR-00048. The implementation CR must NOT re-register it.

---

## Appendix: Research Log

**Date range**: 2026-05-16
**Queries run**: 10 WebSearch, 6 WebFetch
**Mode used**: deep
**Depth level**: deep
**Local context read**: `tests/integration/conftest.py`, `tests/CLAUDE.md`, `ai-dev/active/CR-00049/CR-00049_CR_Design.md`, `/tmp/cr49_abandoned_report.md`, `/tmp/cr49_seed*_v*.log`, `ai-dev/work/TESTS_ENHANCEMENT.md`.

**Operator session context** (2026-05-16): CR-00049 daemon-launched S01 timed out at 80 m. Operator manually completed the work and abandoned after exploring per-test TRUNCATE (3× perf regression rejected) and per-module TRUNCATE (232 within-module subprocess-commit leaks remained). Filed this research before another implementation attempt, per [P1-CR-C-followup-randomly](../../ai-dev/work/TESTS_ENHANCEMENT.md) lineage.
