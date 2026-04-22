# CR-00015_S02_CodeReview_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md`
- `ai-dev/active/CR-00015/reports/CR-00015_S01_Backend_report.md`
- All files listed in the S01 report's `files_changed`
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S02_CodeReview_report.md`

## Review Checklist

### 1. `docker-compose.bootstrap.yml` correctness

- File exists at project root.
- `name: iw-ai-core` top-level key present (this is the belt-and-braces pin for volume naming).
- `db` service content matches the former root file (image, container_name, ports, env, volumes, healthcheck).
- Credentials still come from env-var substitution (`${IW_CORE_DB_*}`), NOT hardcoded.
- Header comment explains WHY and includes a pointer to `docs/IW_AI_Core_DB_Setup.md`.
- `docker compose -f docker-compose.bootstrap.yml config` parses cleanly — reviewer runs this locally to confirm.

### 2. Root `docker-compose.yml` (stub)

- Contains a comment block explaining the intentional emptiness with a pointer to `docs/IW_AI_Core_DB_Setup.md` and the bootstrap file.
- `services: {}` present so Compose parses without error.
- `docker compose config` (from root) succeeds with no services listed.
- If the S01 agent chose deletion over stub, the report justifies that choice; reviewer validates the justification.

### 3. `ai-core.sh` changes

- `cmd_db start` uses `-f docker-compose.bootstrap.yml`.
- `cmd_db stop` uses `-f docker-compose.bootstrap.yml`.
- `cmd_db logs` uses `-f docker-compose.bootstrap.yml`.
- `COMPOSE_PROJECT_NAME=iw-ai-core` still exported inline — unchanged from the prior hardening pass.
- The `db_ready` short-circuit in `cmd_db start` is preserved (no regression on the no-op-when-already-up guard).
- No unrelated behavior changes in `cmd_*` functions.

### 4. `Makefile` changes

- All `docker compose ... db` invocations now use `-f docker-compose.bootstrap.yml`.
- If a `COMPOSE_BOOTSTRAP := docker compose -f docker-compose.bootstrap.yml` variable was introduced, it's at the top of the file and consistently used.
- `.PHONY:` declarations preserved.
- No unrelated target changes.

### 5. No docs touched

- Docs are S03's responsibility. S01 MUST NOT have edited any `*.md` file. If it did, that's a scope violation — flag HIGH.
- But the report's list of "stale doc references found" is valuable context for S03; verify it's present and reasonably complete (grep for `docker compose up.*db` / `docker-compose up.*db` and compare).

### 6. Safety

- No reference to `/opt/postgres/data` added or removed in compose files (bind mount is NOT part of the bootstrap path).
- No destructive commands introduced.
- Live `postgres` container was NOT stopped during S01's smoke testing (verify in the report — the smoke should describe using an alternate port for the "fresh machine" simulation).

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place.

## Subagent Result Contract

Same pattern as prior S02 reviews.

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S02
# review + fix ...
uv run iw step-done CR-00015 --step S02 --report ai-dev/active/CR-00015/reports/CR-00015_S02_CodeReview_report.md
```
