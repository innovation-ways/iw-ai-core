# dashboard/ — FastAPI Web UI

Real-time visibility and manual controls for the IW AI Core orchestration platform. Port 9900.

## Critical Rules

- **NEVER** invoke docker commands from dashboard code, fixtures, or dev scripts. See `docs/IW_AI_Core_Agent_Constraints.md`. Dashboard tests use TestClient — they never need to touch docker directly.
- **NEVER** run alembic migrations from dashboard routes, services, or tests. Migrations are the daemon's responsibility — agents generate, daemon applies. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Stack

FastAPI + Jinja2 templates + htmx (AJAX) + Tailwind CSS (prebuilt).

## Build step

Dashboard CSS is prebuilt via Tailwind CLI:

```bash
make css
```

This regenerates `dashboard/static/styles.css` from `dashboard/templates/**/*.html` and `dashboard/static/**/*.js`. Run it after editing templates that add new Tailwind classes. The generated file is committed to the repo — fresh clones run without needing `make css`.

## Structure

| Path | Purpose |
|------|---------|
| `app.py` | FastAPI factory, router registration, lifespan (marks orphaned test runs + verifies DB identity) |
| `dependencies.py` | `get_db()` dependency — yields DB session per request |
| `routers/` | Route handlers (thin — validation + delegation only) |
| `templates/pages/` | Full-page templates (extend `base.html`) |
| `templates/components/` | Reusable Jinja2 macros/includes |
| `templates/fragments/` | htmx partial responses (NOT wrapped in `base.html`) |
| `static/` | Static assets |
| `utils/` | Shared dashboard helpers |

## Routers (by concern)

**Core navigation & project selection**
| Module | Handles |
|--------|---------|
| `projects.py` | Project list, project creation modal, nav fragment |
| `project_dashboard.py` | Per-project home (`/project/{id}/`) |
| `project_pages.py` | Per-project queue and history pages |
| `running.py` | System-wide "currently running items" view |
| `system.py` | `/system/status`, `/system/config`, `/system/all-active`, `/system/docs/{doc_path:path}` (serves `docs/**/*.md` + curated `**/CLAUDE.md` files) |
| `healthz.py` | `/healthz/identity` — DB instance identity probe (CR-00014), unauthenticated |

**Work items, batches, actions**
| Module | Handles |
|--------|---------|
| `items.py` | Item detail tabs: overview, design-doc, reports, artifacts, logs, fix cycles, execution report, evidences |
| `batches.py` | Batch list, batch detail, batch diagram (PNG/.drawio) |
| `actions.py` | htmx endpoints: approve / unapprove / cancel (full teardown via `orch.cancel`) / pause / resume / restart / restart-merge / full-restart item; batch approve/pause/resume/cancel (full teardown)/archive; create batch from selection |
| `search.py` | Project-scoped FTS search |
| `sse.py` | `GET /api/stream/events` — server-sent events for live updates |

**Code view** (backed by `orch/rag/`)
| Module | Handles |
|--------|---------|
| `code_ui.py` | `/project/{id}/code` page, index status, architecture map, index/reindex/regen-map/delete-index actions, SSE for index progress |
| `code.py` | `/api/projects/{id}/code/modules`, `.../modules/{slug}`, `.../modules/{slug}/generate`, `.../symbol` (F-00046/F-00048) |
| `code_qa.py` | `POST /api/projects/{id}/code/qa` and `.../qa-with-image` — SSE streaming RAG answers with citations |

**Docs view** (backed by `orch/doc_service.py`, `orch/doc_sections.py`, `orch/doc_diff.py`)
| Module | Handles |
|--------|---------|
| `docs.py` | `/project/{id}/docs` catalog, doc detail, HTML/PDF views and exports, versions, diff (full + per-section + AI summary), stale detection, link validation, lint warnings, IDE tab, type/instance/section editorial guides, DocGenerationJob lifecycle (start/stream/status/panel/cancel) |
| `docs_global.py` | `/docs` (cross-project) + `/api/docs/search` |

**Research view**
| Module | Handles |
|--------|---------|
| `research.py` | `/project/{id}/research` list and detail, HTML-view, search (filters doc_type=research) |

**Frontend-triggered runs**
| Module | Handles |
|--------|---------|
| `tests.py` | `/project/{id}/tests` — launch per category, live log, results (Allure reports), kill run |
| `quality.py` | `/project/{id}/quality` — static analysis / quality gates (same shape as tests, `run_type='quality'`), supports launch-fix mode |

**Operations**
| Module | Handles |
|--------|---------|
| `jobs_ui.py` | `/project/{id}/jobs` — unified job table (code index, doc gen, batches, research) via `orch/jobs/aggregator.py` |
| `worktrees.py` | `/system/worktrees` — git status of all active agent worktrees, commit/prune actions, nav badge |
| `daemon_control.py` | `/system/daemon/{panel,start,stop,restart}` — daemon lifecycle from UI |
| `_run_helpers.py` | Shared helpers for tests/quality routers |

## Health endpoints

`healthz.py` exposes lightweight JSON probes that bypass any auth middleware.

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz/identity` | DB instance-identity check (CR-00014). Returns `{expected, actual, mode, match}`. `200` on match/bootstrap; `503` on mismatch/missing. Intentionally unauthenticated so external probes can reach it. |

Plus `GET /health` registered directly on the app in `app.py:142` — used by browser_verification steps and simple monitoring.

## Patterns

- **Routers are thin** — business logic belongs in the `orch/` layer, not in routers
- **htmx POSTs** to `/actions/*` (work-item-scoped) or `/api/...` (resource-scoped) return HTML fragments that replace a `hx-target` element — no JSON, no JS
- **Fragment templates** under `templates/fragments/` MUST NOT extend `base.html`
- **SSE**: `routers/sse.py` and `routers/code_qa.py` stream `text/event-stream`. Frontend listens with `<div hx-ext="sse" sse-connect="/sse/...">` or a plain `EventSource` for token streams
- Tailwind CSS is prebuilt via `make css` — avoid dynamic class construction that breaks JIT purging
- `dependencies.py:get_db()` uses `SessionLocal` from `orch.db.session` — same sync ORM as daemon
- On app startup (`app.py:_lifespan`): `mark_orphaned_runs()` flips running TestRuns left behind by a crash to status=error, then `verify_instance_identity()` refuses to boot on a DB-identity mismatch

## Clipboard buttons

Use the shared `window.iwClipboard.copy(text, button)` helper from
`dashboard/static/clipboard.js` for every "copy to clipboard" button.
NEVER call `navigator.clipboard.writeText(...)` directly from a template or
static JS file — `navigator.clipboard` is undefined outside secure contexts
(plain HTTP on a non-localhost hostname like `iw-dev-01`), and direct calls
silently throw a `TypeError`. The helper falls back to a textarea +
`document.execCommand('copy')` and surfaces success / failure via the button
label ("Copied" / "Copy failed").
