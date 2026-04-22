# F-00058_S05_API_prompt

**Work Item**: F-00058
**Step**: S05
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (2026-04-22 incident).

Allowed:
  1. Testcontainers spun up by pytest fixtures (they self-destruct via Ryuk).
  2. Read-only introspection: docker ps | inspect | logs.
  3. Invocations through ./ai-core.sh or make targets.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule. If a testcontainer appears
stuck, rely on pytest teardown / Ryuk — never `docker kill` it.

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` — API Changes + AC*
- S03 report (service layer) + S04 review verdict
- `dashboard/routers/quality.py` and `dashboard/routers/tests.py` — patterns to match

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S05_API_report.md`
- `dashboard/routers/oss.py` (new)
- `dashboard/app.py` (modified — register router)

## Context

Build the HTTP router for OSS compliance. Routes under `/projects/{project_id}/oss`. Read a sibling router like `dashboard/routers/quality.py` first to match naming, error handling, HTMX headers, and templating conventions.

## Requirements

### Endpoints

All mounted under `/projects/{project_id}/oss`:

| Method | Path | Returns | Purpose |
|--------|------|---------|---------|
| GET | `/` | `pages/project/oss.html` | OSS view page |
| GET | `/status` | `fragments/oss_status_frame.html` (htmx) | Pill + summary — refreshed on HTMX requests, included on every project page |
| GET | `/tools` | `fragments/oss_install_modal.html` or JSON | Tier-1 tool availability (wraps `orch.oss.tool_probe.probe_tier1`) |
| POST | `/install` | JSON `{job_id, stream_url}` | Enqueue a Tier-1 tool install job (wraps `iw oss install`). No worktree. 409 on existing running install job for this project. |
| POST | `/enable` | redirect to `/`, flash | Flip flag + write `.iw/oss-publish.toml` |
| POST | `/disable` | redirect to `/`, flash | Flip flag off |
| POST | `/scan` | JSON `{job_id, stream_url}` | Enqueue scan job |
| POST | `/prepare` | JSON `{job_id, stream_url}` | Enqueue prepare job (make_oss) |
| POST | `/publish` | JSON `{job_id, stream_url}` | Enqueue publish job |
| GET | `/stream/{job_id}` | SSE | Stream progress from service |

### Behavior

- All POST handlers delegate to `dashboard.services.oss_service.*`; no business logic in routers.
- 409 Conflict if a job of the same kind is already `running` for the project (applies to scan, prepare, publish, and install).
- HTMX partial responses set `HX-Trigger` to let the pill refresh.
- SSE endpoint streams events from `oss_service.job_event_stream(...)` for any kind (scan/prepare/publish/install).
- Authorization: reuse existing project-access guard used by `quality.py` / `tests.py`.
- `POST /install`: returns `{job_id, stream_url}` exactly like scan/prepare/publish. Client subscribes to `/stream/{job_id}`; on `complete` event, client re-fetches `/tools` to refresh the install modal.

### Page header integration

The `fragments/oss_status_frame.html` partial must be include-able on every project page. Add an include directive (or equivalent) in the shared project-page header template so every project view renders the frame underneath Git Status. Handle the disabled (`oss_enabled=false`) case: render an "Install OSS" CTA instead of a pill.

## Project Conventions

- Match `dashboard/routers/quality.py` for shape, error handling, dependency injection, and HTMX/SSE patterns.
- No business logic; routers only parse requests and delegate.
- Templates live under `dashboard/templates/`; frontend agent (S06) renders them.

## TDD Requirement

Tests (parallel with S06, so use stub templates if S06 not yet ready — asserts will still work on response shape/status):
- `tests/integration/test_oss_dashboard_routes.py`:
  - each endpoint returns correct status code for valid + invalid inputs
  - 409 on concurrent scan
  - 409 on concurrent install (second POST /install while the first is `running`)
  - POST /install returns `{job_id, stream_url}` and creates a `project_oss_job` row with `kind='install'`, `worktree_path=null`
  - SSE emits events in expected order (for at least one of: scan, install)
  - enable endpoint flips flag + writes toml
  - disable keeps `.iw/` on disk

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make lint` + `uv run mypy dashboard/routers/` pass.

## Subagent Result Contract

Standard JSON.
