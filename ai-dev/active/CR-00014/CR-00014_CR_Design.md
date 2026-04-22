# CR-00014: Orchestration DB instance-identity fingerprint

**Type**: Change Request
**Priority**: High
**Reason**: Defense-in-depth against silent DB swap / impostor. On 2026-04-22 the pre-existing `postgres` orchestration container was SIGKILLed and an empty compose-managed container took over port 5433 for ~80 minutes with no visible symptom. A fingerprint check would have failed loud immediately.
**Created**: 2026-04-22
**Status**: Draft

---

## Description

Introduce a single-row `iw_core_instance` table holding a UUID that uniquely identifies the orchestration database instance. Store the expected UUID in `.env` as `IW_CORE_EXPECTED_INSTANCE_ID`. Every process that talks to the orchestration DB — the daemon, `ai-core.sh status`, and the dashboard — verifies the live UUID matches the expected one on startup. On mismatch the process refuses to start/serve with a loud, unambiguous error.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. In particular: the orchestration DB is a long-lived, bind-mount-backed postgres container (NOT compose-managed in production) — see `docs/IW_AI_Core_Architecture.md`. All operational state lives in that one DB, so misidentification is catastrophic.

## Current Behavior

Nothing checks DB identity. Any process that can reach `postgres://…:5433/iw_orch` with the `iw_orch` credentials connects to whatever is there. If the container is replaced (accidentally or maliciously) and the schema looks compatible, the daemon, the dashboard, and `ai-core.sh` all report green. The 2026-04-22 incident is the concrete example: an empty DB with correct schema but zero data was accepted as healthy.

Specific integration points:
- `orch/daemon/main.py` has a `Running startup health check` phase that verifies DB connectivity via a simple `SELECT 1`-class query and logs "Database connection verified" but never inspects DB identity.
- `dashboard/app.py` builds the FastAPI app; there is no identity gate on startup or on any health endpoint.
- `ai-core.sh` `cmd_status` queries `daemon_events` and reports "PostgreSQL: accepting connections" based on `pg_isready` only.
- `.env` has `IW_CORE_DB_*` connection vars but no identity pin.

## Desired Behavior

1. The orchestration DB carries a stable, unguessable UUID in a new `iw_core_instance` table.
2. `.env` has a new var `IW_CORE_EXPECTED_INSTANCE_ID` holding that UUID on any machine that connects to the DB.
3. On daemon startup, the startup health check calls `verify_instance_identity()`. On mismatch it raises and the daemon **refuses to enter the main loop**, printing an error block that names both UUIDs (expected vs. actual) and a short remediation hint.
4. On dashboard startup (before serving requests), the app performs the same verification. On mismatch it refuses to accept traffic (startup aborts) AND `/healthz/identity` returns `503` when polled from the outside.
5. `ai-core.sh status` runs a new `iw db-identity --check` CLI command and renders a green PASS or red FAIL line in its output.
6. A soft-bootstrap mode is supported: if `IW_CORE_EXPECTED_INSTANCE_ID` is unset AND the `iw_core_instance` row is populated, processes log a one-shot INFO line showing the live UUID and the exact `.env` line to add, then proceed normally (warn-only). This prevents the CR itself from hard-breaking existing deployments the first time it's rolled out.
7. A missing `iw_core_instance` row (e.g., after a post-downgrade) is treated as a hard failure when the env var is set.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|---|---|---|
| `orch/db/models.py` | 20+ models; no identity model | Add `IwCoreInstance` (single-row table) |
| `orch/db/migrations/versions/` | head `824e6e6f34ee` | New migration creates table + seeds UUID |
| `orch/db/identity.py` | Does not exist | New module with `verify_instance_identity()` + bootstrap helper |
| `orch/daemon/main.py` | Startup health check verifies connectivity only | Also calls `verify_instance_identity()`; aborts on mismatch |
| `dashboard/app.py` | No identity gate | Startup-event calls verify; aborts if mismatch. New `/healthz/identity` route |
| `orch/cli/` | No identity command | New `iw db-identity {show\|check}` command |
| `ai-core.sh` | `cmd_status` shows DB reachability only | Adds identity PASS/FAIL line |
| `.env` / `.env.example` | No identity var | Adds `IW_CORE_EXPECTED_INSTANCE_ID` |

