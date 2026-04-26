# F-00063: Stale Process & Migration Detector

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-26
**Status**: Draft

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

## Description

Detect running processes/containers and Alembic DB heads that are stale relative to the current `main` branch on each managed project's main worktree, surface a red dot on each project card on the project list, and a panel on the project home with details and one-click restart / migrate buttons. Pure external observation — no changes to managed projects required. Opt-in: a project with no `[[project.services]]` and no `[project.alembic]` blocks in `projects.toml` shows nothing.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key context for this feature:

- `projects.toml` is parsed in `orch/daemon/project_registry.py` via `tomllib`. `ProjectConfig.config` carries an arbitrary dict, so new keys can be added without DB schema or migration changes.
- The dashboard already has a daemon stop/start/restart pattern in `dashboard/routers/daemon_control.py` using PID files, `os.kill`, and `subprocess.Popen(start_new_session=True)` — the new restart endpoint reuses this approach.
- Auto-refresh fragment pattern: `dashboard/templates/fragments/daemon_panel.html` is fetched via htmx — same model for the new staleness panel.
- No DB schema changes. State is computed live on every panel render. No migrations.
- Dashboard supervision is `ai-core.sh` + PID files. The dashboard cannot cleanly restart itself in-process; a small detached helper script is needed (`bin/restart-dashboard.sh`).

## Scope

### In Scope

- New optional config blocks in `projects.toml`:
  - `[[projects.<id>.services]]` repeating sub-table — declared services to monitor (`name`, `detect`, `watch_paths`, `ignore_paths`, `restart_command`, `start_command`, `stop_command`, `hot_reload`).
  - `[projects.<id>.alembic]` single sub-table — `config` path and an optional `db_url_env` to enable migration head check. When `db_url_env` is omitted, the alembic subprocess inherits the parent environment unchanged (suitable for projects whose alembic `env.py` already resolves the URL from app config, e.g. iw-ai-core itself).
- Backend detection engine supporting four `detect.type` values: `port`, `pidfile`, `docker`, `pgrep`. All cross-check the candidate process's `cwd` (read from `/proc/<pid>/cwd`) is inside the project's `repo_root` to scope to main worktree only.
- Process start time read from `/proc/<pid>/stat` field 22 (jiffies → wall-clock via `/proc/uptime`). For docker, `docker inspect <container> --format '{{.Created}}'`.
- "Commit at start time" lookup: `git -C <repo_root> log --first-parent main --before=@<start_epoch> -1 --format=%H`.
- Staleness check: `git -C <repo_root> log <start_commit>..main -- <watch_paths> :(exclude)<ignore_paths>` — non-empty → stale, list those commits.
- Alembic head check: live query `alembic -c <config> current` against the configured DB env, compared to `alembic -c <config> heads`.
- New API endpoints:
  - `GET /projects/{project_id}/staleness` → full panel fragment (HTML).
  - `GET /projects/{project_id}/staleness-dot` → tiny red/green dot fragment for the project list row.
  - `POST /projects/{project_id}/services/{service_name}/restart` → runs `restart_command` (5s soft-lock).
  - `POST /projects/{project_id}/services/{service_name}/start` → runs `start_command`.
  - `POST /projects/{project_id}/services/{service_name}/stop` → runs `stop_command`.
  - `POST /projects/{project_id}/alembic/upgrade` → runs `alembic -c <config> upgrade head` against the configured DB.
- Frontend UI:
  - Staleness panel injected into `dashboard/templates/pages/project/dashboard.html`. Two sections in fixed order: **Migrations** (alembic) first, **Services** second. Suggests "do migrations first" copy when both are stale.
  - Each service row shows: name, status (`up-to-date` / `stale` / `not running` / `unknown`), start time, list of commits since start (one-line each), and action buttons (`Restart` if `restart_command`; `Stop`/`Start` pair if those are configured; informational only if no commands).
  - "Not running" services render in grey, do not light up the red dot, and show no action buttons except `Start` if `start_command` is present.
  - Detection failures (e.g. port not bound) render as `not running` (grey).
  - Confirm dialog for every action with title + service name + the literal command string + `Confirm` / `Cancel`.
  - 5s soft-lock per service: a successful POST sets a per-service in-memory lockout that rejects subsequent POSTs with 429 for 5 seconds.
  - Red dot fragment lazy-loaded per row on `/` (project list). Lights up red iff the project has at least one stale service or stale alembic head; grey if config is declared but everything is up-to-date or "not running"; absent entirely if no `services` and no `alembic` block.
  - htmx `hx-trigger="every 15s"` auto-refresh on both the panel and each red dot fragment. No client-side caching, no server-side caching: `projects.toml` is re-read on every staleness computation.
