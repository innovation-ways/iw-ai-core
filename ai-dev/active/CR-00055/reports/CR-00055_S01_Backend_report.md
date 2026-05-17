# CR-00055 S01 Backend Implementation Report

**Work Item**: CR-00055 — Re-enable `pytest-randomly` by default via per-test PostgreSQL template-clone  
**Step**: S01 (backend-impl)  
**Date**: 2026-05-16  
**Status**: COMPLETE

---

## Summary

CR-00055 re-enables `pytest-randomly` as the default test-randomisation plugin by replacing the
savepoint/rollback isolation model with per-test PostgreSQL template-clone isolation via
`pgtestdbpy>=0.0.1`. Every integration and dashboard test now gets its own ephemeral database
cloned from a session-scoped migrated template in ~10–25 ms (`CREATE DATABASE … TEMPLATE …`
with WAL_LOG strategy). The per-test clone URL is exported via `IW_CORE_DB_*` env vars so
`iw` CLI subprocesses inherit the isolated DB — closing the cross-test CLI-subprocess leak
that defeated savepoint-only and per-module-TRUNCATE designs in CR-00049.

The implementation was cribbed directly from the spike branch `spike/pgtestdbpy-isolation`
(empirically validated 2026-05-16 across 4 seeds). All 12 deliverables from the prompt were
completed in this session.

---

## Deliverables Completed

| # | Deliverable | Status |
|---|-------------|--------|
| 0 | RED — captured unfixed-state seed-12345 sweep | DONE |
| 1 | Cribbed working implementation from spike branch | DONE |
| 2 | Added `pgtestdbpy>=0.0.1` to `pyproject.toml` dev deps + `uv lock` | DONE |
| 3 | Rewrote `tests/integration/conftest.py` fixture chain | DONE |
| 4 | Re-exported `_pgtestdb_setup` from `tests/dashboard/conftest.py` | DONE |
| 5 | Added 2 class teardowns (TestOssMigrationDowngrade, TestProjectOssJobMigrationDowngrade) | DONE |
| 6 | Added 1 module-level autouse fixture `_restore_iw_core_instance_row` | DONE |
| 7 | Added 3 quarantines with `@pytest.mark.xfail(strict=False)` | DONE |
| 8 | Removed `-p no:randomly` from `pyproject.toml addopts` | DONE |
| 9 | Flipped 4 doc locations to default-on | DONE |
| 10 | Synced skill via `iw sync-skills --force iw-ai-core-testing` | DONE |
| 11 | Updated `ai-dev/work/TESTS_ENHANCEMENT.md` | DONE |
| 12 | GREEN — 4-seed sweep all-green | DONE |

---

## TDD Red Evidence (Deliverable 0)

Before any code change, seed 12345 was run against the unfixed state:

```
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
  -p randomly --randomly-seed=12345 -q --no-cov 2>&1 | tail -10
```

Result:
```
287 failed, 1603 passed, 33 skipped, 3 xfailed, 1017 warnings, 636 errors in 614.16s (0:10:14)
```

The 287 failures + 636 errors match the design's "Current Behavior" section: cross-module
CLI-subprocess leaks (IW_CORE_DB_* pointing at the wrong DB after test-order shuffle) and
intra-module migration mutations (downgrade tests leaving schema torn down for sibling tests).

---

## 4-Seed GREEN Sweep (Deliverable 12)

All 4 seeds passed with 0 failures and 0 errors:

| Seed  | Passed | Skipped | xfailed | xpassed | Failures | Wall-clock |
|-------|--------|---------|---------|---------|----------|------------|
| 12345 | 2523   | 33      | 4       | 2       | 0        | 695.61s (11m35s) |
| 67890 | 2523   | 33      | 3       | 3       | 0        | 669.47s (11m09s) |
| 11111 | 2523   | 33      | 3       | 3       | 0        | 707.31s (11m47s) |
| 42424 | 2523   | 33      | 4       | 2       | 0        | 694.00s (11m33s) |

