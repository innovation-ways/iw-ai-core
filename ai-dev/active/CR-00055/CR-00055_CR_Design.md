# CR-00055: Re-enable `pytest-randomly` by default — per-test PostgreSQL template-clone (P1-CR-C-followup-randomly-v2)

**Type**: Change Request
**Priority**: Medium
**Reason**: Second attempt at item 1.4 cleanup. CR-00049 was cancelled 2026-05-16 after the per-test TRUNCATE-CASCADE design hit a 3× perf regression (28 min vs ~10 min baseline). The replacement strategy — per-test PostgreSQL template-clone via the `pgtestdbpy` library (with a 1-line override to use the WAL_LOG strategy that is ~10× faster than the library's hardcoded `STRATEGY=FILE_COPY` on this codebase's schema) — was researched in `docs/research/R-00077-pytest-randomly-isolation-strategy.md` and spike-validated on branch `spike/pgtestdbpy-isolation` on 2026-05-16: 4 seeds all green at ~10–13 min wall-clock per sweep.
**Created**: 2026-05-16
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR only touches tests/configs/docs. The existing `testcontainers.PostgresContainer` fixture in `tests/integration/conftest.py` is the (allowed) exception; the per-test clones operate *inside* that single session-scoped container, so no new Docker usage is introduced.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Replace `tests/integration/conftest.py`'s outer-transaction-rollback isolation pattern with **per-test PostgreSQL database cloning** (`CREATE DATABASE … TEMPLATE …`) via the `pgtestdbpy>=0.0.1` dev dependency. Each test gets its own fresh fully-migrated database in ~25 ms (override the library's `STRATEGY=FILE_COPY` default to `WAL_LOG` — a 1-line monkey-patch on `pgtestdbpy.QRY_DB_CLONE` is the difference between a ~10-min sweep and a ~28-min sweep on this codebase). The per-test clone URL is exported via `IW_CORE_DB_*` env vars so `iw` CLI subprocesses spawned by tests inherit the isolated DB and their commits cannot leak — closing the gap that defeated savepoint-only and per-module-TRUNCATE designs in CR-00049. With this change, `-p no:randomly` is removed from `pyproject.toml [tool.pytest.ini_options] addopts` and the integration + dashboard suite stays green under `pytest-randomly` across all 4 reference seeds.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `tests/CLAUDE.md` for the testing rules (testcontainer-only, `monkeypatch` over `importlib.reload`, FTS DDL hook, `DaemonEvent.event_metadata`). Read `skills/iw-ai-core-testing/SKILL.md` §2 for the current opt-in recipe + cleanup contract this CR satisfies. Read `ai-dev/work/TESTS_ENHANCEMENT.md` §5 (`P1-CR-C-followup-randomly` row) and §11 changelog (CR-00048 fallback + CR-00049 cancellation). Read `docs/research/R-00077-pytest-randomly-isolation-strategy.md` for the full design rationale — Appendix A of R-00077 contains the implementation outline that this CR follows verbatim.

## Current Behavior

`pytest-randomly>=3.15` is installed as a dev dependency but is **off-by-default** via `-p no:randomly` in `pyproject.toml` `[tool.pytest.ini_options] addopts`. `make test-unit`, `make test-integration`, and `make diff-coverage` all run in deterministic (alphabetical) file order.

Running the integration + dashboard suites together under random order — `uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q --no-cov` — currently produces **271 failed + 12 errors** across many modules (verified 2026-05-16, log preserved at `/tmp/cr49_seed12345_v3.log`). The leak source is two-fold:

1. **Cross-module pollution** — tests in module A invoke `iw` CLI subprocesses or open helper engine connections that commit rows that persist into module B's tests. Outer-transaction rollback only undoes work the bound test session did; subprocess commits escape it entirely.
2. **Intra-module migration mutation** — tests in `test_oss_migration.py`, `test_project_oss_job_migration.py`, `test_db_identity_integration.py`, `test_pending_migration_log_migration.py`, and `test_i_00062_migration.py` use their own module-scoped engines and mutate schema mid-module (e.g. downgrade + re-upgrade); random intra-module order leaves siblings with the wrong schema.

