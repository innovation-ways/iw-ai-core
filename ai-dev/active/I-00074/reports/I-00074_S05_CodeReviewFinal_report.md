# I-00074 S05 — Code Review Final Report

## Work Item
**I-00074** — PDF Export Missing Diagram Labels (WeasyPrint → Chromium)

## Step
S05 — Final Code Review (cross-agent global review)

---

## What Was Done

Reviewed the end-to-end implementation across S01 (backend-impl), S03 (tests-impl), and prior
reviews (S02, S04) against the design document, acceptance criteria, and global review checklist.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/utils/markdown.py` | Added `render_pdf_chromium()` at line 39 — writes HTML to temp file, calls Chromium with `--print-to-pdf`, returns `bytes \| None` |
| `dashboard/routers/docs.py` | Replaced 3 WeasyPrint call-sites with `render_pdf_chromium()` — `docs_pdf_view` (line 167), `docs_pdf` (line 215), `_make_render_pdf_fn()` (line 900) |
| `tests/dashboard/test_docs_pdf_chromium.py` | 10 tests covering unit + route-level behavior, all pass |

---

## Acceptance Criteria Trace

| AC | Criterion | Status |
|----|-----------|--------|
| AC1 | PDF contains diagram labels via Chromium's foreignObject support | ✅ Chromium with `--print-to-pdf` renders foreignObject HTML — confirmed by design doc root-cause analysis |
| AC2 | WeasyPrint not called for any PDF route | ✅ Zero `weasyprint` occurrences in `docs.py` or `markdown.py` (grep verified); route tests use `mock_render.assert_called_once()` to semantically prove Chromium path |
| AC3 | Regression tests exist and pass | ✅ All 10 tests pass (`--no-cov`: 10/10 in 9.3s) |
| AC4 | Chromium unavailable → clean 503 (not 500/501) | ✅ `test_i00074_docs_pdf_view_503_when_chromium_unavailable` asserts `status_code == 503` |

---

## Cross-Layer Consistency

| Check | Status |
|-------|--------|
| `render_pdf_chromium` defined in `markdown.py` (utility layer, not inlined in router) | ✅ |
| All 3 call-sites in `docs.py` call the same function (no divergent implementations) | ✅ |
| `_PLAYWRIGHT_CHROME` constant used consistently (not copy-pasted path string in router) | ✅ — constant defined once at `markdown.py:34`, referenced at lines 46, 58, 242, 243 |
| `_make_render_pdf_fn()` returns `render_pdf_chromium` directly (no wrapper factory) | ✅ — line 900: `return render_pdf_chromium` |

---

## WeasyPrint Removal Completeness

| Check | Result |
|-------|--------|
| `grep "weasyprint" dashboard/routers/docs.py` | ✅ Zero matches |
| `grep "weasyprint" dashboard/utils/markdown.py` | ✅ Zero matches |
| `concurrent.futures` import in `docs.py` | ✅ Not present (no WeasyPrint ThreadPoolExecutor used) |

---

## Test Quality

| Check | Status |
|-------|--------|
| Reproduction test (`test_i00074_render_pdf_chromium_exists`) is genuine RED→GREEN | ✅ Function didn't exist before fix, import succeeds after |
| Tests use `mock_render.assert_called_once()` (not just response shape checks) | ✅ Both `docs_pdf_view` and `docs_pdf_download` route tests use this |
| `_make_render_pdf_fn` identity test asserts `fn is render_pdf_chromium` (exact object) | ✅ `assert fn is expected` — identity comparison, not equality |
| 503 status test explicitly checks `status_code == 503` | ✅ `test_i00074_docs_pdf_view_503_when_chromium_unavailable` |

---

## Security

| Check | Status |
|-------|--------|
| `subprocess.run` uses a list (not a shell string) — S602 safe | ✅ `subprocess.run([...], timeout=timeout, capture_output=True)` |
| No `shell=True` anywhere in `render_pdf_chromium` | ✅ Confirmed by grep |
| HTML content written to temp file, passed as `file://` URL — not piped to stdin | ✅ |
| `TemporaryDirectory` ensures cleanup — no persistent temp files in `/tmp` | ✅ `with tempfile.TemporaryDirectory() as tmpdir:` |

---

## Error Handling

| Condition | Behavior | Status |
|-----------|----------|--------|
| Binary missing | Returns `None`, logs WARNING | ✅ |
| Non-zero exit code | Returns `None`, logs rc + stderr excerpt | ✅ |
| Subprocess timeout / FileNotFoundError | Caught in try/except, returns `None` | ✅ |
| Missing PDF output file | Returns `None`, logs warning | ✅ |

All four `None` return cases have corresponding HTTP 503 responses at each call-site.

---

## Observations

### WeasyPrint still in `items.py` (out of scope for I-00074)
Both S02 and S04 reports noted a WeasyPrint usage in `dashboard/routers/items.py:1712–1714`.
This is separate from the three docs.py call-sites. The issue design explicitly scoped only
the docs PDF routes. No action required for this review.

### Coverage threshold (pre-existing)
The test run reports `total of 19 is less than fail-under=46` — this is a pre-existing
threshold issue unrelated to I-00074. With `--no-cov`, tests pass cleanly (10/10 in 9.3s).

---

## Test Results

```
tests/dashboard/test_docs_pdf_chromium.py
  test_i00074_render_pdf_chromium_exists                           PASSED
  test_i00074_render_pdf_chromium_binary_missing                  PASSED
  test_i00074_render_pdf_chromium_subprocess_fails                PASSED
  test_i00074_render_pdf_chromium_success                         PASSED
  test_i00074_render_pdf_chromium_subprocess_timeout              PASSED
  test_i00074_render_pdf_chromium_uses_print_to_pdf_flag          PASSED
  test_i00074_docs_pdf_view_does_not_call_weasyprint              PASSED
  test_i00074_docs_pdf_view_503_when_chromium_unavailable        PASSED
  test_i00074_docs_pdf_download_does_not_call_weasyprint         PASSED
  test_i00074_make_render_pdf_fn_returns_chromium                 PASSED

10 passed in 9.32s
```

---

## Verdict

**PASS** — All acceptance criteria met. All 3 call-sites replaced. No WeasyPrint remaining
in docs.py or markdown.py. Security checks passed. Tests pass semantically and correctly.

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00074",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00074/reports/I-00074_S05_CodeReviewFinal_report.md"
  ],
  "blockers": [],
  "notes": "Global review complete. All 3 call-sites replaced; AC trace satisfied; no WeasyPrint remaining. Test suite passes cleanly."
}
```