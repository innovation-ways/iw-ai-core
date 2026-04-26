# F-00063_S01_Backend_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md` -- Design document

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S01_Backend_report.md` -- Step report

## Context

You are implementing the **backend foundation** of the Stale Process & Migration Detector. This step builds everything except the HTTP routes and the HTML templates: config schema, detection engine, staleness computation, alembic check, the dashboard self-restart helper, and the AI CORE seed entry in `projects.toml`.

Read `ai-dev/active/F-00063/F-00063_Feature_Design.md` first. Then read the project's `CLAUDE.md` and `orch/CLAUDE.md` for conventions (SQLAlchemy 2.0, psycopg v3, Click 8, dotenv config, sync style).

This feature has **no DB schema changes** — do not write a migration. Everything is live-computed.

## Requirements

### 1. Config schema and parser extension

Create a new package `orch/staleness/` with `__init__.py`. In `orch/staleness/config.py`:

- Define dataclasses (or pydantic models — match what already exists in `orch/`) for:
  - `ServiceDetect` — discriminated union over `type` ∈ `{"port", "pidfile", "docker", "pgrep"}` with type-specific fields (`port: int`, `path: str`, `container: str`, `pattern: str`).
  - `ServiceConfig` — `name`, `detect: ServiceDetect`, `watch_paths: list[str]`, `ignore_paths: list[str]`, `restart_command: str | None`, `start_command: str | None`, `stop_command: str | None`, `hot_reload: bool = False`.
  - `AlembicConfig` — `config: str` (path to `alembic.ini` relative to repo root), `db_url_env: str | None = None`. When `db_url_env` is None, the alembic subprocess inherits the parent process's environment unchanged (suitable for projects whose alembic env.py already resolves the URL from app config — e.g. iw-ai-core itself reads `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD` via `orch.config.get_db_url()`). When set, the named env var must exist; its value is injected as `IW_ALEMBIC_DB_URL` (the alembic env.py for that project is expected to read it) or used as a `-x sqlalchemy.url=<value>` override on the alembic CLI — pick whichever pattern matches the target project's env.py.
  - `ProjectStalenessConfig` — `services: list[ServiceConfig]`, `alembic: AlembicConfig | None`.
- Provide `parse_project_staleness(raw: dict) -> ProjectStalenessConfig` that takes the project's `config` dict (the third argument of `ProjectConfig` from `project_registry.py`) and extracts the `services` and `alembic` keys. Return an empty `ProjectStalenessConfig(services=[], alembic=None)` if neither key is present (this is the opt-out signal).
- Validation: every required field must be present; raise `ValueError` with a clear message on misconfiguration. Unknown `detect.type` values raise.

Update `orch/daemon/project_registry.py` `_build_project_config` to call `parse_project_staleness` for sanity validation only — log a warning and skip the project's services/alembic if parsing fails. Do NOT change the existing `ProjectConfig` shape; the staleness config is read on demand at compute time, not stored on the registry.

### 2. Detection engine

In `orch/staleness/detection.py` implement:

- `find_running_pid(detect: ServiceDetect, repo_root: Path) -> int | None`
  - For `port`: parse `ss -ltnp` (or `lsof -i :PORT`) output to find the listening pid. If multiple, prefer one whose `/proc/<pid>/cwd` is inside `repo_root`.
  - For `pidfile`: read the file (relative to `repo_root`); return the pid only if it is alive.
  - For `pgrep`: regex against `/proc/<pid>/cmdline` (NUL-replaced with spaces). Filter by cwd inside `repo_root`. If multiple, return the oldest by start time and log a warning.
  - For `docker`: skip — handled separately by `find_running_container`.
  - Returns None on any failure (process not alive, cwd outside repo, etc.).
- `find_running_container(detect: ServiceDetect) -> str | None` for `docker` detect type — invokes `docker inspect <container> --format '{{.State.Running}} {{.Created}}'` and returns the container id only when running.
- `read_process_start_time(pid: int) -> datetime` — parse `/proc/<pid>/stat` field 22 (jiffies since boot), `/proc/uptime`, and `os.sysconf("SC_CLK_TCK")`, then resolve to a wall-clock `datetime` (UTC).
- `read_container_start_time(container_id: str) -> datetime` — parse `docker inspect --format '{{.State.StartedAt}}'`.
- `is_cwd_under(pid: int, repo_root: Path) -> bool` — readlink `/proc/<pid>/cwd` and compare to `repo_root.resolve()`.

All shell-outs use `subprocess.run(..., check=False, capture_output=True, text=True)` with explicit timeout of 2s. Never raise on subprocess failure — return None and log.

### 3. Git lookup

In `orch/staleness/git_lookup.py`:

- `find_commit_at(repo_root: Path, ts: datetime) -> str | None` — runs `git -C <repo_root> log --first-parent main --before=@<epoch> -1 --format=%H`. Returns the SHA or None.
- `commits_since(repo_root: Path, since_sha: str, watch_paths: list[str], ignore_paths: list[str]) -> list[CommitSummary]` — runs `git log <since_sha>..main --format=%H%x09%s -- <watch_paths> :(exclude)<ignore_paths>` and parses the output. Each `CommitSummary` has `sha`, `subject`. Empty list → up-to-date.
- Glob translation: `watch_paths` are gitignore-style includes; map each to a literal pathspec. `ignore_paths` use `:(exclude)` git pathspec syntax. Negated patterns inside `watch_paths` (a string starting with `!`) translate to additional `:(exclude)` entries.
- Use `subprocess.run` with timeout 5s. Return empty list on failure and log.

### 4. Alembic check

In `orch/staleness/alembic_check.py`:

- `check_alembic(repo_root: Path, alembic_cfg_path: str, db_url_env: str | None) -> AlembicStatus`
- `AlembicStatus` is a dataclass: `status` ∈ `{"up_to_date", "stale", "unreachable", "no_config"}`, `current: str | None`, `head: str | None`, `pending: list[RevisionSummary]`, `error: str | None`.
- Invokes `alembic -c <repo_root>/<alembic_cfg_path> current --verbose` and `alembic heads --verbose` as subprocess calls with a 10s timeout. When `db_url_env` is None, the subprocess inherits the parent environment unchanged. When set, the value of `os.environ[<db_url_env>]` is passed through to the subprocess (and additionally exposed as `IW_ALEMBIC_DB_URL` for alembic env.py files that look for it) — if the named env var is missing, return `unreachable` with a clear error.
- Parses the verbose output to extract revision IDs and messages.
- On connection failure (psql refused, etc.), return `unreachable` with the stderr in `error`.

### 5. Service orchestrator

In `orch/staleness/service.py`:

- `compute_project_staleness(project_id: str) -> ProjectStalenessResult`
- `ProjectStalenessResult` carries: `project_id`, `services: list[ServiceStaleness]`, `alembic: AlembicStatus | None`, `is_stale: bool` (any service stale OR alembic stale).
- `ServiceStaleness` carries: `name`, `status` ∈ `{"up_to_date", "stale", "not_running", "hot_reload_skipped", "unknown"}`, `start_time: datetime | None`, `start_commit: str | None`, `commits: list[CommitSummary]`, `error: str | None`, `hot_reload: bool`, `actions: list[str]` (subset of `["restart", "start", "stop"]`).
- Reads `projects.toml` fresh on every call (no caching). Looks up the project by id. If no services and no alembic → return an empty result with `is_stale=False`.
- For each service: detect → if not running, status=`not_running` and skip git lookup. If running and `hot_reload=True`, status=`hot_reload_skipped`. Otherwise compute start time → start commit → commits since → stale or up_to_date.
- Action list derived from configured commands.

### 6. Dashboard self-restart helper

Create `bin/restart-dashboard.sh` (chmod +x):

```bash
#!/usr/bin/env bash
# Detached helper used by the dashboard restart endpoint to re-spawn itself.
set -euo pipefail
cd "$(dirname "$0")/.."

