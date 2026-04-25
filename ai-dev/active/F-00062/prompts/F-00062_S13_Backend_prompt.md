# F-00062_S13_Backend_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step**: S13
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

This step writes documentation. No docker invocations. Read-only `docker ps|inspect|logs` allowed for verification while drafting the operator runbook. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No alembic execution against live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc + S01-S12 reports
- `docs/IW_AI_Core_Daemon_Design.md` — daemon design doc to update
- `docs/IW_AI_Core_Database_Schema.md` — already updated by S01; verify consistency
- `CLAUDE.md` — Quick Navigation table + Critical Rules
- `orch/CLAUDE.md` — Daemon Modules table
- `tests/CLAUDE.md` — testing rules
- `executor/CLAUDE.md` — clarify daemon-vs-executor compose ownership
- `docs/IW_AI_Core_Agent_Constraints.md` — note the per-worktree DB safe_migrate exception

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S13_Backend_report.md`

## Context

You are creating the new `docs/IW_AI_Core_Worktree_Isolation.md` document and updating five existing docs to reflect the per-worktree compose stack lifecycle. This is the single source of truth that operators and future agents read.

## Requirements

### 1. Create `docs/IW_AI_Core_Worktree_Isolation.md`

Structure:

```markdown
# IW AI Core — Worktree Container Isolation

## Overview
- Why per-worktree containers (1 paragraph; reference R-00064 research)
- What gets isolated (per-worktree DB + per-worktree app server) vs what stays global (orch metadata on 5433)
- Opt-in semantics (project-level)

## The `ai-dev/iw-config/` contract
- Three files, with full schema + example for each
- File location and discovery (read from `<worktree>/ai-dev/iw-config/`, NOT from main repo)
- Legacy fallback (no iw-config → no stack, no warning)

### `worktree-compose.template.yml`
- Jinja2 vars exposed: batch_item_id, worktree_path, project_name
- Required label conventions (iwcore.role, iwcore.batch_item)
- Dynamic ports (no host port in compose)
- tmpfs for ephemeral DB data
- extra_hosts for host gateway access

### `worktree-env.toml`
- `[port_to_env]` schema with worked example
- `[env_overrides]` schema
- `[env_passthrough].keep` schema (with glob support)