### Breaking Changes

- Once `IW_CORE_EXPECTED_INSTANCE_ID` is set, a DB swap becomes a hard error. **That is the point** and must be called out in release notes.
- During the rollout window (before the env var is set), processes operate in warn-only mode — no hard break.

### Data Migration

- One-row INSERT of `gen_random_uuid()` in the same migration that creates the table. Idempotent guard: `INSERT ... ON CONFLICT (id) DO NOTHING`.
- Migration is reversible: downgrade drops the row + table.
- No existing data is touched.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration + `IwCoreInstance` ORM model | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | `orch/db/identity.py`, daemon wiring, `iw db-identity` CLI, `ai-core.sh` wiring | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | api-impl | Dashboard startup gate + `/healthz/identity` endpoint | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | tests-impl | Unit + integration tests | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | code-review-final-impl | Global cross-layer review | — |
| S10 | qv-gate (lint) | `make lint` | — |
| S11 | qv-gate (format) | `uv run ruff format --check .` | — |
| S12 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S13 | qv-gate (unit-tests) | `make test-unit` | — |
| S14 | qv-gate (integration-tests) | `make test-integration` | — |

### Database Changes

- **New tables**: `iw_core_instance (id SMALLINT PK CHECK (id = 1), instance_id UUID NOT NULL, created_at TIMESTAMPTZ DEFAULT now())`
- **Modified tables**: None
- **Migration notes**: Must call `CREATE EXTENSION IF NOT EXISTS pgcrypto;` before `gen_random_uuid()` (or use `uuid-ossp` — follow existing project convention if an extension is already declared elsewhere). Row inserted within the same migration under `ON CONFLICT DO NOTHING` for idempotency.

### API Changes

- **New endpoints**: `GET /healthz/identity` — returns `{expected, actual, match: bool}`. `200` on match, `503` on mismatch, `200` with `expected: null` in bootstrap mode.
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00014/`:

| File | Type | Purpose |
|---|---|---|
| `CR-00014_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00014_S01_Database_prompt.md` | Prompt | S01 — migration + ORM model |
| `prompts/CR-00014_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/CR-00014_S03_Backend_prompt.md` | Prompt | S03 — identity module + daemon + CLI + ai-core.sh |
| `prompts/CR-00014_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/CR-00014_S05_API_prompt.md` | Prompt | S05 — dashboard health endpoint + startup gate |
| `prompts/CR-00014_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/CR-00014_S07_Tests_prompt.md` | Prompt | S07 — unit + integration tests |
| `prompts/CR-00014_S08_CodeReview_prompt.md` | Prompt | S08 — review S07 |
| `prompts/CR-00014_S09_CodeReview_Final_prompt.md` | Prompt | S09 — final cross-layer review |

## Acceptance Criteria

### AC1: Matching identity → all services start healthy

```
Given .env has IW_CORE_EXPECTED_INSTANCE_ID equal to the live DB's iw_core_instance.instance_id
When the daemon starts, the dashboard starts, and ai-core.sh status is run
Then daemon enters its main loop without errors
 And dashboard serves /healthz/identity with status 200 and {match: true}
 And ai-core.sh status prints a green "DB identity: PASS (<short-uuid>)" line
 And no WARNING banners are logged
```

### AC2: Mismatched identity → all services refuse

```
Given .env has IW_CORE_EXPECTED_INSTANCE_ID set to one UUID
  And the live DB's iw_core_instance.instance_id is a different UUID
When the daemon starts, the dashboard starts, and ai-core.sh status is run
Then daemon logs a clearly-delimited ERROR block naming both UUIDs and exits non-zero before entering the main loop
 And dashboard startup aborts (FastAPI fails to accept traffic) and any live /healthz/identity probe returns 503
 And ai-core.sh status prints a red "DB identity: FAIL (expected=… actual=…)" line and returns non-zero
```

### AC3: Bootstrap mode — env var unset

```
Given .env does NOT have IW_CORE_EXPECTED_INSTANCE_ID
  And the live DB's iw_core_instance row exists
