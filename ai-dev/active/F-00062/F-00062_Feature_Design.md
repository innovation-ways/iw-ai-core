# F-00062: Per-worktree container isolation for parallel AI-agent development

**Type**: Feature
**Priority**: High
**Created**: 2026-04-25
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

This Feature **adds new daemon-managed compose stacks** (per-worktree DB +
app server) but **all docker compose lifecycle calls live in the new
`orch/daemon/worktree_compose.py` module** — the same architectural pattern
as the existing `orch/daemon/browser_env.py`. Agents NEVER call docker
compose directly; the daemon does.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.
  4. Inside the new `orch/daemon/worktree_compose.py` module ONLY:
     `docker compose --project-name iwcore-<id> up/down`, `docker compose port`,
     `docker container/volume prune --filter label=iwcore.batch_item=<id>`.
     This is the daemon's lifecycle code, written exactly once, by the
     backend-impl agent in S03.

If your task seems to require a prohibited command outside these allowed
exceptions, STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in the S01 Database step is to WRITE the migration FILE. The
daemon will apply it as part of the merge pipeline (pre-merge dry-run
against a testcontainer, post-merge apply to live DB). If the migration
is broken, the daemon will refuse to merge the batch.

This Feature introduces a NEW exception that lives ONLY inside the
`safe_migrate` module: when the alembic target URL points at the
**per-worktree DB** (detected via the `IW_CORE_PER_WORKTREE_DB=true` env
flag set by the daemon at agent launch when an isolated stack exists),
the `AgentContextForbiddenError` is suppressed for `upgrade head` only.
The rule against touching the live orch DB on 5433 is unchanged. S03
implements this guard relax.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)
  - **NEW** alembic upgrade head against the per-worktree DB when
    `IW_CORE_PER_WORKTREE_DB=true` is set by the daemon.

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live orch DB
(port 5433), STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

Each parallel work-item worktree gets its own ephemeral docker-compose
stack (Postgres + app server + project-declared services), giving complete
runtime isolation while orch metadata stays global on 5433. Per-project
config in `<project>/ai-dev/iw-config/` declares which services to isolate,
how to map service ports to env vars, and how to seed the per-worktree DB.
iw-ai-core ships as the reference implementation in this Feature; innoforge
and cv get follow-up Incidents to add their own `iw-config/`. Closes a known
correctness gap (silent cross-worktree state interference) and brings
iw-ai-core in line with the per-task-isolated-runtime pattern that every
modern AI-agent platform adopts (see `docs/research/R-00064-per-worktree-db-isolation.md`).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key references:

- `CLAUDE.md` — daemon / dashboard / orch layout; Alembic + psycopg conventions; the 2026-04-22 docker-compose incident
- `orch/CLAUDE.md` — daemon module table (incl. existing `browser_env.py` pattern this Feature mirrors), ORM patterns, append-only tables, gotchas
- `executor/CLAUDE.md` — **executor bash scripts MUST NOT call docker or alembic**. All compose lifecycle in this Feature lives in `orch/daemon/worktree_compose.py`.
- `tests/CLAUDE.md` — testcontainer rules, FTS DDL, no DB mocking in integration tests
- `docs/IW_AI_Core_Agent_Constraints.md` — R1/R2 (docker / migration off-limits) — this Feature **introduces a narrow R2 exception** for per-worktree DB only
- `docs/IW_AI_Core_Daemon_Design.md` — daemon lifecycle phases (this Feature adds a new "worktree_compose_up" phase before agent launch and a "worktree_compose_down" phase on terminal state)
- `docs/IW_AI_Core_Database_Schema.md` — `batch_items` (this Feature adds three nullable columns)

Precedent for the architectural pattern this Feature follows:

- **`orch/daemon/browser_env.py`** — the existing module that manages per-project docker-compose stacks for `browser_verification` steps, opted into via `.iw-orch.json`. Hash-based deterministic port allocation with availability probe (`_is_port_free`). This Feature's new `orch/daemon/worktree_compose.py` mirrors that module's shape: stateless functions, daemon-driven, project-config-opted-in. The key shape difference is **lifecycle scope**: `browser_env` is per-step; `worktree_compose` is per-batch-item (lives across all steps until the item reaches a terminal state).
- **CR-00021** — introduced the pre-merge rebase phase, the `migration_rebase.py` module pattern. Same dispatch-from-merge-queue pattern. **Hard prerequisite**: CR-00021 must ship first; this Feature's tests assume the rebase phase is in place.

## Scope

### In Scope

