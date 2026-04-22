# CR-00015 S02 Code Review Report

## What was done

Reviewed S01 (backend-impl) changes for CR-00015 against the full review checklist. Ran `docker compose config` and `docker compose -f docker-compose.bootstrap.yml config` locally to verify parse correctness.

## Files reviewed

| File | Change | Verdict |
|------|--------|---------|
| `docker-compose.bootstrap.yml` | New — moved `db` service, added `name: iw-ai-core` + header comment | PASS |
| `docker-compose.yml` | Replaced with `services: {}` stub + explanatory comment | PASS |
| `ai-core.sh` | `cmd_db start/stop/logs` use `-f docker-compose.bootstrap.yml` | PASS |
| `Makefile` | Added `COMPOSE_BOOTSTRAP` variable; `db-up`/`db-down` use it | PASS |

## Checklist results

### 1. `docker-compose.bootstrap.yml` correctness
- **File exists**: Yes.
- **`name: iw-ai-core`**: Present at line 20. Confirmed stable volume name: `iw-ai-core_pgdata` (verified via `docker compose -f docker-compose.bootstrap.yml config`).
- **`db` service content**: image `postgres:15-alpine`, `container_name: iw-ai-core-db`, ports `"${IW_CORE_DB_PORT:-5433}:5432"`, env vars with env-var substitution — **no hardcoded credentials**.
- **Header comment**: Lines 1–18 explain WHY (2026-04-22 incident), point to `docs/IW_AI_Core_DB_Setup.md`, explain the design intent.
- **`docker compose -f docker-compose.bootstrap.yml config`**: parses cleanly — verified.
- **No `/opt/postgres/data` bind mount**: correct (bootstrap uses named volume `pgdata`).

### 2. Root `docker-compose.yml` (stub)
- **Contains `services: {}`**: yes.
- **Comment block** explaining intentional emptiness with pointer to `docs/IW_AI_Core_DB_Setup.md`: yes (lines 1–14).
- **`docker compose config`** (root): succeeds, shows `services: {}`, no services.
- **Stub over deletion**: justified in S01 report — `services: {}` is more user-friendly and parseable.

### 3. `ai-core.sh` changes
- **`cmd_db start`** (line 216): `COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml up -d db` — correct.
- **`cmd_db stop`** (line 223): `COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml stop db` — correct.
- **`cmd_db logs`** (line 257): `COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml logs -f db` — correct.
- **`COMPOSE_PROJECT_NAME=iw-ai-core`**: exported inline on each invocation — unchanged from prior hardening pass.
- **`db_ready` short-circuit** (lines 211–214): preserved, no regression.
- **No unrelated changes** in `cmd_*` functions.

### 4. `Makefile` changes
- **`COMPOSE_BOOTSTRAP` variable** (line 63): `docker compose -f docker-compose.bootstrap.yml` — top of file, used consistently.
- **`db-up`** (line 66): `COMPOSE_PROJECT_NAME=iw-ai-core $(COMPOSE_BOOTSTRAP) up -d db` — correct.
- **`db-down`** (line 69): `COMPOSE_PROJECT_NAME=iw-ai-core $(COMPOSE_BOOTSTRAP) down` — correct.
- **`.PHONY:` declarations** (lines 5–8): preserved, unchanged.
- **No unrelated target changes**.

### 5. Docs untouched (scope compliance)
- **S01 did not edit any `.md` file**: confirmed — no markdown files modified by S01.
- **Stale doc references list** in S01 report: present, lists 5 files. The grep run during this review confirms those 5 files (`CLAUDE.md`, `docs/IW_AI_Core_Tech_Stack.md`, `docs/implementation/01_foundation/02_config_and_db.md`, `README.md`, `docs/README.md`) still contain `docker compose up -d db` references. This is S03's scope.

### 6. Safety
- **`/opt/postgres/data`**: no bind mount reference added or removed in compose files.
- **No destructive commands** introduced.
- **Live `postgres` container** not stopped during S01 smoke testing — verified in S01 report (simulated fresh machine via `IW_CORE_DB_PORT=65432`, no impact on live 5433).

## Issues found

**None.** All checklist items pass.

## Verification commands run

```bash
# Root compose parses to empty services
$ docker compose config
name: cr-00015
services: {}

# Bootstrap compose parses correctly, volume name confirmed
$ docker compose -f docker-compose.bootstrap.yml config
name: iw-ai-core
services:
  db:
    container_name: iw-ai-core-db
    ...
volumes:
  pgdata:
    name: iw-ai-core_pgdata
```

## Blockers

None.

## Notes

- `COMPOSE_PROJECT_NAME` in `docker compose config` output shows `cr-00015` (derived from the worktree directory name) for the root compose — expected since the root compose has `services: {}` and no `name:`. The bootstrap compose correctly shows `iw-ai-core` because it has the explicit `name: iw-ai-core` top-level key.
- Pre-existing lint warning in `orch/cli/item_commands.py:593` (`archive_dir` unused) is unrelated to this CR — flagged in S01 report.
- S01 correctly chose `services: {}` stub over deletion; the justification in the report is sound.