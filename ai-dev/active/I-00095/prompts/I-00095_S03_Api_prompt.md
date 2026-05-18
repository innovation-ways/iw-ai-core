# I-00095_S03_Api_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step**: S03
**Agent**: api-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/reports/I-00095_S01_Backend_report.md`
- `orch/auto_merge_aggregator.py` (post-S01)
- `dashboard/routers/auto_merge_ui.py`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S03_Api_report.md`

## Context

S01 added `sort` + `direction` parameters to `list_recent_events` and
raises `ValueError` on invalid values. Route handler must accept these
as query params, validate, and convert errors to 400.

## Requirements

### 1. Extend `auto_merge_events` route signature

In `dashboard/routers/auto_merge_ui.py`, locate `auto_merge_events`
(around lines 138-163). Add:

```python
from typing import Literal

SORT_VALUES = ("created_at", "event_type", "entity_id", "verdict")
DIR_VALUES = ("asc", "desc")

@router.get("/auto-merge/events", response_class=HTMLResponse)
def auto_merge_events(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=0, ge=0),
    type: str | None = Query(default=None),  # noqa: A002
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="created_at"),    # new
    dir: str = Query(default="desc"),            # new  noqa: A002
) -> HTMLResponse:
    if sort not in SORT_VALUES:
        raise HTTPException(status_code=400, detail=f"sort must be one of {SORT_VALUES}; got {sort!r}")
    if dir not in DIR_VALUES:
        raise HTTPException(status_code=400, detail=f"dir must be one of {DIR_VALUES}; got {dir!r}")

    rows, total = agg.list_recent_events(
        db, project_id, page=page, page_size=page_size,
        event_type_filter=type, sort=sort, direction=dir,
    )
    ...
    return _render_fragment(request, "fragments/auto_merge_events_table.html", {
        "request": request, "rows": rows, "total": total, "page": page,
        "page_size": page_size, "has_more": has_more,
        "sort": sort, "direction": dir,   # new — for the template
    })
```

### 2. Use `Literal[...]` ONLY if you also map the FastAPI parameter

FastAPI's `Literal[...]` query parameter typing returns a 422 with a
Pydantic-style error envelope, not a clean 400 with a string message.
For consistency with the existing error patterns in this file (see
`auto_merge_set_config`'s manual `HTTPException`), use plain `str`
parameters and validate manually. Match the existing style.

### 3. Pass sort + direction into the template context

S05 needs to know the current sort to render the chevron on the right
column. Add `"sort": sort, "direction": dir` to the fragment context.

### 4. Do NOT change other route handlers

Out of scope.

### 5. Do NOT touch `auto_merge_set_config`, `auto_merge_event_detail`,
`auto_merge_rollup`, etc.

Those endpoints are unrelated.

## Project Conventions

- `dashboard/CLAUDE.md`: routers are thin; validation + delegation
  only.
- `orch/CLAUDE.md`.
- No `Literal` typing on FastAPI query params for this route (see
  Requirement 2).

## TDD Requirement

API step — behavioural tests live in S07. For your own targeted
verification, run:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "I-00095",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/auto_merge_ui.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — API surface extension; behavioural tests in S07",
  "blockers": [],
  "notes": ""
}
```