CR-00049 attempted two designs and abandoned both: savepoint sessions alone left the 271 cross-module failures unaddressed; per-test TRUNCATE-CASCADE caught everything but added 18 min of wall-clock per sweep (a 3× regression on every `make test-integration` run); per-module TRUNCATE got the suite back to ~10 min but left ~230 within-module CLI-subprocess failures.

Docs that describe the off-by-default state and the opt-in recipe: `tests/CLAUDE.md` §7, `docs/IW_AI_Core_Testing_Strategy.md` §3 subsection + §9 gaps-table row, `skills/iw-ai-core-testing/SKILL.md` §2 (also synced to `.claude/skills/iw-ai-core-testing/SKILL.md`).

## Desired Behavior

After this CR ships:

- `pyproject.toml` `[tool.pytest.ini_options] addopts` no longer contains `-p no:randomly`. The default invocation is randomised; the per-run seed prints at the top of every pytest run (`Using --randomly-seed=<N>`).
- The integration + dashboard suite is green under `-p randomly` across **all four reference seeds (12345 / 67890 / 11111 / 42424)** — spike-validated on 2026-05-16 producing `~2 520 passed, ~34 skipped, ~5 xfailed, 0 failures, 0 errors` per seed in 10–13 min wall-clock.
- The mechanism is per-test PostgreSQL template-clone:
  - The session-scoped `PostgresContainer("postgres:15-alpine")` is kept.
  - A session-scoped `pgtestdbpy.templates()` context manager builds the migrated template **once** (a custom `_migrate_template` callable runs OSS enums + alembic upgrade + `Base.metadata.create_all`).
  - Per-test, `pgtestdbpy.clone()` creates a fresh database via `CREATE DATABASE … TEMPLATE …` (with the WAL_LOG strategy override) and the test's `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD` env vars are monkeypatched to point at the clone — so any `iw` subprocess spawned by the test commits into the isolated clone.
  - The clone is dropped at test teardown by `pgtestdbpy.clone()`'s context manager.
- A new module-level autouse `_restore_iw_core_instance_row` fixture in `tests/integration/test_db_identity_integration.py` repairs the `iw_core_instance` row after sibling tests DELETE / downgrade it — fixes the 3 `TestDaemonStartupGate` methods + the pre-roundtrip read in `TestMigrationRoundtrip` that otherwise break under random intra-module order.
- Two module-scoped test-class teardowns re-apply the migration SQL after the intentional downgrade tests:
  - `tests/integration/test_oss_migration.py::TestOssMigrationDowngrade::test_downgrade_drops_tables`
  - `tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade::test_downgrade_drops_table`
- Three quarantines (already validated as necessary by the spike) — module-scoped `migrated_engine` tests the per-test clone cannot reach — are marked `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason="…")` with `# NOTE(P1-CR-C-followup-randomly):` tracking comments:
  - `tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`
  - `tests/integration/test_pending_migration_log_migration.py::test_valid_enum_values_accepted`
  - `tests/integration/db/test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade`