- Self-restart helper script for the dashboard: `bin/restart-dashboard.sh` — kills the old PID, starts a new dashboard, writes the new PID file. Wired through `ai-core.sh dashboard restart` so the existing supervisor path keeps working.
- Seed configuration in `projects.toml` for the `iw-ai-core` project itself (dogfood): `daemon` and `dashboard` services with appropriate `watch_paths`, plus the alembic block.
- Tests: unit tests for detection helpers (port, pidfile, docker, pgrep), staleness algorithm (git log against include/exclude globs), alembic head comparison, and 5s soft-lock; integration tests for panel fragment render and restart endpoints with mocked subprocess invocations.

### Out of Scope

- DB schema changes / migrations / new tables. Pure live computation, stateless.
- Daemon-emitted `service_stale` timeline events (revisit in v2 if needed).
- Polling-back after a restart to confirm the new process came up cleanly (revisit in v2). The user trusts `hx-trigger="every 15s"` to re-render.
- Showing the SQL diff before alembic upgrade (`alembic upgrade head --sql` dry-run).
- Showing a count badge on the red dot — single dot only.
- Auto-starting declared services when iw-ai-core itself starts. The user starts services manually; iw-ai-core only observes.
- Per-project `iw-services.toml` shipped inside the project repo. Configuration lives only in iw-ai-core's `projects.toml`.
- Production / staging environment monitoring. Local dev only.
- Hot-reloading Python code in the running daemon/dashboard. Restart is the only mechanism.
- Per-worktree DB tracking (only the project's main DB, identified by `db_url_env` or — when omitted — by the parent process's environment, is monitored).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Config schema + parser extension; detection engine; staleness computation; alembic head check; dashboard self-restart helper script; seed AI CORE service config in `projects.toml` | — |
| S02 | code-review-impl | Review S01 (backend) | — |
| S03 | api-impl | Endpoints: panel + dot fragments, restart/start/stop, alembic upgrade, with 5s soft-lock | S04 |
| S04 | frontend-impl | Staleness panel integrated into project home; red dot lazy-loaded per row on project list; confirm dialog; htmx auto-refresh every 15s | S03 |
| S05 | code-review-impl | Review S03 (api) | S06 |
| S06 | code-review-impl | Review S04 (frontend) | S05 |
| S07 | tests-impl | Additional unit + integration coverage | — |
| S08 | code-review-final-impl | Cross-layer global review | — |
| S09–S13 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |
| S14 | qv-browser | Browser verification: project list red dot + project home staleness panel + restart confirm flow | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No alembic revision required. Feature is fully stateless (live-computed on each render).

### API Changes

- **New endpoints**:
  - `GET /projects/{project_id}/staleness` — staleness panel HTML fragment.
  - `GET /projects/{project_id}/staleness-dot` — red dot HTML fragment for project list.
  - `POST /projects/{project_id}/services/{service_name}/restart` — invoke `restart_command`.
  - `POST /projects/{project_id}/services/{service_name}/start` — invoke `start_command`.
  - `POST /projects/{project_id}/services/{service_name}/stop` — invoke `stop_command`.
  - `POST /projects/{project_id}/alembic/upgrade` — run `alembic upgrade head` for the project.
- **Modified endpoints**: None.

### Frontend Changes

- **New components**:
  - `dashboard/templates/fragments/staleness_panel.html` — full panel (migrations + services sections).
  - `dashboard/templates/fragments/staleness_dot.html` — red/grey/empty dot for project list rows.
  - `dashboard/templates/fragments/staleness_confirm.html` — confirm dialog content.
