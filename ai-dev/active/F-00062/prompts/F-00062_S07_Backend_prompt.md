# F-00062_S07_Backend_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step**: S07
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You write iw-ai-core's reference compose template, env config, and seed script — these are config FILES, not docker invocations. You do NOT run `docker compose up` against your template. The daemon (S03 module) executes them at runtime. Read-only `docker ps|inspect|logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You do NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. The seed script (`worktree-seed.sh`) you write here is for the per-worktree DB and runs `pg_dump`/`psql` against the global orch DB as the SOURCE only — read-only on 5433. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc (ACs 1, 2, 9; iw-ai-core's reference implementation requirements)
- S01-S06 reports
- `orch/daemon/worktree_compose.py` (S03 — for the contract your config must satisfy)
- `orch/daemon/state_machine.py` or wherever step prompts are loaded for agent launch (the placeholder substitution insertion site)
- `ai-dev/templates/*.md` — existing prompt templates that may hardcode `:9900` or `localhost:5433`
- Existing iw-ai-core `.env.example` (if present) for the IW_CORE_* env var schema
- `executor/worktree_setup.sh` lines ~145-163 (skill sync — this is where IW_CORE_PER_WORKTREE_DB env flag MIGHT be threaded; verify the right insertion point)

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S07_Backend_report.md`

## Context

You are writing iw-ai-core's reference `ai-dev/iw-config/` directory — the project-side contract that the S03 daemon module reads. You are also adding the orchestrator-side placeholder substitution that injects `${WORKTREE_*}` values into step prompts at agent-launch time, AND auditing existing prompts for hardcoded ports/paths.

This step turns the abstract "engine + contract" of S03/S05 into a concrete working iw-ai-core implementation.

## Requirements

### 1. `ai-dev/iw-config/worktree-compose.template.yml`

Jinja2 template. Required variables: `{{ batch_item_id }}`, `{{ worktree_path }}`, `{{ project_name }}`. Two services:

```yaml
name: iwcore-{{ batch_item_id }}

services:
  db:
    image: postgres:16-alpine
    tmpfs:
      - /var/lib/postgresql/data
    environment:
      POSTGRES_USER: iw_orch
      POSTGRES_PASSWORD: iw_orch
      POSTGRES_DB: iw_orch
    ports:
      - "5432"        # docker-dynamic host port
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U iw_orch"]
      interval: 2s
      timeout: 3s
      retries: 30
    labels:
      iwcore.role: worktree-db
      iwcore.batch_item: "{{ batch_item_id }}"
      iwcore.project: "{{ project_name }}"

  app:
    image: python:3.12-slim
    working_dir: /workspace
    volumes:
      - "{{ worktree_path }}:/workspace"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command:
      - bash
      - -lc
      - |
        pip install -q uv
        uv sync --frozen
        uv run uvicorn dashboard.app:create_app --factory --host 0.0.0.0 --port 9900 --reload
    environment:
      IW_CORE_DB_HOST: db
      IW_CORE_DB_PORT: 5432
      IW_CORE_DB_NAME: iw_orch
      IW_CORE_DB_USER: iw_orch
      IW_CORE_DB_PASSWORD: iw_orch
    ports:
      - "9900"
    depends_on:
      db:
        condition: service_healthy
    labels:
      iwcore.role: worktree-app
      iwcore.batch_item: "{{ batch_item_id }}"
      iwcore.project: "{{ project_name }}"
```

**Confirmed**: iw-ai-core's FastAPI entrypoint is the factory `dashboard.app:create_app` (see `ai-core.sh:421`/`500` — `uvicorn dashboard.app:create_app`); `dashboard/main.py` does NOT exist. Use `--factory`. Re-verify against the live tree before writing the template.

### 2. `ai-dev/iw-config/worktree-env.toml`

```toml
# Maps "<service>:<container_port>" → env var name. The daemon discovers
# the host port assigned to that container port and writes the env var
# in the worktree's .env.
[port_to_env]
"db:5432" = "IW_CORE_DB_PORT"
"app:9900" = "IW_CORE_DASHBOARD_PORT"

# Literal env-var overrides (applied after passthrough, before port rewrite)
[env_overrides]
IW_CORE_DB_HOST = "localhost"
IW_CORE_DB_NAME = "iw_orch"
IW_CORE_DB_USER = "iw_orch"
IW_CORE_DB_PASSWORD = "iw_orch"

# Env vars copied verbatim from the project's main .env.
# Globs supported (e.g., "IW_CORE_ORCH_DB_*").
[env_passthrough]
keep = [
  "IW_CORE_ORCH_DB_*",
  "ANTHROPIC_API_KEY",
  "OPENAI_API_KEY",
  "GITHUB_TOKEN",
  "IW_CORE_DASHBOARD_HOST",
  "IW_CORE_POLL_INTERVAL",
  "IW_CORE_STALL_THRESHOLD",
  "IW_CORE_EXPECTED_INSTANCE_ID",
]
```

### 3. `ai-dev/iw-config/worktree-seed.sh`

```bash
#!/usr/bin/env bash
# F-00062 — iw-ai-core per-worktree DB seed
# Runs after `docker compose up` succeeds for an iw-ai-core worktree.
# pg_dump from the global orch DB on 5433 -> psql restore into the
# per-worktree DB.
#
# The daemon loads the worktree's .env into this script's environment.
# Required env vars:
#   IW_CORE_ORCH_DB_HOST/PORT/NAME/USER/PASSWORD  — global source
#   IW_CORE_DB_PORT                                — per-worktree dest port
#   (other IW_CORE_DB_* are already set)

set -euo pipefail

