# I-00080 S08 CodeReview — Report

## Step Reviewed: S07 (tests-impl)

## Files Changed (S07)

- `tests/dashboard/test_i00080_docs_diagram_render.py` — 536 lines; tests for client-side diagram render, HTML cache, PDF graceful degradation, PDF download regression
- `tests/unit/test_markdown_mermaid_legibility.py` — 150 lines; S01 tests for enforced dark colour token (1e293b), wrapper div, Kroki fallback, render_mermaid=False preservation

## Pre-Flight Gate Results

### `make lint` ✅
All checks passed (ruff + `scripts/check_templates.py`).

### `make format-check` ✅
```
1 file already formatted
```
No format violations.

---

## Review Checklist

### 1. Reproduction Coverage

| Test | Design Name | Status |
|------|-------------|--------|
| `test_i00080_docs_detail_calls_render_mermaid_false` | Matches `test_i00080_diagram_doc_render_does_not_block_on_mmdc` | ✅ Present — spy captures `render_mermaid=False` |
| `test_i00080_docs_detail_page_contains_mermaid_lib` | Mermaid lib presence on docs page | ✅ Present |
| `test_i00080_raw_dsl_diagram_doc_not_garbled` | Matches `test_i00080_raw_dsl_diagram_doc_renders_as_diagram` | ✅ Present — checks `class="language-mermaid" or class="mermaid"` and absence of DSL-as-heading |
| `test_i00080_html_view_caches_to_html_path_keyed_by_version` | Matches `test_i00080_html_view_caches_to_html_path` | ✅ Now PASSING (was blocked in prior S08) |
| `test_i00080_html_view_does_not_cache_degraded_render` | Degraded render guard | ✅ Present |
| `test_i00080_pdf_view_unavailable_returns_200_with_message_not_503` | PDF unavailable → 200 + message | ✅ Present |
| `test_i00080_pdf_view_caches_on_success` | PDF cache with version key | ✅ Present |
| `test_i00080_pdf_download_still_works` | PDF download Content-Disposition regression | ✅ Present |

### 2. Semantic Correctness of Assertions

**`test_i00080_docs_detail_calls_render_mermaid_false`** (line 136-189):
- Spy on `dashboard.routers.docs.render_markdown_with_callouts` captures `render_mermaid` kwarg ✅
- Asserts `render_mermaid is False` (distinguishes pre-fix True from post-fix False) ✅
- Asserts `status_code == 200` ✅
- Descriptive failure message explains what the bug was ✅

**`test_i00080_docs_detail_page_contains_mermaid_lib`** (line 191-216):
- `"mermaid.min.js" in html` checks library is loaded (template-injected) ✅
- Status code asserted ✅

**`test_i00080_raw_dsl_diagram_doc_not_garbled`** (line 218-282):
- Checks `class="language-mermaid" in html or class="mermaid" in html` — scoped to attribute value, not bare substring ✅
- Checks absence of DSL-as-heading: `re.findall(r"<h2[^>]*>(.*?)</h2>", ...)` then asserts no DSL text in any h2 ✅
- Pre-fix: raw DSL (no fence) passes through markdown → `config:` becomes setext `<h2>`, `graph TD` becomes `<p>`; test correctly detects this ✅

**`test_i00080_html_view_caches_to_html_path_keyed_by_version`** (line 289-329):
- After first request: `"-v3.html" in updated_doc.html_path` ✅
- After second request: `cache_file.exists()` and file path resolves ✅
- No broken assertion on `call_count["renders"] == 0` — the test restructured since prior S08 ✅

**`test_i00080_html_view_does_not_cache_degraded_render`** (line 331-375):
- Degraded HTML (still has `language-mermaid`) → `updated_doc.html_path is None` ✅
- Correct sentinel: presence of unrendered mermaid block means mmdc failed ✅

**`test_i00080_pdf_view_unavailable_returns_200_with_message_not_503`** (line 386-427):
- `status_code == 200` AND `text/html` content-type AND `"unavailable" in html_lower` AND `"pdf" in html_lower` ✅
- NOT `!= 503` — explicit status check ✅