- **Modified components**:
  - `dashboard/templates/pages/project/dashboard.html` — embed `staleness_panel.html` (htmx auto-refresh `every 15s`).
  - `dashboard/templates/pages/project_selector.html` (or whichever project list template `dashboard/routers/projects.py:370` renders) — embed lazy-loaded `staleness_dot.html` per row.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00063/F-00063_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00063/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00063/prompts/F-00063_S01_Backend_prompt.md` | Prompt | S01 backend instructions |
| `ai-dev/active/F-00063/prompts/F-00063_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `ai-dev/active/F-00063/prompts/F-00063_S03_API_prompt.md` | Prompt | S03 api instructions |
| `ai-dev/active/F-00063/prompts/F-00063_S04_Frontend_prompt.md` | Prompt | S04 frontend instructions |
| `ai-dev/active/F-00063/prompts/F-00063_S05_CodeReview_API_prompt.md` | Prompt | S05 review of S03 |
| `ai-dev/active/F-00063/prompts/F-00063_S06_CodeReview_Frontend_prompt.md` | Prompt | S06 review of S04 |
| `ai-dev/active/F-00063/prompts/F-00063_S07_Tests_prompt.md` | Prompt | S07 additional tests |
| `ai-dev/active/F-00063/prompts/F-00063_S08_CodeReview_Final_prompt.md` | Prompt | S08 cross-layer final review |
| `ai-dev/active/F-00063/prompts/F-00063_S14_BrowserVerification_prompt.md` | Prompt | S14 qv-browser end-to-end verification |
| `orch/staleness/__init__.py` | Source (new) | Package init for staleness module |
| `orch/staleness/config.py` | Source (new) | Pydantic models for `[[services]]` and `[alembic]` blocks; parser extension |
| `orch/staleness/detection.py` | Source (new) | Detection engine: port / pidfile / docker / pgrep + cwd cross-check + start-time read |
| `orch/staleness/git_lookup.py` | Source (new) | Commit-at-time lookup + git-log-since-start path-filtered query |
| `orch/staleness/alembic_check.py` | Source (new) | Alembic current vs heads comparison |
| `orch/staleness/service.py` | Source (new) | `compute_project_staleness(project_id) -> StalenessResult` orchestrator |
| `orch/daemon/project_registry.py` | Source (modify) | Extend `_build_project_config` to validate `services` and `alembic` keys |
| `dashboard/routers/staleness.py` | Source (new) | All new endpoints (panel/dot/restart/start/stop/alembic-upgrade) with 5s soft-lock |
| `dashboard/main.py` | Source (modify) | Register `staleness` router |
| `dashboard/templates/fragments/staleness_panel.html` | Template (new) | Panel fragment (migrations + services) |
| `dashboard/templates/fragments/staleness_dot.html` | Template (new) | Red/grey/empty dot fragment |
| `dashboard/templates/fragments/staleness_confirm.html` | Template (new) | Confirm dialog body |
| `dashboard/templates/pages/project/dashboard.html` | Template (modify) | Embed staleness panel with `hx-trigger="every 15s"` |
| `dashboard/templates/pages/project_selector.html` | Template (modify) | Embed lazy-loaded staleness dot per row (verify exact path during S04) |
| `dashboard/static/theme.css` (or `tailwind.src.css`) | Stylesheet (modify) | `.iw-staleness-dot` / `.iw-staleness-dot--red` / `--grey` styles (S04 picks the file matching existing conventions) |
| `bin/restart-dashboard.sh` | Script (new) | Detached self-restart helper for the dashboard |
| `ai-core.sh` | Script (modify) | Optionally call helper for `dashboard restart` parity (verify behavior intact) |
| `projects.toml` | Config (modify) | Seed `[[projects.iw-ai-core.services]]` for `daemon` + `dashboard`, plus `[projects.iw-ai-core.alembic]` |
| `tests/unit/staleness/test_config.py` | Test (new) | Unit: parsing of services/alembic blocks, validation errors |
| `tests/unit/staleness/test_detection.py` | Test (new) | Unit: port/pidfile/docker/pgrep detection with `/proc` mocks |
| `tests/unit/staleness/test_git_lookup.py` | Test (new) | Unit: commit-at-time + path-filtered git log against a temp git repo |
| `tests/unit/staleness/test_alembic_check.py` | Test (new) | Unit: current vs heads comparison with mocked alembic |
| `tests/unit/staleness/test_service.py` | Test (new) | Unit: end-to-end `compute_project_staleness` with mocked dependencies |
| `tests/dashboard/test_staleness_router.py` | Test (new) | Integration: panel/dot fragment render, restart endpoint, 5s soft-lock |

Reports are created during execution under `ai-dev/active/F-00063/reports/`.

## Acceptance Criteria

### AC1: Project with stale service shows red dot and panel detail

```
Given the iw-ai-core project has a daemon process running, started from commit abc123
And main has been advanced past abc123 with commits touching orch/daemon/**
When I open the dashboard project list at /
Then a red dot is rendered next to the iw-ai-core project card
And navigating to /projects/iw-ai-core shows a "Services" section listing the daemon as "stale"
And the panel lists the missing commits (one-liners) since process start
```

