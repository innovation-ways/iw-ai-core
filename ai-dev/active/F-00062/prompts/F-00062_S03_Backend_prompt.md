# F-00062_S03_Backend_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits — with one narrow exception

You MUST NOT execute docker / docker-compose state-changing commands FROM CODE OUTSIDE `orch/daemon/worktree_compose.py`. The single exception in this Feature is the new `worktree_compose.py` module itself, which is the daemon's lifecycle code for per-worktree compose stacks. Inside that module ONLY, the following are allowed and necessary:

- `docker compose --project-name iwcore-<id> -f <path> up -d` (in `up()`)
- `docker compose --project-name iwcore-<id> down -v --remove-orphans` (in `down()`)
- `docker compose --project-name iwcore-<id> -f <path> port <service> <container_port>` (in `discover_ports()`)
- `docker compose --project-name iwcore-<id> ps` (in `is_alive()`)
- `docker container prune --filter label=iwcore.batch_item=<id>` and `docker volume prune --filter label=iwcore.batch_item=<id>` (belt-and-suspenders teardown)

All invocations MUST use `subprocess.run(..., shell=False, check=False)` with explicit timeouts and the daemon's standard subprocess pattern. NEVER use shell=True. NEVER call docker outside this module.

Read-only `docker ps|inspect|logs` are still allowed elsewhere (debugging only).

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You do NOT run `alembic upgrade|downgrade|stamp` against the live orch DB on port 5433.

This step ALSO modifies `orch/db/safe_migrate.py` to **relax** the `AgentContextForbiddenError` for the **per-worktree DB only**. The relax is gated on the `IW_CORE_PER_WORKTREE_DB=true` env flag (set by the daemon at agent launch when an isolated stack exists). The live 5433 protection is unchanged. Read the design's "⛔ Migrations" header carefully — your relax MUST NOT weaken protection of the global orch DB.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- `ai-dev/active/F-00062/F-00062_Feature_Design.md` — design (read FIRST; ACs 1, 3, 6, 8 are your scope)
- `ai-dev/active/F-00062/reports/F-00062_S01_Database_report.md` and `F-00062_S02_CodeReview_report.md`
- `orch/daemon/browser_env.py` — **STUDY THIS FIRST**. Mirror its module shape, subprocess patterns, port-allocation idioms, and lifecycle function signatures.
- `orch/db/safe_migrate.py` — locate `AgentContextForbiddenError` and the guard that raises it
- `executor/worktree_setup.sh` lines 116-142 — the `.env` copy step you must coexist with (you do NOT modify this file)

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S03_Backend_report.md`

## Context

You are creating the new `orch/daemon/worktree_compose.py` module — the daemon's per-worktree compose stack lifecycle. This is the architectural twin of `browser_env.py`: stateless, daemon-driven, opt-in via per-project config (`<worktree>/ai-dev/iw-config/`). Your code is what runs `docker compose up`, discovers the dynamic host ports, rewrites the worktree's `.env`, runs the project's seed script, and provides teardown helpers.

You are ALSO modifying `safe_migrate.py` to relax `AgentContextForbiddenError` when the agent is targeting its per-worktree DB.

Steps S05 (reaper + lifecycle hooks) and S07 (iw-ai-core reference iw-config + placeholder substitution) consume your module's API; design APIs accordingly.

## Requirements

### 1. Create `orch/daemon/worktree_compose.py`

Module structure (mirror `browser_env.py`):

```python
"""worktree_compose — per-worktree docker-compose lifecycle.

Daemon-managed compose stacks for parallel work-item isolation. Projects
opt in by adding `ai-dev/iw-config/{worktree-compose.template.yml,
worktree-env.toml, worktree-seed.sh}` to their repo. Projects without
iw-config use legacy mode (no stack created).

See docs/IW_AI_Core_Worktree_Isolation.md for the contract.
"""
```

Public API (function signatures — fill in implementation):

```python
@dataclass(frozen=True)
class WorktreeStackConfig:
    batch_item_id: str
    project_id: str
    worktree_path: Path
    template_path: Path
    env_toml_path: Path
    seed_script_path: Path | None  # None if absent — proceed without seed
    rendered_compose_path: Path     # <worktree>/.iw/docker-compose-<id>.yml
    compose_project_name: str        # iwcore-<batch_item_id>

