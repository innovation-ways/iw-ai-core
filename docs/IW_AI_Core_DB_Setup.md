# IW AI Core — Database Setup

The orchestration database is a single long-lived PostgreSQL 15 instance on
host port 5433. There are TWO paths to stand it up; pick the one that matches
your context.

| Path | When to use | Data location |
|---|---|---|
| **Production** (raw `docker run`, bind mount) | Any machine where the DB must persist across container replacements | Host bind mount `/opt/postgres/data` |
| **Bootstrap** (compose, named volume) | First-time dev machine with no pre-existing container | Docker volume `iw-ai-core_pgdata` |

**Never run `docker compose up` from a worktree against the orchestration DB.**
See *Why this split exists* below for the incident that shaped this rule.

---

## Production path (primary)

The production DB is a raw `docker run` container with a **host bind mount** at
`/opt/postgres/data`. This means the data survives container restarts and
replacements — the container itself is ephemeral but the data is persistent.

### Pre-flight

Ensure the data directory exists on the host with appropriate ownership:

```bash
sudo mkdir -p /opt/postgres/data
sudo chown 999:999 /opt/postgres/data   # postgres UID in the container
```

(Replace the UID if running as a different user; 999 is the `postgres` user
inside the `postgres:15-alpine` image.)

### Credentials

All credentials come from `.env` — nothing is hardcoded. Copy `.env.example`
to `.env` and set `IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, and
`IW_CORE_DB_PASSWORD` before starting.

Set `IW_CORE_DB_DATA_DIR` to your production bind-mount path (for example
`/opt/postgres/data`) so `./ai-core.sh db start-prod` can recreate/start the
production container without hardcoded host paths.

### Run command

```bash
docker run -d \
  --name postgres \
  --restart unless-stopped \
  -p 5433:5432 \
  -v /opt/postgres/data:/var/lib/postgresql/data \
  -e POSTGRES_DB="$IW_CORE_DB_NAME" \
  -e POSTGRES_USER="$IW_CORE_DB_USER" \
  -e POSTGRES_PASSWORD="$IW_CORE_DB_PASSWORD" \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  postgres:15-alpine
```

### Verify

```bash
./ai-core.sh db status
```

Expected output: "PostgreSQL: accepting connections" — no container name check
needed, only port + connection check.

### DB identity (post-CR-00014)

After the DB is up, register its identity fingerprint so CR-00014's integrity
check can detect any accidental swap:

```bash
uv run iw db-identity show
```

Add the returned UUID to `.env` as `IW_CORE_EXPECTED_INSTANCE_ID`. See
`docs/IW_AI_Core_Daemon_Design.md` for the full identity verification flow.

---

## Bootstrap path (dev only — throwaway DB)

> Use this only when you don't have a pre-existing `postgres` container and
> the DB will be ephemeral (local dev, no important data).

```bash
docker compose -f docker-compose.bootstrap.yml up -d db
```

This creates a named volume `iw-ai-core_pgdata` (not a bind mount). The
volume is managed entirely by Docker; destroying the container does NOT
destroy the volume, but re-running from a clean state is expected.

Note the `-f` flag is mandatory. `docker compose up` without it does nothing —
the root `docker-compose.yml` is an intentional stub.

Preferred (uses `./ai-core.sh` which sets `COMPOSE_PROJECT_NAME`):

```bash
./ai-core.sh db start
```

### Guarded behavior when production identity is pinned

If `.env` sets `IW_CORE_EXPECTED_INSTANCE_ID` and the DB is down,
`./ai-core.sh db start` now **refuses** to run bootstrap compose. This prevents
an empty `iw-ai-core_pgdata` database from taking over production port 5433
while the real bind-mount cluster is offline.

Use the production recovery command instead:

```bash
./ai-core.sh db start-prod
```

`start-prod` requires `IW_CORE_DB_DATA_DIR` in `.env`. It starts (or creates)
a stable raw Docker container (`iw-orch-pg`) with `--restart=always`, binds
`${IW_CORE_DB_PORT}:5432`, mounts `${IW_CORE_DB_DATA_DIR}` to
`/var/lib/postgresql/data`, and waits for readiness.

---

## Why this split exists

On **2026-04-22**, the default `docker-compose.yml` (which then contained
the `db` service directly) was invoked from a git worktree at
`.worktrees/F-00058/`. Docker Compose uses the cwd basename as its project
name unless overridden, so the invocation created a volume
`f-00058_pgdata` (empty, fresh schema) and a container `iw-ai-core-db`
that took over port 5433. The real orchestration DB — a raw `docker run`
container named `postgres` with a host bind mount at `/opt/postgres/data`
— had been SIGKILLed minutes earlier by an unrelated process. Nothing
detected the swap because the impostor DB had the correct schema and
credentials. 94 work items, 35 batches, 631 step runs, and 66 project
docs silently stopped being written for ~80 minutes.

CR-00014 added an identity-fingerprint check that now catches such a
swap immediately. CR-00015 (this change) removed the underlying
temptation: `docker compose up` from any directory no longer touches
port 5433 because the `db` service has been moved to
`docker-compose.bootstrap.yml`, which requires an explicit `-f` flag.

---

## Quick reference — common commands

| I want to... | Command |
|---|---|
| Check if DB is running | `./ai-core.sh db status` |
| Start the DB (bootstrap path) | `./ai-core.sh db start` |
| Start/recover the production bind-mount DB | `./ai-core.sh db start-prod` |
| Stop the DB | `./ai-core.sh db stop` |
| Restart the DB | `./ai-core.sh db restart` |
| Tail DB container logs | `./ai-core.sh db logs` |
| Open a psql shell | `./ai-core.sh db shell` |
| Run Alembic migrations | `./ai-core.sh db migrate` |
| Generate a migration | `./ai-core.sh db revision "message"` |
| Verify DB identity | `uv run iw db-identity check` |

`./ai-core.sh db start`/`stop`/`logs` route through the bootstrap compose file
with the correct project name and are safe for dev/bootstrap usage from any
worktree. The production recovery path is `./ai-core.sh db start-prod`, which
uses raw `docker run`/`docker start` against `IW_CORE_DB_DATA_DIR`.