### AC2: Restart button executes restart_command after confirmation

```
Given the daemon service is shown as stale on the project home staleness panel
When I click the "Restart" button for the daemon row
Then a confirm dialog appears showing the literal command "./ai-core.sh daemon restart"
And clicking "Confirm" issues POST /projects/iw-ai-core/services/daemon/restart
And the response runs the configured restart_command in a subprocess
And subsequent POSTs to the same endpoint within 5 seconds return HTTP 429
```

### AC3: Alembic head mismatch surfaces a dedicated banner with one-click upgrade

```
Given the iw-ai-core orch DB is at alembic revision XXX
And the project's alembic versions/ has head YYY != XXX
When I open /projects/iw-ai-core
Then the staleness panel renders the "Migrations" section ABOVE the "Services" section
And the section shows "DB at XXX, code has YYY (N unapplied revisions)" with the revision messages
And a copy line suggests "Apply migrations first, then restart services" when services are also stale
And clicking "Upgrade head" → confirming → triggers POST /projects/iw-ai-core/alembic/upgrade
And the endpoint runs `alembic -c <config> upgrade head` with the configured db_url_env
```

### AC4: Project with no service/alembic config has zero footprint

```
Given the cv project in projects.toml has neither [[projects.cv.services]] nor [projects.cv.alembic]
When I open the dashboard project list at /
Then there is no dot — neither red nor grey — next to the cv project card
And navigating to /projects/cv shows no staleness panel at all
```

### AC5: Auto-refresh updates the panel and dot without a manual page reload

```
Given the staleness panel is open at /projects/iw-ai-core showing all services up-to-date
When a new commit lands on main touching watched paths between two refresh ticks
Then within 16 seconds (next htmx tick) the panel re-renders showing the affected service as stale
And no manual page reload is required
And the project list red dot for the same project also lights up within the same window
```

### AC6: Service detected but not running renders grey, no red dot

