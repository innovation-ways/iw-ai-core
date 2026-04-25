# F-00062_S08_CodeReview_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Being Reviewed**: S07 (backend-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits

State-changing docker commands MUST live only in `orch/daemon/worktree_compose.py`. The reference compose template, env.toml, and seed.sh from S07 are config files — your review verifies their content, not by running docker. Read-only `docker ps|inspect|logs` allowed for sanity checks. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No alembic execution against live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc, S01-S07 reports
- `ai-dev/iw-config/worktree-compose.template.yml` (new)
- `ai-dev/iw-config/worktree-env.toml` (new)
- `ai-dev/iw-config/worktree-seed.sh` (new, executable)
- Modified orchestrator file with placeholder substitution
- `tests/unit/daemon/test_prompt_substitution.py`
- All prompt files audited & rewritten in S07
- `.gitignore` (if modified)

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S08_CodeReview_report.md`

## Context

You are reviewing iw-ai-core's reference `iw-config/` implementation and the orchestrator's placeholder substitution. The biggest risks: (a) the compose template has a bug that only surfaces at runtime in a real worktree, (b) the seed script has a credentials/SQL injection risk, (c) the placeholder substitution has corner cases that break legacy items.

## Review Checklist

### 1. Compose template (`worktree-compose.template.yml`)

- Renders cleanly when given concrete vars (manually run a Jinja2 render with `batch_item_id="TEST-001"`, `worktree_path="/tmp/wt"`, `project_name="iw-ai-core"` and validate the output is valid YAML)
- Both services have `iwcore.role` and `iwcore.batch_item` labels (Invariant #5)
- Uses `tmpfs` for the db data dir (Notes → "no data left after destroyed")
- App service has `extra_hosts: ["host.docker.internal:host-gateway"]` (Linux requirement for reaching the host)
- Both services declare `ports: ["..."]` with NO host port (dynamic allocation per design)
- Healthcheck on db; app `depends_on: db: condition: service_healthy`
- App's `command:` actually starts the dashboard correctly — verify the module path matches current iw-ai-core source (`dashboard.main:app` or whichever)
- Bind-mount path is `{{ worktree_path }}:/workspace` and the working_dir + uvicorn refer to `/workspace`

### 2. `worktree-env.toml`

- `[port_to_env]` keys use the `<service>:<container_port>` format
- Every service in the compose template that exposes ports has a corresponding entry (don't leave `app:9900` un-mapped)
- `[env_overrides]` covers every per-worktree-specific value (host, db name, credentials)
- `[env_passthrough].keep` includes `IW_CORE_ORCH_DB_*` glob (CRITICAL — without this the iw CLI can't reach 5433 from the worktree) and standard secret keys

### 3. `worktree-seed.sh`

- `set -euo pipefail` at the top
- `pg_dump` uses `--no-owner --no-acl` to avoid role-mismatch errors when restoring as a different user
- Uses `--clean --if-exists` so the script is idempotent (re-runs don't accumulate)
- Connection strings are properly quoted; no `eval`, no string-interpolation into SQL
- Echoes go to stderr, not stdout (per project bash conventions)
- Executable bit set (verify: `test -x ai-dev/iw-config/worktree-seed.sh`)
- `bash -n` syntax check passes
- Does NOT echo or otherwise leak `${IW_CORE_*_PASSWORD}` values

### 4. Placeholder substitution

- Insertion point is at the right layer (where prompts are loaded for agent launch — confirm by tracing one step's prompt-loading path)
- All five placeholders are handled: `${WORKTREE_APP_PORT}`, `${WORKTREE_DB_PORT}`, `${WORKTREE_PATH}`, `${BATCH_ITEM_ID}`, `${PROJECT_NAME}`
- Legacy-mode items (NULL ports) raise a clear error if a prompt contains `${WORKTREE_APP_PORT}` (rather than substituting "None")
- Unknown placeholders (`${UNKNOWN}`) are left alone, not erased
- All four required tests in `test_prompt_substitution.py` exist and pass

### 5. Prompt audit
- Searched `git grep` for hardcoded `9900` / `localhost:5433` across `ai-dev/templates/`, iw-ai-core's own prompts, and `skills/`
- Replaced occurrences (NOT in `docs/*.md` — those are documentation)
- The replacement uses the right placeholder per context (`:9900` → `:${WORKTREE_APP_PORT}`)

### 6. `IW_CORE_PER_WORKTREE_DB` flag

- Set to `"true"` in agent-launch env when `batch_item.worktree_compose_path is not None`
- NOT set otherwise (legacy mode → safe_migrate continues to forbid alembic operations from agents)
- Insertion point is the agent subprocess spawn (verify by reading the path)

### 7. iw-ai-core `.gitignore`

- Both `.env` and `.iw/` are listed (or already-listed broader patterns cover them)

### 8. Project conventions

- Read `CLAUDE.md`, `executor/CLAUDE.md`
- TOML schema is consistent with iw-ai-core's existing TOML usage (e.g., `projects.toml`)
- Bash scripts follow `executor/CLAUDE.md` style (set -euo pipefail, stderr for info)

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all pass (specifically the new `test_prompt_substitution.py`)
2. `make lint`
3. Render the compose template manually as described in Checklist #1 and validate the YAML
4. Run `bash -n ai-dev/iw-config/worktree-seed.sh` and verify zero output

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | Compose template doesn't render; seed.sh leaks secrets to logs; `IW_CORE_PER_WORKTREE_DB` not set when stack exists (safe_migrate relax inert) |
| HIGH | Missing label; missing service in port_to_env; placeholder substitution silently produces "None" for legacy items; .gitignore missing `.env` or `.iw/` |
| MEDIUM_FIXABLE | Missing test; weak passthrough list; healthcheck timing too tight |
| MEDIUM_SUGGESTION | Compose template style; clearer comments |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "F-00062",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