@dataclass(frozen=True)
class UpResult:
    success: bool
    rendered_compose_path: Path | None
    discovered_ports: dict[str, int]   # {"IW_CORE_DB_PORT": 34567, ...}
    error_message: str | None
    seed_stderr_tail: str | None

def has_iw_config(worktree_path: Path) -> bool: ...
    # Returns True if <worktree>/ai-dev/iw-config/worktree-compose.template.yml exists.
    # Used by callers to decide legacy vs isolated path BEFORE constructing config.

def load_config(batch_item_id: str, project_id: str, worktree_path: Path) -> WorktreeStackConfig: ...
    # Builds the dataclass. Raises FileNotFoundError if iw-config absent.

def assert_gitignore_safe(project_repo_root: Path) -> None: ...
    # Raises ValueError("refusing to launch: .env must be in .gitignore for project <id>")
    # if project's .gitignore doesn't include both '.env' and '.iw/'. AC8.

def render_compose(cfg: WorktreeStackConfig) -> Path: ...
    # Jinja2 render of cfg.template_path with vars batch_item_id, worktree_path,
    # project_name. Writes to cfg.rendered_compose_path (creates .iw/ if needed).
    # Returns the path written.

def up(cfg: WorktreeStackConfig) -> UpResult: ...
    # 1. assert_gitignore_safe (raises on failure)
    # 2. render_compose
    # 3. subprocess `docker compose -p <project> -f <path> up -d` with timeout
    # 4. discover_ports for every entry in worktree-env.toml [port_to_env]
    # 5. rewrite_env (writes worktree's .env in place)
    # 6. run_seed (if seed script exists; on non-zero exit -> down + return failure)
    # 7. emit DaemonEvent(event_type='worktree_compose', metadata={phase:'up', ...})
    # Returns UpResult.

def down(batch_item_id: str, compose_path: Path | None) -> bool: ...
    # `docker compose -p iwcore-<id> down -v --remove-orphans` (use -f if compose_path given).
    # Belt-and-suspenders prune by label.
    # Idempotent — succeeds (returns True) if nothing was running.
    # Emit DaemonEvent(phase='down').

def is_alive(batch_item_id: str) -> bool: ...
    # `docker compose -p iwcore-<id> ps --quiet` returns non-empty.

def discover_ports(cfg: WorktreeStackConfig) -> dict[str, int]: ...
    # For each [port_to_env] entry "<service>:<container_port>" -> "<env_var>",
    # call `docker compose -p <project> -f <compose> port <service> <container_port>`,
    # parse "0.0.0.0:NNNN" or "[::]:NNNN", return {env_var: NNNN}.

def rewrite_env(cfg: WorktreeStackConfig, discovered_ports: dict[str, int]) -> None: ...
    # 1. Read worktree's .env (already populated by executor/worktree_setup.sh)
    # 2. Apply [env_overrides] from worktree-env.toml (literal replacements)
    # 3. Set each discovered port env var
    # 4. Preserve [env_passthrough] keep-list verbatim
    # 5. Write back to <worktree>/.env

def run_seed(cfg: WorktreeStackConfig) -> tuple[bool, str | None]: ...
    # If seed script absent or non-executable, returns (True, None) — no-op.
    # Else subprocess.run with worktree's .env loaded into env, capture stderr.
    # On non-zero exit return (False, stderr_tail).
```

Key implementation rules:
- **All `subprocess.run` calls**: `shell=False`, explicit `args=[...]` list, `timeout=` keyword, `check=False` (you handle exit codes; never let CalledProcessError propagate); `env=` filtered to NOT propagate the daemon's secret-bearing env unless intentional.
- **Logging**: import `logging.getLogger(__name__)`. NEVER log raw `.env` content. NEVER log subprocess `env=` dict. When tailing seed stderr, ensure the project's seed script does not echo secrets (you can't enforce, but document in S13).
- **Jinja2**: use `jinja2.Environment(autoescape=False)` (YAML output, not HTML); `StrictUndefined` so missing template vars raise instead of silently emitting blanks.
- **TOML parsing**: stdlib `tomllib` (Python 3.11+).
- **Compose project name**: `f"iwcore-{batch_item_id.lower().replace('_','-')}"` to satisfy docker's lowercase rule.

Schema of `worktree-env.toml` (parse this in `load_config`/`rewrite_env`):
```toml
[port_to_env]
"db:5432" = "IW_CORE_DB_PORT"
"app:9900" = "IW_CORE_DASHBOARD_PORT"