```
Given the dashboard service is declared in projects.toml with detect type=port port=9900
And no process is bound to port 9900
When I open /projects/iw-ai-core
Then the dashboard row shows status "not running" in grey
And the project list dot does NOT light up red on account of this row
And no Restart button is shown (Start is shown only if start_command is configured)
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Project not in projects.toml | unknown project_id | Endpoints return 404 |
| Project has no services or alembic block | `cv` project | Panel returns empty fragment; dot fragment returns empty fragment; no DOM footprint |
| Service declared, port detect, nothing bound | port=9900, no listener | Status `not running` (grey); no red dot contribution; no Restart button |
| Service declared, pidfile detect, file missing | `.daemon.pid` does not exist | Status `not running` (grey) |
| Service declared, pidfile detect, stale PID | file holds dead PID | Status `not running` (grey) |
| Process found but cwd is in an agent worktree | cwd outside `repo_root` main checkout | Service treated as `not running` (only main worktree counts) |
| Process found, no commits since start | start commit == HEAD | Status `up-to-date` (green check) |
| Process found, commits since start, none touch watched paths | commits exist but excluded by `watch_paths`/`ignore_paths` | Status `up-to-date` |
| Process found, watched paths matched | commits exist that touch `watch_paths` and not excluded by `ignore_paths` | Status `stale`; list each commit |
| Service has `hot_reload = true` and is stale | watched paths matched | Status `up-to-date` (banner notes hot-reload assumption); no Restart button needed |
| Restart command not configured | only `start_command` + `stop_command` present | Show two buttons (Stop, Start); no Restart |
| Neither restart nor start/stop commands | informational only | Show stale warning, no action buttons |
| Two restart POSTs within 5s | rapid double-click | First returns 200/204, second returns 429 with `Retry-After` |
| Alembic config missing | no `[projects.X.alembic]` block | Migrations section omitted entirely |
| Alembic DB unreachable | psql connection refused | Migrations section renders "unknown" with the connection error in tooltip; no upgrade button |
| Alembic current == heads | DB up-to-date | Migrations section renders "up-to-date" (green) |
| Alembic upgrade triggered while DB out of reach | endpoint failure | Endpoint returns HTTP 502 with the error; UI shows error toast |
| `projects.toml` malformed when staleness endpoint is hit | TOML parse error | Endpoint returns HTTP 500 with parse error; logs the error; does not affect other dashboard pages |
| Process detected by `docker` and container stopped | container exists but exited | Status `not running` (grey) |
| `pgrep` matches multiple processes whose cwd is in repo_root | ambiguous match | Use the oldest by start time; log a warning |
| Self-restart of dashboard via API | POST to dashboard's own restart_command | Endpoint returns 202 immediately, helper script runs detached, dashboard re-comes-up within ~3s |

## Invariants

1. The feature creates no new DB tables, columns, or migrations.
2. A project with no `[[projects.<id>.services]]` and no `[projects.<id>.alembic]` block produces zero new DOM elements (no panel, no dot, no banner) on any dashboard page.
3. Staleness detection only ever inspects the project's main worktree (cwd cross-check ensures processes from agent worktrees are ignored).
4. Process restart endpoints reject duplicate invocations within a 5-second window per `(project_id, service_name)` tuple.
5. The Alembic upgrade endpoint runs `alembic upgrade head` only against the DB resolved from the configured `db_url_env` — or, when `db_url_env` is omitted, from the parent process's existing environment — never against any other DB.
6. `projects.toml` is re-read from disk on every staleness computation; no in-memory caching of staleness results.
7. The Migrations section is rendered above the Services section whenever both exist.
8. The red dot lights up red if and only if at least one service is `stale` or the alembic head check is `stale`. "Not running" (grey) does not contribute.
9. Confirmation dialogs are presented before every action that runs a configured command (restart, start, stop, alembic upgrade).
10. The dashboard self-restart endpoint never blocks waiting for the new process to come up — it spawns the helper script detached and returns immediately.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests**:
  - `tests/unit/staleness/test_config.py` — parsing variants (all four `detect` types, missing fields, hot_reload flag, watch_paths/ignore_paths globs, command optionality)
  - `tests/unit/staleness/test_detection.py` — port/pidfile/docker/pgrep with mocked `/proc`, mocked `ss` output, mocked `docker inspect`, cwd-outside-repo rejection, multiple-match warning, stale pidfile
  - `tests/unit/staleness/test_git_lookup.py` — commit-at-time picks the right commit; path-filtered log matches gitignore-style includes and `:(exclude)` patterns
  - `tests/unit/staleness/test_alembic_check.py` — current vs heads comparison; multiple unapplied revisions list; current matches heads → up-to-date
  - `tests/unit/staleness/test_service.py` — orchestrator behavior: missing config returns empty result; stale service produces commits list; alembic stale produces revisions list; combined ordering (alembic first)
- **Integration tests**:
  - `tests/dashboard/test_staleness_router.py` — panel fragment renders for project with services declared; dot fragment renders red when stale; restart endpoint invokes subprocess with the configured command; 5s soft-lock returns 429 on second POST; 404 for unknown project
- **Edge cases** (each row in Boundary Behavior table maps to a test): malformed projects.toml; alembic DB unreachable; service detected but not running; hot_reload skips warnings; cross-worktree process correctly ignored; self-restart endpoint returns 202 quickly.

## Notes

- **Why no DB schema changes**: every piece of information needed (process identity, start time, current commit, alembic head) is observable from outside the project at compute time. Caching introduces invalidation complexity for no measurable benefit at this scale.
- **15s polling cadence**: trades freshness vs load. Each poll runs N small `git log` invocations and N `/proc` reads — well under 100ms total per project. With 3 projects on the list page that's < 50 ms/sec average load.
- **Why `start_new_session=True`** when invoking restart commands: matches the existing `daemon_control.py` pattern so the spawned process survives the parent FastAPI worker restart.
- **Why a separate helper script** for dashboard self-restart: a process cannot cleanly kill-and-respawn itself in-process. The helper script (~15 lines of bash) is detached via `setsid`, sleeps to let the HTTP response flush, then kills the old PID and starts the new one.
- **Hot-reload handling**: services running under `uvicorn --reload`, vite, nodemon, etc. self-reload on file change and don't need restart. Setting `hot_reload = true` skips the warning entirely for those services. Default is `false`.
- **`pgrep` ambiguity**: when multiple processes match (rare in a dev box but possible), pick the one with the oldest start time (assumed to be the canonical long-running service) and log a warning. The user can always switch to `port` or `pidfile` detection for unambiguous results.
- **No version-2 polling-back after restart**: deferred per design discussion. User trusts the 15s auto-refresh to surface the new state.
- **Alembic against per-worktree DBs**: out of scope. Only the main DB resolved by `db_url_env` (or, when omitted, the parent process's existing environment) is monitored.
