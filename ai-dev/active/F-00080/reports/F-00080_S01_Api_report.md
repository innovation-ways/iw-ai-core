# F-00080 S01 — API Implementation Report

## What was done

Created the help fragment delivery endpoint (`GET /_help/{slug}`) for the contextual help system (F-00080). The endpoint is read-only, has no DB calls, and renders Jinja partials from `dashboard/templates/_partials/help/<slug>.html`.

## Files changed

| File | Change |
|------|--------|
| `dashboard/routers/help.py` | New router — slug allow-list from disk at import time, regex validation, HTMLResponse render |
| `dashboard/app.py` | Registered `help_router` alongside other dashboard routers |
| `tests/dashboard/test_help_router.py` | 5 unit tests (RED first, then GREEN) |

## Implementation notes

- **Slug allow-list** computed once at module import via `_load_allow_list()`, cached in `_ALLOWED_SLUGS`. Directory may not exist yet (S03 creates the fragments) — a one-time WARNING is logged and an empty allow-list is used.
- **Path traversal prevention**: slug validated against `^[a-z][a-z0-9_-]{0,31}$` before any allow-list check. Slugs containing `..` or `/` fail the regex and return 404.
- **No os.path joins on user input**: template name constructed directly as `f"_partials/help/{slug}.html"` — Jinja's loader, not the filesystem, resolves the template.
- **Empty directory edge case**: both the missing-dir and empty-dir cases log the same WARNING once and return 404 for all slugs.

## Test results

```
5 passed, 0 failed
```

All 5 tests pass:
1. `test_valid_slug_in_allow_list_returns_200` — patched allow-list + render fn → 200, text/html
2. `test_unknown_slug_returns_404` — patched allow-list, unknown slug → 404
3. `test_path_traversal_attempt_returns_404` — `../etc/passwd` → 404, body contains no secrets
4. `test_uppercase_slug_returns_404` — `UPPERCASE` → 404 (regex rejects)
5. `test_query_string_ignored` — `?foo=bar` → 200 (query string ignored)

## Preflight

| Gate | Result |
|------|--------|
| `make format` / `make format-check` | ok |
| `make lint` (ruff) | ok |
| `make typecheck` (mypy) | ok |