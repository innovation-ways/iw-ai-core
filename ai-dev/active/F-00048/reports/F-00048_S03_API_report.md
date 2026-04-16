# F-00048 S03 API Implementation Report

## Summary

Successfully implemented 4 API endpoints for the Code Understanding Module + Symbol Views feature (F-00048). All tests pass and quality checks are clean.

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `dashboard/routers/code.py` | **Created** | 4 new API endpoints (existing from F-00046, but file didn't exist in merged codebase) |
| `dashboard/app.py` | **Modified** | Registered `code.router` (note: this was required despite instructions saying router was "already registered") |
| `dashboard/templates/fragments/code_module_cards.html` | **Created** | Fragment for module cards grid |
| `dashboard/templates/fragments/code_module_detail.html` | **Created** | Fragment for module detail view |
| `dashboard/templates/fragments/code_symbol_panel.html` | **Created** | Fragment for symbol explanation panel |
| `tests/integration/test_code_module_routes.py` | **Created** | Integration tests for all 4 endpoints (15 tests) |

## Endpoints Implemented

### GET /api/projects/{project_id}/code/modules
- Lists all modules parsed from the Level 1 architecture doc
- Returns 404 HTML fragment if no Level 1 doc exists
- Returns HTML fragment with module cards grid

### GET /api/projects/{project_id}/code/modules/{module_slug}
- Gets or generates Level 2 module detail
- Uses 500ms timeout with `asyncio.shield` for generation
- Returns generating fragment with polling marker on timeout
- Returns cached/fresh badge in response

### POST /api/projects/{project_id}/code/modules/{module_slug}/generate
- Force regenerates Level 2 module doc, bypassing cache
- Deletes existing doc via DocService, then calls `generate_level2` directly

### GET /api/projects/{project_id}/code/symbol
- Explains a file or symbol using SymbolGenerator
- Validates path traversal (rejects `..`, absolute paths)
- Returns 400 on invalid input, 404 if project not found
- Returns HTML fragment with markdown-rendered explanation

## Test Results

- **15 new tests passed** (0 failed)
- **745 unit tests passed** (0 failed)
- **F-00046 regression tests**: 5 passed (no regressions)

## Quality Checks

- `uv run ruff check dashboard/routers/code.py`: All checks passed
- `uv run mypy dashboard/routers/code.py`: No issues found

## Notable Issues/Observations

1. **Router registration**: The step instructions stated `dashboard/routers/code.py` "already exists" from F-00046 and was "already registered in app.py". In reality, F-00046 created `dashboard/routers/code_ui.py` (different file with different URL prefix `/project/{project_id}`). The new endpoints required a new router with prefix `/api/projects/{project_id}/code`. I created `code.py` and registered it in `app.py`.

2. **Templates**: The step instructions said S05 (frontend-impl) would create `code_module_cards.html`, `code_module_detail.html`, and `code_symbol_panel.html`. For the API tests to pass, I created minimal placeholder templates. S05 will replace these with full implementations.

3. **`_make_slug` usage**: `ModuleGenerator._make_slug` is a private method. Used via `# noqa: SLF001` since there's no public alternative and it's needed for slug computation.

4. **`asyncio.TimeoutError` → `TimeoutError`**: Fixed ruff UP041 warning by using builtin `TimeoutError`.

## Notes

- All external services (LanceDB, Ollama) are mocked in tests
- All tests use testcontainers (NEVER the live platform DB on port 5433)
- The path traversal validation correctly rejects absolute paths and `..` segments
- The 500ms timeout pattern with `asyncio.shield` ensures background generation continues even if client gives up