- `tests/dashboard/conftest.py` re-exports the new session-scoped `_pgtestdb_setup` fixture alongside the existing fixtures — **without this re-export every dashboard test fails with `fixture '_pgtestdb_setup' not found`** (the spike confirmed 549 such errors before the re-export was added).
- `tests/CLAUDE.md` §7, `docs/IW_AI_Core_Testing_Strategy.md` §3 subsection + §9 row, `skills/iw-ai-core-testing/SKILL.md` §2 are flipped from ⚠️ "off-by-default fallback" to ✅ "default-on; integration suite robust to randomisation via per-test PostgreSQL template-clone (`pgtestdbpy`)". The fallback paragraph is preserved as a short "Earlier fallback (CR-00048)" historical note at section end (not silently deleted).
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-C-followup-randomly` flipped to **DONE (CR-00055, 2026-05-16)**; item 1.4 flipped from **PARTIAL** → **DONE (CR-00055)**; §11 changelog entry added with the strategy summary + 4-seed verification numbers + reference to R-00077.
- `.claude/skills/iw-ai-core-testing/SKILL.md` in sync with `skills/iw-ai-core-testing/SKILL.md` (via `iw sync-skills --force iw-ai-core-testing`).
- **Wall-clock impact on `make test-integration` is ≤ 12 min** (spike measured 10 min 54 s on seed 12345, 12–14 min on other seeds running in parallel with each other). Pre-CR-00049 unrandomised baseline was ~10 min; the ~8 % overhead is the per-test `CREATE DATABASE` cost (~25 ms × ~2 500 tests amortised against test work).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `pyproject.toml [tool.pytest.ini_options] addopts` | trailing `-p no:randomly` | `-p no:randomly` removed; comment block rewritten to describe default-on behaviour with the CR-00048 fallback as a brief historical note |
| `pyproject.toml [dependency-groups] dev` | no `pgtestdbpy` | `pgtestdbpy>=0.0.1` added |
| `uv.lock` | unchanged | regenerated to include `pgtestdbpy` |
| `tests/integration/conftest.py` `db_engine` fixture | session-scoped; opens engine on the testcontainer's shared DB; runs OSS enums + alembic upgrade + `Base.metadata.create_all` once | function-scoped; clones the template via `pgtestdbpy.clone`, monkeypatches `IW_CORE_DB_*` env vars to the clone URL, yields engine bound to the clone |
| `tests/integration/conftest.py` `_db_test_connection` fixture | opens connection + outer transaction; rolls back at teardown | opens connection only (no outer tx needed — clone is dropped at teardown) |
| `tests/integration/conftest.py` (new) `_migrate_template` function | did not exist | session-scoped callable invoked by `pgtestdbpy.templates()` to apply OSS enums + alembic upgrade + `Base.metadata.create_all` to the template DB **once** |
| `tests/integration/conftest.py` (new) `_pgtestdb_setup` fixture | did not exist | session-scoped autouse-adjacent fixture that wraps `pgtestdbpy.templates(config, migrator)`; yields `(config, migrator)` |
| `tests/dashboard/conftest.py` fixture re-exports | exports `_db_test_connection`, `db_engine`, `db_session`, `db_session_factory`, `pg_container`, `test_project` | also re-exports `_pgtestdb_setup` (otherwise every dashboard test fails at fixture resolution) |
| `tests/integration/test_oss_migration.py::TestOssMigrationDowngrade.test_downgrade_drops_tables` | downgrades then asserts; leaves schema downgraded | downgrades, asserts, then re-applies `MIGRATION_SQL` so siblings find the schema migrated |
| `tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade.test_downgrade_drops_table` | downgrades then asserts; leaves schema downgraded | downgrades, asserts, then re-applies `MIGRATION_SQL` |
| `tests/integration/test_db_identity_integration.py` (new) module-level autouse `_restore_iw_core_instance_row` | did not exist | runs before every test in the module; SELECTs `pg_tables` for `iw_core_instance`, runs `alembic upgrade head` if the table is missing, then INSERTs the (id=1, gen_random_uuid()) row if absent — mirrors the existing class-scoped `TestDashboardHealthzIdentity::ensure_instance_row` but at module scope |
| `tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` | runs and may pass or fail under random order | `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason="…")` + `# NOTE(P1-CR-C-followup-randomly):` |
| `tests/integration/test_pending_migration_log_migration.py::test_valid_enum_values_accepted` | runs and may fail under random order | quarantined with the same triad |
| `tests/integration/db/test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade` | runs and may fail under some seeds | quarantined with the same triad |
| `tests/CLAUDE.md` §7 | "off-by-default; opt-in recipe; cleanup contract" | "default-on; reproduce recipe; quarantine policy"; old paragraph moves to "Earlier fallback (CR-00048)" historical note |
| `docs/IW_AI_Core_Testing_Strategy.md` §3 + §9 row | ⚠️ rows + fallback paragraph | ✅ rows + "default-on via per-test template-clone" prose; historical-note pattern |
| `skills/iw-ai-core-testing/SKILL.md` §2 | "currently OFF-by-default" | "default-on" + reproduce recipe + quarantine policy |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | mirror of master | re-synced via `iw sync-skills --force iw-ai-core-testing` |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §5 follow-up row open after CR-00049 cancellation, item 1.4 PARTIAL, §11 stops at 2026-05-16 CR-00049 cancellation | §5 row DONE (CR-00055), item 1.4 DONE (CR-00055), §11 entry added with full strategy summary + 4-seed verification |

