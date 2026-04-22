# CR-00015_S01_Backend_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun (split into bootstrap.yml)
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md` — Design document (Desired Behavior, AC1–AC4, AC7)
- `docker-compose.yml` — current root compose file (22 lines, sole service is `db`)
- `ai-core.sh` — contains `cmd_db start|stop|logs`; already has `COMPOSE_PROJECT_NAME=iw-ai-core` guard
- `Makefile` — has `db-up` / `db-down` / `db-logs` targets
- `.env.example` — env-var conventions (read-only reference)
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S01_Backend_report.md`
- `docker-compose.bootstrap.yml` — new file with the former `db` service
- `docker-compose.yml` — stub (with explanatory comment) OR deleted — pick per §3 below
- `ai-core.sh` — `cmd_db start`, `cmd_db stop`, `cmd_db logs` updated to use `-f docker-compose.bootstrap.yml`
- `Makefile` — `db-up` (and related) updated

## Context

You're moving the `db` service from the default `docker-compose.yml` to a dedicated `docker-compose.bootstrap.yml` so it cannot be invoked accidentally. Read the design doc first — especially the **Current Behavior** section (explains the 2026-04-22 data-loss incident) and AC1–AC4. Then read `ai-core.sh cmd_db` and the Makefile's `db-*` targets.

## Requirements

### 1. Create `docker-compose.bootstrap.yml`

Move the contents of the current `docker-compose.yml` into a new file `docker-compose.bootstrap.yml` at the project root. Apply these changes during the move:

- Add a top-level `name: iw-ai-core` key (Compose v2 supports this; it pins the project name regardless of the cwd where the file is invoked). This is the belt-and-braces for the `COMPOSE_PROJECT_NAME=iw-ai-core` env-var already set in `ai-core.sh`.
- Prepend a header comment block explaining the file's purpose:

```yaml
# docker-compose.bootstrap.yml
#
# Bootstrap compose file — for FRESH DEV MACHINES ONLY.
#
# Production-path orchestration DB is NOT managed by Compose. It is a raw
# `docker run` postgres container with a host bind mount at /opt/postgres/data.
# See docs/IW_AI_Core_DB_Setup.md for the full setup guide.
#
# This file exists because the previous default docker-compose.yml caused a
# data-loss incident on 2026-04-22 when it was invoked from a git worktree
# and created a per-worktree empty volume that clobbered port 5433.
#
# Usage:
#   docker compose -f docker-compose.bootstrap.yml up -d db
#
# Never invoke this file implicitly (i.e. without `-f`). The default
# docker-compose.yml at the project root is intentionally empty so that
# `docker compose up` from any directory (including worktrees) is a no-op.
```

- Keep all existing behavior otherwise: same image (`postgres:15-alpine`), same `container_name: iw-ai-core-db`, same port mapping, same env-var substitution for credentials (must still read from `.env`), same `pgdata` named volume, same healthcheck.

### 2. Update root `docker-compose.yml`

Replace the root `docker-compose.yml` with a minimal stub:

```yaml
# docker-compose.yml
#
# INTENTIONALLY EMPTY.
#
# The `db` service has been moved to docker-compose.bootstrap.yml to prevent
# accidental `docker compose up` invocations from creating empty postgres
# volumes that clobber the production orchestration DB. See
# docs/IW_AI_Core_DB_Setup.md for context and the 2026-04-22 incident.
#
# If you are looking for a `db` service, use:
#   docker compose -f docker-compose.bootstrap.yml up -d db
#
# Or, preferred for the production orchestration DB:
#   see docs/IW_AI_Core_DB_Setup.md

services: {}
```

`services: {}` is a valid Compose document that parses without error and produces no containers on `docker compose up`. Verify locally: `docker compose config` from the root should return successfully with "no services defined" (or equivalent).

### 3. Stub-vs-delete decision

- **Strongly prefer the stub.** A deleted file produces a misleading `no configuration file provided` error that sends users hunting. The stub is self-documenting and guides them to `docs/IW_AI_Core_DB_Setup.md`.
- If for some reason the stub breaks tooling you cannot fix (e.g., some CI script treats `services: {}` as a syntax error), fall back to deletion and document it in the report.

