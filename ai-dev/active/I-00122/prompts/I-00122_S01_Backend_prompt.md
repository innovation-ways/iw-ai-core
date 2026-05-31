# I-00122_S01_Backend_prompt

**Work Item**: I-00122 — `ai-core.sh db start` silently bootstraps an empty DB over a down production cluster
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any Docker command that changes container/volume/network
state (`docker compose up/down`, `docker rm`, `docker volume rm`, etc.). The
orchestration DB, daemon, and dashboard are outside your scope — touching them
caused the very outage this item fixes. Read-only `docker ps`/`inspect`/`logs`
is allowed. Do NOT run `./ai-core.sh db start`/`stop`/`restart` against the live
DB to "try it out" — your verification runs through the targeted test harness in
S03, not the live script. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no** migrations. Do not generate or apply any.

## Input Files

- **Runtime step state**: prefer `uv run iw item-status I-00122 --json`.
- `ai-dev/active/I-00122/I-00122_Issue_Design.md` — design document (read first).
- `CLAUDE.md` — project conventions, especially the "Live DB Setup" and
  "Critical Rules" sections.
- `docs/IW_AI_Core_DB_Setup.md` — current DB setup doc (production vs bootstrap).
- `orch/db/identity.py` — existing identity machinery (`IW_CORE_EXPECTED_INSTANCE_ID`).

## Output Files

- `ai-dev/active/I-00122/reports/I-00122_S01_Backend_report.md` — step report.

## Context

You are implementing the core fix for **I-00122**. When the production
orchestration DB (a raw bind-mount container on port 5433) is down,
`ai-core.sh`'s `cmd_db start` currently runs the bootstrap compose stack, which
creates an **empty** database that seizes port 5433 — the daemon/dashboard then
run on an empty DB. Read the design doc's **Root Cause Analysis** and **Code
Changes** sections before writing anything.

Relevant existing code:
- `ai-core.sh:124` — `db_ready()` (bare connectivity probe).
- `ai-core.sh:210-219` — `cmd_db start` (runs bootstrap compose when DB is down).
- `ai-core.sh:524-543` — `cmd_start` (identity check fires too late, line 528).
- `docker-compose.bootstrap.yml` — the bootstrap `db` service (`iw-ai-core-db`).

## Requirements

### 1. Identity-aware guard in `cmd_db start`

In `ai-core.sh`, inside the `start)` branch of `cmd_db` (around lines 210-219),
**before** the `docker compose -f docker-compose.bootstrap.yml up -d db`
invocation:

- Keep the existing early return when `db_ready` is true (no behaviour change
  when the DB is already up).
- When the DB is **not** ready, determine whether a **production identity is
  pinned** — i.e. the `IW_CORE_EXPECTED_INSTANCE_ID` environment variable is set
  and non-empty (it is loaded from `.env`). Read it directly in the shell; do not
  call into Python for this cheap check.
- If a production identity **is** pinned: **refuse**. Print a loud, actionable
  error to stderr (use the existing `print_err` helper) explaining that the DB on
  `${DB_HOST}:${DB_PORT}` is a **production** database that is currently **down**,
  that `db start` will **not** create a bootstrap database over it, and how to
  bring the real cluster back (point at the safe prod-start path from requirement
  2 and at `docs/IW_AI_Core_DB_Setup.md`). Then `return 1` **without** running the
  bootstrap compose.
- If **no** production identity is pinned (genuine fresh dev machine): preserve
  the current behaviour exactly — run the bootstrap compose and wait for the DB.

### 2. Config-driven, auto-restarting safe prod-start path

Operators need a scripted, non-hardcoded way to bring the real cluster back up.
Add this to `ai-core.sh` (extend the `cmd_db` dispatch with a new subcommand,
e.g. `start-prod`, and document it in the `db` usage string):

- Read the host data directory from a new env var **`IW_CORE_DB_DATA_DIR`**
  (loaded from `.env`). **Do NOT hardcode any `/opt/...` path** in the script.
