# F-00063_S03_API_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step**: S03
**Agent**: api-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed: testcontainers in fixtures; `docker ps`/`inspect`/`logs`; `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orchestration DB. Allowed: `alembic revision --autogenerate`, read-only commands. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- `ai-dev/active/F-00063/reports/F-00063_S02_CodeReview_report.md` (and S01 backend report)

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S03_API_report.md`

## Context

You are adding HTTP endpoints for the Stale Process & Migration Detector. The backend (`orch/staleness/`) is already in place — your job is to expose it via FastAPI routes that return HTML fragments (panel + dot) and execute the action commands (restart/start/stop/alembic-upgrade) with a 5-second per-service soft-lock.

Read the design doc and the S01 backend implementation. Match the style of existing dashboard routers, especially `dashboard/routers/daemon_control.py` (the canonical restart-via-subprocess pattern).

## Requirements

### 1. New router file

Create `dashboard/routers/staleness.py` with `router = APIRouter()` and these endpoints:

- `GET /projects/{project_id}/staleness` — returns the panel HTML fragment for the project home page. Calls `compute_project_staleness(project_id)` and renders `fragments/staleness_panel.html`. Returns an empty fragment if the project has no `services` and no `alembic` block. 404 if `project_id` is not in `projects.toml`.
- `GET /projects/{project_id}/staleness-dot` — returns the small dot fragment for the project list row. Renders `fragments/staleness_dot.html`. Empty fragment for opt-out projects (CRITICAL: this must be a literal empty body, not whitespace, so htmx replaces the placeholder with nothing).
- `POST /projects/{project_id}/services/{service_name}/restart` — invokes the configured `restart_command` via `subprocess.Popen([...], shell=True, start_new_session=True, stdout=DEVNULL, stderr=DEVNULL, cwd=<project_repo_root>)`. The cwd MUST be the project's `repo_root` from `projects.toml`. Returns 204 on success with `HX-Trigger` toast. Returns 404 if project/service unknown. Returns 409 if no `restart_command` configured. Returns 429 if the per-service soft-lock is engaged. Use `shell=True` here because the configured commands are operator-supplied strings that may include `&&`, `cd`, etc. (see Security note).
- `POST /projects/{project_id}/services/{service_name}/start` — same but for `start_command`.
- `POST /projects/{project_id}/services/{service_name}/stop` — same but for `stop_command`.
- `POST /projects/{project_id}/alembic/upgrade` — runs `alembic -c <config> upgrade head` synchronously with a 60s timeout. When `db_url_env` is configured, its value is injected into the subprocess env (and additionally as `IW_ALEMBIC_DB_URL`); when omitted, the subprocess inherits the parent process environment unchanged — matching `check_alembic`'s contract from S01. Returns 200 on success with the alembic stdout in the response toast. Returns 502 on alembic failure (DB unreachable, migration error) with stderr captured. Returns 404 if no alembic block.

### 2. 5-second soft-lock

Implement an in-memory per-key lock keyed by `(project_id, service_name)`. The simplest correct approach: a module-level `dict[tuple[str, str], float]` mapping the key to the timestamp of the last successful restart/start/stop. On each POST, check if `now - last < 5.0`; if so return 429 with header `Retry-After: <remaining_seconds>`. Otherwise record `now` and proceed.

Single-process is sufficient — the dashboard runs as one uvicorn worker. Document this assumption in a comment.

### 3. Toast trigger

On every successful action, set the `HX-Trigger` response header to a JSON payload `{"showToast": {"message": "<msg>", "kind": "success", "reload": false}}`. Reuse whatever existing toast helper the codebase already has (search `dashboard/routers/` for `HX-Trigger`). The panel and dot will refresh on their own 15s timer; do not force a reload.

### 4. Register the router

Add `dashboard/main.py` import and `app.include_router(staleness.router)` next to the other routers. Verify the dashboard starts without errors after wiring.

### 5. Self-restart special case

For the iw-ai-core dashboard restarting itself: the `restart_command` in `projects.toml` is `bin/restart-dashboard.sh`. The endpoint MUST spawn it detached (`start_new_session=True`) and return 202 immediately (not 204), because the response must flush before the helper kills the dashboard. Do not block waiting.

### 6. Security

- Sanity-check `project_id` and `service_name` against the loaded config before doing anything (no path traversal, no log injection). Reject unknown ids with 404 before touching subprocesses.
- The restart commands are operator-supplied strings from `projects.toml`. They run as the dashboard user with `shell=True` — this is intentional but document it in a comment ("`projects.toml` is a trusted operator-only config; commands run with `shell=True` so operators can use shell features").
- When `db_url_env` is configured, its value is injected as a plain env var; do not log its contents. When omitted, no env override happens.

### 7. TDD: tests first

In `tests/dashboard/test_staleness_router.py` write integration tests using the existing FastAPI TestClient pattern from `tests/dashboard/`. Cover:

- `GET /projects/iw-ai-core/staleness` returns 200 with the panel fragment (mock `compute_project_staleness`).
- `GET /projects/cv/staleness` (opt-out project) returns 200 with empty body.
- `GET /projects/unknown/staleness` returns 404.
- `POST /projects/iw-ai-core/services/daemon/restart` invokes subprocess with the configured command (assert via patched `subprocess.Popen`).
- A second `POST` within 5s returns 429 with `Retry-After`.
- `POST /projects/iw-ai-core/services/daemon/restart` after no `restart_command` configured → 409.
- `POST /projects/iw-ai-core/alembic/upgrade` happy path (mocked subprocess returning rc=0).
- `POST /projects/iw-ai-core/alembic/upgrade` failure path (rc!=0) → 502.

Write tests RED first.

## Project Conventions

- `dashboard/routers/daemon_control.py` is the canonical reference for spawning detached subprocesses.
- Use `dashboard.dependencies.get_db` if you need a DB session. (You probably don't for this feature — staleness is filesystem/proc-only.)
- HTMX-style fragments live under `dashboard/templates/fragments/` — that's S04's concern but make sure your endpoints reference the names S04 will create (`staleness_panel.html`, `staleness_dot.html`).
- Keep response handlers small; push logic into `orch/staleness/`.

## TDD Requirement

Follow Red-Green-Refactor. Tests before implementation.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` and the dashboard integration tests
2. `make lint`
3. `make typecheck`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "F-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
