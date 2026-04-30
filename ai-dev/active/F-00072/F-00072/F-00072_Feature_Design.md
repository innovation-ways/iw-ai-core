# F-00072: Pragmatic Migration Safety + Schema Validation

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-29
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Migration roundtrip tests use testcontainers — explicitly allowed exception. NO operations against the live orchestration DB on port 5433.)

## ⛔ Migrations: agents generate, daemon applies

This feature adds a TEST around migrations; it does NOT add a new migration. **Critical**: tests run against testcontainers ONLY. The `make db-migrate` / `alembic upgrade` commands MUST NOT be invoked against the live DB at any point during this feature's implementation or its tests.

## Description

Add a pragmatic safety net around alembic migrations: a parameterised
testcontainer-based test that, for each of the latest 3 revisions,
upgrades to that revision, downgrades by one, and re-upgrades — proving
each migration's `downgrade()` is at least non-erroring. Plus a CI
workflow that runs `alembic check` on every PR to catch model/schema
drift (a model field added without a corresponding migration). This is
the pragmatic-tier choice the user picked over strict roundtrip testing
of every revision in the planning conversation 2026-04-29.

## Project Context

Read `CLAUDE.md`, `tests/CLAUDE.md`, `docs/IW_AI_Core_Database_Schema.md`, `docs/IW_AI_Core_Daemon_Design.md`. Existing migration-related tests live in `tests/integration/` (`test_migration_pipeline*.py`, `test_migration_lock.py`, several per-migration tests). This feature complements them with a generic latest-N roundtrip test that does NOT need to be updated when a new migration is added.

## Scope

### In Scope

1. **Generic roundtrip test** — `tests/integration/test_migration_roundtrip.py`:
   - Uses the existing testcontainer pattern from `tests/conftest.py`.
   - Reads `alembic history` to get the ordered list of revisions.
   - For each of the **last 3 revisions** (parameterised), using a shared module-scoped testcontainer:
     - `alembic downgrade base` (reset to empty — ensures clean state for each parametrized case)
     - `alembic upgrade <rev>` (target this revision via Python API: `alembic.command.upgrade`)
     - `alembic downgrade <parent_rev_id>` (**explicit** parent revision ID looked up from `ScriptDirectory` — rule 4a: **never** `-1`; if rev is the base, skip downgrade)
     - `alembic upgrade head` (restore to head)
     - Assert: each command completes without raising (use `alembic.command.*` Python API, not subprocess).
     - Assert: after the final upgrade, the schema matches what `Base.metadata` expects (use `inspect(engine).get_table_names()` vs expected-set comparison).
   - The test name MUST include the revision ID so a failure is unambiguous.
   - The test MUST NOT touch the live DB. Use testcontainers only. Use the `pg_engine` fixture pattern.
   - The test marks itself with the existing `@pytest.mark.integration` marker so it runs under `make test-integration`.

2. **Schema validation CI workflow** — `.github/workflows/schema-validation.yml`:
   - Triggers: `pull_request` to main, `push` to main.
   - Permissions: `contents: read` only (no SARIF here — failures surface as workflow status).
   - Single job that:
     - Spins up a Postgres service container (matching the version used in production — see `docker-compose.bootstrap.yml`).
     - Installs deps via `uv sync --frozen`.
     - Runs `uv run alembic upgrade head`.
     - Runs `uv run alembic check` — fails if there's drift between models and migrations.
   - All `uses:` pinned to commit SHAs (matching `compliance-scan.yml` convention).
   - Action versions documented with trailing `# vN.N.N` comments.

3. **Smoke regression guard** — `tests/unit/test_migration_roundtrip_targets.py`:
   - Asserts the roundtrip test file exists.
   - Asserts the schema-validation workflow file exists.
   - Asserts the workflow runs `alembic check` (grep for the string).
   - Asserts the workflow uses pinned SHAs (40-char regex).

4. **Documentation** — append a short note (≤80 words) to `docs/IW_AI_Core_Daemon_Design.md` (or `tests/CLAUDE.md`, whichever is more visible) explaining:
   - The roundtrip test runs only the latest 3 revs (pragmatic choice).
   - `alembic check` is the drift gate.
   - When a developer adds a new migration, neither file needs to be edited — the test parameterisation reads alembic history dynamically.

### Out of Scope

- Strict roundtrip testing of every historical revision (rejected as too costly per user decision 2026-04-29).
- A new alembic migration of any kind.
- Modifications to `alembic.ini` or `orch/db/migrations/env.py` (other than additions if strictly required for testcontainer wiring; flag and discuss before changing).
- Modifications to live-DB connection logic.
- Schema documentation auto-generation (skipped per user decision; was tied to the dropped ERD work).
- Touching existing per-migration tests.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | tests/integration/test_migration_roundtrip.py + .github/workflows/schema-validation.yml + docs blurb | — |
| S02 | code-review-impl | Review S01 (test pattern + workflow + safety) | — |
| S03 | tests-impl | tests/unit/test_migration_roundtrip_targets.py — regression guard | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | code-review-final-impl | Cross-cutting global review | — |
| S06–S10 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |

No frontend / browser verification.

### Database Changes

None. (This feature TESTS migrations; it does not add one.)

### API Changes

None.

### Frontend Changes