### Breaking Changes

**None.** The fixture API (`db_session`, `db_session_factory`, `test_project`, `cli_get_session`) is preserved byte-for-byte. Only internal plumbing of `db_engine` and `_db_test_connection` changes — and those are documented as private (leading underscore on `_db_test_connection`). No production code touched; no CLI flag, daemon contract, or GH Actions workflow shape changes. The only externally observable effect is the extra "Using --randomly-seed=<N>" line at the top of pytest output.

### Data Migration

**None.** No DB tables, no rows, no migrations touched. The schema-bearing data is the template database — built and dropped within each test session.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `pgtestdbpy` dev dep; rewrite `tests/integration/conftest.py` fixture chain (`_migrate_template`, `_pgtestdb_setup`, `db_engine`, `_db_test_connection`); re-export `_pgtestdb_setup` from `tests/dashboard/conftest.py`; add 2 class teardowns + 1 module-level autouse fixture + 3 quarantines; remove `-p no:randomly` from `addopts` + rewrite comment block; flip 4 doc locations to default-on with historical note; `iw sync-skills --force iw-ai-core-testing`; update `ai-dev/work/TESTS_ENHANCEMENT.md` §5 + item 1.4 + §11 changelog | — |
| S02 | code-review-impl | Per-agent review of S01 — verify the WAL_LOG override is present (this is the perf-cliff hinge), all 4 doc locations flipped consistently, 3 quarantines + 2 teardowns + 1 autouse fixture all in place, `.claude/skills/iw-ai-core-testing/SKILL.md` matches master byte-for-byte, no production code touched, no scope creep | — |
| S03 | code-review-final-impl | Global cross-agent review — re-run the 4-seed sweep recipe (12345 / 67890 / 11111 / 42424) to independently verify all green, no scope creep beyond `allowed_paths` | — |
| S04 | qv-gate (lint) | `make lint` | — |
| S05 | qv-gate (assertions) | `make test-assertions` | — |
| S06 | qv-gate (format) | `make format-check` | — |
| S07 | qv-gate (typecheck) | `make type-check` | — |
| S08 | qv-gate (unit-tests) | `make test-unit` — first run with `pytest-randomly` default-on; will print `Using --randomly-seed=<N>` | — |
| S09 | qv-gate (integration-tests) | `make test-integration` — first run with `pytest-randomly` default-on; expect ≤ 12 min wall-clock | — |
| S10 | qv-gate (diff-coverage) | `make diff-coverage` — the gate that previously burned 5 fix cycles on CR-00048; passing here is the definitive proof randomisation cleanup landed | — |
| S11 | qv-gate (security-secrets) | `make security-secrets` (gitleaks) | — |
| S12 | self-assess-impl | Self-assessment via `iw-item-analyze`; cross-reference patterns with CR-00048 + cancelled CR-00049 — did the spike branch reference + the R-00077 outline keep S01 inside its budget? Did any seed surface a new offender beyond the 3 known quarantines? | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No alembic changes. The "template" DB built by `pgtestdbpy.templates()` is an ephemeral session-scoped database within the testcontainer; it has no lifecycle outside the pytest session.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00055_CR_Design.md` | Design | This document |
| `CR-00055_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00055_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00055_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/CR-00055_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review instructions |
| `prompts/CR-00055_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment instructions |

QV gate steps S04–S11 are command-only (no prompt file).

## Acceptance Criteria

### AC1: `-p no:randomly` removed from `addopts`

```
Given the merged branch
When  `grep -n 'no:randomly' pyproject.toml` runs from the repo root
Then  it returns no matches (exit code 1)
And   `grep -n 'pgtestdbpy' pyproject.toml` returns at least one match in the `[dependency-groups] dev` block
And   `--strict-markers` is still present in `addopts`
```

### AC2: 4-seed sweep green

```
Given the merged branch
When  the following runs:
        for seed in 12345 67890 11111 42424; do
          uv run pytest tests/integration/ tests/dashboard/ \
            --ignore=tests/dashboard/browser \
            -p randomly --randomly-seed=$seed -q --no-cov
        done