SRC_URL="postgresql://${IW_CORE_ORCH_DB_USER}:${IW_CORE_ORCH_DB_PASSWORD}@${IW_CORE_ORCH_DB_HOST}:${IW_CORE_ORCH_DB_PORT}/${IW_CORE_ORCH_DB_NAME}"
DST_URL="postgresql://${IW_CORE_DB_USER}:${IW_CORE_DB_PASSWORD}@localhost:${IW_CORE_DB_PORT}/${IW_CORE_DB_NAME}"

echo "[seed] dumping from global orch DB and restoring into per-worktree DB" >&2

# Stream dump → restore. --no-owner / --no-acl avoid role-mismatch errors.
pg_dump --no-owner --no-acl --clean --if-exists "$SRC_URL" \
  | psql --quiet --set ON_ERROR_STOP=1 "$DST_URL"

echo "[seed] done" >&2
```

`chmod +x ai-dev/iw-config/worktree-seed.sh`. Verify the script is syntactically valid (`bash -n worktree-seed.sh`). Note: `pg_dump` and `psql` must be available on the daemon host — document in S13 docs as a daemon-host prerequisite.

### 4. Step prompt placeholder substitution

Locate where the daemon loads a step's prompt file before launching the agent (likely in `orch/daemon/state_machine.py`, `orch/daemon/step_executor` wrapper, or `executor/step_executor.sh` env preparation — read the codebase to find the exact insertion site). Add a substitution pass that replaces:

- `${WORKTREE_APP_PORT}` → `str(batch_item.worktree_app_port)`  (raises if NULL when placeholder is present in a non-legacy item)
- `${WORKTREE_DB_PORT}` → `str(batch_item.worktree_db_port)`
- `${WORKTREE_PATH}` → `str(batch_item.worktree_path)`
- `${BATCH_ITEM_ID}` → `batch_item.id`
- `${PROJECT_NAME}` → `batch_item.project_id`

For legacy-mode items (where `worktree_*_port` are NULL), the substitution is a no-op AND the prompt is expected to use legacy-safe defaults; if a prompt contains `${WORKTREE_APP_PORT}` for a legacy item, raise a clear error so the operator can fix the prompt or add iw-config.

Implementation: Python `string.Template` (custom delimiter `${...}`) OR a simple regex pass — your call, document in report.

Add unit tests in `tests/unit/daemon/test_prompt_substitution.py`:
- `test_substitutes_all_known_placeholders`
- `test_unknown_placeholder_left_alone` (`${UNKNOWN_VAR}` is preserved)
- `test_legacy_mode_with_no_placeholders_unchanged`
- `test_legacy_mode_with_placeholders_raises_clear_error`

### 5. Audit existing prompts for hardcoded ports/paths

Use `git grep -n "9900\|localhost:5433\|127.0.0.1:5433\|localhost:9900"` across:
- `ai-dev/templates/*.md`
- Any committed prompt files in `ai-dev/active/*/prompts/` belonging to iw-ai-core itself (NOT prompts for other projects — leave those alone)
- `skills/**/*.md` if they contain hardcoded ports

Replace with the appropriate `${WORKTREE_*}` placeholder. Document the count in your report. Estimate from the design: 5–10 occurrences.

**Do NOT modify** `docs/*.md` content beyond what's required for the audit (those are documentation and intentionally describe the production ports).

### 6. Daemon: set `IW_CORE_PER_WORKTREE_DB=true` at agent launch

In the agent-launch path (likely `executor/step_executor.sh` env preparation, or wherever the agent subprocess is spawned in `orch/daemon/`), add the env flag setting:

```python
if batch_item.worktree_compose_path is not None:
    agent_env["IW_CORE_PER_WORKTREE_DB"] = "true"
```

This flag is what S03's `safe_migrate.py` relax checks. Without it set, the relax is inert (Invariant #3).

### 7. `.gitignore` audit for iw-ai-core

Ensure iw-ai-core's `.gitignore` includes both `.env` and `.iw/`. If either is missing, add it. (This is iw-ai-core's own gitignore — not other projects'. Other projects fix their own as part of the follow-up Incidents.)

## Project Conventions

- Read `CLAUDE.md` and `orch/CLAUDE.md`
- Compose files: prefer named services, explicit healthchecks, dynamic ports (no host-side numbers)
- Bash scripts: `set -euo pipefail`, no positional argument parsing magic, redirect informational output to stderr
- Python: stdlib `string.Template` if you need template substitution

## TDD Requirement

For the placeholder substitution work (Requirement 4), RED → GREEN → REFACTOR. The compose template, env.toml, and seed.sh are config files — verify them by:
- `bash -n worktree-seed.sh` (syntax check)
- `python -c "import tomllib; tomllib.loads(open('ai-dev/iw-config/worktree-env.toml').read())"` (TOML validity)
- Render the Jinja2 template manually with sample vars and verify the YAML is valid (`python -c "import yaml; yaml.safe_load(open('rendered.yml'))"`)

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all pass
2. `make lint` — including any new shell scripts (`shellcheck` if available locally)
3. Manually render the compose template with batch_item_id="TEST-001", worktree_path="/tmp/wt", project_name="iw-ai-core" and verify the YAML is well-formed

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "backend-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/iw-config/worktree-compose.template.yml",
    "ai-dev/iw-config/worktree-env.toml",
    "ai-dev/iw-config/worktree-seed.sh",
    "<orchestrator file with placeholder substitution>",
    "tests/unit/daemon/test_prompt_substitution.py",
    "<list of audited & rewritten prompt files>",
    "<agent-launch file that sets IW_CORE_PER_WORKTREE_DB>",
    ".gitignore (if updated)"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Number of prompt occurrences rewritten; placeholder substitution insertion site"
}
```
