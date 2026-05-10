# I-00074 S02 Code Review Report

## Work Item
**I-00074** — PDF Export Missing Diagram Labels

## Step
S02 — Code Review (reviewing S01 backend-impl output)

## Files Changed
- `dashboard/utils/markdown.py` — added `render_pdf_chromium()` function
- `dashboard/routers/docs.py` — replaced 3 WeasyPrint call-sites with `render_pdf_chromium()`

---

## Review Result: ✅ PASS

All critical, high, medium, and low checks pass. No mandatory fixes required.

---

## Critical Checks

| Check | Status | Notes |
|-------|--------|-------|
| All 3 WeasyPrint call-sites replaced | ✅ | `docs_pdf_view` (line 167), `docs_pdf` (line 215), `_make_render_pdf_fn()` (line 900) — all call `render_pdf_chromium` |
| No `from weasyprint import` in `docs.py` | ✅ | Grep confirmed zero occurrences in `dashboard/routers/docs.py` |
| `render_pdf_chromium` returns `None` on missing binary | ✅ | Line 46–50: checks `_PLAYWRIGHT_CHROME.exists()` → returns `None` with warning |
| `render_pdf_chromium` returns `None` on non-zero exit | ✅ | Lines 72–78: checks `result.returncode != 0` → returns `None` with warning |
| Call-sites convert `None` → HTTP 503 | ✅ | `docs_pdf_view` (line 169), `docs_pdf` (line 217) both raise/return 503 |
| `subprocess.run` uses list (no shell) | ✅ | Lines 57–65: list of args, no `shell=True` |
| HTML written to temp file under `TemporaryDirectory` | ✅ | Lines 51–82: all within `with tempfile.TemporaryDirectory()` context |

**CRITICAL security**: `subprocess.run` uses a proper list — no shell injection risk (S602/S603 safe).

---

## High Checks

| Check | Status | Notes |
|-------|--------|-------|
| `render_pdf_chromium` in `dashboard/utils/markdown.py` | ✅ | Function at line 39 in `markdown.py`, imported at module level in `docs.py` line 15 |
| `_PLAYWRIGHT_CHROME` constant reused (not duplicated) | ✅ | Defined once at `markdown.py:34-36`, used at lines 46, 58, 242, 243 |
| `capture_output=True` suppresses Chromium noise | ✅ | Line 67 |
| `timeout` has reasonable default (30s) | ✅ | Parameter `timeout: int = 30` at line 39 |
| `concurrent.futures` removed from `docs.py` | ✅ | Not present in `docs.py` (only in `code_qa.py`) |

---

## Medium Checks

| Check | Status | Notes |
|-------|--------|-------|
| `render_pdf_chromium` imported at module level | ✅ | Line 15: `from dashboard.utils.markdown import render_pdf_chromium` |
| Logger warnings include context | ✅ | Lines 47–49 (path), 73–77 (returncode + stderr), 79–80 (pdf_path) |
| Function docstring mentions WeasyPrint limitation | ✅ | Lines 40–45 explain SVG `<foreignObject>` is why Chromium is used |
| Type annotation correct | ✅ | `def render_pdf_chromium(html_content: str, timeout: int = 30) -> bytes \| None:` |

---

## Low Checks

| Check | Status | Notes |
|-------|--------|-------|
| `_make_render_pdf_fn()` is a one-liner | ✅ | Line 900: `return render_pdf_chromium` |
| No stray TODO/FIXME in changed files | ✅ | Grep found none |
| `Any` type still in `docs.py` for `_make_render_pdf_fn` return | ✅ | `Any` imported at line 8, used for return type annotation on line 899 — correct, needed for the factory pattern |

---

## Additional Observations

### `--no-sandbox` and `--disable-setuid-sandbox` flags ✅
Lines 61–62 confirm both flags are present, required for WSL/Linux headless Chromium.

### Test failure is pre-existing and unrelated
The one failing test `test_skills_sync_is_byte_identical[iw-workflow]` is a pre-existing issue with skill file synchronization — not related to this work item's changes.

### WeasyPrint still used in `items.py`
Grep found a WeasyPrint import in `dashboard/routers/items.py:1712`. This is a **different router** (used for artifact PDF generation), not one of the three `docs.py` call-sites specified in I-00074. The issue design explicitly scoped only the three `docs.py` call-sites.

---

## Quality Gates Run

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make type-check` (mypy) | ✅ Success — no issues in 240 source files |
| `make test-unit` | ⚠️ 1 pre-existing failure unrelated to I-00074 |

---

## Verdict

**S01 backend-impl correctly implemented the fix.** All three WeasyPrint call-sites have been replaced, the new `render_pdf_chromium` function follows the exact signature and logic specified in the design, error handling returns clean 503 responses, and security (shell injection prevention, temp file cleanup) is properly implemented.

No blocking issues found. S03 (tests-impl) can proceed.

---

*Reviewer: code-review-impl*
*Step: S02*
*Date: 2026-05-10