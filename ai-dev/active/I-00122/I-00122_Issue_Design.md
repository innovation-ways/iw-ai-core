# I-00122: `ai-core.sh db start` silently bootstraps an empty DB over a down production cluster

**Type**: Issue
**Severity**: High
**Created**: 2026-05-31
**Reported By**: Operator (dashboard showed only 1 project / 0 batches on 2026-05-30)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Agents MUST NOT run any container/volume state-changing Docker
command. Invoking `./ai-core.sh` and `make` targets is allowed; read-only
`docker ps`/`inspect`/`logs` is allowed. Testcontainer fixtures in tests are
exempt. The reproduction test in this item stubs a fake `docker` executable on
`PATH` — it never touches real Docker state.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migrations. It touches an operations shell script, an env
example file, a doc, and adds one test. The schema is unchanged.

## Description

When the production orchestration database — a raw `docker run` PostgreSQL
container that bind-mounts a host data directory onto port 5433 — is down,
`ai-core.sh db start` silently runs `docker compose -f docker-compose.bootstrap.yml up -d db`.
That command starts an **empty** bootstrap database on the `iw-ai-core_pgdata`
compose volume, which seizes port 5433. The daemon and dashboard then read and
write a near-empty database while the real cluster sits unmounted on disk, so
operators see a platform that appears to have lost every project and batch. This
displacement happened on 2026-04-22 (~80 minutes) and recurred on 2026-05-29
22:31 → 2026-05-30 09:08 (~10.5 hours).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules —
in particular the "Live DB Setup" section, which documents that the production
DB on port 5433 is a pre-existing, non-compose container and that
`docker compose up` must never be run against it. See also
`docs/IW_AI_Core_DB_Setup.md` and `docs/IW_AI_Core_Agent_Constraints.md`.

## Steps to Reproduce

