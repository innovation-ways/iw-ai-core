# CR-00015: Remove docker-compose `db` service foot-gun

**Type**: Change Request
**Priority**: High
**Reason**: The 2026-04-22 data-loss incident was caused by the default `docker-compose.yml` being runnable from any git worktree, which created a per-worktree volume (`f-00058_pgdata`) and an empty `iw-ai-core-db` container that took over port 5433. Removing the `db` service from the default compose file eliminates the ambient foot-gun.
**Created**: 2026-04-22
**Status**: Draft

---

## Description

Move the sole `db` service out of the default `docker-compose.yml` into a dedicated `docker-compose.bootstrap.yml` invoked only with `-f`. Update `ai-core.sh`, `Makefile`, CLAUDE.md files, and project documentation to match. Add a new `docs/IW_AI_Core_DB_Setup.md` that documents the **production** path (raw `docker run` with bind mount) as primary and the bootstrap compose as a fallback for fresh development machines. Every developer-facing doc (top-level `README.md`, top-level `CLAUDE.md`, `docs/README.md`, `docs/IW_AI_Core_Tech_Stack.md`, `docs/implementation/01_foundation/02_config_and_db.md`) must explain **why** this split exists (the data-loss incident) so future contributors don't revert it.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key fact for this CR: **the orchestration DB on port 5433 is a pre-existing raw-docker `postgres` container with a host bind mount at `/opt/postgres/data`** — it is NOT compose-managed in production. The compose file exists only for first-time bootstrap on a developer's machine.

## Current Behavior

The repo has a single `docker-compose.yml` at the project root with one service, `db`:

```yaml
services:
  db:
    image: postgres:15-alpine
    container_name: iw-ai-core-db
    ports:
      - "${IW_CORE_DB_PORT:-5433}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

Any `docker compose up [-d db]` invocation — from the project root OR from any worktree under `.worktrees/` — causes Compose to:
1. Use the current directory's basename as the compose project name (so a worktree named `F-00058` becomes project `f-00058`).
2. Create a volume named `<project>_pgdata` — per-worktree, so `f-00058_pgdata` for worktree F-00058.
3. Create a container named `iw-ai-core-db` (explicit `container_name:`).
4. Map host port 5433 to container port 5432.

If nothing else occupies port 5433, Compose succeeds and the resulting container has a **fresh empty volume** with zero data. On 2026-04-22 this is exactly what happened: the pre-existing `postgres` container was SIGKILLed, Compose was invoked from `.worktrees/F-00058/`, and `f-00058_pgdata` replaced the real data on port 5433 for ~80 minutes before anyone noticed.

Files that currently tell users to run `docker compose [up -d] db`:
- `ai-core.sh` — `cmd_db start` / `cmd_db stop` / `cmd_db logs`
- `Makefile` — `db-up` target (and related)
- `CLAUDE.md` — "Live DB Setup" section with `make db-up` guidance
- `docs/IW_AI_Core_Tech_Stack.md`
- `docs/implementation/01_foundation/02_config_and_db.md`
- `README.md` (if applicable — confirm during implementation)

## Desired Behavior

1. `docker-compose.yml` at project root exists but contains **no `db` service**. Either an empty `services: {}` stub with a comment explaining the move, or the file is deleted — implementer picks the cleanest option per the Design notes below.
2. A new `docker-compose.bootstrap.yml` at project root contains the former `db` service, with an explicit top-level `name: iw-ai-core` so the volume is always `iw-ai-core_pgdata` regardless of the cwd the file is invoked from (belt-and-braces with the `COMPOSE_PROJECT_NAME` guard already added to `ai-core.sh`).
3. Running `docker compose up` (or `docker compose up -d`) from the project root or any worktree produces **no containers and no volumes**. If the root `docker-compose.yml` was deleted, this command simply errors — which is also fine.
4. `ai-core.sh cmd_db start` invokes `docker compose -f docker-compose.bootstrap.yml up -d db`. The existing guard (no-op if `db_ready` is true) is preserved.
5. `Makefile` `db-up` target is updated to use the `-f` form.
6. A new `docs/IW_AI_Core_DB_Setup.md` documents both paths:
   - **Production path (primary)**: raw `docker run -d --name postgres ...` with bind mount to `/opt/postgres/data`. Includes the exact command.
   - **Bootstrap path (dev-only)**: `docker compose -f docker-compose.bootstrap.yml up -d db` using a named volume `iw-ai-core_pgdata`. Clearly marked as "dev only — do not use this for the long-lived orchestration DB".
7. **Every developer-facing doc** (top-level `README.md`, top-level `CLAUDE.md`, `docs/README.md`, `docs/IW_AI_Core_Tech_Stack.md`, `docs/implementation/01_foundation/02_config_and_db.md`) has a clear short paragraph explaining:
   - WHY the split exists (short reference to the 2026-04-22 incident).
   - That `docker compose up` from a worktree must never be run against the orchestration DB.
   - A pointer to `docs/IW_AI_Core_DB_Setup.md` as the single source of truth.
8. Users going through `ai-core.sh` see no behavior change — the script handles the `-f` flag transparently.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|---|---|---|
| `docker-compose.yml` | Single `db` service at root | Either empty stub (with comment) or deleted |
| `docker-compose.bootstrap.yml` | Does not exist | New file with former `db` service + top-level `name: iw-ai-core` |
| `ai-core.sh` | `cmd_db start` uses `docker compose up -d db` | Uses `docker compose -f docker-compose.bootstrap.yml up -d db` |
| `Makefile` | `db-up` target is `docker compose up -d db` | Same with `-f docker-compose.bootstrap.yml` |
| `docs/IW_AI_Core_DB_Setup.md` | Does not exist | New primary reference for DB setup |
| `CLAUDE.md` (top-level) | Notes "pre-existing postgres container, not compose-managed" in passing | Adds explicit "Why we split compose" subsection + pointer to `docs/IW_AI_Core_DB_Setup.md` |
| `README.md` | References `./ai-core.sh install` / `make db-up` | Same + incident-driven note + doc pointer |
| `docs/README.md` | Doc index | Lists `IW_AI_Core_DB_Setup.md` |
| `docs/IW_AI_Core_Tech_Stack.md` | Mentions compose-managed DB | Clarifies: compose is bootstrap-only, prod path is raw docker |
| `docs/implementation/01_foundation/02_config_and_db.md` | Setup instructions use `make db-up` | Updated + doc pointer |

### Breaking Changes

- **Yes, for direct compose users**: `docker compose up -d db` no longer works from the project root. Users must use `docker compose -f docker-compose.bootstrap.yml up -d db` OR `./ai-core.sh db start`. Documented in the migration note of every affected doc.
- **Users of `ai-core.sh`**: no visible change.
- **Users of `make db-up`**: no visible change if they keep using the Makefile target.

### Data Migration

- **None.** This CR is structural / documentation-only. No DB schema change.
- The `iw-ai-core_pgdata` volume created by the bootstrap file (on a fresh dev machine) is a *different* path from the production `/opt/postgres/data` bind mount — this is intentional (bootstrap mode is for dev-only, throwaway DBs).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Rename `docker-compose.yml` → `docker-compose.bootstrap.yml`; add top-level `name: iw-ai-core`; stub or delete default compose file; update `ai-core.sh cmd_db start/stop/logs` to use `-f` flag; update `Makefile` `db-up` target. | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | template-impl | Write `docs/IW_AI_Core_DB_Setup.md`; update top-level `README.md`, top-level `CLAUDE.md`, `docs/README.md`, `docs/IW_AI_Core_Tech_Stack.md`, `docs/implementation/01_foundation/02_config_and_db.md`. Grep for any remaining `docker compose up.*db` / `docker-compose up.*db` strings anywhere in the repo and fix. | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | Shell-level smoke test (bash test file): asserts `docker compose config` on the root yields zero services; asserts `docker compose -f docker-compose.bootstrap.yml config` lists `db`. `ai-core.sh db start` behavior test: if `db_ready`, no-op (no docker calls). | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Global: no stray `docker compose up -d db` or `docker-compose up -d db` in any doc/script/CI; CR-00014 identity check still green after the change; new doc reachable from every affected doc; incident rationale explained (not just mechanical). | — |
| S08 | qv-gate (lint) | `make lint` | — |
| S09 | qv-gate (format) | `uv run ruff format --check .` | — |
| S10 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S11 | qv-gate (unit-tests) | `make test-unit` | — |
| S12 | qv-gate (integration-tests) | `make test-integration` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A — no alembic migration in this CR.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00015/`:

| File | Type | Purpose |
|---|---|---|
| `CR-00015_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00015_S01_Backend_prompt.md` | Prompt | Rename + ai-core.sh + Makefile updates |
| `prompts/CR-00015_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00015_S03_Template_prompt.md` | Prompt | New setup doc + update README/CLAUDE/docs |
| `prompts/CR-00015_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00015_S05_Tests_prompt.md` | Prompt | Shell smoke test |
| `prompts/CR-00015_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00015_S07_CodeReview_Final_prompt.md` | Prompt | Final cross-layer review |

## Acceptance Criteria

### AC1: `docker compose up` from project root does nothing to port 5433

```
Given the working directory is the project root (main/iw-ai-core/)
  And port 5433 is currently accepting connections (live DB up)
When a user runs: docker compose up -d
Then no container is created, no volume is created, and port 5433 listener is unchanged
 And either the command succeeds with "no services defined" OR errors cleanly that there is no compose file — whichever is implemented
```