- Schema additions on `batch_items`: `worktree_db_port INT NULL`, `worktree_app_port INT NULL`, `worktree_compose_path TEXT NULL` — additive, backward-compatible with NULLs for legacy worktrees.
- New module `orch/daemon/worktree_compose.py`: Jinja2 template rendering, docker-compose-up + dynamic port discovery + `.env` rewrite + `worktree-seed.sh` execution + teardown helpers.
- New module function (or extension) `orch/daemon/worktree_reaper.py` (or section in `worktree_compose.py`): label-based orphan/stale container detection + reap on daemon startup and on a periodic schedule.
- Daemon-restart re-attach: on startup, scan non-terminal `batch_items` with non-NULL `worktree_compose_path`; if `docker compose ps` shows the stack alive, re-attach; otherwise mark for re-setup.
- `orch/db/safe_migrate.py` relax: when `IW_CORE_PER_WORKTREE_DB=true` is set, allow `alembic upgrade head` against the per-worktree DB. Live orch DB on 5433 remains protected.
- Per-project config contract at `<project>/ai-dev/iw-config/`:
  - `worktree-compose.template.yml` (Jinja2)
  - `worktree-env.toml` (port→env mapping + passthrough rules)
  - `worktree-seed.sh` (executable; project-owned seed strategy)
- iw-ai-core's reference `ai-dev/iw-config/` (db + app services, `pg_dump` from global 5433 seed strategy).
- Step prompt placeholder substitution at execution time: `${WORKTREE_APP_PORT}`, `${WORKTREE_DB_PORT}`, `${WORKTREE_PATH}`, `${BATCH_ITEM_ID}`, `${PROJECT_NAME}`. Audit and rewrite of existing iw-ai-core prompts that hardcode `:9900` or `localhost:5433`.
- Dashboard extension: add columns + per-row actions (Open / Logs / Force teardown) to the existing global Worktree Health view at `/worktrees`. **No new view.**
- Defensive `.gitignore` enforcement: daemon refuses to launch a worktree if `.env` or `.iw/` are not gitignored in the project repo.
- `worktree-seed.sh` non-zero exit → daemon tears down stack → `BatchItem.status = setup_failed` → emit `DaemonEvent` with stderr tail. No silent continuation.
- New doc `docs/IW_AI_Core_Worktree_Isolation.md` — the iw-config contract, agent permissions, operator runbook.
- Updates to `docs/IW_AI_Core_Daemon_Design.md`, `CLAUDE.md` Quick Navigation row + Critical Rules additions, `orch/CLAUDE.md` daemon-modules table, and `tests/CLAUDE.md` (per-worktree DB exists for app runtime; testcontainers still mandatory for `make test-integration`).
- Comprehensive tests (unit + integration) across rendering, env rewrite, seed-script invocation, reaper classification, parallel isolation, daemon-restart re-attach.

### Out of Scope

