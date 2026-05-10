# I-00074_S05_CodeReview_Final_prompt

**Work Item**: I-00074 — PDF Export Missing Diagram Labels
**Step**: S05
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/I-00074/I-00074_Issue_Design.md` — full design, acceptance criteria
- `dashboard/utils/markdown.py` — `render_pdf_chromium()` implementation
- `dashboard/routers/docs.py` — all 3 replaced call-sites
- `tests/dashboard/test_docs_pdf_chromium.py` — reproduction + regression tests
- `ai-dev/work/I-00074/reports/I-00074_S02_code_review_report.md` — per-agent review S01
- `ai-dev/work/I-00074/reports/I-00074_S04_code_review_report.md` — per-agent review S03

## Output Files

- `ai-dev/work/I-00074/reports/I-00074_S05_code_review_final_report.md` — global findings

## Global Review Checklist

### AC Trace

Verify each acceptance criterion is met:

| AC | Criterion | Verified By |
|----|-----------|-------------|
| AC1 | PDF contains diagram labels (Chromium renders foreignObject) | `render_pdf_chromium` uses `--print-to-pdf`; Chromium supports foreignObject |
| AC2 | WeasyPrint not called for any PDF route | Grep: no `from weasyprint import` in `docs.py`; tests assert mock_render called |
| AC3 | Regression tests exist and pass | `test_docs_pdf_chromium.py` — all tests green in S03 |
| AC4 | Chromium unavailable → clean 503 (not 500/501) | T7 asserts `status_code == 503` |

### Cross-Layer Consistency

- [ ] `render_pdf_chromium` is defined in `markdown.py` (utility layer) — not inlined in router
- [ ] All 3 call-sites in `docs.py` call the same function (no divergent implementations)
- [ ] `_PLAYWRIGHT_CHROME` constant used consistently (not copy-pasted path string in router)
- [ ] `_make_render_pdf_fn()` returns `render_pdf_chromium` directly (no wrapper factory)

### WeasyPrint Removal Completeness

- [ ] `grep -n "weasyprint" dashboard/routers/docs.py` returns zero lines
- [ ] `grep -n "weasyprint" dashboard/utils/markdown.py` returns zero lines
- [ ] `concurrent.futures` import removed from `docs.py` if no other use

### Test Quality

- [ ] Reproduction test (`test_i00074_render_pdf_chromium_exists`) is a genuine RED→GREEN test
- [ ] Tests use `mock_render.assert_called_once()` (not just shape checks on response)
- [ ] `_make_render_pdf_fn` identity test asserts `fn is render_pdf_chromium` (exact object)
- [ ] 503 status test explicitly checks `status_code == 503` (semantic: verifies old 501 gone)

### Security

- [ ] `subprocess.run` uses a list (not a shell string) — S602 safe
- [ ] No `shell=True` anywhere in `render_pdf_chromium`
- [ ] HTML content is written to a temp file and passed as `file://` URL — not piped to stdin
- [ ] `TemporaryDirectory` ensures cleanup — no persistent temp files in `/tmp`

### Error Handling

- [ ] Binary missing → `None` (logged as WARNING, not raised as exception)
- [ ] Non-zero exit code → `None` (logged with rc + stderr excerpt)
- [ ] Subprocess timeout / FileNotFoundError → `None` (caught in try/except; mirrors
  `dashboard/utils/markdown.py:218` mmdc pattern; route returns 503 not 500)
- [ ] Missing PDF output file → `None` (covers case where Chromium exits 0 but doesn't write)
- [ ] All four `None` return cases handled in each call-site as appropriate HTTP error

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00074/reports/I-00074_S05_code_review_final_report.md"
  ],
  "blockers": [],
  "notes": "Global review complete. All 3 call-sites replaced; AC trace satisfied; no WeasyPrint remaining."
}
```
