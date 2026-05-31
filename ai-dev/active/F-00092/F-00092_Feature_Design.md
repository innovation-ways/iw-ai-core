# F-00092: Tier-1 scheduled + on-demand logical backups for the orchestration DB

**Type**: Feature
**Priority**: High
**Created**: 2026-05-31
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Agents MUST NOT run container/volume state-changing Docker
commands. The backup engine itself invokes `pg_dump`/`pg_restore`/`psql` — these
client binaries are obtained by running a throwaway `postgres:15-alpine` container
with `docker run --rm` connecting over TCP to the configured DB (the host has no
pg client tools); that is allowed because it changes no long-lived
container/volume state and self-removes. Tests use testcontainer fixtures. Agents
MUST NOT run backups against the live orchestration DB on 5433.

## ⛔ Migrations: agents generate, daemon applies

This feature **adds** one migration: a new `db_backup_jobs` table (the
`DbBackupJob` model). The Database step generates the migration file via
`make migration-pending`; the daemon applies it at merge time. Agents MUST NOT run
`alembic upgrade` against the live DB.

## Description

A first-class backup subsystem for the `iw_orch` orchestration database. It takes
daily scheduled logical dumps (`pg_dump -Fc` + `pg_dumpall --globals-only`) driven
by a daemon job with missed-window catch-up, supports on-demand backups via
`iw db-backup`, prunes scheduled backups older than a configurable retention
(default 30 days) while keeping manual/labeled backups, and ships a guided restore
helper plus a written restore guide. Motivated by three production DB-displacement
incidents (2026-04-22, 2026-05-29, 2026-05-31) where the only backup was a single
five-week-old dump stored inside the very bind mount it was meant to protect.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules —
especially "Live DB Setup", the config conventions (all config in `.env`, never
hardcode ports/paths/credentials), the daemon job-poller pattern
(`orch/daemon/doc_job_poller.py`, `doc_index_poller.py`,
`chat_summarization_poller.py`), the unified jobs view (`orch/jobs/aggregator.py`,
`dashboard/routers/jobs_ui.py`), and the DB identity machinery
(`orch/db/identity.py`, `IW_CORE_EXPECTED_INSTANCE_ID`). This feature builds on
**I-00122**, which introduces `IW_CORE_DB_DATA_DIR` and the guarded prod-start
path.

## Scope

### In Scope

- A new `DbBackupJob` ORM model + Alembic migration recording each backup
  (type scheduled/manual, label, path, status, timestamps, error, manifest data).
- Backup configuration in `orch/config.py` read from `.env`:
  `IW_CORE_BACKUP_ENABLED` (default true), `IW_CORE_BACKUP_DIR`
  (default `/opt/postgres/data/backups`), `IW_CORE_BACKUP_RETENTION_DAYS`
  (default 30), `IW_CORE_BACKUP_TIME` (daily, default `03:00`).
- A standalone **backup engine** (library code, callable by both the daemon and
  the CLI) that produces, per backup: a `pg_dump -Fc` archive of `iw_orch`, a
  `pg_dumpall --globals-only` SQL file (roles + passwords), a `pg_restore --list`
  integrity check, and a JSON manifest (UTC timestamp, alembic revision,
  `iw_core_instance` id, row counts for projects/batches/work_items, type, label,
  and the PostgreSQL **server version** for restore-time client/server compatibility).
- **Retention/prune**: age-based deletion of *scheduled* backups older than the
  configured retention; *manual/labeled* backups are exempt.
- A **guided restore helper** (`iw db-backup restore --from <set>`) that by default
  restores into a SAFE non-prod target (a fresh database/throwaway container, never
  in-place over prod), applies globals first, runs `iw db-identity check`, and
  prints row counts.
- **Daemon scheduling**: a backup poller registered in `orch/daemon/main.py` that
  runs a scheduled backup daily at `IW_CORE_BACKUP_TIME`, with missed-window
  catch-up (if no successful scheduled backup exists within the interval and the
  window has passed, run one immediately — so a backup fires when the daemon
  recovers from downtime).
- **A-la-carte CLI**: `iw db-backup create [--label X]`, `iw db-backup list`,
  `iw db-backup prune`, `iw db-backup restore`; plus `./ai-core.sh db backup`
  wrappers. `create` runs synchronously and works even when the daemon is down.
- **Jobs UI surfacing**: backup jobs appear in the unified jobs view
  (`orch/jobs/aggregator.py` + `dashboard/routers/jobs_ui.py` + template).