- If `IW_CORE_DB_DATA_DIR` is unset/empty, print an actionable error telling the
  operator to set it in `.env` and `return 1`.
- Otherwise start the real cluster as a raw container (NOT compose):
  `docker run -d --name <stable-name> --restart=always -p "${IW_CORE_DB_PORT}:5432" -v "${IW_CORE_DB_DATA_DIR}:/var/lib/postgresql/data" postgres:15-alpine`.
  Pin the image to `postgres:15-alpine` (matches the cluster `PG_VERSION`). Pick a
  stable container name distinct from the bootstrap `iw-ai-core-db` (e.g.
  `iw-orch-pg`); if a container with that name already exists, `docker start` it
  instead of `docker run`. Then wait for readiness using the existing
  `wait_for_db` helper.
- The refusal message from requirement 1 should reference this subcommand by name.

> The guard (requirement 1) is the regression fix and is what the S03 test
> targets. The `start-prod` path (requirement 2) is the operator recovery aid.
> Keep both behind the same `IW_CORE_DB_DATA_DIR`/identity configuration so a dev
> machine with neither set is unaffected.

### 3. Config example + documentation

- Add `IW_CORE_DB_DATA_DIR` to `.env.example` with a short comment (host path to
  the production bind-mount data directory; leave empty on dev machines). If a
  `.env.example` does not exist, add the variable to whichever env-template file
  the repo uses and note it in your report.
- Update `docs/IW_AI_Core_DB_Setup.md`: document (a) that `db start` now refuses
  to bootstrap when a production identity is pinned and the DB is down, and (b)
  the `db start-prod` recovery procedure and the `IW_CORE_DB_DATA_DIR` variable.
  Keep it consistent with the existing 2026-04-22 incident narrative in that doc.

Keep the change minimal and shell-idiomatic — match the existing `print_*`
helpers, quoting, and `case` style in `ai-core.sh`. Do not refactor unrelated
parts of the script.

## Project Conventions

Read `CLAUDE.md` for the Live DB Setup rules (never run `docker compose up`
against the orch DB; always go through `./ai-core.sh db start`) and the env-var
conventions (`IW_CORE_*`, never hardcode ports/paths/credentials). Match existing
code in `ai-core.sh`.

## TDD Requirement

The behavioural test for this fix is authored in **S03** (`tests-impl`) and
targets the guard. For your step:

1. Implement the guard and the `start-prod` path as specified.
2. Do a quick **local sanity check with a stubbed `docker`** (a throwaway script
   on `PATH` that just echoes its args) and a closed `IW_CORE_DB_PORT`, to confirm
   the guard returns non-zero and prints the refusal **without** emitting a
   `compose ... up` call. Do NOT run it against the real Docker daemon or the live
   DB. Capture the observed behaviour in your report.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix:
1. `make format` — auto-fix formatting drift (applies to any Python you touched).
2. `make typecheck` — zero new errors in files you changed.
3. `make lint` — zero errors. Note: `make lint` includes `lint-templates`/`lint-js`;
   if it does not lint shell, run `bash -n ai-core.sh` (syntax check) and, if
   available, `shellcheck ai-core.sh` on your changes, and record the result.

## Test Verification (NON-NEGOTIABLE)

Do **NOT** run the full test suite — that is the QV gates' job. Run only the
targeted sanity check described above. Do not report `tests_passed: true` unless
your sanity check behaves as specified.

> **Verification Placement Rule (canonical — `skills/iw-workflow/SKILL.md`)**: a
> full suite or aggregate gate passing is never a completion gate for this step.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00122",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["ai-core.sh", ".env.example", "docs/IW_AI_Core_DB_Setup.md"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "stub-docker sanity check: refused with exit!=0, no compose-up call",
  "tdd_red_evidence": "n/a — behavioural test authored in S03; this step is shell/config/doc changes",
  "blockers": [],
  "notes": "Record the chosen prod container name and whether .env.example existed."
}
```
