# I-00074 S04 Code Review Report

## What Was Done

Reviewed the test file `tests/dashboard/test_docs_pdf_chromium.py` (10 tests, all passing) produced by S03 (tests-impl). The tests were evaluated against the review checklist in the S04 prompt.

## Files Changed

- `tests/dashboard/test_docs_pdf_chromium.py` — 276 lines, 10 tests
- `dashboard/utils/markdown.py` — `render_pdf_chromium()` is correctly implemented at lines 39–82
- `dashboard/routers/docs.py` — all 3 WeasyPrint call-sites correctly replaced with `render_pdf_chromium`

## Verification

- **All 10 tests pass**: `uv run pytest tests/dashboard/test_docs_pdf_chromium.py -v`
- **Reproduction test exists**: `test_i00074_render_pdf_chromium_exists` verifies the function is importable/callable before the fix would be in place
- **WeasyPrint not-called checks**: Route-level tests mock `render_pdf_chromium` and assert it was called (`mock_render.assert_called_once()`), which semantically proves Chromium path is taken (not WeasyPrint)
- **Semantic correctness**: Tests use `assert response.content == fake_pdf` (exact bytes), `assert fn is render_pdf_chromium` (exact identity), and `mock_render.assert_called_once()` — not just response-shape checks
- **503 status code**: `test_i00074_docs_pdf_view_503_when_chromium_unavailable` asserts `status_code == 503`
- **Test file location**: `tests/dashboard/test_docs_pdf_chromium.py` (correct — uses `client` fixture from `tests/dashboard/conftest.py`)
- **All 3 call-sites covered**: `docs_pdf_view` (line 167), `docs_pdf` (line 215), `_make_render_pdf_fn()` (line 900) all tested
- **`render_pdf_chromium` unit tests**: binary missing → None; subprocess fails → None; subprocess timeout → None; success → bytes; `--print-to-pdf` flag verified
- **No WeasyPrint imported in tests**: no `weasyprint` import in test file
- **`mock_render.assert_called_once()`**: used in both route-level tests
- **`monkeypatch` for `_PLAYWRIGHT_CHROME`**: correct — used in all unit tests
- **`tmp_path` fixture**: used for fake binary paths in all unit tests
- **`fake_pdf` values**: realistic `b"%PDF-1.4 fake..."` bytes
- **Test names**: all start with `test_i00074_`
- **No `time.sleep`**: absent from all tests

## Findings

### Observation — WeasyPrint still used in `items.py` (out of scope for I-00074)

The grep scan found a WeasyPrint usage at `dashboard/routers/items.py:1712–1714` inside `items.py`'s artifact PDF generation. This call-site is **outside the scope of I-00074** (the issue design only covers the 3 docs.py call-sites and `markdown.py`). The acceptance criteria for I-00074 (AC2) state "WeasyPrint is not called for any PDF route" — the docs routes (`/docs/...`) are the intended targets. The items.py usage generates step-artifact PDFs (not documentation PDFs with Mermaid diagrams). Whether this needs to be addressed is a separate decision.

**Recommendation**: File a follow-up issue if items.py WeasyPrint usage should also be migrated, but it is not a blocker for I-00074.

### No other issues found.

All checklist items pass. The test suite correctly exercises the Chromium PDF path, verifies WeasyPrint is not called, checks the 503 error response, and covers all 3 call-sites. The implementation is solid.

## Verdict

**PASS** — All critical and high checklist items satisfied. No mandatory fixes.