- innoforge and cv `ai-dev/iw-config/` files — follow-up Incidents per project (legacy fallback in this Feature ensures these projects keep working unchanged).
- Project-context-aware prompt generation beyond the dynamic placeholder substitution listed above (richer skill metadata injection is deferred to a future Feature).
- Container resource limits (`mem_limit`, `cpus`) — assumed adequate; can be added later via the project's compose template.
- Per-worktree dashboard refactor for multi-project support — iw-ai-core's reference uses a two-engine pattern (per-worktree app DB + global orch DB); other projects' app servers will hit only their per-worktree DB and don't have this concern.
- Changing `executor/worktree_setup.sh` to call docker — **explicitly forbidden** by `executor/CLAUDE.md`. The daemon (`batch_manager.py`) invokes `worktree_compose.up()` AFTER `worktree_setup.sh` returns.
- Removal of the existing `safe_migrate.AgentContextForbiddenError` — only relaxed for the per-worktree DB; live 5433 protection unchanged.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `BatchItem.worktree_db_port`, `worktree_app_port`, `worktree_compose_path` (all nullable). Single additive Alembic migration. Update `docs/IW_AI_Core_Database_Schema.md`. | — |
| S02 | code-review-impl | Review S01 (additive shape, nullable defaults, backward-compat with legacy NULL rows, schema docs reflect the three new columns). | — |
| S03 | backend-impl | Create `orch/daemon/worktree_compose.py`: `WorktreeStackConfig` dataclass, `render_compose(...)`, `up(batch_item_id, project_id, worktree_path)`, `discover_ports(...)`, `rewrite_env(...)`, `run_seed(...)`, `down(batch_item_id)`, `is_alive(batch_item_id)`. Mirror `orch/daemon/browser_env.py` patterns. Relax `orch/db/safe_migrate.py:AgentContextForbiddenError` when `IW_CORE_PER_WORKTREE_DB=true` AND target URL matches per-worktree DB. | — |
| S04 | code-review-impl | Review S03 (subprocess safety: `shell=False`, timeouts; idempotent `up`; teardown handles non-existent stacks; seed-script failure → tear-down + setup_failed; `.gitignore` enforcement check; no secrets in any logger call; safe_migrate relax tightly scoped). | — |
| S05 | backend-impl | Reaper (label-based orphan/stale detection) on daemon startup + periodic schedule. Daemon-restart re-attach via `BatchItem.worktree_compose_path`. Lifecycle hooks in `orch/daemon/batch_manager.py`: invoke `worktree_compose.up()` after `worktree_setup.sh`; invoke `worktree_compose.down()` on **every terminal `BatchItemStatus` transition** — the actual set per `orch/db/models.py` is `{merged, failed, stalled, skipped, migration_invalid, migration_rolled_back, migration_rebase_failed, setup_failed}` (NOT `archived`/`restarted_discarded` — those are batch-level statuses, not item-level). Implement and use `BatchItemStatus.is_terminal()` (or a module-level `TERMINAL_BATCH_ITEM_STATUSES` constant) so all hook sites share one source of truth. | — |
| S06 | code-review-impl | Review S05 (reaper classification correctness — Active/Stale/Orphan; idempotent re-attach; teardown idempotency; no race between reaper and active worktree creation; lifecycle hooks fire on every terminal-state transition). | — |
| S07 | backend-impl | Write iw-ai-core's `ai-dev/iw-config/worktree-compose.template.yml`, `worktree-env.toml`, `worktree-seed.sh`. Add `${WORKTREE_*}` placeholder substitution to step-prompt loader (likely `orch/daemon/state_machine.py` or wherever prompts are read for agent launch). Audit existing prompts in `ai-dev/templates/` and any committed iw-ai-core prompts; replace hardcoded `:9900` and `localhost:5433` with `${WORKTREE_APP_PORT}` / `${WORKTREE_DB_PORT}`. Set `IW_CORE_PER_WORKTREE_DB=true` in agent launch env when stack exists. | — |
| S08 | code-review-impl | Review S07 (compose template renders with all placeholder vars; env.toml port mapping is complete; seed.sh handles dump failure; prompt audit captures all hardcoded ports; placeholder substitution covers every dynamic value). | — |
| S09 | frontend-impl | Extend `dashboard/templates/pages/system/worktrees.html` and `dashboard/templates/fragments/worktree_table.html` with new columns (Container Status, DB Port, App Port, Class) and per-row actions (Open, Logs, Force teardown). Extend `dashboard/routers/worktrees.py:_collect_worktrees` to enrich each row with container status from `docker ps` (label-filtered) reconciled against `BatchItem`. Logs streaming via existing htmx + SSE pattern from daemon-events feed. Force teardown POST handler. | S07 (no shared files) |
| S10 | code-review-impl | Review S09 (htmx fragment correctness; orphan-row styling distinguishable; Force teardown CSRF protection follows existing dashboard convention; no JS regressions per `make lint`). | — |
| S11 | tests-impl | Unit tests: `tests/unit/daemon/test_worktree_compose.py` (template render, env rewrite, port discovery parsing, seed runner success/failure, gitignore enforcement, AgentContext relax detection). `tests/unit/daemon/test_worktree_reaper.py` (Active/Stale/Orphan classification, reap-only-stale-and-orphan, idempotency). Integration tests: `tests/integration/test_per_worktree_isolation.py` (two parallel iw-ai-core worktrees, distinct migrations, both succeed, no cross-visibility). `tests/integration/test_daemon_restart_reattach.py` (kill daemon mid-batch, restart, verify stack re-attached and item resumes). | — |
| S12 | code-review-impl | Review S11 (AC coverage map; no DB mocks; testcontainer fixtures reused; deterministic; reaper test simulates real labelled containers via testcontainers; parallel-isolation test asserts schema separation via `psql` not just ORM). | — |
| S13 | backend-impl | Docs: NEW `docs/IW_AI_Core_Worktree_Isolation.md` (iw-config contract, agent permissions, operator runbook for force-teardown / seed-failure debugging / orphan reap). UPDATE `docs/IW_AI_Core_Daemon_Design.md` (worktree compose lifecycle phase). UPDATE `CLAUDE.md` Quick Navigation + Critical Rules (add `.iw/` and `.env` gitignore enforcement; add per-worktree DB note). UPDATE `orch/CLAUDE.md` Daemon Modules table (new `worktree_compose.py` row). UPDATE `tests/CLAUDE.md` (per-worktree DB note + testcontainers still mandatory rule). UPDATE `executor/CLAUDE.md` (clarify the daemon, not the executor, owns compose lifecycle). | — |
| S14 | code-review-final-impl | Cross-layer review: trace AC1–AC8 through schema → module → wiring → reference impl → frontend → tests → docs. Verify executor scripts remain docker-free. Verify CR-00021 interaction is preserved (rebase phase still runs, dry-run still uses testcontainer not per-worktree DB). Verify no regression to existing `browser_env` flows. | — |
| S15 | qv-gate | lint (`make lint`) | — |
| S16 | qv-gate | format (`uv run ruff format --check .`) | — |
| S17 | qv-gate | typecheck (`make quality` or equivalent) | — |
| S18 | qv-gate | unit-tests (`make test-unit`) | — |
| S19 | qv-gate | integration-tests (`make test-integration`) | — |

`browser_verification: false` in the manifest. This Feature's frontend changes are structural extensions to an existing template; full browser verification can be added in a follow-up if needed.

### Database Changes