### AC2: `docker compose up` from a worktree does nothing to port 5433

```
Given the working directory is a git worktree under .worktrees/
When a user runs: docker compose up -d
Then no container is created, no volume is created, and port 5433 listener is unchanged
```

### AC3: Bootstrap path works for a fresh machine

```
Given the working directory is the project root
  And no container named "iw-ai-core-db" exists
  And the host has no DB on port 5433
When a user runs: docker compose -f docker-compose.bootstrap.yml up -d db
Then a container named "iw-ai-core-db" is created using volume "iw-ai-core_pgdata"
 And the container becomes healthy within 20 seconds
 And the volume name is exactly "iw-ai-core_pgdata" regardless of the cwd
```

### AC4: `./ai-core.sh db start` behavior unchanged for users

```
Given a user runs ./ai-core.sh db start
When the DB is already accepting connections
Then the script prints "Database already accepting connections" and exits 0, calling NO docker commands
When the DB is not accepting connections
Then the script invokes docker compose with -f docker-compose.bootstrap.yml, waits for readiness, and exits 0
```

### AC5: Docs explain the WHY, not just the WHAT

```
Given a developer reads any of the updated docs (top-level README.md, top-level CLAUDE.md,
    docs/README.md, docs/IW_AI_Core_Tech_Stack.md, docs/implementation/01_foundation/02_config_and_db.md)
Then they find a short paragraph (2–4 sentences) explaining:
  - The split exists because of the 2026-04-22 data-loss incident.
  - Running `docker compose up` from a worktree must never touch the orchestration DB.
  - A pointer to docs/IW_AI_Core_DB_Setup.md as the single source of truth.
```

### AC6: Production path is documented as primary

```
Given a developer opens docs/IW_AI_Core_DB_Setup.md
Then the first setup section is "Production" with a raw `docker run` command using a bind mount
 And the "Bootstrap (dev only)" section is clearly marked as such
 And neither section contains hardcoded credentials — both reference .env
```

### AC7: No regression

```
Given CR-00014 has been merged and the identity check is live
When this CR is applied and make check is executed
Then every existing test passes
 And ai-core.sh status still reports green on a healthy live DB
 And the dashboard /healthz/identity endpoint still returns the correct match status
```

## Rollback Plan

- **Database**: N/A — no schema change.
- **Code**: Revert the squash-merge commit. `docker-compose.yml` returns to its original shape; `docker-compose.bootstrap.yml` disappears; docs revert. Immediate restoration of prior behavior (including the foot-gun).
- **Data**: No data affected.
- **Environment**: No env var changes.

## Dependencies

- **Depends on**: **CR-00014** — identity check must be merged and active so any accidental DB-swap introduced by this CR's regression is caught loudly. Blocking.
- **Blocks**: CR-00016 (agent prompt hardening — "never run docker") benefits from this landing first because prompts can state "docker compose operations require an explicit `-f` flag" as a discoverable rule.

## TDD Approach

- **Unit tests**: N/A — no Python logic changes.
- **Integration tests**: One new shell-level smoke test in `tests/integration/test_compose_split.sh` (or as a pytest `subprocess.run` wrapper). Asserts:
  - `docker compose config` from the root has no `db` service.
  - `docker compose -f docker-compose.bootstrap.yml config` has `db` service.
  - `COMPOSE_PROJECT_NAME` expansion: invoking bootstrap with any `cwd` yields volume `iw-ai-core_pgdata`.
- **Updated tests**: Any existing test that shells out to `docker compose up -d db` (search for this pattern). There are probably none, but search.

## Notes

- **Why bootstrap file instead of deletion**: Keeps a one-command path for fresh dev machines while neutralising the ambient foot-gun. Deletion is cleaner but harder to rediscover; bootstrap file is discoverable AND safe.
- **Why `name: iw-ai-core` in the bootstrap file**: Belt-and-braces with the `COMPOSE_PROJECT_NAME=iw-ai-core` env var already added to `ai-core.sh`. If a user invokes the bootstrap file directly (bypassing the script), the volume name stays stable.
- **Root `docker-compose.yml` — stub vs. delete**: The S01 agent picks based on whether any other service needs to exist in the default file. Today there are zero other services. Recommended: leave as a minimal stub with a comment pointing to `docker-compose.bootstrap.yml` and `docs/IW_AI_Core_DB_Setup.md`, so a reader who runs into it has discoverable guidance. Implementer can choose deletion if they prefer and document accordingly.
- **Dashboard e2e compose files** (`iw-ai-core-e2e-*-dashboard-*`): untouched — they're separate compose files for e2e tests and they don't reuse the root file.
- **F-00058 worktree**: its `.worktrees/F-00058/docker-compose.yml` is stale (it's a git-worktree-scoped copy of the pre-CR file). When F-00058 rebases against main after this CR lands, the change propagates automatically.