[env_overrides]
IW_CORE_DB_HOST = "localhost"
IW_CORE_DB_NAME = "iw_orch"

[env_passthrough]
keep = ["IW_CORE_ORCH_DB_*", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
```

### 2. Relax `safe_migrate.AgentContextForbiddenError`

In `orch/db/safe_migrate.py`:

- Locate the existing guard that raises `AgentContextForbiddenError` when `IW_CORE_AGENT_CONTEXT=true`
- Add a second condition: if `os.getenv('IW_CORE_PER_WORKTREE_DB') == 'true'` AND the alembic target URL points at the per-worktree DB (host=localhost, port matches `IW_CORE_DB_PORT` env var), allow the operation
- Live orch DB on 5433 is detected via `IW_CORE_ORCH_DB_*` env vars OR by direct port comparison — your guard MUST refuse the operation if the URL points at port 5433 regardless of any other flag (Invariant #3)

Add focused unit tests by **extending the existing** `tests/unit/test_safe_migrate.py` (the file already exists — add new test functions, don't create `tests/unit/db/` which is not a convention in this repo):
- `test_blocks_against_orch_db_when_agent_context` (existing behavior preserved — likely already there in some form; verify and don't duplicate)
- `test_allows_against_per_worktree_db_when_per_worktree_flag_set` (new)
- `test_blocks_against_orch_db_even_with_per_worktree_flag` (Invariant #3)
- `test_blocks_when_only_per_worktree_flag_set_without_agent_context_is_irrelevant` (the relax only matters in agent context; outside agent context everything is already allowed)

### 3. Module-level documentation

Add a comprehensive module docstring to `worktree_compose.py` covering:
- Purpose
- Opt-in mechanism (`ai-dev/iw-config/`)
- Lifecycle (up → discover → rewrite → seed → live; down on terminal state)
- Reference to `docs/IW_AI_Core_Worktree_Isolation.md` (created in S13)
- Reference to the precedent module `browser_env.py`

## Project Conventions

- Read `CLAUDE.md`, `orch/CLAUDE.md`, `executor/CLAUDE.md`
- Mirror `browser_env.py` patterns for subprocess invocation, port allocation, error handling, DaemonEvent emission
- Use `psycopg` v3 (NOT psycopg2) if you write SQL inline
- Sync code only — no `async`/`await`

## TDD Requirement

Follow RED → GREEN → REFACTOR for every public function. Tests live in `tests/unit/daemon/test_worktree_compose.py` (you create this; the comprehensive suite is S11's scope, but you write ENOUGH tests now to drive your implementation). Required:

- `test_render_compose_substitutes_jinja_vars`
- `test_render_compose_writes_to_iw_subdir`
- `test_discover_ports_parses_docker_compose_port_output` (mock subprocess)
- `test_rewrite_env_applies_port_to_env_mapping`
- `test_rewrite_env_preserves_passthrough_keys`
- `test_run_seed_zero_exit_succeeds` (stub seed.sh in tmp_path)
- `test_run_seed_nonzero_exit_returns_failure_with_stderr_tail`
- `test_assert_gitignore_safe_passes_when_env_and_iw_present`
- `test_assert_gitignore_safe_raises_when_env_missing`
- `test_assert_gitignore_safe_raises_when_iw_dir_missing`

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — all unit tests pass (yours + existing)
2. Run `make lint` and `make quality`
3. NEVER report `tests_passed: true` unless all unit tests pass

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/worktree_compose.py",
    "orch/db/safe_migrate.py",
    "tests/unit/daemon/test_worktree_compose.py",
    "tests/unit/test_safe_migrate.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
