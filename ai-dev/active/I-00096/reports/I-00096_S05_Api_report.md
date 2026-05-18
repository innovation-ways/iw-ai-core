# I-00096 S05 API Report

## What was done

Added the `all` boolean query parameter to the `GET /project/{project_id}/auto-merge/events` endpoint (`auto_merge_events` route in `dashboard/routers/auto_merge_ui.py`).

**Changes made to `dashboard/routers/auto_merge_ui.py`:**

1. **Added `all` query param** with FastAPI's bool parsing (`alias="all"`) — accepts `?all=1`, `?all=true`, `?all=on` and coerces to `True`.
2. **Forwarded `all` to aggregator** via `include_non_auto_merge=all` argument in the `agg.list_recent_events()` call.
3. **Passed `show_all=all` into the template context** so templates can render the toggle button's active state and propagate the flag through pagination URLs.

## Files changed

- `dashboard/routers/auto_merge_ui.py` — route `auto_merge_events` augmented with `all: bool = Query(default=False, alias="all")`, forwarded to aggregator, and `show_all` added to template context.

## Test results

```
tests/dashboard/test_auto_merge_routes.py -v
37 passed, 0 failed
```

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format` | ok (760 files already formatted) |
| `make typecheck` | ok (Success: no issues found in 255 source files) |
| `make lint` | ok (All checks passed!) |

## Notes

- `show_all` is the template-context name; `all` is the FastAPI query param with builtin-shadowing `# noqa: A002` annotation.
- `tdd_red_evidence = "n/a — API surface extension"` per instructions.
- No other route handlers were modified.