1. Have a production setup where `.env` pins `IW_CORE_EXPECTED_INSTANCE_ID`
   (the real cluster's instance fingerprint) and the real DB is served by a raw
   bind-mount container on port 5433.
2. Stop or kill the real production DB container (e.g. host restart, SIGKILL,
   manual `docker rm`) so nothing is listening on 5433.
3. Run `./ai-core.sh db start` (directly, or transitively via `./ai-core.sh start`,
   or any supervisor that calls it when the DB looks down).

**Expected**: With an instance identity pinned in `.env`, `db start` recognises
that the down DB is a *production* DB and **refuses** to create a bootstrap
database on port 5433. It exits non-zero with a clear message directing the
operator to bring the real bind-mount cluster back up. No empty database is ever
created on 5433.

**Actual**: `db_ready()` is a bare connectivity probe; finding 5433 unreachable,
`cmd_db start` runs `docker compose -f docker-compose.bootstrap.yml up -d db`,
which creates an empty database on the `iw-ai-core_pgdata` volume and binds it to
5433. The daemon/dashboard then operate on the empty DB; the real cluster is left
unmounted.

## Root Cause Analysis

- `ai-core.sh:124` — `db_ready()` only checks whether something is accepting
  connections on `${DB_HOST}:${DB_PORT}`. It has no notion of *which* database is
  there, so a down production DB and a fresh dev machine are indistinguishable to
  it.
- `ai-core.sh:210-219` — `cmd_db start`: when `db_ready` is false it
  unconditionally runs
  `COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml up -d db`.
  The bootstrap compose service (`docker-compose.bootstrap.yml`) is defined with
  `container_name: iw-ai-core-db` on the `pgdata` volume → `iw-ai-core_pgdata`,
  binding `${IW_CORE_DB_PORT:-5433}:5432`. This is the empty DB that seizes 5433.
- `ai-core.sh:524-543` — `cmd_start` *does* run `iw db-identity check`
  (`ai-core.sh:528`), but only **after** `cmd_db start` (line 526) has already
  created and started the rogue container. The check then fails (the empty DB has
  no `iw_core_instance` row), and `cmd_start` aborts — but it never tears the
  rogue container down, and a daemon/dashboard that were already running simply
  reconnect to the empty DB on 5433.
- The displacement is therefore a *silent, automatic* action: nothing requires
  operator confirmation before an empty database is bound to the production port.

The identity machinery already exists (`orch/db/identity.py`:
`IW_CORE_EXPECTED_INSTANCE_ID`, `check_identity`, `InstanceRowMissingError`,
`InstanceMismatchError`) — it is simply consulted too late. The fix moves a
cheap, env-only check **before** the bootstrap action.

## Affected Components

| Component | Impact |
|-----------|--------|
| `ai-core.sh` (`cmd_db start`) | Silently creates an empty DB on the production port when the real DB is down |
| Daemon / Dashboard | Operate on the empty bootstrap DB → platform appears to have lost all projects/batches |
| `docs/IW_AI_Core_DB_Setup.md` | Does not document a guarded prod-start path; operators have no scripted, safe way to restart the bind-mount cluster |
| `.env` / `.env.example` | No configured production data directory, so the safe restart path cannot be parameterised without hardcoding a host path |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md` for the canonical rule.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add an identity-aware guard to `cmd_db start` + a config-driven, `--restart=always` prod-start path; update `.env.example` and `docs/IW_AI_Core_DB_Setup.md` | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | tests-impl | Reproduction test + regression tests (stub-`docker` harness driving `ai-core.sh`) | — |
| S04 | code-review-impl | Review S03 output | — |
| S05 | code-review-final-impl | Global review of all work | — |
| S06..S12 | qv-gate | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests | — |
| S13 | self-assess-impl | Post-execution self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migrations. Schema unchanged.

### Code Changes

- **Files to modify**: `ai-core.sh`, `.env.example`, `docs/IW_AI_Core_DB_Setup.md`; new test under `tests/unit/`.
- **Nature of change**:
  1. **Guard** — in `cmd_db start`, before invoking the bootstrap compose,
     resolve whether a production instance identity is pinned (a non-empty
     `IW_CORE_EXPECTED_INSTANCE_ID` in the environment). If it is **and** the DB
     is not ready, **refuse**: print a loud, actionable error (the DB on 5433 is
     a production DB that is down — bring up the real bind-mount cluster; do NOT
     bootstrap) and return non-zero **without** running `docker compose ... up`.
     The bootstrap compose path is taken only when no instance identity is pinned
     (a genuine fresh dev machine).
  2. **Safe prod-start path** — provide a scripted way to bring the real cluster
     back up: a raw `docker run` with `--restart=always`, binding
     `${IW_CORE_DB_DATA_DIR}:/var/lib/postgresql/data` and
     `${IW_CORE_DB_PORT}:5432`, image pinned to `postgres:15-alpine` (matching the
     cluster's `PG_VERSION`). The host data directory comes from a new
     `IW_CORE_DB_DATA_DIR` env var — **no hardcoded `/opt/...` path** in the
     script. If `IW_CORE_DB_DATA_DIR` is unset when the guard fires, the error
     message explains how to set it and run the safe path.
  3. **Docs + example** — add `IW_CORE_DB_DATA_DIR` to `.env.example` with a
     comment, and document the guard and the safe prod-start procedure in
     `docs/IW_AI_Core_DB_Setup.md`.

## File Manifest

All files for this work item live under `ai-dev/active/I-00122/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00122_Issue_Design.md` | Design | This document |
| `I-00122_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00122_S01_Backend_prompt.md` | Prompt | S01 guard + safe prod-start path + docs |
| `prompts/I-00122_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00122_S03_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00122_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00122_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00122_S13_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/active/I-00122/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it. Because the bug
lives in an operations shell script, the test drives `ai-core.sh` directly with a
controlled environment and a **stub `docker` executable** placed first on `PATH`.
The stub records every invocation to a log file and never touches real Docker.
The test stubs `db_ready` to report "down" (e.g. by pointing `IW_CORE_DB_PORT` at
a closed port) and asserts the script's behaviour.

This is a pure-shell-behaviour test with **no FastAPI, template, or database
dependency**, so it belongs under `tests/unit/` (per the test-file-location rule:
only route/template-driving tests need `tests/dashboard/`, and only
testcontainer-backed tests need `tests/integration/`).

```python
def test_i00122_db_start_refuses_bootstrap_when_instance_pinned(tmp_path, monkeypatch):
    """FAILS before the fix (bootstrap compose is invoked), PASSES after (refused)."""
    # Arrange: stub `docker` on PATH that logs its args; pin a prod instance id;
    # force db_ready() to see a down DB (closed port).
    # Act: run `bash ai-core.sh db start`, capturing exit code + the docker call log.
    # Assert (semantic, not shape):
    #   - exit code != 0
    #   - the docker call log contains NO "compose ... up" / "up -d db" invocation
    #   - stderr mentions the production DB is down / refuses to bootstrap
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given IW_CORE_EXPECTED_INSTANCE_ID is set (a production identity is pinned)
  And nothing is listening on the configured DB port (the real DB is down)
When the operator runs `./ai-core.sh db start`
Then the script exits non-zero
  And it does NOT run `docker compose ... up -d db`
  And it prints an actionable message to bring up the real bind-mount cluster
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test (instance pinned + DB down → no bootstrap, non-zero exit) passes
  And the regression tests pass (no instance pinned → bootstrap still runs; DB already up → no-op)
```

## Regression Prevention

- The guard turns a silent, automatic failure into a **loud, blocking** one: an
  empty DB can never again be bound to the production port while an identity is
  pinned. The identity check is moved *ahead* of the destructive action instead of
  *after* it.
- The new `tests/unit/` test pins both the positive (refuse) and negative
  (dev-machine bootstrap still works) paths, so a future refactor of `cmd_db start`
  cannot silently reintroduce the displacement.
- `IW_CORE_DB_DATA_DIR` + the documented `--restart=always` prod-start path reduce
  the *trigger frequency* (the prod container auto-restarts instead of staying
  down) and give operators a scripted, non-hardcoded recovery command.
- Documentation in `docs/IW_AI_Core_DB_Setup.md` records the guard behaviour so the
  next operator understands why `db start` refuses.

## Dependencies

- **Depends on**: None
- **Blocks**: None (a follow-up Feature for off-volume backup tooling —
  pg_basebackup + WAL archiving — is recommended but tracked separately).

## Impacted Paths

- `ai-core.sh`
- `.env.example`
- `docs/IW_AI_Core_DB_Setup.md`
- `tests/unit/test_db_start_guard.py`

## TDD Approach

- Reproducing test: `tests/unit/test_db_start_guard.py::test_i00122_db_start_refuses_bootstrap_when_instance_pinned`
  — fails before the fix (stub `docker` log shows a `compose ... up -d db` call),
  passes after (refused, non-zero exit, no compose call).
- Unit tests:
  - Instance pinned + DB down → refuse, non-zero exit, no `docker compose up`.
  - No instance pinned + DB down → bootstrap compose **is** invoked (dev path
    preserved).
  - DB already up (`db_ready` true) → early return, no `docker` invocation at all.
- Integration tests: none required (no DB schema or service interaction); the QV
  integration gate runs the existing suite to confirm no regression.

## Notes

- Severity **High**: production data-availability outage that recurred twice and
  silently ran the whole platform on an empty database for hours. Not Critical
  because both occurrences were recovered with **zero data loss** (WAL crash
  recovery from the intact bind-mount cluster) and the fault is a latent footgun
  rather than active data corruption.
- **Out of scope (deliberate)**: off-volume backup tooling (pg_basebackup + WAL
  archiving + retention). The only existing backup is from 2026-04-22 and lives
  *inside* the same bind mount it is meant to protect — see
  `/opt/postgres/data/backup_260422/README.txt`. That is net-new functionality and
  is recommended as a separate Feature.
- The bug was discovered on 2026-05-30 when the dashboard showed a single project
  (`iw-ai-core`) and zero batches; root-caused to the displaced empty bootstrap
  container and recovered by removing it and restarting the real cluster on the
  bind mount.