### `worktree-seed.sh`
- Run timing (after compose up succeeds, before agent launch)
- Environment loaded (worktree's .env)
- Failure semantics (non-zero exit → setup_failed)
- iw-ai-core's reference: pg_dump from global orch DB → restore into per-worktree DB

## Daemon lifecycle
- When `worktree_compose.up()` fires (after worktree_setup.sh)
- When `worktree_compose.down()` fires (terminal status transitions)
- Container naming: `iwcore-<batch_item_id>`
- Persisted state: `BatchItem.worktree_db_port`, `worktree_app_port`, `worktree_compose_path`

## The reaper
- What it scans (containers with iwcore.role label)
- Classification (Active / Stale / Orphan)
- When it runs (daemon startup + periodic)
- Operator controls (Force teardown via dashboard)

## Daemon-restart behavior
- Re-attach via worktree_compose_path
- No double `up()` for already-running stacks
- Re-setup if stack vanished

## Step prompt placeholders
- `${WORKTREE_APP_PORT}`, `${WORKTREE_DB_PORT}`, `${WORKTREE_PATH}`, `${BATCH_ITEM_ID}`, `${PROJECT_NAME}`
- Substituted at execution time from `BatchItem` row
- Legacy items: clear error if a prompt uses these placeholders

## Agent permissions (the contract)
- Agent CAN: inspect `.iw/docker-compose-<id>.yml`, `docker compose ps|logs|restart` against the worktree's stack
- Agent CANNOT: edit the compose file, `docker compose up|down`, modify the daemon's compose lifecycle
- `make test-integration` STILL uses testcontainers (rule unchanged)
- `safe_migrate.AgentContextForbiddenError` is RELAXED for per-worktree DB only (`IW_CORE_PER_WORKTREE_DB=true` flag); live 5433 protection unchanged

## .gitignore enforcement
- Daemon refuses to launch if project's .gitignore is missing `.env` or `.iw/`
- No auto-fix; operator must update the project's .gitignore

## Operator runbook
- How to check container status: `docker ps --filter label=iwcore.role`
- How to inspect a worktree's compose file: `cat <worktree>/.iw/docker-compose-<id>.yml`
- How to stream logs: `docker compose -p iwcore-<id> logs -f`
- How to force-teardown via dashboard: navigate to `/worktrees`, click the trash icon
- How to debug a seed failure: read the DaemonEvent for `phase='seed', success=false`
- How to recover from a leaked container: `docker ps --filter label=iwcore.role -q | xargs docker rm -fv`

## Daemon-host prerequisites
- Docker engine installed and running
- `docker compose` plugin (v2)
- For iw-ai-core's reference seed script: `pg_dump` and `psql` (Postgres client tools) on PATH
- Other projects: their seed script's prereqs, documented per-project

## Multi-project scope
- This Feature ships iw-ai-core's reference implementation only
- innoforge and cv get follow-up Incidents to add their own ai-dev/iw-config/
- Until those land, those projects use the legacy fallback (no per-worktree stack)
```

### 2. Update `docs/IW_AI_Core_Daemon_Design.md`

Add a new section "Worktree Container Lifecycle" (placement: between worktree creation and step launch). Cover:

- New phase `worktree_compose.up()` invoked by `batch_manager` after `worktree_setup.sh`
- Phase failures → `setup_failed` status, no step launch
- Teardown phase on terminal status transitions
- The container reaper schedule (startup + periodic)
- Daemon-restart re-attach via `BatchItem.worktree_compose_path`
- Reference to `docs/IW_AI_Core_Worktree_Isolation.md` for the full contract

Update the failure-matrix table (if present) with `setup_failed`.

### 3. Update `CLAUDE.md`

In the **Quick Navigation** table, add a row:

```
| Worktree container isolation | `orch/daemon/worktree_compose.py` · `docs/IW_AI_Core_Worktree_Isolation.md` |
```

In the **Critical Rules** section, add:

```
- **MUST** ensure `.env` and `.iw/` are listed in every managed project's `.gitignore` — daemon refuses to launch worktrees otherwise.
- **NEW**: per-worktree DB exists for app runtime when project has `ai-dev/iw-config/`. The agent's `IW_CORE_DB_*` env vars point at the per-worktree DB; `IW_CORE_ORCH_DB_*` always points at the global orch DB on 5433.
```

In the **Common Commands** section, no changes needed (no new CLI commands in this Feature).

### 4. Update `orch/CLAUDE.md`

In the **Daemon Modules** table, add rows:

```
| `worktree_compose.py` | Per-worktree docker-compose stack lifecycle (project-opted-in via ai-dev/iw-config/). Mirrors browser_env.py architecture. |
| `worktree_reaper.py` | Label-based orphan/stale container reaper; runs on daemon startup and periodic schedule. |
```

If reaper was kept inside `worktree_compose.py` per the S05 author's judgment, document accordingly (one row instead of two).

### 5. Update `tests/CLAUDE.md`

Add a section/note:

```
## Per-worktree DB vs testcontainers

The Feature F-00062 introduces a per-worktree Postgres container for app
runtime (started by the daemon when the project ships ai-dev/iw-config/).
This is separate from `make test-integration`'s testcontainers.

- `make test-integration` MUST continue to use testcontainers (existing rule).
- The per-worktree DB is for the agent's app runtime (e.g., dashboard exercising
  Backend step changes), NOT for tests.
- Tests must NEVER assume the per-worktree DB exists — they spin up their own
  testcontainer.
```

### 6. Update `executor/CLAUDE.md`

Reaffirm and clarify:

```
## Compose lifecycle ownership

Executor scripts MUST NOT call docker. The per-worktree compose stack
introduced in F-00062 is owned by `orch/daemon/worktree_compose.py` —
the daemon invokes `up()` after `worktree_setup.sh` returns and `down()`
on terminal-status transitions. See `docs/IW_AI_Core_Worktree_Isolation.md`.
```

### 7. Update `docs/IW_AI_Core_Agent_Constraints.md`

Document the safe_migrate relax:

```
## Per-worktree DB exception (F-00062)

When the daemon launches an agent into a worktree with an active per-worktree
compose stack, it sets `IW_CORE_PER_WORKTREE_DB=true` in the agent's env. In
that mode only, `alembic upgrade head` is allowed against the per-worktree DB
(detected by URL→IW_CORE_DB_*). The live orch DB on port 5433 remains
protected regardless. See safe_migrate.py.
```

## Project Conventions

- Read `CLAUDE.md` and the existing docs in `docs/` for the style (sentence-case headings, terse tables, link-rich)
- Diagrams optional but welcome — Mermaid renders in `docs/` and on GitHub

## TDD Requirement

Documentation step. No tests required, but ensure:
- Every claim is traceable to code (cite file paths)
- All link references resolve (`docs/...` paths exist)

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — verify markdown link formatting if lint covers it
2. Manually click through each cross-reference: `docs/IW_AI_Core_Worktree_Isolation.md` → references → exist
3. `make test-unit` — sanity check no regressions

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "backend-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_Worktree_Isolation.md",
    "docs/IW_AI_Core_Daemon_Design.md",
    "docs/IW_AI_Core_Agent_Constraints.md",
    "CLAUDE.md",
    "orch/CLAUDE.md",
    "tests/CLAUDE.md",
    "executor/CLAUDE.md"
  ],
  "tests_passed": true,
  "test_summary": "no test changes; lint passes",
  "blockers": [],
  "notes": ""
}
```