- **Docs**: README, CLAUDE.md (config + ⚠️ same-disk limitation + "agents don't
  touch the backup directory"), `docs/IW_AI_Core_DB_Setup.md` (link/section), and a
  new restore guide `docs/IW_AI_Core_DB_Backup_Restore.md`.

### Out of Scope

- Physical base backups, WAL archiving, and point-in-time recovery (deferred Tier 2).
- Off-host / object-storage (S3/MinIO) upload (deferred Tier 2; the configurable
  `IW_CORE_BACKUP_DIR` is the seam that makes it easy later).
- Backing up per-worktree DBs (ephemeral; restored from prod — not backed up).
- An `AGENTS.md` (none exists in the repo; explicitly out of scope).

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `DbBackupJob` model + migration (`make migration-pending`) | — |
| S02 | qv-gate (migration-check) | Alembic round-trip + drift check | — |
| S03 | backend-impl | Backup config (`IW_CORE_BACKUP_*`) + backup engine (dump + globals + integrity + manifest) | — |
| S04 | code-review-impl | Review S01 + S03 (core) | — |
| S05 | backend-impl | Retention/prune (manual-exempt) + restore helper (safe target, globals-first, identity check) | — |
| S06 | pipeline-impl | Daemon backup scheduler/poller (daily + missed-window catch-up) + `daemon/main.py` wiring | — |
| S07 | code-review-impl | Review S05 + S06 | — |
| S08 | frontend-impl | Surface backup jobs in unified Jobs view (aggregator + jobs_ui + template) | — |
| S09 | backend-impl | CLI (`iw db-backup` group) + `./ai-core.sh db backup` wrappers | — |
| S10 | backend-impl | Docs (README, CLAUDE, DB-Setup, new restore guide) | — |
| S11 | tests-impl | Unit + integration tests incl. dump/restore round-trip + jobs-UI render test | — |
| S12 | code-review-impl | Review S08–S11 | — |
| S13 | code-review-final-impl | Global review | — |
| S14..S20 | qv-gate | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests | — |
| S21 | self-assess-impl | Self-assessment | — |

### Database Changes

- **New tables**: `db_backup_jobs` (`DbBackupJob`). Columns (indicative): `id`,
  `backup_type` (enum/text: scheduled|manual), `label` (nullable), `status`
  (queued|running|success|failed), `path` (backup set directory/file),
  `bytes` (nullable), `alembic_revision`, `instance_id`, `row_counts` (JSON),
  `error` (nullable), `created_at`, `started_at`, `finished_at`. Index on
  (`backup_type`, `status`, `created_at`) to support catch-up + prune queries.
- **Modified tables**: None.
- **Migration notes**: Generate with `make migration-pending MSG="add db_backup_jobs"`
  (sets `down_revision = "PENDING"`; resolved at merge). Verified by S02
  `migration-check`.

### API Changes

- **New endpoints**: None (the Jobs view is server-rendered; backup jobs flow
  through the existing aggregator/jobs_ui, not a new JSON API).
- **Modified endpoints**: None.

### Frontend Changes

- **New components**: None.
- **Modified components**: Unified Jobs view (`dashboard/routers/jobs_ui.py` +
  its template) gains a backup-job row type, fed by `orch/jobs/aggregator.py`.

## File Manifest

All files for this work item live under `ai-dev/active/F-00092/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00092_Feature_Design.md` | Design | This document |
| `F-00092_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00092_S01_Database_prompt.md` | Prompt | S01 model + migration |
| `prompts/F-00092_S03_Backend_prompt.md` | Prompt | S03 config + engine |
| `prompts/F-00092_S04_CodeReview_prompt.md` | Prompt | Review S01+S03 |
| `prompts/F-00092_S05_Backend_prompt.md` | Prompt | S05 retention/prune + restore |
| `prompts/F-00092_S06_Pipeline_prompt.md` | Prompt | S06 daemon scheduler/poller |
| `prompts/F-00092_S07_CodeReview_prompt.md` | Prompt | Review S05+S06 |
| `prompts/F-00092_S08_Frontend_prompt.md` | Prompt | S08 Jobs view surfacing |
| `prompts/F-00092_S09_Backend_prompt.md` | Prompt | S09 CLI + ai-core.sh wrappers |
| `prompts/F-00092_S10_Backend_prompt.md` | Prompt | S10 docs |
| `prompts/F-00092_S11_Tests_prompt.md` | Prompt | S11 tests |
| `prompts/F-00092_S12_CodeReview_prompt.md` | Prompt | Review S08–S11 |
| `prompts/F-00092_S13_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/F-00092_S21_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/active/F-00092/reports/`.

### Files Changed (production code/docs)

- `orch/db/models.py` (DbBackupJob), `orch/db/migrations/versions/**` (migration)
- `orch/config.py` (IW_CORE_BACKUP_* settings)
- `orch/backup/**` (new package: engine, retention, restore)
- `orch/daemon/backup_poller.py` (new) + `orch/daemon/main.py` (wiring)
- `orch/jobs/aggregator.py`, `dashboard/routers/jobs_ui.py`, the jobs template
- `orch/cli/backup_commands.py` (new) + CLI registration, `ai-core.sh` (wrappers)
- `.env.example`, `README.md`, `CLAUDE.md`, `docs/IW_AI_Core_DB_Setup.md`,
  `docs/IW_AI_Core_DB_Backup_Restore.md` (new)
- `tests/**`

## Acceptance Criteria

### AC1: Scheduled daily backup + retention

```
Given backups are enabled and the daemon is running
When the configured daily backup time passes
Then exactly one scheduled backup set (dump + globals + manifest) is created in IW_CORE_BACKUP_DIR
  And scheduled backups older than IW_CORE_BACKUP_RETENTION_DAYS are deleted
  And manual/labeled backups are NOT deleted regardless of age
```

### AC2: On-demand backup works even when the daemon is down

```
Given the daemon is not running
When an operator runs `iw db-backup create --label pre-migration`
Then a backup set is produced synchronously
  And a DbBackupJob row of type=manual with that label is recorded with status=success
```

### AC3: Globals are captured (restore-into-fresh-cluster works)

```
Given a completed backup set
When it is restored into a brand-new empty PostgreSQL cluster
Then the iw_orch role (with its password) exists from the globals file
  And the iw_orch database restores without authentication or ownership errors
```

### AC4: Missed-window catch-up

```
Given the daemon was down across the configured daily backup window
  And no successful scheduled backup exists within the interval
When the daemon next polls
Then it runs a scheduled backup immediately rather than waiting for the next window
```

### AC5: Guided restore to a safe target

```
Given a completed backup set and a chosen non-prod target
When an operator runs `iw db-backup restore --from <set>`
Then globals are applied first, then the iw_orch dump
  And `iw db-identity check` passes against the restored target
  And row counts for projects/batches/work_items are printed
  And the live prod DB on 5433 is never overwritten by default
```

### AC6: Backup jobs visible in the Jobs view

```
Given at least one DbBackupJob exists
When the unified Jobs view is rendered
Then a row for the backup job appears with its type, status, and timestamp
```

### AC7: Fully configurable

```
Given IW_CORE_BACKUP_ENABLED / _DIR / _RETENTION_DAYS / _TIME are set in .env
When the engine and scheduler run
Then they honor those values, and IW_CORE_BACKUP_ENABLED=false disables scheduled backups
```

## Boundary Behavior

**Every row becomes a mandatory test case.**

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Backups disabled | `IW_CORE_BACKUP_ENABLED=false` | Scheduler creates no backups; `iw db-backup create` still works on explicit invocation (manual override) and says backups are disabled-by-schedule |
| Backup dir missing | `IW_CORE_BACKUP_DIR` does not exist | Engine creates it (recursively) before writing |
| pg_dump produces truncated/corrupt archive | integrity check fails | Backup marked `failed`, partial files cleaned up or clearly marked, error recorded; not counted as a successful scheduled backup (so catch-up still fires) |
| Retention with only manual backups | 5 manual backups older than 30d | None deleted |
| Retention boundary | scheduled backup exactly N days old | Deterministic rule (e.g. strictly `> retention_days` kept-or-deleted) documented and tested |
| Catch-up when a recent success exists | last scheduled success within interval | No extra backup is run |
| Restore target = prod (guard) | operator points restore at the live 5433 DB | Refuse unless an explicit override flag is given; default target is non-prod |
| Concurrent scheduled + manual | manual backup running when window hits | No corruption; the scheduler does not double-run; jobs serialize or are isolated by distinct paths |
| DB unreachable at backup time | 5433 down | Backup marked `failed` with a clear error; scheduler retries next poll/window (and catch-up applies) |
| Backup dir disk full mid-dump | a write fails partway through producing the set | Backup marked `failed` with a clear error; the partial set is cleaned up (or clearly marked) so it is NOT counted as a successful scheduled backup; catch-up retries on the next window |
| Globals file contains role password hashes | any backup set on disk | The backup-set directory is created `0700` and the `--globals-only` file is written `0600`; a co-located backup never widens credential exposure |

## Invariants

1. Every successful backup set contains all three artifacts: the `pg_dump -Fc`
   archive, the `pg_dumpall --globals-only` SQL, and the JSON manifest.
2. A backup is only recorded `success` if the `pg_restore --list` integrity check
   passed.
3. Retention/prune never deletes a backup whose `backup_type=manual`.
4. The restore helper never overwrites the live prod DB (5433) unless an explicit
   override flag is supplied.
5. `iw db-backup create` succeeds independently of daemon state (no dependency on
   the daemon process being alive).
6. The self_assess step is the final step in the manifest (determinism — F-00078
   Invariant 6).
7. No port, path, or credential is hardcoded; all come from `.env` via
   `orch/config.py`.
8. The backup-set directory is created with restrictive permissions (`0700`) and the
   `pg_dumpall --globals-only` file (which contains role password hashes) is written
   `0600`, so a co-located backup never widens credential exposure.

## Dependencies

- **Depends on**: I-00122
- **Blocks**: None

F-00092 must run **after** I-00122 merges — they share `ai-core.sh`,
`.env.example`, and `docs/IW_AI_Core_DB_Setup.md` (file overlap, so not in
parallel), and F-00092 builds on I-00122's `IW_CORE_DB_DATA_DIR`. A future Tier-2
feature (physical/WAL/PITR/off-host) would build on F-00092.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/config.py`
- `orch/backup/**`
- `orch/daemon/backup_poller.py`
- `orch/daemon/main.py`
- `orch/jobs/aggregator.py`
- `orch/cli/backup_commands.py`
- `orch/cli/__init__.py`
- `dashboard/routers/jobs_ui.py`
- `dashboard/templates/**`
- `dashboard/static/styles.css`
- `ai-core.sh`
- `.env.example`
- `README.md`
- `CLAUDE.md`
- `docs/IW_AI_Core_DB_Setup.md`
- `docs/IW_AI_Core_DB_Backup_Restore.md`
- `tests/unit/**`
- `tests/integration/**`
- `tests/dashboard/**`

## TDD Approach

- Unit tests: config parsing/defaults; manifest contents; retention rule
  (manual-exempt, boundary at exactly N days); catch-up decision logic
  (recent-success vs missed-window) using injected timestamps; restore-target
  safety guard.
- Integration tests (testcontainer): full dump → restore round-trip into a fresh
  testcontainer asserting row counts match and the `iw_orch` role exists from
  globals; integrity-check-fails path; backup against a reachable testcontainer DB.
- Dashboard test (`tests/dashboard/`, file-local `client` fixture): the unified
  jobs view renders a backup-job row when a `DbBackupJob` exists.
- Edge cases: every Boundary Behavior row above.

## Notes

- **Engine must be connection-string based and testable.** Implement the engine
  around a libpq connection (host/port/user/db/password from `orch/config.py`), and
  obtain `pg_dump`/`pg_restore`/`psql` via a `docker run --rm postgres:<major>-alpine`
  connecting over TCP when host client tools are absent (the host has no psql).
  Tests target a testcontainer Postgres, never the live 5433 DB.
- **Docker pg-client networking + version match (two sharp edges).** (a) On Linux a
  throwaway `docker run --rm` container reaches a **host-bound** 5433 only via
  `--network host` (or `--add-host host.docker.internal:host-gateway` and connecting
  to `host.docker.internal`) — plain `localhost` inside the container will not find
  it. (b) `pg_dump` **refuses to dump from a server newer than the client**, so the
  pg-client image major version MUST match the production server's major version. The
  engine should resolve the client image major from the live server version (or
  config) rather than hardcoding `15`, and the manifest records the server version so
  restore-time compatibility can be checked.
- **Globals file holds credentials.** `pg_dumpall --globals-only` emits role password
  hashes (SCRAM/md5) as plaintext SQL. Because the default `IW_CORE_BACKUP_DIR` is
  co-located with the data disk, the engine MUST create each backup-set directory
  `0700` and write the globals file `0600` (Invariant 8). The restore guide and the
  security-SAST gate (S18) should treat the globals file as a secret.
- **⚠️ Same-disk default storage limitation (must be documented in CLAUDE.md and
  the restore guide).** The default `IW_CORE_BACKUP_DIR=/opt/postgres/data/backups`
  is a *sibling* of `pgdata/` (NOT inside the live cluster directory). It is on the
  **same disk** as the data: this protects against operator mistakes, bad
  migrations, and container displacement (the actual recurring incidents;
  `/opt/postgres/data` is a host bind mount, so `docker volume rm`/`compose down -v`
  cannot touch it), but does **not** protect against disk failure or
  `rm -rf /opt/postgres/data`. The path is configurable precisely so it can be
  repointed off-host later; the docs must say this and show how.
- **Identity nuance**: the `iw_core_instance` row is captured in the logical dump,
  so a restored DB keeps the same instance id and the `IW_CORE_EXPECTED_INSTANCE_ID`
  pin still matches — the restore guide should note this and how to re-pin if
  restoring to a deliberately new identity.
- A future Tier-2 feature (pgBackRest/WAL-G physical backups + WAL archiving +
  off-host upload + PITR) is recommended but explicitly deferred.
