# I-00074_S01_Backend_report.md

## Step S01 — Backend Implementation

**Work Item**: I-00074 — PDF Export Missing Diagram Labels — WeasyPrint Does Not Support SVG foreignObject
**Agent**: backend-impl
**Step**: S01
**Date**: 2026-05-10

---

## What was done

Replaced WeasyPrint PDF generation with headless Chromium across all three call-sites in `dashboard/routers/docs.py`.

### R1: Added `render_pdf_chromium()` to `dashboard/utils/markdown.py`

Added the new function after the `_PLAYWRIGHT_CHROME` constant (line 38), before `_sanitize_mermaid()`. The function:

- Uses the existing `_PLAYWRIGHT_CHROME` path (Playwright-managed Chromium binary)
- Writes HTML to a temp file and runs Chromium with `--print-to-pdf`
- Returns `bytes | None` — `None` on any failure (binary missing, subprocess error, timeout)
- Logs warnings for all failure modes rather than propagating exceptions
- Uses `tempfile.TemporaryDirectory` for guaranteed cleanup
- Hardens against races between `.exists()` check and `subprocess.run` with `FileNotFoundError` handling

### R2: Replaced 3 WeasyPrint call-sites in `dashboard/routers/docs.py`

**Call-site 1** (`docs_pdf_view`, line 167): Replaced `try/except ImportError → HTML(string=html_content).write_pdf()` with:
```python
pdf_bytes = cast("bytes", render_pdf_chromium(html_content))
if pdf_bytes is None:
    raise HTTPException(status_code=503, detail="PDF generation unavailable — Chromium binary not found")
```
Returns 503 (Service Unavailable) instead of 501 when Chromium is missing.

**Call-site 2** (`docs_pdf`, line 215): Replaced the full `try/except ImportError` + `ThreadPoolExecutor` block with the same pattern, returning 503 JSON response.

**Call-site 3** (`_make_render_pdf_fn()`, line 891): Replaced the nested `render_pdf` closure with direct delegation to `render_pdf_chromium`:
```python
def _make_render_pdf_fn() -> Any:
    return render_pdf_chromium
```

### R3: Removed `concurrent.futures` import

Confirmed the import was only used for the ThreadPoolExecutor in the WeasyPrint call-site. Removed `import concurrent.futures`.

---

## Files changed

| File | Change |
|------|--------|
| `dashboard/utils/markdown.py` | Added `render_pdf_chromium()` after `_PLAYWRIGHT_CHROME` constant |
| `dashboard/routers/docs.py` | Replaced 3 WeasyPrint call-sites; removed `concurrent.futures` import |

---

## Verification results

| Check | Result |
|-------|--------|
| Import check: `from dashboard.utils.markdown import render_pdf_chromium` | OK |
| `make lint` | Passed (ruff + check_templates.py) |
| `uv run mypy dashboard/utils/markdown.py dashboard/routers/docs.py` | Success: no issues found |

---

## Design notes

- `cast("bytes", ...)` is used at both call-sites because mypy (v1.20) cannot narrow `bytes | None` through a `if pdf_bytes is None: raise/return` guard when the variable is assigned from a `bytes | None` return type. The cast is local and documented by the surrounding non-None check.
- `make lint` required quoting the type argument to `cast()` (`cast("bytes", ...)`) per the project's Ruff TC006 rule.
- The `docs_pdf_view` return type is `Response` — the `cast` ensures mypy sees `bytes` at the `Response(content=pdf_bytes)` call site.