### 4. Update `ai-core.sh`

Affected functions:

- `cmd_db start` — change `docker compose up -d db` to `docker compose -f docker-compose.bootstrap.yml up -d db`. The existing `COMPOSE_PROJECT_NAME=iw-ai-core` inline export stays.
- `cmd_db stop` — currently `docker compose stop db`. Change to `docker compose -f docker-compose.bootstrap.yml stop db`. Add the same `COMPOSE_PROJECT_NAME=iw-ai-core` inline so it targets the correct project.
- `cmd_db logs` — currently `docker compose logs -f db`. Change to `docker compose -f docker-compose.bootstrap.yml logs -f db` (same project-name export).

Preserve every other behavior in `cmd_db` (the `db_ready` short-circuit added in the earlier hardening pass, the `wait_for_db` call, etc.).

### 5. Update `Makefile`

Search for every target that runs `docker compose ... db`. Typical targets: `db-up`, `db-down`, `db-logs`. Update each to use `-f docker-compose.bootstrap.yml`. Keep them readable — consider a top-of-Makefile variable:

```make
COMPOSE_BOOTSTRAP := docker compose -f docker-compose.bootstrap.yml
```

Then targets read as `$(COMPOSE_BOOTSTRAP) up -d db`. Use `COMPOSE_PROJECT_NAME=iw-ai-core` export at the target level (or a `.EXPORT_ALL_VARIABLES:` directive if that's already how the Makefile handles env).

Do NOT change any target unrelated to DB (lint, test, daemon-start, dashboard-start, etc.).

### 6. No changes to `.env` or `.env.example`

Neither file references the compose file directly. Leave untouched.

### 7. Do NOT touch documentation

Docs are S03's responsibility. You may add a TODO line in your S01 report listing the docs you believe still reference `docker compose up -d db`, but do not edit them here.

## Project Conventions

- `ai-core.sh` already uses `print_info` / `print_ok` / `print_err` helpers and has a specific guard structure (if `db_ready` → return 0 without calling docker). Preserve that.
- Makefile targets use `.PHONY:` declarations. Preserve.
- Do NOT add new dependencies.

## TDD Requirement

This step has limited testable code; S05 handles integration-level tests. Smoke-test locally:

1. `docker compose config` (from project root) → parses cleanly, no `db` service.
2. `docker compose -f docker-compose.bootstrap.yml config` → parses cleanly, lists `db`, project name `iw-ai-core`.
3. `./ai-core.sh db start` with the live DB already up → prints "Database already accepting connections", does NOT invoke docker.
4. Stop the live DB briefly (to simulate a fresh machine) → `./ai-core.sh db start` should now invoke the bootstrap compose. **IMPORTANT**: do not actually stop the production `postgres` container during this test; instead, temporarily override `IW_CORE_DB_PORT` to an unused port in a subshell and run `./ai-core.sh db start` — confirm it attempts the `-f` flag. Restore.

Document the smoke steps you ran in the S01 report.

## Safety rails

- Do NOT stop, restart, or remove the live `postgres` container under any circumstance.
- Do NOT touch `/opt/postgres/data`.
- Do NOT run `docker compose up -d db` against the root file during testing (the root file is intentionally empty; this is fine but make sure you don't revert).
- Do NOT delete existing volumes.

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — pass.
2. `./ai-core.sh db start` behaves correctly (smoke step 3 above).
3. `docker compose config` (root) and `docker compose -f docker-compose.bootstrap.yml config` both succeed with the expected shapes.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00015",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docker-compose.yml",
    "docker-compose.bootstrap.yml",
    "ai-core.sh",
    "Makefile"
  ],
  "tests_passed": true,
  "test_summary": "lint green; docker compose config smoke PASS; ai-core.sh db start no-op PASS",
  "blockers": [],
  "notes": "Chose stub over deletion for root docker-compose.yml. Docs intentionally untouched (deferred to S03). Stale doc references enumerated below: [...]"
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S01
# implement ...
uv run iw step-done CR-00015 --step S01 --report ai-dev/active/CR-00015/reports/CR-00015_S01_Backend_report.md
```
