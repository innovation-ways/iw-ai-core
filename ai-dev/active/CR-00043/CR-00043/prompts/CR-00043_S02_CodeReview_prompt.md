# CR-00043_S02_CodeReview_prompt

**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S02
**Agent**: code-review-impl

---

## Task

Review the S01 changes to `dashboard/utils/markdown.py`.

## Source of truth

Read `ai-dev/active/CR-00043/CR-00043_CR_Design.md` first — the design doc is authoritative. Then diff S01's changes against it.

## Review checklist

- **Resolution order is exactly**: `$IW_PLAYWRIGHT_CHROME_PATH` (the **existing** env-var name — not renamed, no new var added; only used if set AND path exists) → newest `~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome` (only candidates whose `chrome` exists; incomplete dirs skipped) → `shutil.which("chromium"|"chromium-browser"|"google-chrome"|"google-chrome-stable")` → `None`. A set-but-nonexistent env path must NOT be returned (fall through).
- `_PLAYWRIGHT_CHROME` is now `Path | None`; both call-sites (`render_pdf_chromium`, `_render_mermaid_mmdc`) handle `None` without raising.
- **Graceful degradation unchanged**: `render_pdf_chromium()` still returns `None` (→ caller 503s) when nothing resolves; `_render_mermaid_mmdc()` simply omits `PUPPETEER_EXECUTABLE_PATH` and the Kroki fallback path is untouched.
- `dashboard/routers/docs.py` was **not** modified (AC4 — its 503 contract is intentional).
- No new import that drags in the DB engine / `orch.config` / `dashboard.routers.*` / `dashboard.dependencies` — `markdown.py` must stay DB-import-free (`tests/CLAUDE.md`). `import shutil` is fine.
- Subprocess flags in `render_pdf_chromium()` are unchanged (`--no-sandbox --disable-setuid-sandbox` etc.).
- Logging on the not-found path is informative (says what was searched) and at `warning` level (matching the prior behavior).
- `make lint`, `make format-check`, `make type-check` pass.

## Output

Produce a review report with severities (CRITICAL / HIGH / MEDIUM / LOW / NIT) and a `mandatory_fix_count`. If S01 deviates from the design doc, that is at least HIGH.

**Do NOT** call `iw step-done` / `iw step-fail`.