None.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00072/F-00072_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00072/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00072/prompts/F-00072_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `ai-dev/active/F-00072/prompts/F-00072_S02_CodeReview_prompt.md` | Prompt | Review of S01 |
| `ai-dev/active/F-00072/prompts/F-00072_S03_Tests_prompt.md` | Prompt | Smoke regression guard |
| `ai-dev/active/F-00072/prompts/F-00072_S04_CodeReview_Tests_prompt.md` | Prompt | Review of S03 |
| `ai-dev/active/F-00072/prompts/F-00072_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `tests/integration/test_migration_roundtrip.py` | New | Generic roundtrip test for latest 3 revs |
| `.github/workflows/schema-validation.yml` | New | CI workflow running `alembic check` |
| `tests/unit/test_migration_roundtrip_targets.py` | New | Regression guard for the above |
| `docs/IW_AI_Core_Daemon_Design.md` or `tests/CLAUDE.md` | Modified | Brief explainer |

## Acceptance Criteria

### AC1: Roundtrip test passes for latest 3 revisions

```
Given the testcontainer-based pg_engine fixture is healthy
When the developer runs `make test-integration` (or pytest tests/integration/test_migration_roundtrip.py)
Then for each of the latest 3 revisions, the test executes upgrade(rev) -> downgrade(-1) -> upgrade(head)
And every alembic invocation exits 0
And after the final upgrade, the schema matches Base.metadata
And the test name in pytest output includes the revision short SHA so failures are unambiguous
```

### AC2: Test ignores live DB

```
Given a test session runs (any environment)
When the migration roundtrip test executes
Then no connection is opened to the live orchestration DB on port 5433
And the test fails clean (not silently passes) if the testcontainer fixture is unavailable
And the test honors all rules in tests/CLAUDE.md
```

### AC3: schema-validation workflow runs on PRs

```
Given a PR is opened against main
When the schema-validation.yml workflow triggers
Then a Postgres service container is started, deps installed, `alembic upgrade head` runs, `alembic check` runs
And the workflow fails if `alembic check` reports drift (model field without migration)
And the workflow passes on a clean PR
```

### AC4: Regression guard catches deletions

```
Given a developer accidentally deletes the roundtrip test or removes alembic check from the workflow
When `make test-unit` runs
Then tests/unit/test_migration_roundtrip_targets.py fails with a clear message naming what's missing
```

### AC5: Adding a new migration does not require editing F-00072 files

```
Given a developer adds a new alembic revision
When they re-run `make test-integration`
Then the roundtrip test automatically picks up the new revision (latest 3 sliding window)
And no edits to test_migration_roundtrip.py or schema-validation.yml are required
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Repo has fewer than 3 revisions | Hypothetical | Test parameterises over what exists; passes on the available set; does NOT crash on parametrize |
| Migration's `downgrade()` raises | Real bug | Test fails with the alembic error and the revision short SHA |
| `alembic check` reports drift | Model added without migration | Workflow fails; PR blocked |
| Testcontainer fails to start | Network/Docker issue | Test fails with the existing skip-or-fail behavior in `tests/conftest.py` (don't reinvent) |
| Live DB on 5433 unreachable | Production DB down | No effect — test does not connect there |
| New migration added between test parametrize collection and execution | Race-condition | Acceptable — collection is a single subprocess invocation |
| `IW_CORE_AGENT_CONTEXT=true` set | Agent run | Test still passes via testcontainer (env var only blocks live-DB alembic operator commands) |
| `pytest -k roundtrip` invoked | Targeted run | Just the roundtrip test runs, not the rest of the integration suite |

## Invariants

1. The roundtrip test MUST never connect to the live orchestration DB on port 5433.
2. The roundtrip test parameterisation reads alembic history at collection time — adding a new migration auto-shifts the window with no test edits.
3. `schema-validation.yml` action `uses:` are pinned to 40-char commit SHAs.
4. The workflow's permissions are `contents: read` only.
5. No new alembic migrations are created by this feature.
6. The test honors `tests/CLAUDE.md`'s strict live-DB-guard rules (no `importlib.reload(orch.config)`, no monkeypatching that bypasses the guard, etc.).
7. The Postgres major version in `schema-validation.yml` matches the production DB version (introspect from `docker-compose.bootstrap.yml`).
8. The roundtrip test handles the case of "fewer than 3 revisions in history" without crashing — parametrize over `min(3, len(revs))`.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Integration test**: `tests/integration/test_migration_roundtrip.py` — itself the deliverable. Write RED first by deliberately introducing a bad downgrade in a temp migration (do NOT commit), confirm test fails, restore.
- **Unit smoke test**: `tests/unit/test_migration_roundtrip_targets.py` — string assertions on file contents.
- **Edge cases**:
  - Latest revision's downgrade is a no-op (rolls back the migration's effect cleanly).
  - Only 2 revisions available (parametrize correctly handles the slice).
  - Base revision (no parent): downgrade step is skipped, only upgrade→reset is exercised.

## Notes

- **Why "latest 3" specifically**: covers the highest-risk window (the last few changes, where bugs are most likely fresh and not yet exercised by users) without exploding CI time. Older revisions are a one-time-only transition; if they were bad, the daemon's pre-merge dry-run (`uv run iw migrations dry-run`) would have caught them at the time. Documented in the user's planning conversation 2026-04-29.
- The test should NOT itself invoke `iw migrations apply` (operator-only). It should drive alembic via the `alembic` Python API or `subprocess` against the testcontainer's URL.
- The test MUST use `psycopg` (not `psycopg2`) per `CLAUDE.md`'s rule about replacing `postgresql+psycopg2://` with `postgresql+psycopg://` in testcontainers.
- This feature is independent of F-00069/F-00070/F-00071 — the batch executor can run all four in parallel.