- **New tables**: none.
- **Modified tables**: `batch_items` — three nullable columns added (`worktree_db_port INT NULL`, `worktree_app_port INT NULL`, `worktree_compose_path TEXT NULL`).
- **Modified enums**: none. (Setup-failure cases use the existing `BatchItemStatus.setup_failed` value if present; otherwise S01 audits whether to add a value — if so, follows CR-00019/CR-00021 enum-add pattern.)
- **Migration notes**: pure additive ALTER TABLE ADD COLUMN ... NULL for three columns. No data backfill (legacy worktrees keep NULL — daemon treats NULL as "no per-worktree stack" → legacy mode). Reversibility: `downgrade()` drops the three columns; trivial. **`BatchItemStatus.setup_failed` does NOT exist in current code** (verified against `orch/db/models.py` — the enum has `pending|setting_up|executing|completed|merging|merged|failed|stalled|skipped|migration_invalid|migration_rolled_back|migration_rebase_failed`); S01 MUST add it via `op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'setup_failed'")` inside `op.get_context().autocommit_block()`, mirroring the CR-00019/CR-00021 enum-add pattern, AND add the `setup_failed` member to the Python `BatchItemStatus` enum.

### API Changes

- **New endpoints**: `POST /worktrees/<batch_item_id>/teardown` (operator force-teardown override, S09).
- **Modified endpoints**: `GET /worktrees/table` (returns enriched rows with container status; backward-compatible — same template, more columns).
- **Removed endpoints**: none.

### Frontend Changes

- **New components**: none (htmx fragments only).
- **Modified components**: `dashboard/templates/pages/system/worktrees.html` (add column headers); `dashboard/templates/fragments/worktree_table.html` (add column cells + actions); `dashboard/routers/worktrees.py:_collect_worktrees` (enrich rows with container status). New JS module not required — the Logs streaming reuses the existing daemon-events SSE/htmx pattern.
- **Removed components**: none.

## File Manifest

