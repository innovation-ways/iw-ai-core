# F-00048_S04_CodeReview_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Step Being Reviewed**: S03 (api-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- `ai-dev/work/F-00048/reports/F-00048_S03_API_report.md` -- S03 implementation report
- All files listed in S03 report's `files_changed`:
  - `dashboard/routers/code.py` (extended from F-00046; review only the newly added endpoints and any shared helpers)
  - `tests/integration/test_code_module_routes.py` (new file; `test_code_index_pipeline.py` is NOT in scope)

## Output Files

- `ai-dev/work/F-00048/reports/F-00048_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the API layer implemented in S03 for **F-00048: Code Understanding: Module + Symbol Views**.

Read the design document to understand what was intended. Read the S03 report to understand what was done. Then review all changed files in detail.

## Review Checklist

### 1. Architecture Compliance

- Are the 4 new endpoints present: GET /modules, GET /modules/{module_slug}, POST /modules/{module_slug}/generate, GET /symbol?
- Were the new endpoints added to the **existing** `APIRouter` in `dashboard/routers/code.py` (F-00046)? **A new router instance or a second `include_router` call is a CRITICAL finding** — it will break F-00046's 5 existing endpoints.
- Is `dashboard/app.py` **unchanged**? The router is already registered. A diff in `app.py` is a CRITICAL finding.
- Are the 5 pre-existing F-00046 endpoints untouched (lint, functionality)?
- Are route handlers thin — no business logic in the handler body?
- Does each handler delegate to `orch/rag/` classes (`ModuleGenerator`, `SymbolGenerator`, `parse_modules_from_level1`)?
- Does each handler return an HTML fragment via `templates.TemplateResponse(...)`, NOT `JSONResponse`?
- Is markdown-to-HTML conversion done server-side (via `markdown` package) before rendering? Raw markdown passed through `| safe` is a HIGH finding (XSS + broken rendering).

### 2. Correctness of GET /modules

- Does it look up the Level 1 ProjectDoc using the actual slug pattern used by F-00046's `MapGenerator`? (Grep `orch/rag/mapgen.py` for `slug=` to verify — do NOT accept a guessed pattern.)
- Does it return 404 (not 500) when no Level 1 doc exists?
- Does it render `fragments/code_module_cards.html` with `{modules, project_id, source_doc_slug}`?
- Are all module fields present in the rendered cards: `name`, `path`, `description`, `slug`?

### 3. Correctness of GET /modules/{module_slug}

- Does it find the module entry by matching `slug`?
- Is the 500ms timeout implemented with `asyncio.wait_for(asyncio.shield(task), timeout=0.5)` so the task is NOT cancelled on timeout? A plain `asyncio.wait_for(...)` without `shield` is a HIGH finding — the background work is discarded and the polling loop deadlocks.
- On timeout, is the fragment rendered with `generating=True` and a `hx-trigger="load delay:2s"` polling element?
- When generation completes within timeout, does the fragment receive `doc_html` (server-rendered HTML), `was_cached`, `generating=False`?
- Is `CodeUnderstandingConfig` built from `project.config.get("code_understanding", {})`?

### 4. Correctness of POST /modules/{module_slug}/generate

- Does it delete the existing cached ProjectDoc before generating (not just call generate)?
- Does it call `generate_level2()` directly (not `get_or_generate()`)? This is the key invariant.
- Does it render the same `fragments/code_module_detail.html` as GET with `was_cached=False`?

### 5. Correctness of GET /symbol

- Is `file_path` query parameter required (not optional)?
- Is `symbol_name` query parameter optional (defaults to None)?
- Is path traversal validation in place: rejects paths starting with `/` or `\`, containing `..` segments?
- Does it render `fragments/code_symbol_panel.html` with `{explanation_html, file_path, symbol_name}`?
- Is `explanation_html` the result of `markdown.markdown(...)` on the LLM response (not raw markdown)?
- Does it return 404 if the project is not found?

### 6. Code Quality

- Are HTTPException used correctly (correct status codes for each error type)?
- Is async/await used correctly throughout?
- Are type annotations present on all handler parameters and return types?
- Is there any business logic (markdown parsing, LanceDB access, Ollama calls) in the router? There should not be.

### 7. Security

- Is path traversal prevention in place for the `file_path` query param in GET /symbol?
- Are there any hardcoded values (URLs, model names, slugs) that should come from config?
- Are input lengths bounded (excessively long `file_path` or `symbol_name` could cause issues)?

### 8. Testing

- Are all 4 endpoints tested (at least happy path + error path for each)?
- Is path traversal rejection tested?
- Is the 500ms timeout/polling behavior tested?
- Do tests mock only external services (LanceDB, Ollama), not the DB?
- Are tests isolated (no shared state between test functions)?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `uv run pytest tests/integration/test_code_module_routes.py -v` -- new tests must pass
2. Run `uv run pytest tests/integration/test_code_index_pipeline.py -v` -- F-00046's tests must still pass (no regressions in the 5 pre-existing endpoints)
3. Run `uv run pytest tests/unit/ -v` -- no regressions in unit tests
4. Run `uv run ruff check dashboard/routers/code.py tests/integration/test_code_module_routes.py`
5. Run `uv run mypy dashboard/routers/code.py`
6. Report test results accurately in the result contract

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00048",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