The xfailed/xpassed variation (3-4 each) is expected — `strict=False` on the 3 quarantines
means they show as xfailed when run in the "bad" order and xpassed when run in the "safe" order.
Total xfailed+xpassed stays constant at 6 across all seeds, within the expected 3-6 range.

---

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `pgtestdbpy>=0.0.1` to dev deps; removed `-p no:randomly` from addopts; rewrote comment block |
| `uv.lock` | Updated by `uv lock` |
| `tests/integration/conftest.py` | Full rewrite of fixture chain: `_migrate_template`, `_pgtestdb_setup` (session), `db_engine` (function → clone), `_db_test_connection` (simplified) |
| `tests/dashboard/conftest.py` | Added `_pgtestdb_setup` to re-export list |
| `tests/integration/test_oss_migration.py` | Added teardown: re-applies MIGRATION_SQL after downgrade test |
| `tests/integration/test_project_oss_job_migration.py` | Added teardown: re-applies MIGRATION_SQL after downgrade test |
| `tests/integration/test_db_identity_integration.py` | Added module-level autouse `_restore_iw_core_instance_row`; added `@pytest.mark.xfail(strict=False)` quarantine |
| `tests/integration/test_pending_migration_log_migration.py` | Added `@pytest.mark.xfail(strict=False)` quarantine |
| `tests/integration/db/test_i_00062_migration.py` | Added `@pytest.mark.xfail(strict=False)` quarantine |
| `tests/CLAUDE.md` | §7 flipped to default-on; CR-00048 fallback preserved as historical note |
| `docs/IW_AI_Core_Testing_Strategy.md` | §3 subsection rewritten for CR-00055; §9 row flipped from ⚠️ to ✅ |
| `skills/iw-ai-core-testing/SKILL.md` | §2 flipped to default-on; CR-00048 fallback preserved |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Re-synced via `iw sync-skills --force iw-ai-core-testing` |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §5 row DONE, item 1.4 DONE, §11 changelog entry added |

---

## Preflight Gate Results

| Gate | Result |
|------|--------|
| `make format` | ok — no reformatting needed |
| `make typecheck` | ok — zero errors on touched files |
| `make lint` | ok — zero errors |

---

## Key Implementation Decisions

1. **WAL_LOG override** — `pgtestdbpy.QRY_DB_CLONE` was overridden to drop the library's
   hardcoded `STRATEGY=FILE_COPY` suffix. FILE_COPY is ~310 ms/clone; WAL_LOG is ~25 ms/clone
   on this codebase's schema (~12x speedup). Without this override the 4-seed sweep would
   take ~28 min per seed vs ~11 min.

2. **`_pgtestdb_setup` re-export** — Added to `tests/dashboard/conftest.py` alongside the
   existing fixtures. Without this re-export, the dashboard suite fails with
   `fixture '_pgtestdb_setup' not found` for every test.

3. **`strict=False` on quarantines** — MANDATORY. These 3 tests pass in alphabetical order
   (which some seeds hit), so `strict=True` would cause xpass-failures in clean runs.

4. **Module-level autouse `_restore_iw_core_instance_row`** — New fixture (not carry-forward)
   in `test_db_identity_integration.py`. Ensures the `iw_core_instance` singleton row is
   present for every test class in that module, not just `TestDashboardHealthzIdentity`.

---

## Observations

- The per-test clone overhead (~25 ms) adds about 1 min total to the suite wall-clock vs
  the session-scoped rollback model — well within the ~10-min baseline.
- All 3 quarantined tests (xfail strict=False) behaved as expected: some seeds hit them in
  the "bad" order (xfailed), others in the "safe" order (xpassed). No 4th quarantine needed.
- The `SAWarning: transaction already deassociated from connection` in seed 67890 is a
  pre-existing benign warning from `test_oss_migration.py`; it was present before CR-00055.
