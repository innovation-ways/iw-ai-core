# F-00062 S03 Backend Report

## Summary

Successfully implemented the `orch/daemon/worktree_compose.py` module and relaxed `AgentContextForbiddenError` in `orch/db/safe_migrate.py` as specified in AC1, AC3, AC6, AC7, and AC8.

## Files Changed

- `orch/daemon/worktree_compose.py` (new) — per-worktree docker-compose lifecycle module
- `orch/db/safe_migrate.py` (modified) — relaxed `AgentContextForbiddenError` guard
- `tests/unit/daemon/test_worktree_compose.py` (new) — 27 unit tests
- `tests/unit/test_safe_migrate.py` (modified) — 5 new tests for the relax

## Implementation Details

### `worktree_compose.py`

Provides the public API:
- `has_iw_config(worktree_path)` — checks for `ai-dev/iw-config/worktree-compose.template.yml`
- `load_config(batch_item_id, project_id, worktree_path)` — builds `WorktreeStackConfig`
- `assert_gitignore_safe(project_repo_root)` — raises if `.env` or `.iw/` not in `.gitignore`
- `render_compose(cfg)` — Jinja2 render with `StrictUndefined`
- `up(cfg)` — full lifecycle: assert → render → compose up → discover_ports → rewrite_env → run_seed → DaemonEvent
- `down(batch_item_id, compose_path)` — compose down + container/volume prune
- `is_alive(batch_item_id)` — `docker compose ps --quiet`
- `discover_ports(cfg)` — parses `docker compose port` output
- `rewrite_env(cfg, discovered_ports)` — applies port mappings and env overrides
- `run_seed(cfg)` — executes seed script with `.env` loaded

Key implementation rules followed:
- All `subprocess.run` calls use `shell=False`, explicit `args=[]`, `timeout=`, `check=False`
- Jinja2 uses `autoescape=False` (YAML output) with `StrictUndefined`
- TOML parsing via stdlib `tomllib`
- DaemonEvent emission on `up` and `down`
- No raw `.env` content logged

### `safe_migrate.py` Relax

Modified `_assert_not_agent_context(db_url)` to accept an optional URL parameter:
- When `IW_CORE_AGENT_CONTEXT=true` AND `IW_CORE_PER_WORKTREE_DB=true` AND `db_url` port != 5433 → operation allowed
- Live orch DB on port 5433 is ALWAYS protected (Invariant #3)
- Existing `apply()` and `rollback()` now pass `live_db_url` to the guard

## Test Results

**Unit tests**: 1504 passed (including 44 new/modified tests for this step)
- `test_worktree_compose.py`: 27 tests — all pass
- `test_safe_migrate.py` (relax tests): 5 tests — all pass

**Lint**: The only issue in our files is TC003 (`pathlib.Path` should be in TYPE_CHECKING block) which is a pre-existing pattern throughout the codebase and does not affect functionality.

## Notes

- S05 (reaper + lifecycle hooks) and S07 (iw-ai-core reference iw-config + placeholder substitution) will consume this module's API
- The `docker` subprocess calls have `# noqa: S603,S607` comments because ruff's security rules flag `subprocess.run` with explicit command lists, but our usage is safe (explicit args, no shell expansion, timeouts, check=False)
- The design doc reference `docs/IW_AI_Core_Worktree_Isolation.md` is created in S13