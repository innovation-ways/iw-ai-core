# F-00048_S07_CodeReview_Final_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- All implementation reports:
  - `ai-dev/work/F-00048/reports/F-00048_S01_Backend_report.md`
  - `ai-dev/work/F-00048/reports/F-00048_S03_API_report.md`
  - `ai-dev/work/F-00048/reports/F-00048_S05_Frontend_report.md`
- All per-agent code review reports:
  - `ai-dev/work/F-00048/reports/F-00048_S02_CodeReview_report.md`
  - `ai-dev/work/F-00048/reports/F-00048_S04_CodeReview_report.md`
  - `ai-dev/work/F-00048/reports/F-00048_S06_CodeReview_report.md`
- All files changed across S01, S03, S05:
  - `orch/rag/parser.py`
  - `orch/rag/module_gen.py`
  - `orch/rag/symbol_gen.py`
  - `dashboard/routers/code.py` (extended from F-00046 — review only the 4 new handlers plus any shared helpers; confirm F-00046's 5 pre-existing endpoints are unchanged)
  - `dashboard/templates/fragments/code_module_cards.html`
  - `dashboard/templates/fragments/code_module_detail.html`
  - `dashboard/templates/fragments/code_symbol_panel.html`
  - `dashboard/templates/fragments/code_module_spinner.html`
  - `dashboard/templates/fragments/code_architecture_view.html` (F-00047's file, extended with new containers)
  - All test files created by S01/S03 (`tests/unit/test_module_parser.py`, `tests/unit/test_module_gen.py`, `tests/integration/test_module_gen_integration.py`, `tests/integration/test_code_module_routes.py`)
  - `dashboard/app.py` must be **UNCHANGED** — verify this explicitly

## Output Files

- `ai-dev/work/F-00048/reports/F-00048_S07_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **F-00048: Code Understanding: Module + Symbol Views**.

Per-agent reviews (S02, S04, S06) have already been done. Your job is to look at the complete picture — how all three layers (backend, API, frontend) fit together and catch cross-cutting issues that per-agent reviews could not see.

Read the design document first to understand the full intended scope. Then read all implementation and review reports to understand what was built. Then review all changed files holistically.

## Review Checklist

### 1. Completeness vs Design Document

Verify every requirement in `F-00048_Feature_Design.md` is implemented:

- [ ] `parse_modules_from_level1()` exists in `orch/rag/parser.py` and is pure (no I/O)
- [ ] `ModuleGenerator` in `orch/rag/module_gen.py` with `generate_level2()` and `get_or_generate()`
- [ ] `SymbolGenerator` in `orch/rag/symbol_gen.py` with `explain_symbol()` (never stores ProjectDoc)
- [ ] `GET /api/projects/{project_id}/code/modules` returns parsed module list
- [ ] `GET /api/projects/{project_id}/code/modules/{module_slug}` returns Level 2 doc or `generating: true`
- [ ] `POST /api/projects/{project_id}/code/modules/{module_slug}/generate` force regenerates
- [ ] `GET /api/projects/{project_id}/code/symbol` returns explanation string
- [ ] Module cards fragment renders below Mermaid diagram via htmx
- [ ] Level 2 module detail view with breadcrumb + content + regenerate button
- [ ] Level 3 inline symbol panel with close button
- [ ] Breadcrumb navigation across all three levels
- [ ] All 4 API endpoints registered in `dashboard/app.py`

Flag any missing item as a CRITICAL finding.

### 2. Cross-Layer Integration

- Do the htmx attributes in templates call the correct API endpoint paths from `code.py`?
- Does each endpoint return an HTML fragment via `templates.TemplateResponse(...)` — NOT `JSONResponse`? Any JSON response from the 4 new endpoints is a CRITICAL finding (the templates will not render it).
- Does each rendered template receive the context variables documented in the design?
  - `code_module_cards.html` ← `{modules, project_id, source_doc_slug}`
  - `code_module_detail.html` ← `{project_id, module, doc_html, was_cached, generating}`
  - `code_symbol_panel.html` ← `{explanation_html, file_path, symbol_name}`
- Is markdown-to-HTML conversion done in the **router** (using the `markdown` Python package) before rendering? If `doc.content` or the raw LLM response is passed to the template and marked `| safe` without being converted first, this is a HIGH finding (XSS + broken rendering).
- **Router integration with F-00046**: Are the 4 new endpoints added to F-00046's existing `router` object (no new `APIRouter()` call, no `include_router` in `app.py`)? If a second router was created or `app.py` was edited, this is a CRITICAL finding — F-00046's endpoints will break.

### 3. Module-Scoped LanceDB Filtering

- Does `ModuleGenerator.generate_level2()` correctly filter LanceDB results by `module_path` prefix?
- Is the filter using the LanceDB `where` clause correctly (not post-filtering in Python on the full index)?
- Is this consistent with how `CodeIndexer`/`MapGenerator` access LanceDB (same connection pattern)?

### 4. ProjectDoc Slug Invariant

- Is the slug format `f"{project_id}-module-{module_path.strip('/').replace('/', '-')}"` consistent everywhere?
  - In `ModuleGenerator._make_slug()`
  - In `ModuleGenerator.get_or_generate()`
  - In API endpoint when looking up cached doc
  - In API endpoint when calling regenerate (must delete by same slug)

### 5. Idempotency of get_or_generate()

- Is `get_or_generate()` idempotent in the **sequential** case (two back-to-back calls return the same doc, no duplicate rows)?
- There is **no unique constraint** on `project_docs.slug` (verified in `orch/db/models.py` — accepted in the design's Concurrency Note). Concurrent calls can produce duplicate rows. This is NOT a finding — the design explicitly accepts it. Only flag if the implementation does something worse (e.g., crashes on concurrent write, or `get_by_slug` returns a deterministic-but-wrong row).
- Does the 500ms-timeout path in GET /modules/{slug} use `asyncio.shield` so the background task survives the timeout and eventually writes the doc? Without `shield`, the task is cancelled and subsequent polls deadlock — this IS a CRITICAL finding.

### 6. Symbol Explanation Security

- Does `SymbolGenerator.explain_symbol()` validate `file_path` before reading from disk?
- Is path traversal (e.g., `../../etc/passwd`) possible through this code path?
- Is there a consistent check in BOTH the API layer and the `SymbolGenerator` itself, or only in one?
- Is the max file size bounded to prevent sending huge files to Ollama?

### 7. Test Coverage (Holistic)

- Is `parse_modules_from_level1()` tested with multiple format variations as documented?
- Is the cache hit/miss behavior of `get_or_generate()` tested end-to-end (not just mocked)?
- Is the 500ms timeout behavior tested in the API integration tests?
- Is path traversal rejection tested in API integration tests?
- Are there any integration test scenarios that cross all three layers (backend + API + template rendering)?

### 8. Markdown Rendering Safety

- In `code_module_detail.html`, does the template render `doc_html | safe` (not `doc.content | safe`)?
- In `code_symbol_panel.html`, does the template render `explanation_html | safe` (not `explanation | safe`)?
- In the router, is markdown-to-HTML conversion done via `markdown.markdown(...)` on the Python side BEFORE passing to the template?
- If raw markdown flows through `| safe` anywhere, this is a HIGH finding.

### 9. Architecture Compliance

- Do all fragments in `templates/fragments/` avoid extending `base.html`?
- Are all route handlers thin (no business logic in `dashboard/routers/code.py`)?
- Does `orch/rag/` not import from `dashboard/`?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `uv run pytest tests/unit/ -v` -- ALL unit tests must pass
2. Run `uv run pytest tests/integration/ -v` -- ALL integration tests must pass
3. Run `uv run ruff check .`
4. Run `uv run mypy orch/ dashboard/`
5. If any test fails, this is a CRITICAL finding. Report the failure output.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "F-00048",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: Use `pass` only if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings.
- `missing_requirements`: List any design document requirements with no corresponding implementation. Each is automatically a CRITICAL finding.
- `cross_cutting`: Set to `true` on findings that span multiple agents' work.
