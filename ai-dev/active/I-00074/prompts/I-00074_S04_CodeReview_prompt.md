# I-00074_S04_CodeReview_prompt

**Work Item**: I-00074 — PDF Export Missing Diagram Labels
**Step**: S04 (Tests Review)
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00074/I-00074_Issue_Design.md` — acceptance criteria, bug description
- `tests/dashboard/test_docs_pdf_chromium.py` — tests written in S03
- `ai-dev/work/I-00074/reports/I-00074_S03_tests_report.md` — S03 report

## Output Files

- `ai-dev/work/I-00074/reports/I-00074_S04_code_review_report.md` — findings with severities

## Review Checklist

### Critical checks (block merge if failed)

- [ ] **Reproduction test exists**: `test_i00074_render_pdf_chromium_exists` is present
  and would FAIL if `render_pdf_chromium` were missing from `markdown.py`
- [ ] **WeasyPrint not-called check**: At least one test verifies WeasyPrint is NOT called
  (e.g., by asserting `render_pdf_chromium` mock was called, or by patching weasyprint
  and asserting it was not invoked)
- [ ] **Semantic correctness**: Tests assert SPECIFIC values, not just response shape:
  - BAD: `assert response.status_code == 200` alone
  - GOOD: `assert response.content == fake_pdf` (exact bytes)
  - GOOD: `mock_render.assert_called_once()` (verifies Chromium path taken)
  - GOOD: `assert fn is render_pdf_chromium` (exact function identity)
- [ ] **503 status code**: T7 asserts `status_code == 503` (not 501 or 500) when Chromium
  is unavailable — this specifically verifies WeasyPrint's 501 error code is gone
- [ ] **Test file in correct location**: `tests/dashboard/test_docs_pdf_chromium.py`
  (NOT `tests/unit/` or `tests/integration/` — `client` fixture only in `tests/dashboard/`)

### High checks

- [ ] **All 3 call-sites covered**: Tests cover `docs_pdf_view`, `docs_pdf`, and
  `_make_render_pdf_fn()` separately
- [ ] **`render_pdf_chromium` unit tests**: Binary missing → None; subprocess fails → None;
  **subprocess timeout → None** (TimeoutExpired must be coerced, not raised);
  success → bytes; `--print-to-pdf` flag verified
- [ ] **No test imports WeasyPrint**: Tests should not import or reference `weasyprint`
  directly (that would make them fragile to WeasyPrint's installation state)
- [ ] **`mock_render.assert_called_once()`** used rather than just asserting response shape

### Medium checks

- [ ] Tests use `monkeypatch` for `_PLAYWRIGHT_CHROME` path override (not environment hacks)
- [ ] `tmp_path` fixture used for fake binary paths (not hardcoded temp paths)
- [ ] `fake_pdf` values are realistic PDF-like bytes (e.g., `b"%PDF-1.4 fake"`) not empty bytes

### Low checks

- [ ] Test function names all start with `test_i00074_` for easy grep/filter
- [ ] No test uses `time.sleep` or similar
- [ ] Test docstrings briefly state the failure scenario and fix expectation

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00074/reports/I-00074_S04_code_review_report.md"
  ],
  "blockers": [],
  "notes": "Review complete. List any CRITICAL/HIGH findings."
}
```
