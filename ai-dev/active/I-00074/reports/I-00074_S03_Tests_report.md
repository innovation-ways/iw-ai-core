# I-00074 S03 Tests Report

## What Was Done

Implemented `tests/dashboard/test_docs_pdf_chromium.py` covering the full test surface for I-00074 (PDF export via Chromium instead of WeasyPrint).

## Files Changed

- `tests/dashboard/test_docs_pdf_chromium.py` — new file with 10 test cases

## Test Results

```
10 passed, 1 warning in 8.22s
```

All 10 tests pass:
- `test_i00074_render_pdf_chromium_exists` — reproduction test (fails before fix, passes after)
- `test_i00074_render_pdf_chromium_binary_missing` — returns None when binary absent
- `test_i00074_render_pdf_chromium_subprocess_fails` — returns None on non-zero return code
- `test_i00074_render_pdf_chromium_success` — returns PDF bytes on success
- `test_i00074_render_pdf_chromium_subprocess_timeout` — returns None on TimeoutExpired (not exception propagation)
- `test_i00074_render_pdf_chromium_uses_print_to_pdf_flag` — semantic: --print-to-pdf, --headless, --no-sandbox all present
- `test_i00074_docs_pdf_view_does_not_call_weasyprint` — route uses Chromium mock
- `test_i00074_docs_pdf_view_503_when_chromium_unavailable` — 503 response when Chromium unavailable
- `test_i00074_docs_pdf_download_does_not_call_weasyprint` — download route uses Chromium mock
- `test_i00074_make_render_pdf_fn_returns_chromium` — factory returns `render_pdf_chromium` (not WeasyPrint wrapper)

## Semantic Correctness

Tests use semantic assertions (proving Chromium path taken) rather than shape-only checks:
- `mock_render.assert_called_once()` — proves `render_pdf_chromium` was called
- `assert response.content == fake_pdf` — proves exact bytes from Chromium mock returned
- `assert "--print-to-pdf=" in flags` — proves correct Chromium flag used
- `assert response.status_code == 503` — proves correct error code (not WeasyPrint's 501)

## Issues Fixed During Implementation

1. `DocStatus.active` → `DocStatus.published` (no `active` value exists; `published` is the correct equivalent)
2. `tier` and `editorial_category` not nullable — added `DocTier.human_authored` and `EditorialCategory.technical`
3. `test_project.repo_root = "/repos"` (non-writable) → new `test_doc_project` fixture with `repo_root="/tmp/test-pdf-proj"`
4. `pdf-view` route URL used `/pdf/view` path instead of Flask-style `/pdf-view` (hyphen, not slash)
5. Route-level tests patch `dashboard.routers.docs.render_pdf_chromium` (the import binding in docs.py), not `dashboard.utils.markdown.render_pdf_chromium`

## Blockers

None. All 10 tests pass.