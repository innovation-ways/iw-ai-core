# CR-00015 S01 Backend Report

## What was done

Moved the `db` service from `docker-compose.yml` into a new `docker-compose.bootstrap.yml`, updated `ai-core.sh` and `Makefile` to use the `-f` flag explicitly, and replaced the root `docker-compose.yml` with a self-documenting empty stub.

## Files changed

| File | Change |
|------|--------|
| `docker-compose.bootstrap.yml` | New file — contents of former `docker-compose.yml` plus `name: iw-ai-core` top-level key and header comment |
| `docker-compose.yml` | Replaced with empty stub (`services: {}`) + explanatory comment |
| `ai-core.sh` | `cmd_db start/stop/logs` each updated to use `-f docker-compose.bootstrap.yml` and `COMPOSE_PROJECT_NAME=iw-ai-core` |
| `Makefile` | Added `COMPOSE_BOOTSTRAP` variable; `db-up` and `db-down` now use `-f docker-compose.bootstrap.yml` |

## Verification

- **`docker compose config`** (root): parses cleanly, shows `services: {}` — no `db` service, no foot-gun.
- **`docker compose -f docker-compose.bootstrap.yml config`**: parses cleanly, lists `db` service, project name `iw-ai-core`, volume `iw-ai-core_pgdata`.
- **`make lint`**: ruff passes (1 pre-existing unrelated warning in `orch/cli/item_commands.py:593` about unused `archive_dir` — not touched by this CR).
- **`./ai-core.sh db start`** (live DB up): correctly short-circuits with "Database already accepting connections" without invoking docker.
- **`./ai-core.sh db start`** (simulated fresh machine via `IW_CORE_DB_PORT=65432`): correctly invokes `docker compose -f docker-compose.bootstrap.yml up -d db` with the correct `-f` flag and project name.

## Decisions made

- **Stub over deletion**: chose `services: {}` for `docker-compose.yml` because it parses without error and contains discoverable guidance pointing to `docs/IW_AI_Core_DB_Setup.md` and the bootstrap file. Deletion was considered but stub is more user-friendly.
- **Top-level `name: iw-ai-core`** in bootstrap file: belt-and-braces with the `COMPOSE_PROJECT_NAME` env-var already set in `ai-core.sh`. Ensures stable volume name even if someone invokes the bootstrap file directly.

## Stale doc references (deferred to S03)

The following docs still reference `docker compose up -d db` or `make db-up` and need updating in S03:
- `CLAUDE.md` (top-level) — "Live DB Setup" section with `make db-up` guidance
- `docs/IW_AI_Core_Tech_Stack.md` — mentions compose-managed DB
- `docs/implementation/01_foundation/02_config_and_db.md` — setup instructions use `make db-up`
- `README.md` (top-level) — references `./ai-core.sh install` / `make db-up`
- `docs/README.md` — doc index

## Blockers

None.

## Notes

- Docs intentionally untouched — S03's responsibility per the step instructions.
- Pre-existing lint warning in `orch/cli/item_commands.py:593` is unrelated to this CR.
- The bootstrap compose's `pgdata` volume is `iw-ai-core_pgdata` regardless of cwd (confirmed in `docker compose -f docker-compose.bootstrap.yml config` output).