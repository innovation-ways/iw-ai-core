# CR-00006 S03 — API Implementation

## Input Files

- `CLAUDE.md` and `dashboard/CLAUDE.md` — FastAPI/Jinja2/htmx conventions
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md` — source of truth
- `orch/jobs/aggregator.py` — the read-only service built in S01 (used by these routes)
- `dashboard/routers/project_pages.py:238-282` — reference pattern for a project-scoped list/filter page
- `dashboard/routers/sse.py:22-135` — toast event type + severity map (must be extended)
- `dashboard/app.py` — app factory / router registration (must register the new router)
- `dashboard/dependencies.py` — `get_db()` dependency

## Output Files

- **New**: `dashboard/routers/jobs_ui.py` — Jobs list page, detail page, and filter fragment endpoints
- **Modified**: `dashboard/routers/sse.py` — add `code_map_completed` to `_TOAST_EVENTS` and `_TOAST_SEVERITY`
- **Modified**: `dashboard/app.py` — register the `jobs_ui` router

## Context

**Work item**: CR-00006
**Step**: S03
**Agent**: api-impl

You are adding three new routes that surface the `JobsAggregator` to the dashboard, and you are adding `code_map_completed` to the SSE toast map so the event inserted in S01 becomes a visible toast.

## Task 1: Create `dashboard/routers/jobs_ui.py`

### Routes

```
GET /project/{project_id}/jobs
GET /project/{project_id}/jobs/fragment/table
GET /project/{project_id}/jobs/{job_type}/{job_id}
```

### `GET /project/{project_id}/jobs`

Full page. Renders `pages/project/jobs.html` (created in S05 — template does not exist yet but the route must reference it). Context passed to template:

```python
{
    "current_project": project,
    "rows": result.rows,
    "total": result.total,
    "page": result.page,
    "page_size": result.page_size,
    "type_filter": types,
    "status_filter": statuses,
    "date_from": date_from or "",
    "date_to": date_to or "",
    "sort_by": sort_by,
    "sort_dir": sort_dir,
    "job_types": [t.value for t in JobType],
    "job_statuses": ["queued", "running", "completed", "failed", "cancelled"],
}
```

Query parameters (all optional):
- `type` — repeatable (`?type=code_mapping&type=batch_execution`), maps to `JobType[]`
- `status` — repeatable
- `date_from` — ISO date (YYYY-MM-DD)
- `date_to` — ISO date
- `page` — int ≥ 1, default 1
- `sort_by` — one of `started_at|finished_at|status|job_type`, default `started_at`
- `sort_dir` — `asc|desc`, default `desc`

Validation:
- Unknown `type` or `status` values → HTTP 422 (let FastAPI/Pydantic enforce via `Literal`/enum query typing).
- `page < 1` → HTTP 422.
- Missing project → HTTP 404 with `"detail": "Project not found"` (reuse the existing `_get_project_or_404` pattern used in `code_ui.py:32-36`).

### `GET /project/{project_id}/jobs/fragment/table`

Same query params. Returns **only** the `fragments/jobs_table.html` fragment (headers + rows + pagination). Used by htmx when filters change. Do NOT extend `base.html` (see `dashboard/CLAUDE.md` — fragments must not extend base).

### `GET /project/{project_id}/jobs/{job_type}/{job_id}`

`job_type` is a path param typed as a `Literal["code_mapping", "doc_generation", "batch_execution", "research"]` (FastAPI will 422 on invalid values). `job_id` is an arbitrary string.

Calls `JobsAggregator.get_job(...)`. If `None`, raise HTTPException(404). Otherwise render `pages/project/job_detail.html` with:

```python
{
    "current_project": project,
    "job": job_row,  # the JobRow dataclass
    "raw": job_row.raw,  # convenience for template
}
```

### Route registration

Create an `APIRouter` with `prefix="/project/{project_id}"` (matches `code_ui.py`). In `dashboard/app.py`, register it:

```python
from dashboard.routers import jobs_ui
app.include_router(jobs_ui.router)
```

Add the import next to the other router imports, alphabetically. Call `include_router` next to the others.

### Skeleton

```python
"""Jobs view router — unified list of async background operations."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from dashboard.dependencies import get_db
from orch.db.models import Project
from orch.jobs.aggregator import JobsAggregator, JobType

router = APIRouter(prefix="/project/{project_id}")


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _parse_date(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, detail=f"Invalid {field}: {value}") from exc


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    project_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    type: Annotated[list[JobType] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    sort_by: Literal["started_at", "finished_at", "status", "job_type"] = "started_at",
    sort_dir: Literal["asc", "desc"] = "desc",
) -> Any:
    project = _get_project_or_404(project_id, db)
    result = JobsAggregator(db).list_jobs(
        project_id=project_id,
        types=type,
        statuses=status,
        date_from=_parse_date(date_from, "date_from"),
        date_to=_parse_date(date_to, "date_to"),
        page=page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/jobs.html",
        {
            "current_project": project,
            "rows": result.rows,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "type_filter": [t.value for t in (type or [])],
            "status_filter": status or [],
            "date_from": date_from or "",
            "date_to": date_to or "",
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "job_types": [t.value for t in JobType],
            "job_statuses": ["queued", "running", "completed", "failed", "cancelled"],
        },
    )


@router.get("/jobs/fragment/table", response_class=HTMLResponse)
def jobs_fragment_table(
    project_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    # (same query params as jobs_page)
    ...,
) -> Any:
    # same body but renders "fragments/jobs_table.html"
    ...


@router.get(
    "/jobs/{job_type}/{job_id}",
    response_class=HTMLResponse,
)
def job_detail(
    project_id: str,
    job_type: Literal["code_mapping", "doc_generation", "batch_execution", "research"],
    job_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Any:
    project = _get_project_or_404(project_id, db)
    row = JobsAggregator(db).get_job(
        project_id=project_id,
        job_type=JobType(job_type),
        job_id=job_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/job_detail.html",
        {"current_project": project, "job": row, "raw": row.raw},
    )
```

Fill in the `...` placeholders (the fragment handler is a direct copy of `jobs_page` but renders the fragment template).

## Task 2: Extend the SSE toast map

File: `dashboard/routers/sse.py`

Add `"code_map_completed"` to `_TOAST_EVENTS` (around lines 56-91 — pick the most contextually appropriate group; the lifecycle-events cluster is fine).

Add `"code_map_completed": "success"` to `_TOAST_SEVERITY` (around lines 105-135).

No other events change. No structural refactor of `sse.py`.

## Task 3: Register the new router

File: `dashboard/app.py`

1. Add `from dashboard.routers import jobs_ui` next to the other `dashboard.routers import …` lines.
2. Add `app.include_router(jobs_ui.router)` next to the other `include_router` calls.

Keep import order and registration order consistent with existing style (grep the file first).

## Do NOT do in this step

- Do NOT create templates (`jobs.html`, `job_detail.html`, `jobs_table.html`) — S05 owns those. The routes will 500 on first call until S05 lands; that is expected.
- Do NOT touch `code_qa_panel.html`, `base.html`, `code_job_report.html`, or the sidebar nav.
- Do NOT write tests.

## Verification

```bash
uv run ruff check dashboard/routers/jobs_ui.py dashboard/routers/sse.py dashboard/app.py
uv run mypy dashboard/routers/jobs_ui.py

grep -n "code_map_completed" dashboard/routers/sse.py   # must appear twice
grep -n "jobs_ui" dashboard/app.py                       # must appear twice (import + include)
```

Spin up the app and confirm the route registers (it will 500 on render — that's OK):

```bash
uv run python -c "from dashboard.app import create_app; app = create_app(); print([r.path for r in app.routes if 'jobs' in r.path])"
```

Expected output includes `/project/{project_id}/jobs`, `/project/{project_id}/jobs/fragment/table`, and `/project/{project_id}/jobs/{job_type}/{job_id}`.

## Signal completion

```bash
iw step-done CR-00006 S03 --summary "Added dashboard/routers/jobs_ui.py with list/fragment/detail routes backed by JobsAggregator; extended sse.py toast map with code_map_completed=success; registered jobs_ui router in dashboard/app.py"
```

On failure:

```bash
iw step-fail CR-00006 S03 --reason "<what failed>"
```
