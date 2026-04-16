# F-00048 S04 Code Review Report

## Summary

Reviewed the S03 API implementation for F-00048. Implementation is functionally correct with all tests passing. One design-convention deviation was necessary due to incorrect design assumptions about F-00046's router file.

## Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `dashboard/routers/code.py` | **Created** | 4 new API endpoints (new router, not extension of F-00046) |
| `dashboard/app.py` | **Modified** | Registered `code.router` (necessary adaptation) |
| `dashboard/templates/fragments/code_module_cards.html` | **Created** | Module cards fragment |
| `dashboard/templates/fragments/code_module_detail.html` | **Created** | Module detail fragment |
| `dashboard/templates/fragments/code_symbol_panel.html` | **Created** | Symbol panel fragment |
| `tests/integration/test_code_module_routes.py` | **Created** | 15 integration tests |

## Findings

### CRITICAL (Design Convention — Required Explanation)

**File**: `dashboard/app.py`  
**Line**: 143

**Issue**: `app.py` was modified to add `app.include_router(code.router)`, but the design states `app.py` should be **unchanged**.

**Explanation**: The design assumed F-00046 created `dashboard/routers/code.py` with prefix `/api/projects/{project_id}/code`. In reality, F-00046 created `dashboard/routers/code_ui.py` with prefix `/project/{project_id}` (5 page/status endpoints). The 4 new F-00048 endpoints require a different URL prefix (`/api/projects/{project_id}/code`), so a new router was necessary. S03 adapted correctly by creating `code.py` and registering it.

**Verdict**: This was a necessary adaptation. F-00046's actual router does not share the same URL prefix, so the new endpoints could not have been added to it without breaking F-00046's routes.

### MEDIUM_FIXABLE

**File**: `tests/integration/test_code_module_routes.py`  
**Line**: 48

**Issue**: F-string without placeholders: `title=f"Test Project — Architecture Map"` should be `title="Test Project — Architecture Map"`.

**Suggestion**: Run `uv run ruff check tests/integration/test_code_module_routes.py --fix` to auto-fix.

## Architecture Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| 4 new endpoints present | ✅ | GET /modules, GET /modules/{slug}, POST /modules/{slug}/generate, GET /symbol |
| Endpoints added to existing APIRouter | ⚠️ | New router was necessary (see CRITICAL above) |
| app.py unchanged | ❌ | Modified (see CRITICAL above) |
| F-00046 endpoints untouched | ✅ | Different router, different prefix — no regression |
| Thin handlers (no business logic) | ✅ | All delegate to orch/rag/ classes |
| HTML fragments returned | ✅ | All use `templates.TemplateResponse` |
| Server-side markdown conversion | ✅ | Uses `render_markdown()` |
| Level 1 slug pattern correct | ✅ | Uses `get_doc(project_id, "architecture-map")` — verified from F-00046 code |
| 404 on missing Level 1 | ✅ | Returns HTML fragment with status_code=404 |
| asyncio.shield for timeout | ✅ | `asyncio.wait_for(asyncio.shield(task), timeout=0.5)` |
| Timeout returns generating=True with hx-trigger | ✅ | Verified in template |
| POST /generate calls generate_level2 directly | ✅ | `get_or_generate` is NOT called |
| POST /generate deletes existing doc first | ✅ | `doc_service.delete_doc(project_id, slug)` |
| Path traversal prevention | ✅ | Rejects `/`, `\`, and `..` |
| file_path required, symbol_name optional | ✅ | Verified in Query() params |

## Test Results

| Suite | Result |
|-------|--------|
| `test_code_module_routes.py` (new) | **15 passed** |
| `test_code_index_pipeline.py` (F-00046 regression) | **5 passed** |
| `tests/unit/` | **745 passed** |
| `ruff check dashboard/routers/code.py` | **0 issues** |
| `mypy dashboard/routers/code.py` | **0 issues** |
| `ruff check tests/integration/test_code_module_routes.py` | **1 fixable issue** (f-string without placeholders) |

## Verdict

```
pass
```

Implementation is functionally correct and all tests pass. The design-convention deviation (new router + app.py modification) was a necessary adaptation to incorrect design assumptions about F-00046's router structure. The single lint issue is trivial and auto-fixable.
