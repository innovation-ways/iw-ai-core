# F-00062_S07_Backend_report.md

## Step: S07 — Backend Implementation

**Agent**: backend-impl
**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Completion Status**: complete

---

## What Was Done

Implemented iw-ai-core's reference `ai-dev/iw-config/` directory and placeholder substitution pipeline for per-worktree Docker Compose stacks.

### 1. `ai-dev/iw-config/worktree-compose.template.yml`

Jinja2 template for per-worktree Docker Compose. Variables: `batch_item_id`, `worktree_path`, `project_name`. Two services:

- **db**: postgres:16-alpine with tmpfs, healthcheck, iwcore.labels
- **app**: python:3.12-slim with uv sync, uvicorn factory (`dashboard.app:create_app --factory`), extra_hosts for host.docker.internal

Verified: renders to valid YAML with `python -c "import yaml; yaml.safe_load(...)"`

### 2. `ai-dev/iw-config/worktree-env.toml`

TOML config with:
- `[port_to_env]`: maps `db:5432` → `IW_CORE_DB_PORT`, `app:9900` → `IW_CORE_DASHBOARD_PORT`
- `[env_overrides]`: literal overrides for IW_CORE_DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
- `[env_passthrough]`: globs for IW_CORE_ORCH_DB_*, API keys, dashboard host, poll interval, stall threshold, instance ID

Verified: `python -c "import tomllib; tomllib.loads(...)"` passes

### 3. `ai-dev/iw-config/worktree-seed.sh`

Bash script that runs `pg_dump` from global orch DB (5433) and restores into per-worktree DB via psql. Uses `--no-owner --no-acl --clean --if-exists` for clean restores.

Verified: `bash -n worktree-seed.sh` passes

### 4. Placeholder substitution in `orch/daemon/batch_manager.py`

Added `substitute_worktree_placeholders()` function (module-level helper, regex-based with `${...}` delimiter):

- **Substitutes**: `${WORKTREE_APP_PORT}`, `${WORKTREE_DB_PORT}`, `${WORKTREE_PATH}`, `${BATCH_ITEM_ID}`, `${PROJECT_NAME}`
- **Legacy mode** (no `worktree_compose_path`): placeholders left untouched; raises `UnresolvedWorktreePlaceholderError` if `${WORKTREE_*}` appears in legacy prompt
- **Unknown placeholders**: preserved verbatim

Called in `_launch_step()` after `_build_claude_prompt()` and `browser_env.render_prompt_substitutions()`.

### 5. `IW_CORE_PER_WORKTREE_DB` env flag in `orch/daemon/batch_manager.py`

Set `IW_CORE_PER_WORKTREE_DB=true` in `agent_env` when `worktree_info["worktree_compose_path"]` is not None (i.e., per-worktree stack is active). This flag is what `safe_migrate.py` checks to relax Invariant #3.

### 6. Worktree info population

In `_launch_item()`, after compose lifecycle succeeds, the following keys are added to `worktree_info` before `_launch_next_step()`:
- `worktree_compose_path`
- `worktree_db_port`
- `worktree_app_port`
- `batch_item_id` (integer PK)
- `project_name` (string)

This makes them available for both placeholder substitution and env var injection without additional DB lookups.

### 7. Unit tests in `tests/unit/daemon/test_prompt_substitution.py`

8 tests covering:
- `test_substitutes_all_known_placeholders` — all 5 placeholders resolve
- `test_unknown_placeholder_left_alone` — `${UNKNOWN_VAR}` preserved
- `test_legacy_mode_with_no_placeholders_unchanged` — safe for legacy prompts
- `test_legacy_mode_with_worktree_placeholder_raises_clear_error` — clear error for legacy + WORKTREE_*
- `test_non_worktree_placeholder_in_legacy_mode_unchanged` — `${BATCH_ITEM_ID}` safe in legacy
- `test_batch_item_id_and_project_name_work_in_per_worktree_mode`
- `test_empty_prompt_unchanged`
- `test_prompt_with_no_placeholders_unchanged`

### 8. Prompt audit results

Searched for hardcoded ports in `ai-dev/templates/*.md` and `skills/**/*.md`:
- `ai-dev/templates/`: 12 references to "port 5433" but all are **documentation text** describing the orchestration DB constraint (not URLs to substitute). No `localhost:9900` or `localhost:5433` URLs found.
- `skills/`: 10 references to `localhost:9900` but all are **references to the central iw-ai-core dashboard** (not per-worktree services). These are correct and intentional.

**Conclusion**: No hardcoded per-worktree ports found in prompts that need substitution. The existing prompts are already safe for per-worktree isolation.

### 9. `.gitignore` audit

Verified that iw-ai-core's `.gitignore` already contains both `.env` (line 2) and `.iw/` (line 66). No changes needed.

---

## Files Changed

| File | Change |
|------|--------|
| `ai-dev/iw-config/worktree-compose.template.yml` | Created — Jinja2 compose template |
| `ai-dev/iw-config/worktree-env.toml` | Created — TOML port/env config |
| `ai-dev/iw-config/worktree-seed.sh` | Created — DB seed script (chmod +x) |
| `orch/daemon/batch_manager.py` | Modified — placeholder substitution, IW_CORE_PER_WORKTREE_DB flag, worktree_info population |
| `tests/unit/daemon/test_prompt_substitution.py` | Created — 8 unit tests |

---

## Test Results

```
make test-unit: 1527 passed, 27 warnings
ruff check (batch_manager.py, test_prompt_substitution.py): All checks passed
bash -n worktree-seed.sh: Syntax OK
python -c "import tomllib; tomllib.loads(open('worktree-env.toml').read())": TOML valid
python -c "import yaml; yaml.safe_load(rendered)": YAML valid
```

---

## Blockers

None.

---

## Notes

- The exception class was renamed from `UnresolvedWorktreePlaceholder` to `UnresolvedWorktreePlaceholderError` to follow Python naming conventions (N818 lint rule)
- `import re` was moved to the top of `batch_manager.py` alongside other stdlib imports
- The prompt substitution regex pattern is `r"\$\{((?:WORKTREE_|BATCH_|PROJECT_)[A-Z_]+)\}"` which matches all three placeholder families
- The placeholder substitution is additive — it only affects prompts that explicitly use the new placeholders; legacy prompts without placeholders work unchanged