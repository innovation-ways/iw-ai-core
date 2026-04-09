# dashboard/ — FastAPI Web UI

Real-time visibility and manual controls for the IW AI Core orchestration platform. Port 9900.

## Stack

FastAPI + Jinja2 templates + htmx (AJAX) + Tailwind CDN. **No build step** — Tailwind loaded from CDN.

## Structure

| Path | Purpose |
|------|---------|
| `app.py` | FastAPI app factory, router registration, lifespan |
| `dependencies.py` | `get_db()` dependency — yields DB session per request |
| `routers/` | Route handlers (thin — validation + delegation only) |
| `templates/` | Jinja2 templates (base, pages, components, fragments) |
| `static/` | Static assets |
| `utils/` | Shared dashboard helpers |

## Routers

| Module | Handles |
|--------|---------|
| `project_dashboard.py` | Per-project dashboard home |
| `project_pages.py` | Work item detail, history pages |
| `items.py` | Work item CRUD + status |
| `batches.py` | Batch management |
| `running.py` | Currently running items view |
| `actions.py` | htmx action endpoints (approve, pause, retry) |
| `search.py` | Full-text search |
| `sse.py` | Server-Sent Events for real-time updates |
| `system.py` | Health check, daemon status |
| `projects.py` | Project list/register |

## Templates

```
templates/
├── base.html            # Layout skeleton, htmx/Tailwind CDN includes
├── pages/               # Full-page templates (extend base.html)
├── components/          # Reusable Jinja2 macros/includes
└── fragments/           # htmx partial responses (no full page reload)
```

**htmx pattern**: actions POST to `/actions/*` endpoints that return HTML fragments. The fragment replaces a `hx-target` element in the DOM — no JSON, no JS.

**SSE pattern**: `routers/sse.py` streams `text/event-stream` responses. Frontend listens with `<div hx-ext="sse" sse-connect="/sse/...">`.

## Gotchas

- Routes are thin — business logic belongs in `orch/` layer, not routers
- Templates in `fragments/` must NOT extend `base.html` (they are partial responses)
- Tailwind classes applied via CDN — no purge, no build; avoid dynamic class construction
- `dependencies.py:get_db()` uses `SessionLocal` from `orch.db.session` — same sync ORM as daemon