Then  each invocation exits 0
And   the per-seed pass count is ≥ 2 520
And   the per-seed failure + error count is 0
And   the per-seed xfailed + xpassed total is between 3 and 6 (the 3 carry-forward quarantines + 2 pre-existing CR-00048 xfails; some show as xpassed depending on seed)
```

### AC3: Wall-clock budget

```
Given the merged branch
When  `time make test-integration` runs on the reference dev box
Then  the wall-clock is ≤ 12 minutes
And   the suite logs `Using --randomly-seed=<N>` at the top (proves randomisation is on)
```

### AC4: Docs flipped consistently

```
Given the merged branch
When  the four doc locations are read:
        - tests/CLAUDE.md §7
        - docs/IW_AI_Core_Testing_Strategy.md §3 (pytest-randomly subsection)
        - docs/IW_AI_Core_Testing_Strategy.md §9 ("Test-order randomisation" row)
        - skills/iw-ai-core-testing/SKILL.md §2
Then  each location describes randomisation as default-on
And   each location explains the mechanism (per-test PostgreSQL template-clone via pgtestdbpy + IW_CORE_DB_* env var monkeypatch for subprocess inheritance)
And   each location preserves a brief "Earlier fallback (CR-00048)" historical note rather than silently deleting the prior prose
And   the §9 row prefix is "✅ (CR-00055, 2026-05-16) — default-on; …"
```

### AC5: Plan + changelog updated

```
Given the merged branch
When  ai-dev/work/TESTS_ENHANCEMENT.md is read
Then  the §5 row "P1-CR-C-followup-randomly" status is "DONE (CR-00055, 2026-05-16)" with the strategy summary + 4-seed verification
And   the item 1.4 row status is "✅ DONE (CR-00055, 2026-05-16)" (previously PARTIAL)
And   the §11 changelog has a new entry dated 2026-05-16 referencing CR-00055, the per-test template-clone strategy, the WAL_LOG override, the 3 quarantines + 2 teardowns + 1 autouse fixture, and the 4-seed verification numbers
```

### AC6: Skill in sync

```
Given the merged branch
When  `diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` runs
Then  the command produces no output (files are byte-identical)
```

## Rollback Plan

- **Database**: N/A. No schema or data changes.
- **Code**: Revert the squash-merge commit. The fixture API is preserved, so existing test code keeps working with the older `db_engine` (session-scoped) + `_db_test_connection` (outer-tx rollback) pair. `pyproject.toml` regains `-p no:randomly`. The docs flip back to "off-by-default" via the revert.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00048 (P1-CR-C — `pytest-randomly` dev dep + `--strict-markers` + `order_dependent` marker registration). CR-00048 is merged at `a789701` (2026-05-13); this CR builds on its foundation. Independently: R-00077 (the research that produced this design) is published as a draft research doc.
- **Blocks**: None. P1-CR-A-followup (assertion baseline scrub) and Phase 2 work (mutation testing, Hypothesis property tests) are independent of this CR.

## Impacted Paths

- `pyproject.toml`
- `uv.lock`
- `tests/integration/conftest.py`
- `tests/dashboard/conftest.py`
- `tests/integration/test_oss_migration.py`
- `tests/integration/test_project_oss_job_migration.py`
- `tests/integration/test_db_identity_integration.py`
- `tests/integration/test_pending_migration_log_migration.py`
- `tests/integration/db/test_i_00062_migration.py`
- `tests/CLAUDE.md`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

No production code (`orch/**`, `dashboard/**`, `executor/**`). No migrations (`orch/db/migrations/**`). No GH Actions workflow changes (`.github/workflows/**`).

## TDD Approach

- **TDD anchor — the RED reproduction itself.** Deliverable 0 of S01 runs the 4-seed sweep against the **un-fixed** state and captures the failure counts (the `/tmp/cr49_seed12345_v3.log` data — 271 failed + 12 errors — is recorded as `tdd_red_evidence`). The GREEN evidence is deliverable 4's 4-seed sweep ending all-clean.
- **No new test files.** This CR fixes the existing 2 500+ tests by giving them better isolation; it does not add behavioural tests. New tests under random order are the proof.
- **Updated tests**: 2 class teardowns (`test_oss_migration.py::TestOssMigrationDowngrade.test_downgrade_drops_tables`, `test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade.test_downgrade_drops_table`) and 1 new module-level autouse fixture (`_restore_iw_core_instance_row` in `test_db_identity_integration.py`). These are **test-isolation fixes only**, not behavioural changes.
- **Bounded exception authorised**: deliverables 0 + 4 may run `pytest tests/integration/ tests/dashboard/ -p randomly --randomly-seed=<N>` (×4 seeds total). Outside those two deliverables the standard rule applies — no `make check`, no `make test-integration`, no `make diff-coverage` in S01; those are S08 / S09 / S10's job.

## Notes

- **Spike reference**: a working end-to-end implementation lives on branch `spike/pgtestdbpy-isolation` (HEAD as of 2026-05-16). The S01 prompt directs the implementing agent to `git diff main..spike/pgtestdbpy-isolation` to crib the exact working code — this should eliminate the agent's diagnostic budget and let it focus on the docs + plan updates. The spike's diff covers every file in the impacted-paths list above except `pyproject.toml` comment-block rewrite, doc flips, `TESTS_ENHANCEMENT.md` updates, and the `iw sync-skills --force` step.
- **The WAL_LOG override is the perf-cliff hinge.** `pgtestdbpy>=0.0.1` hardcodes `STRATEGY=FILE_COPY` in its `QRY_DB_CLONE` constant. On this codebase's schema size (~30 tables, many indexes, FTS triggers), FILE_COPY runs ~310 ms per clone vs ~25 ms for WAL_LOG — the difference between a ~28 min sweep and a ~10 min sweep (measured 2026-05-16 in the spike). The override is one line: `pgtestdbpy.QRY_DB_CLONE = 'CREATE DATABASE "{db_name}" WITH TEMPLATE "{template}" OWNER "{user}"'` (drops the `STRATEGY=FILE_COPY` suffix; PostgreSQL 15+ defaults to WAL_LOG). Setting this BEFORE `pgtestdbpy.templates()` is entered is mandatory because `clone()` reads the constant on every invocation. The S02 review must verify this line is present.
- **Bake `--no-cov` into the bounded sweep.** Running `pytest --cov` four times in S01 adds ~30–40 % per-sweep overhead and is wasted work — S10 `diff-coverage` builds its own combined coverage. The CR-00049 daemon-launched S01 burned its 80 m budget partly on `--cov` sweeps. Use `--no-cov` for the bounded multi-seed sweep.
- **The 3 quarantines + the new module-level autouse fixture + the 2 class teardowns** are all spike-validated as necessary. Seed 12345 + 67890 are green with just the autouse fixture; seeds 11111 + 42424 require the I-00062 quarantine to also be green. Add all three quarantines pre-emptively so all 4 seeds pass on the first attempt.
- **The `pgtestdbpy` library is new and lightly maintained.** Verified `pgtestdbpy==0.0.1` works against `postgres:15-alpine` testcontainer (smoke-tested 2026-05-16). If the library disappears, the spike's `_migrate_template` + `_pgtestdb_setup` + `db_engine` fixtures can be vendored in (~100 lines) — this CR's risk is bounded.
- **Orthogonal follow-up (not in scope here)**: scope down the 3 quarantined tests' `migrated_engine` fixtures to function scope, eliminating the quarantines. File as `P1-CR-C-followup-randomly-quarantine-cleanup` after this CR merges. Low urgency — quarantines aren't blocking.
- **Housekeeping (not in scope here)**: archive `ai-dev/active/CR-00049/` → `ai-dev/archive/CR-00049/` (CR-00049 is in `cancelled` state but its scaffold is still in `active/`). File as a tiny direct commit OR fold into a Phase-1 archival sweep — operator's call.