All files for this work item live under `ai-dev/active/F-00062/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00062_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator (incl. `scope.allowed_paths`) |
| `prompts/F-00062_S01_Database_prompt.md` | Prompt | Schema additions — three nullable columns + Alembic migration + schema docs |
| `prompts/F-00062_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/F-00062_S03_Backend_prompt.md` | Prompt | `worktree_compose.py` module + safe_migrate relax |
| `prompts/F-00062_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/F-00062_S05_Backend_prompt.md` | Prompt | Reaper + daemon-restart re-attach + lifecycle hooks in batch_manager |
| `prompts/F-00062_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/F-00062_S07_Backend_prompt.md` | Prompt | iw-ai-core reference iw-config files + prompt placeholder substitution + agent env flag |
| `prompts/F-00062_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/F-00062_S09_Frontend_prompt.md` | Prompt | Extend Worktree Health view |
| `prompts/F-00062_S10_CodeReview_prompt.md` | Prompt | Review S09 |
| `prompts/F-00062_S11_Tests_prompt.md` | Prompt | Unit + integration tests |
| `prompts/F-00062_S12_CodeReview_prompt.md` | Prompt | Review S11 |
| `prompts/F-00062_S13_Backend_prompt.md` | Prompt | Docs (new isolation doc + daemon design + CLAUDE.md updates) |
| `prompts/F-00062_S14_CodeReview_Final_prompt.md` | Prompt | Final cross-layer review |

Reports are written during execution in `ai-dev/active/F-00062/reports/`.

Expected production-code files to be created/modified by implementation steps:

- `orch/db/models.py` — add `BatchItem.worktree_db_port`, `worktree_app_port`, `worktree_compose_path` (modify)
- `orch/db/migrations/versions/<hash>_f_00062_worktree_isolation.py` — Alembic migration (new)
- `orch/daemon/worktree_compose.py` — new module
- `orch/daemon/worktree_reaper.py` — new module (or section in worktree_compose.py)
- `orch/daemon/batch_manager.py` — invoke `worktree_compose.up()` after worktree_setup.sh; invoke `down()` on terminal transitions (modify)
- `orch/daemon/main.py` — call reaper on startup + register periodic schedule (modify)
- `orch/db/safe_migrate.py` — relax `AgentContextForbiddenError` when `IW_CORE_PER_WORKTREE_DB=true` (modify)
- `orch/daemon/state_machine.py` (or prompt loader) — placeholder substitution `${WORKTREE_*}` from `BatchItem` row (modify)
- `ai-dev/iw-config/worktree-compose.template.yml` — new (iw-ai-core reference)
- `ai-dev/iw-config/worktree-env.toml` — new (iw-ai-core reference)
- `ai-dev/iw-config/worktree-seed.sh` — new (iw-ai-core reference, executable)
- `ai-dev/templates/*.md` — audit + replace hardcoded `:9900` / `localhost:5433` with `${WORKTREE_*}` placeholders (modify)
- `dashboard/routers/worktrees.py` — enrich `_collect_worktrees` with container status; new POST teardown handler (modify)
- `dashboard/templates/pages/system/worktrees.html` — column headers (modify)
- `dashboard/templates/fragments/worktree_table.html` — column cells + actions (modify)
- `tests/unit/daemon/test_worktree_compose.py` — new
- `tests/unit/daemon/test_worktree_reaper.py` — new
- `tests/integration/test_per_worktree_isolation.py` — new
- `tests/integration/test_daemon_restart_reattach.py` — new
- `docs/IW_AI_Core_Worktree_Isolation.md` — new
- `docs/IW_AI_Core_Daemon_Design.md` — modify
- `docs/IW_AI_Core_Database_Schema.md` — modify
- `CLAUDE.md` — modify
- `orch/CLAUDE.md` — modify
- `tests/CLAUDE.md` — modify
- `executor/CLAUDE.md` — modify
- `.gitignore` — append `.iw/` if missing (modify)

## Acceptance Criteria

### AC1: Per-worktree compose stack is rendered, started, and ports discovered

```
Given a managed project with `ai-dev/iw-config/worktree-compose.template.yml`,
      `ai-dev/iw-config/worktree-env.toml`, and `ai-dev/iw-config/worktree-seed.sh`
  and a new BatchItem with id "F-99001"
When the daemon's batch_manager invokes worktree_compose.up("F-99001", project_id, worktree_path)
Then the rendered compose file is written to <worktree>/.iw/docker-compose-F-99001.yml, AND
     `docker compose -p iwcore-F-99001 -f <path> up -d` succeeds, AND
     each service's host-bound port is discovered via `docker compose port <service> <container_port>`, AND
     BatchItem.worktree_db_port, .worktree_app_port, and .worktree_compose_path are persisted, AND
     the worktree's .env is rewritten so each port-bound env var (per worktree-env.toml mapping)
       contains the discovered host port, AND
     `worktree-seed.sh` is executed with the worktree's .env loaded, AND
     a DaemonEvent(event_type='worktree_compose', metadata={phase:'up', success:true,
       ports:{db:NNNN, app:NNNN}}) is written.
```

### AC2: Two parallel iw-ai-core worktrees do not interfere

```
Given main at rev1
  and two BatchItems A and B for iw-ai-core, both with per-worktree stacks up
  and worktree A's Database step has run `alembic upgrade head` plus a
      manual `psql -c "ALTER TABLE work_items ADD COLUMN col_a TEXT"` against
      its per-worktree DB
  and worktree B's Database step has run `alembic upgrade head` plus a
      manual `psql -c "ALTER TABLE work_items ADD COLUMN col_b TEXT"` against
      its per-worktree DB
When each worktree's Backend step queries its own DB
Then worktree A's `psql -c "\d work_items"` shows col_a but NOT col_b, AND
     worktree B's `psql -c "\d work_items"` shows col_b but NOT col_a, AND
     the global 5433 orch DB shows neither col_a nor col_b, AND
     each worktree's `iw step-done` writes its WorkflowStep + StepRun to
       the global 5433 (verified by querying global) without errors.
```

### AC3: `safe_migrate.AgentContextForbiddenError` is relaxed for per-worktree DB only

```
Given an agent process with IW_CORE_AGENT_CONTEXT=true (the existing guard)
  and IW_CORE_PER_WORKTREE_DB=true (the new daemon-set flag)
  and IW_CORE_DB_HOST=localhost, IW_CORE_DB_PORT=<worktree_db_port>
When the agent runs `alembic upgrade head` against IW_CORE_DB_*
Then the upgrade succeeds — no AgentContextForbiddenError raised.

Given the same agent
When the agent runs `alembic upgrade head` against IW_CORE_ORCH_DB_*
       (port 5433, the live orch DB)
Then AgentContextForbiddenError is raised — the existing protection holds.
```

### AC4: Container reaper handles orphans + stale on daemon startup

```
Given a running container with labels iwcore.role=worktree-db,
      iwcore.batch_item=GHOST-99999
  and no row in batch_items with id "GHOST-99999"
  and a second running container with labels iwcore.role=worktree-db,
      iwcore.batch_item=DONE-99998
  and a row batch_items(id='DONE-99998', status='merged')
      (any terminal BatchItemStatus — merged, failed, stalled, skipped,
       migration_invalid, migration_rolled_back, migration_rebase_failed,
       setup_failed — qualifies as 'stale')
When the daemon starts
Then within one startup cycle, both containers are torn down via
       `docker compose -p iwcore-GHOST-99999 down -v` and
       `docker compose -p iwcore-DONE-99998 down -v`, AND
     a DaemonEvent records each reap action with the labels found and
       the classification (orphan vs stale).
```

### AC5: Daemon-restart re-attach succeeds

```
Given a non-terminal BatchItem (status NOT IN the terminal set defined for S05) with worktree_compose_path set and
      a corresponding compose stack running (verified by `docker compose ps`)
When the daemon process is killed (SIGKILL) and restarted
Then the new daemon does NOT tear down the stack on startup, AND
     the next-poll-cycle handling of that BatchItem proceeds without
       re-running worktree_compose.up (idempotent — verified by no second
       DaemonEvent of phase='up' for that item).
```

### AC6: `worktree-seed.sh` non-zero exit fails the worktree cleanly

```
Given a project whose worktree-seed.sh exits with code 1 (e.g., simulated
      pg_dump failure with stderr "FATAL: source DB unreachable")
When the daemon's batch_manager invokes worktree_compose.up()
Then the partial compose stack is torn down via
       `docker compose -p iwcore-<id> down -v --remove-orphans`, AND
     BatchItem.status transitions to 'setup_failed', AND
     a DaemonEvent(event_type='worktree_compose', metadata={phase:'seed',
       success:false, stderr_tail:"FATAL: source DB unreachable", ...}) is
       written, AND
     no zombie containers remain (verified by
       `docker ps -a --filter label=iwcore.batch_item=<id>` returning empty).
```

### AC7: Project missing `iw-config/` falls back to legacy mode silently

```
Given a managed project that does NOT have ai-dev/iw-config/worktree-compose.template.yml
When the daemon launches a new worktree for that project
Then no compose stack is created (worktree_compose.up is a no-op), AND
     BatchItem.worktree_db_port, .worktree_app_port, .worktree_compose_path
       remain NULL, AND
     the existing executor/worktree_setup.sh .env-copy behavior runs unchanged, AND
     no warning or error is emitted — quiet opt-in semantics, AND
     all subsequent steps execute normally against the global orch DB
       (legacy behavior preserved).
```

### AC8: Defensive `.gitignore` enforcement

```
Given a managed project whose .gitignore does NOT contain ".env"
  and the project HAS ai-dev/iw-config/worktree-compose.template.yml
When the daemon attempts to launch a worktree
Then worktree_compose.up() raises a clear error
       "refusing to launch: .env must be in .gitignore for project <id>", AND
     no compose stack is started, AND
     BatchItem.status transitions to 'setup_failed', AND
     a DaemonEvent records the refusal with project_id and the missing entry.

Given the same project's .gitignore is updated to include .env but NOT .iw/
When the daemon retries
Then the same shape of refusal fires for ".iw/" (loud, no auto-fix).
```

### AC9: Step prompt placeholders are substituted at execution time

```
Given a step prompt containing the literal string "http://localhost:${WORKTREE_APP_PORT}/jobs"
  and a BatchItem with worktree_app_port=29900
When the daemon launches the agent for that step
Then the prompt handed to the agent contains "http://localhost:29900/jobs"
       (literal substitution), AND
     the same substitution applies to ${WORKTREE_DB_PORT}, ${WORKTREE_PATH},
       ${BATCH_ITEM_ID}, ${PROJECT_NAME}.
```

### AC10: Worktree Health view classifies and exposes per-row actions

```
Given two running iwcore-* containers, one matching a non-terminal BatchItem
      and one with no matching BatchItem
When an operator visits /worktrees in the dashboard
Then the table renders one row classified as Active (Open / Logs / Force teardown
       buttons present) and one row classified as Orphan (highlighted), AND
     clicking "Open" navigates to http://localhost:<worktree_app_port>, AND
     clicking "Logs" opens an htmx-streamed log tail of the matched container, AND
     clicking "Force teardown" issues POST /worktrees/<id>/teardown which
       invokes worktree_compose.down(<id>) and returns a refreshed table fragment.
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Empty `iw-config/` directory (exists but contains no template) | `<project>/ai-dev/iw-config/` exists, `worktree-compose.template.yml` absent | Treated as legacy fallback (AC7) — no stack, no error |
| `worktree-env.toml` declares a port mapping for a service that doesn't exist in compose | `[port_to_env]` references service `redis:6379` but compose has no `redis` service | Daemon emits clear validation error during render; setup_failed |
| `worktree-seed.sh` is non-executable | File exists but missing execute bit | Daemon attempts execution, captures the OS error, treats as seed failure (AC6 path) |
| Two batch items with identical id (impossible by schema; defensive) | (cannot occur) | N/A — primary key uniqueness on batch_items |
| `worktree_compose_path` points at a deleted file (operator tampering) | File missing on daemon restart | Treat as "not running" — re-render and re-up (idempotent) |
| Docker daemon down at worktree setup | `docker compose up` fails with connection refused | Setup_failed with clear stderr; no partial state |
| Port discovery returns unexpected value (e.g., container exposes 0.0.0.0:0) | `docker compose port` returns no host binding | Setup_failed; surface the error message |
| Reaper finds container with label but no `batch_item` label value | Malformed labels (e.g., `iwcore.batch_item=`) | Treated as orphan; reaped |
| Daemon launches worktree when project's `iw-config/` is partially present (template + env.toml but no seed.sh) | seed.sh missing | Treated as "no seed" — daemon proceeds without seeding (allows projects to skip seed if their app handles fresh DB) |
| Bind-mount path contains spaces | `worktree_path` has whitespace | Compose template properly quotes the path; `docker compose up` succeeds |
| `pg_dump` source DB is the per-worktree DB itself (cycle) | iw-ai-core seed script targets `IW_CORE_DB_*` instead of `IW_CORE_ORCH_DB_*` | Project's seed.sh bug — caught by integration test that verifies the seeded DB is non-empty |
| Worktree restarted before merge | `BatchItem.status` transitions through `restarted_discarded` | Stack torn down + recreated with same compose project name; reaper sees the new stack as Active |

## Invariants

Conditions that must hold true after implementation. Each maps to a test.

1. `executor/worktree_setup.sh` and `executor/worktree_commit.sh` contain ZERO `docker` or `docker-compose` invocations (grep enforced by integration test).
2. The only `docker compose up/down` calls in the codebase live in `orch/daemon/worktree_compose.py` (and the existing `orch/daemon/browser_env.py` — pre-existing, not in scope).
3. `safe_migrate.AgentContextForbiddenError` fires for any alembic upgrade against the live orch DB on 5433, regardless of `IW_CORE_PER_WORKTREE_DB` flag value.
4. Per-worktree compose stacks are deterministically named `iwcore-<batch_item_id>`; no other prefix exists.
5. Every container created by `worktree_compose.py` carries both `iwcore.role=<service>` and `iwcore.batch_item=<id>` labels (verified by `docker inspect`).
6. `BatchItem.worktree_db_port`, `worktree_app_port`, `worktree_compose_path` are all NULL or all non-NULL — partial state is invalid.
7. Reaper NEVER reaps a container whose `iwcore.batch_item` matches a non-terminal `BatchItem.status`.
8. Daemon NEVER prints any value from `.env` (key=value pairs) into any logger.* call — verified by static analysis test.
9. The legacy fallback path (no `iw-config/`) is byte-identical to current pre-Feature behavior — verified by integration test against a project with no iw-config.
10. CR-00021's pre-merge rebase + dry-run phase still runs against a fresh testcontainer (NOT the per-worktree DB) — verified by tracing the merge_queue dispatch path in tests.

## Dependencies

- **Depends on**: CR-00021 (merge-time chain rebase must be in place; AC2 and the `test_per_worktree_isolation.py` integration test depend on the rebase phase).
- **Blocks**: future Feature for project-context-aware prompt generation (skill metadata injection beyond the dynamic `${WORKTREE_*}` substitution this Feature ships); follow-up Incidents to add `ai-dev/iw-config/` to innoforge and cv repos.

## TDD Approach

### Unit tests

`tests/unit/daemon/test_worktree_compose.py`:
- `test_render_compose_substitutes_jinja_vars` — feed a template with `{{ batch_item_id }}`, `{{ worktree_path }}`, `{{ project_name }}`; assert rendered output has literal substitution.
- `test_render_compose_writes_to_iw_subdir` — assert output path is `<worktree>/.iw/docker-compose-<id>.yml`.
- `test_discover_ports_parses_docker_compose_port_output` — mock subprocess; feed `0.0.0.0:34567`; assert returned port is 34567.
- `test_rewrite_env_applies_port_to_env_mapping` — feed worktree-env.toml + discovered ports; assert .env has correct `IW_CORE_DB_PORT=34567` etc.
- `test_rewrite_env_preserves_passthrough_keys` — assert API keys, IW_CORE_ORCH_DB_* are unchanged.
- `test_run_seed_zero_exit_succeeds` — stub seed.sh that exits 0; assert no exception, returns success.
- `test_run_seed_nonzero_exit_returns_failure_with_stderr_tail` — stub seed.sh that exits 1 with known stderr; assert returned dataclass has `success=False, stderr_tail=<known>`.
- `test_up_refuses_when_env_not_gitignored` — project with `.env` missing from `.gitignore`; assert clear refusal error and no docker invocation.
- `test_up_refuses_when_iw_dir_not_gitignored` — `.iw/` missing from `.gitignore`; same refusal.
- `test_up_legacy_fallback_when_iw_config_missing` — no `ai-dev/iw-config/`; assert no-op return, no docker calls.
- `test_safe_migrate_relax_with_per_worktree_flag` — set `IW_CORE_AGENT_CONTEXT=true` and `IW_CORE_PER_WORKTREE_DB=true`; target URL points at per-worktree DB; assert no AgentContextForbiddenError.
- `test_safe_migrate_blocks_against_orch_db_even_with_per_worktree_flag` — same flags but URL points at port 5433; assert AgentContextForbiddenError still raised.
- `test_no_secrets_in_logs` — render compose + run seed with .env containing `SECRET=hunter2`; capture log output; assert "hunter2" never appears.

`tests/unit/daemon/test_worktree_reaper.py`:
- `test_classify_running_with_active_batchitem_is_active` — assert classification.
- `test_classify_running_with_terminal_batchitem_is_stale` — assert classification.
- `test_classify_running_with_no_batchitem_is_orphan` — assert classification.
- `test_reap_only_acts_on_stale_and_orphan` — feed mixed list; assert only stale/orphan get `down -v` invoked.
- `test_reaper_idempotent_on_already_torn_down_stack` — call twice; assert second call is a no-op (no exception).
- `test_reattach_recognizes_alive_stack_and_skips_recreate` — set up running stack + non-terminal BatchItem; assert daemon-startup re-attach does NOT call `up` again.

### Integration tests (testcontainer where possible; real docker for the compose-isolation test)

`tests/integration/test_per_worktree_isolation.py` — AC2 happy path:
- Set up two scratch git worktrees (via `tmp_path` + `git worktree`) each as iw-ai-core (or a minimal fixture project mirroring the iw-ai-core compose template).
- Drive `worktree_compose.up()` for both; assert both stacks come up with distinct ports.
- In each worktree, run `psql` to add a distinct column to `work_items`.
- Assert each worktree's `\d work_items` shows only its own column.
- Assert global 5433 (testcontainer) shows neither column.
- Tear down both stacks; assert both are gone.

`tests/integration/test_daemon_restart_reattach.py` — AC5:
- Start a stack; persist `worktree_compose_path` to a `BatchItem` row in a testcontainer-hosted batch_items table.
- Simulate daemon restart (call the startup re-attach function fresh).
- Assert no second `up` call is issued.
- Assert the next merge-queue poll for that item proceeds.

### Edge case tests
- Reap dry-run against a labelled container created by tests: ensure the test fixtures use a unique label scheme that the reaper does NOT touch.
- Ensure `make test-integration` (which uses testcontainers per `tests/conftest.py`) does NOT accidentally instantiate per-worktree compose stacks — verified by asserting no `iwcore-*` containers exist after the test suite.

## Notes

- **Why `orch/daemon/worktree_compose.py` and not `executor/`?** `executor/CLAUDE.md` explicitly forbids docker calls in executor scripts. `orch/daemon/browser_env.py` is the established pattern for daemon-managed compose lifecycles. This Feature mirrors that shape: stateless module, called by the daemon's batch_manager, with deterministic naming and label-based reaping.
- **Why dynamic ports (`ports: ["5432"]`) instead of slot-based?** Eliminates an entire class of port-collision failures. `browser_env` uses hash-based deterministic ports with a probe; for the per-worktree compose case, dynamic is simpler because we already need to persist the resolved port to `BatchItem` so the dashboard can display it. We rely on the kernel's atomic port allocation rather than a probe race.
- **Why `IW_CORE_PER_WORKTREE_DB` env flag instead of URL inspection in safe_migrate?** Robustness: the daemon knows definitively whether a stack exists; URL inspection would have to assume "host=localhost AND port matches recorded value" which is fragile across `host.docker.internal` variants. The flag is set by the daemon at agent launch time, alongside `IW_CORE_AGENT_CONTEXT`.
- **Why no per-worktree dashboard refactor in scope?** iw-ai-core's case is the special one where the orch DB IS the app DB. Other managed projects' dashboards/apps connect only to their per-worktree DB and don't need a two-engine setup. This Feature treats iw-ai-core's two-engine as a project-level configuration concern (the seed script handles `pg_dump`-from-global), not a framework concern.
- **`worktree-seed.sh` security**: the script runs as the daemon user, with the worktree's `.env` loaded. Secrets in `.env` flow through subprocess environment to the script. The script must not re-export secrets to logs (S08 review verifies). The script is in the project repo, version-controlled, reviewable.
- **Risks**:
  - **Docker daemon failure during peak parallel-worktree use** — mitigation: clear setup_failed signal + DaemonEvent + reaper cleans up partial stacks on next start.
  - **Bind-mount permission issues with `python:3.12-slim`** — mitigation: container runs as root by default; for projects that need a non-root user, they can override the compose template.
  - **`pg_dump` from the global 5433 ties iw-ai-core's seed strategy to network availability of the orch DB** — by design (iw-ai-core IS the orch DB project). Other projects choose their own seed source.
  - **Reaper false-positive race**: a worktree being created at the same instant as the reaper runs could be misclassified. Mitigation: reaper only acts on containers >10 seconds old (timestamp filter), and `worktree_compose.up` writes the `worktree_compose_path` to `BatchItem` BEFORE invoking `docker compose up` (so the reaper sees the row first if it races).
  - **PostgreSQL `tmpfs` data dir loses state on container restart** — by design; agents that need durable state across restarts (rare in our model) must override the compose template to use a named volume. Documented in the iw-ai-core reference template.

## Rollback Plan

- **Database**: `alembic downgrade -1` drops the three nullable columns. No data loss (legacy worktrees had NULLs anyway).
- **Code**: revert the merge commit. `worktree_compose.py` becomes orphaned import-able code if referenced from elsewhere; `batch_manager.py` lifecycle hooks are removed. The reaper stops running. Existing `browser_env.py` flows unaffected.
- **Containers in flight at revert**: any per-worktree compose stacks running at revert time become "leaked" since the reaper is gone. Manual cleanup: `docker ps --filter label=iwcore.role -q | xargs -r docker rm -fv && docker volume prune --filter label=iwcore.role`.
- **iw-config files**: harmless to leave in iw-ai-core's `ai-dev/iw-config/`. The daemon ignores them post-revert.
- **Operator action required**: none beyond the manual container cleanup if any are leaked. No data corruption possible (per-worktree DBs were ephemeral by design).
