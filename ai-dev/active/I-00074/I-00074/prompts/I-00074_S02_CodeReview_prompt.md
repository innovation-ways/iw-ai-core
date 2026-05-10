# I-00074_S02_CodeReview_prompt

**Work Item**: I-00074 — PDF Export Missing Diagram Labels
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/I-00074/I-00074_Issue_Design.md` — acceptance criteria and requirements
- `dashboard/utils/markdown.py` — new `render_pdf_chromium()` function
- `dashboard/routers/docs.py` — 3 replaced WeasyPrint call-sites
- `ai-dev/work/I-00074/reports/I-00074_S01_backend-impl_report.md` — S01 implementation report

## Output Files

- `ai-dev/work/I-00074/reports/I-00074_S02_code_review_report.md` — findings with severities

## Review Checklist

### Critical checks

- [ ] All three WeasyPrint call-sites have been replaced:
  - `docs_pdf_view` (inline PDF)
  - `docs_pdf` (download + disk cache)
  - `_make_render_pdf_fn()` (export bundle)
- [ ] No new `from weasyprint import` appears anywhere in `dashboard/routers/docs.py`
- [ ] `render_pdf_chromium` returns `None` on Chromium binary missing — no exception raised
- [ ] `render_pdf_chromium` returns `None` on non-zero Chromium exit code — no exception raised
- [ ] Call-sites convert `None` return to clean HTTP error (503, not 500)
- [ ] `subprocess.run` uses a list (no shell string injection — S602/S603 safe)
- [ ] HTML is written to a temp file under `TemporaryDirectory` — no leftover temp files
- [ ] `--no-sandbox` and `--disable-setuid-sandbox` flags present (required for WSL/Linux headless)

### High checks

- [ ] `render_pdf_chromium` is in `dashboard/utils/markdown.py` (not inlined in the router)
- [ ] `_PLAYWRIGHT_CHROME` constant is reused (not duplicated)
- [ ] `capture_output=True` suppresses Chromium console noise
- [ ] `timeout` parameter has a reasonable default (30s)
- [ ] `concurrent.futures` import removed from `docs.py` if no longer used

### Medium checks

- [ ] `render_pdf_chromium` is imported at module level in `docs.py` (not inside functions)
- [ ] Logger warnings include enough context (path, returncode, stderr excerpt)
- [ ] Function docstring mentions WeasyPrint limitation (WHY comment)
- [ ] Type annotation: `render_pdf_chromium(html_content: str, timeout: int = 30) -> bytes | None`

### Low checks

- [ ] `_make_render_pdf_fn()` body is now a one-liner (`return render_pdf_chromium`)
- [ ] No stray TODO/FIXME comments left in the code
- [ ] `Any` type still imported in `docs.py` for `_make_render_pdf_fn` return type

## Severity Guide

- **CRITICAL**: WeasyPrint still called in any of the 3 call-sites; shell injection risk; temp file leak
- **HIGH**: `None` return not handled as HTTP error; `_PLAYWRIGHT_CHROME` path duplicated
- **MEDIUM**: Missing type annotations; logger message too vague
- **LOW**: Minor style issues, unused imports still present

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00074/reports/I-00074_S02_code_review_report.md"
  ],
  "blockers": [],
  "notes": "Review complete. List any CRITICAL/HIGH findings that block S03."
}
```
