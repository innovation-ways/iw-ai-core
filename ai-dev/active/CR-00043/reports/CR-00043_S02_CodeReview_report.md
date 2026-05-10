# CR-00043_S02_CodeReview_report.md

## Step: S02
## Agent: code-review-impl
## Work Item: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers

---

## Summary

S01 (backend-impl) added `_resolve_chromium_binary()` to `dashboard/utils/markdown.py`, replacing the hardcoded `chromium-1217` path with a priority-order resolver. The implementation matches the design doc exactly.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/utils/markdown.py` | Added `_resolve_chromium_binary()` helper; updated `_PLAYWRIGHT_CHROME` to be `Path | None`; updated `render_pdf_chromium()` and `_render_mermaid_mmdc()` call sites to handle `None`; updated warning log message |
| (no other files) | `dashboard/routers/docs.py` was **not** modified (AC4 preserved) |

---

## Review Against Design Doc (CR-00043_CR_Design.md)

### AC1 — Env var override wins ✅
`$IW_PLAYWRIGHT_CHROME_PATH` is checked first (step 1). If set but the path doesn't exist, execution falls through to step 2 (glob) and step 3 (which). Exactly as specified.

### AC2 — ms-playwright cache glob resolves regardless of version ✅
Step 2 iterates `ms-playwright-root.iterdir()`, filters `chromium-*` dirs, parses the integer suffix, sorts descending, and returns the `chrome-linux64/chrome` from the highest-numbered directory. Only candidates where the `chrome` file actually exists are returned. The hardcoded `chromium-1217` string is no longer load-bearing.

### AC3 — PATH fallback ✅
Step 3 calls `shutil.which()` for `chromium`, `chromium-browser`, `google-chrome`, `google-chrome-stable` in that order, returning the first match.

### AC4 — Graceful degradation preserved ✅
- `render_pdf_chromium()` returns `None` when `_PLAYWRIGHT_CHROME is None or not exists()`; the warning log now says what was searched.
- `_render_mermaid_mmdc()` sets `PUPPETEER_EXECUTABLE_PATH` only when `_PLAYWRIGHT_CHROME is not None and _PLAYWRIGHT_CHROME.exists()` — Kroki fallback path untouched.
- `dashboard/routers/docs.py` was **not** modified — its 503 contract is intact.

### Subprocess flags unchanged ✅
`render_pdf_chromium()` still uses `--headless --disable-gpu --no-sandbox --disable-setuid-sandbox` (no new flags added).

### Logging on not-found path informative ✅
Warning message: `"Chromium binary not found — PDF generation unavailable (searched IW_PLAYWRIGHT_CHROME_PATH, ms-playwright cache, and PATH)"` — at `warning` level, matching prior behavior.

### DB-import-free ✅
`markdown.py` imports: `logging`, `os`, `re`, `shutil`, `subprocess`, `tempfile`, `Path`, `TYPE_CHECKING`, `markdown`, `bs4`. No DB engine, no `orch.config`, no router imports. `import shutil` is permitted.

### Resolution order exactly as specified ✅
1. `$IW_PLAYWRIGHT_CHROME_PATH` (only if set AND path exists)
2. Newest `~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome`
3. `shutil.which("chromium"|"chromium-browser"|"google-chrome"|"google-chrome-stable")`
4. `None`

---

## Quality Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 666 files already formatted |
| `make type-check` | ✅ Success: no issues found in 240 source files |
| `make test-unit` | ✅ 2722 passed, 4 skipped, 5 xfailed, 1 xpassed |

---

## Notes

- The `chromium-1217` literal still appears in `.playwright/cli.config.json` and elsewhere — per the design doc, that's out of scope for this CR.
- `_PLAYWRIGHT_CHROME` is now `Path | None` (was always a `Path`, including a possibly-nonexistent one). Both call sites handle `None` gracefully.
- The resolution is recomputed once at module import time (not re-resolved on every call) — consistent with the design doc's intent.

---

## Verdict

**PASS** — S01 implementation fully conforms to the CR-00043 design doc. No deviations. No mandatory fixes.

---

## Findings

*(none — all acceptance criteria met)*