When the daemon starts, the dashboard starts, and ai-core.sh status is run
Then each process emits exactly one INFO line showing the live UUID and the exact .env line to add
 And daemon enters its main loop, dashboard serves, ai-core.sh status reports a yellow "DB identity: UNVERIFIED" line
 And /healthz/identity returns 200 with {expected: null, actual: "<uuid>", match: null}
```

### AC4: Missing row with env var set → hard fail

```
Given .env has IW_CORE_EXPECTED_INSTANCE_ID set
  And the iw_core_instance table is empty (e.g., after a downgrade)
When the daemon starts
Then daemon aborts with an error naming the expected UUID and "row missing" remediation
```

### AC5: Migration reversible

```
Given the migration has been applied (head includes this CR's revision)
When alembic downgrade -1 is executed
Then the iw_core_instance table is dropped without error
 And re-running alembic upgrade head restores the table with a newly-generated UUID
```

### AC6: No regression in existing behavior

```
Given IW_CORE_EXPECTED_INSTANCE_ID matches (or is in bootstrap mode)
When make check is executed
Then every existing test passes with zero new failures
 And lint, format, and typecheck remain green
```

## Rollback Plan

- **Database**: `alembic downgrade -1` drops `iw_core_instance`. Table is isolated (no FKs in or out), downgrade is safe.
- **Code**: Revert the squash-merge commit. Processes return to their current (no-identity-check) behavior immediately.
- **Data**: No data loss. No existing rows modified; only a new table is added and removed.
- **Environment**: Remove `IW_CORE_EXPECTED_INSTANCE_ID` from `.env` on any host where it was set.

## Dependencies

- **Depends on**: None. (Independent CR; does not require F-00058 to land.)
- **Blocks**: None directly. Recommended prerequisite for CR-00015 (remove compose-db foot-gun) because the identity check is the safety net that makes the compose removal observably testable.

## TDD Approach

- **Unit tests** (`tests/unit/test_db_identity.py`):
  - `verify_instance_identity` — happy path (match), mismatch raises, missing row raises, bootstrap mode (env unset) returns a `BootstrapNotice` instead of raising.
  - Env-var parsing: empty string treated as unset, whitespace trimmed, case-insensitive UUID normalisation.
- **Integration tests** (`tests/integration/test_db_identity_integration.py`):
  - Spin a testcontainer DB, apply migrations, set `IW_CORE_EXPECTED_INSTANCE_ID` to a UUID **different** from the one the migration seeded. Assert daemon startup call raises `InstanceMismatchError`. Assert dashboard TestClient aborts / `/healthz/identity` returns 503.
  - Separate test: env unset, assert bootstrap notice and normal proceed.
  - Migration downgrade-then-upgrade round trip asserts table and row are recreated.
- **Updated tests**: Any daemon-startup or dashboard-startup test fixture must set `IW_CORE_EXPECTED_INSTANCE_ID` to match the seeded migration UUID in its testcontainer. A shared fixture (`identity_matched`) in `tests/conftest.py` is the cleanest pattern.

## Notes

- **Migration lock warning**: At design-time the migration lock is held by F-00058. Before S01 runs, release the stale lock (F-00058's S01 was killed on 2026-04-22; lock is stale). The S01 prompt handles this.
- **UUID extension**: Project convention is to `CREATE EXTENSION IF NOT EXISTS pgcrypto;` inside the migration. Check `orch/db/migrations/versions/a1b2c3d4e5f6_initial_schema.py` for existing extension declarations; piggy-back if one already exists.
- **Secret status**: The instance UUID is not a secret; its value is visible in `.env` which is gitignored, and knowing it does not grant any capability. Its role is integrity, not confidentiality.
- **Dashboard-auth exception**: `/healthz/identity` must bypass any auth middleware so an external probe can reach it. Follow whatever pattern existing `/healthz` routes use (if any); otherwise document as a new convention.
- **Future work**: A companion CR could make the daemon refuse to apply any migration that doesn't preserve or re-seed `iw_core_instance` (prevents accidental data-loss migrations). Out of scope here.
