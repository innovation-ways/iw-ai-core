# I-00096_S05_Api_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S05
**Agent**: api-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/reports/I-00096_S03_Backend_report.md`
- `dashboard/routers/auto_merge_ui.py`
- `orch/auto_merge_aggregator.py` (post-S03)

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S05_Api_report.md`

## Context

S03 added `include_non_auto_merge` to the aggregator. The route must
accept `?all=1` (or `?all=true`) and pass it through.

## Requirements

### 1. Add `all` query param to `auto_merge_events`

In `dashboard/routers/auto_merge_ui.py:auto_merge_events`, add:

```python
all: bool = Query(default=False, alias="all"),  # noqa: A002 — shadowing builtin
```

(Using FastAPI's bool parsing — `?all=1`, `?all=true`, `?all=on` all
coerce to True.)

Forward to the aggregator:

```python
rows, total = agg.list_recent_events(
    db, project_id, page=page, page_size=page_size,
    event_type_filter=type,
    include_non_auto_merge=all,  # new
    # ...other params if I-00095 has landed
)
```

### 2. Pass `all` into the template context

Templates need to know the current value to render the toggle button's
state and to propagate the flag through filter chip / pagination
URLs:

```python
return _render_fragment(request, "fragments/auto_merge_events_table.html", {
    "request": request,
    "rows": rows,
    "total": total,
    "page": page,
    "page_size": page_size,
    "has_more": has_more,
    "show_all": all,  # new
    # ... any other context from sibling incidents (sort/direction from I-00095)
})
```

S01's template can use `show_all` directly (cleaner than re-reading
the query param in Jinja2).

### 3. Preserve compatibility with manual `?all=1` in URLs

The template uses `request.query_params.get('all')` — make sure the
forwarded URL fragments include `all=1` literally so curl users can
bookmark.

### 4. No change to other route handlers

Out of scope.

## Project Conventions

`dashboard/CLAUDE.md`; routers stay thin.

## TDD Requirement

API step — `tdd_red_evidence = "n/a — API surface extension"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "I-00096",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/auto_merge_ui.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — API surface extension",
  "blockers": [],
  "notes": ""
}
```