# Allow caller-issued HTTP response to flush and disconnect cleanly.
sleep 1

PID_FILE=".dashboard.pid"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    kill -TERM "$OLD_PID" || true
    for _ in $(seq 1 10); do
      kill -0 "$OLD_PID" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

exec ./ai-core.sh dashboard start
```

Verify the script is invoked under `setsid`/`nohup` from any caller — the caller is responsible for detaching. Confirm `ai-core.sh dashboard start/stop/restart` semantics in the existing script remain intact; do not break them.

### 7. AI CORE seed config

Append to `projects.toml` under the `[projects.iw-ai-core]` table:

```toml
[[projects.iw-ai-core.services]]
name = "daemon"
watch_paths = ["orch/**", "executor/**"]
ignore_paths = ["**/tests/**", "**/*.md"]
restart_command = "./ai-core.sh daemon restart"
detect = { type = "pidfile", path = ".daemon.pid" }

[[projects.iw-ai-core.services]]
name = "dashboard"
watch_paths = ["dashboard/**", "orch/**"]
ignore_paths = ["**/tests/**", "**/*.md"]
restart_command = "bin/restart-dashboard.sh"
detect = { type = "pidfile", path = ".dashboard.pid" }

[projects.iw-ai-core.alembic]
config = "alembic.ini"
# db_url_env intentionally omitted — iw-ai-core's alembic env.py
# already resolves the URL via orch.config.get_db_url() from
# IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD in .env, so the alembic
# subprocess inherits the parent environment unchanged.
```

Do NOT add staleness blocks for the `innoforge` or `cv` projects — they are intentionally opt-out for now.

### 8. TDD: tests for everything in this step

Create `tests/unit/staleness/` (with `__init__.py`) and write unit tests for items 1–5 BEFORE writing implementation code (RED → GREEN → REFACTOR). Use temporary git repos (created via `subprocess` in the test fixture) for the git lookup tests. Mock `/proc` reads via `tmp_path` and a pluggable reader. Mock `subprocess.run` for `ss`, `docker`, and `alembic` invocations.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 sync style (`Mapped[]`)
- psycopg v3 (NOT psycopg2)
- dotenv loaded at module import
- Click 8.1 for CLI
- ruff + mypy clean
- Tests under `tests/unit/` and `tests/integration/`

Match existing helpers (e.g. how `orch/daemon/worktree_compose.py` shells out and times-out). Do not introduce new third-party deps; pure-stdlib subprocess + tomllib + dataclasses are sufficient.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior.
2. **GREEN**: Write the minimal implementation to make tests pass.
3. **REFACTOR**: Improve code structure while keeping all tests green.

Do not skip the RED phase.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — must be all green (zero failures).
2. `make lint` — must be clean.
3. `make typecheck` — must be clean for any new module under `orch/staleness/`.
4. Do not report `tests_passed: true` unless every gate passes locally.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/staleness/__init__.py", "..."],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
