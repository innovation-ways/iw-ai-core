# F-00092_S03_Backend_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

No long-lived container/volume state changes. The engine MAY invoke
`docker run --rm postgres:<major>-alpine ...` to obtain `pg_dump`/`pg_restore`/`psql`
client binaries connecting over TCP (the host has no pg client tools) — this is
allowed because it self-removes and changes no persistent state. You MUST NOT run
backups against the live orchestration DB on 5433 during development; exercise the
engine only against a throwaway/testcontainer DB.

**Two sharp edges to handle (do not hardcode around them):**
- **Networking**: on Linux a `docker run --rm` container reaches a **host-bound**
  5433 only via `--network host` (or `--add-host host.docker.internal:host-gateway`
  and connecting to `host.docker.internal`) — plain `localhost` inside the container
  will not find the host DB.
- **Version match**: `pg_dump` refuses to dump from a server **newer** than the
  client, so the pg-client image major version MUST match the production server's
  major version. Resolve the client image major from the live server version (or
  config) rather than pinning `15`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step (S01 owns the schema).

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — read **Scope**, **Notes**
  (engine testability + same-disk caveat), **Invariants** 1, 2, 7.
- `ai-dev/active/F-00092/reports/F-00092_S01_Database_report.md` — final
  `DbBackupJob` column names.
- `orch/config.py` — existing config pattern (reads `.env`; `IW_CORE_*` vars).
- `orch/db/identity.py` — how to read the `iw_core_instance` id and alembic rev.

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S03_Backend_report.md`.

## Context

Add backup configuration and the standalone **backup engine**. The engine is
library code used by BOTH the daemon scheduler (S06) and the CLI (S09), so it must
not import daemon-only state and must work as a plain function call.

## Requirements

### 1. Config in `orch/config.py`

Add settings read from `.env` (match the existing config style/validation):
- `IW_CORE_BACKUP_ENABLED` (bool, default `true`)
- `IW_CORE_BACKUP_DIR` (path, default `/opt/postgres/data/backups`)
- `IW_CORE_BACKUP_RETENTION_DAYS` (int, default `30`)
- `IW_CORE_BACKUP_TIME` (daily HH:MM, default `03:00`)

Never hardcode these anywhere else — read them from config.

### 2. Backup engine (new package `orch/backup/`)

A function (e.g. `create_backup(config, *, backup_type, label=None) -> result`)
that:
1. Resolves a connection to `iw_orch` from config (host/port/user/db/password).
   Target a **libpq connection string**; obtain `pg_dump`/`pg_dumpall` via the host
   binary if present, else via `docker run --rm postgres:15-alpine` over TCP.
2. Creates a timestamped backup-set directory under `IW_CORE_BACKUP_DIR` (create the
   dir tree if missing). The backup-set directory MUST be created with mode `0700`.
3. Produces three artifacts:
   - `pg_dump -Fc` custom-format archive of `iw_orch`.
   - `pg_dumpall --globals-only` SQL (roles **and passwords** — MANDATORY; without
     it a restore into a fresh cluster has no `iw_orch` role, the exact live failure
     `password authentication failed for user "iw_orch"`). This file holds role
     password hashes — write it with mode `0600` (Invariant 8); never log its
     contents.
   - a JSON **manifest**: UTC timestamp, alembic revision, `iw_core_instance` id,
     row counts (projects/batches/work_items), `backup_type`, `label`, artifact
     filenames + sizes, and the **PostgreSQL server version** (for restore-time
     client/server compatibility).
4. Runs a `pg_restore --list` **integrity check** on the produced archive; if it
   fails, the backup is `failed` (Invariant 2) — clean up or clearly mark the
   partial set. The same `failed` + cleanup path applies to **any** mid-run write
   failure (disk full while writing the set, dump subprocess error, DB unreachable):
   never leave a half-written set that could be mistaken for a successful scheduled
   backup (Boundary "Backup dir disk full mid-dump" / "DB unreachable").
5. Records a `DbBackupJob` row (status transitions queued→running→success/failed,
   timestamps, path, bytes, error, manifest fields). The engine accepts an
   optional injected session/`session_factory` so it can record the row, and a
   way to run without a session for pure-dump unit testing.

Keep it deterministic and side-effect-isolated: no reliance on the daemon being
alive (Invariant 5). Do NOT implement retention, restore, the daemon scheduler, the
CLI, or docs here — those are S05/S06/S09/S10.

## Project Conventions

Read `CLAUDE.md`. Match `orch/config.py` conventions; respect layer boundaries
(engine is a service-layer module, no FastAPI/daemon imports). Use the project's
logging and error-handling style.

## TDD Requirement (RED first)

Write failing unit tests first for the pure pieces (manifest construction, config
defaults/overrides, the integrity-check failure path with a stubbed/garbage
archive), run them targeted (`uv run pytest tests/unit/.../test_backup_engine.py -v`),
capture the RED failure, then implement. The full dump↔restore round-trip
(testcontainer) is owned by S11 — do not build that here, but design the engine so
S11 can call it against a testcontainer.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — zero new errors.

## Test Verification (NON-NEGOTIABLE)

Run only your targeted unit tests. Do NOT run `make test-unit`/`make test-integration`.

> **Verification Placement Rule**: a full suite/aggregate gate passing is never a
> completion gate for this step.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["orch/config.py", "orch/backup/__init__.py", "orch/backup/engine.py", "tests/unit/..."],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "tests/unit/.../test_backup_engine.py::test_manifest_fields — AssertionError ... // captured RED run",
  "blockers": [],
  "notes": "Document the engine's public function signature for S05/S06/S09."
}
```