**`test_i00080_pdf_view_caches_on_success`** (line 428-477):
- `"-v4.pdf" in updated_doc.pdf_path` ✅
- `cache_file.exists()` ✅

**`test_i00080_pdf_download_still_works`** (line 483-531):
- `Content-Disposition: attachment` + slug + version in filename ✅

### 3. Tokens Match Reality

| Token | Source of Truth | Test Assertion | Match? |
|-------|----------------|----------------|--------|
| Colour token `1e293b` | S01 report (line 41-43) | `assert "1e293b" in result` in `test_markdown_mermaid_legibility.py:68` | ✅ |
| `render_mermaid=False` | S05 report (line 28) | Spy captures `render_mermaid=False` in `test_i00080_docs_detail_calls_render_mermaid_false` | ✅ |
| "PDF unavailable" wording | S05 report (line 42) | `assert "unavailable" in html_lower and "pdf" in html_lower` | ✅ |
| Version-keyed cache `v{version}` | S05 report (line 35) | `"-v3.html" in updated_doc.html_path`, `"-v4.pdf" in updated_doc.pdf_path` | ✅ |
| Cache dir `docs/.generated/{pid}/` | S05 report (line 35) + code | `cache_file = tmp_path / updated_doc.html_path` (path relative to `repo_root`) | ✅ |

### 4. Test File Location

- `tests/dashboard/test_i00080_docs_diagram_render.py` → `tests/dashboard/` ✅ (route/template-driven, uses `client` fixture)
- `tests/unit/test_markdown_mermaid_legibility.py` → `tests/unit/` ✅ (pure markdown util, no DB)

### 5. Isolation / Determinism

- `db_session` from testcontainer (never live 5433) ✅
- `spy_render` patches `dashboard.routers.docs.render_markdown_with_callouts` at the module namespace where `docs.py` imports it ✅
- `render_pdf_chromium` patched at same location ✅
- mmdc-availability skip only on legibility unit tests (appropriate — they directly call `render_markdown_with_callouts` which shells out to mmdc; the dashboard route tests mock at router level and don't need mmdc) ✅
- `tmp_path` for cache files (no live filesystem side effects) ✅

### 6. No Weakened Assertions

S07 did not soften any assertions. All tests verify specific observable contracts.

---

## Test Results

```
tests/dashboard/test_i00080_docs_diagram_render.py
  TestDocsDetailClientSideDiagram
    test_i00080_docs_detail_calls_render_mermaid_false         PASSED
    test_i00080_docs_detail_page_contains_mermaid_lib          PASSED
    test_i00080_raw_dsl_diagram_doc_not_garbled               PASSED
  TestHtmlViewCaching
    test_i00080_html_view_caches_to_html_path_keyed_by_version  PASSED
    test_i00080_html_view_does_not_cache_degraded_render        PASSED
  TestPdfViewGracefulDegradation
    test_i00080_pdf_view_unavailable_returns_200_with_message_not_503  PASSED
    test_i00080_pdf_view_caches_on_success                    PASSED
  TestPdfDownloadRegression
    test_i00080_pdf_download_still_works                      PASSED

tests/unit/test_markdown_mermaid_legibility.py
  TestMermaidLegibility
    test_mermaid_render_contains_enforced_dark_colour_token   PASSED
    test_mermaid_render_does_not_produce_bare_white_labels    PASSED
    test_mermaid_render_kroki_fallback_also_has_wrapper       PASSED
    test_render_mermaid_false_preserves_raw_block             PASSED

12 passed, 0 failed, 0 skipped
```

---

## Verdict

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "I-00080",
  "step_reviewed": "S07",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "12 passed, 0 failed, 0 skipped",
  "notes": "All tests pass. The prior S08 report identified two issues: (1) format-check failure (now resolved — file is already formatted), (2) blocked html cache test (now passes). All tokens match S01/S05/S03 reality. Test isolation is correct (testcontainer DB, router-level mocks, tmp_path for cache files)."
}
```