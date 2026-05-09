# CR-00038 S01 — Frontend Implementation Report

## Summary

Implemented three related UX improvements to the docs library page:

1. **Filter bar redesign** — replaced three-row pill/input layout with a single compact row (Type select + Status select + search input)
2. **Running-jobs strip** — added `<div id="docs-running-jobs">` with SSE-backed live job cards between filter bar and doc grid
3. **Generate button fix** — changed `docs_generate` POST response to return a disabled "Queued…" button instead of an infinite-spinner fragment

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/docs_library.html` | Replaced filter bar (lines 47–117) with compact select+input form; added running-jobs strip container |
| `dashboard/templates/fragments/docs_running_jobs.html` | **NEW** — SSE-powered job cards with elapsed timer, cancel button, and cleanup logic |
| `dashboard/routers/docs.py` | Added `docs_running_jobs` endpoint; fixed `docs_generate` to return disabled button + `runningJobsReload` trigger; removed unused `request` param |
| `dashboard/static/styles.css` | No changes needed (`make css` already handled) |

## Files Deleted

- `dashboard/templates/fragments/docs_generate_running.html` — no longer referenced after `docs_generate` fix

## Verification

```
$ make lint
All checks passed!

$ make type-check
Success: no issues found in 233 source files
```

## Notes

- The `docs_running_jobs` endpoint uses `list[dict[str, Any]]` annotation (fixed from `list[dict]` to satisfy mypy)
- CSS custom properties (`--primary`, `--muted-foreground`, etc.) from Tailwind config are used directly — no additional CSS rules appended to `styles.css` as they were not needed after `make css`
- SSE deduplication via `window._docJobSources` prevents connection leaks on htmx-triggered reloads