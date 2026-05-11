# I-00080_S06_CodeReview_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware
**Step Being Reviewed**: S05 (api-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If S05 added an alembic file or a new `project_docs` column, CRITICAL — the cache is supposed to reuse the existing `html_path` / `pdf_path` columns.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design (read **Root Cause Analysis**, **AC2 / AC3**, **TDD Approach**).
- `ai-dev/active/I-00080/reports/I-00080_S05_api-impl_report.md` — S05 report.
- `ai-dev/active/I-00080/reports/I-00080_S03_frontend-impl_report.md` — S03 report (to confirm the `<!-- purpose -->`-comment handling is consistent between S03 and S05 — exactly one of them strips it; server-side in S05 is preferred).
- All files in S05's `files_changed` (expected: `dashboard/routers/docs.py`).
- `dashboard/routers/docs.py` `docs_pdf` route (~line 177-235) — the existing cache pattern S05 should mirror; `orch/doc_service.py:189-213` — `update_doc` NULL-on-content-change behaviour.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S06_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on S05's `files_changed`, report only:
```bash
make lint
make format-check
```
Any NEW violation → CRITICAL (`"category":"conventions"`).

## Review Checklist

1. **`docs_detail` no longer shells out to mmdc** — it passes `render_mermaid=False`; the markdown panel will contain `language-mermaid` `<pre>` blocks, not an mmdc `<svg>`. The page should return promptly.
2. **HTML-view caching** — `docs_html_view`'s fallback branch writes the rendered HTML to `docs/.generated/{project_id}/{doc_id}-v{version}.html` and calls `svc.update_doc(html_path=...)`; a second request serves the cached file (the "prefer pre-generated HTML" branch now matches). The `project` object is properly bound. Cache-write failures are caught (no 500). The cached HTML keeps `render_mermaid=True` (self-contained file needs the inline SVG). **Version keying**: the filename embeds `v{version}` and `update_doc` NULLs `html_path` on content change → a regenerated doc gets a fresh render. Confirm this chain holds.
3. **PDF-view: no bare 503, and cached** — when `render_pdf_chromium` returns `None`, the route returns HTTP **200** with an HTML "PDF unavailable" body (not `HTTPException(503)` → blank iframe). When it returns bytes, they're written to `docs/.generated/{project_id}/{doc_id}-v{version}.pdf` and `update_doc(pdf_path=...)` is called. Cache-write wrapped in try/except.
4. **Bare-DSL `doc_type=diagram` normalisation** — a shared helper (`_normalize_doc_content_for_render` or similar) wraps fence-less `doc_type=diagram` content in a ` ```mermaid ` fence (stripping a leading `<!-- … -->` line), is idempotent, only touches `doc_type=diagram` docs without an existing fence, does no DB I/O, and is called from `docs_detail`, `docs_html_view`, `docs_pdf_view`, `docs_pdf`, and both `docs_export_*` `render_html_fn` lambdas. It does NOT alter what the doc-generation skills store.
5. **No over-reach** — `render_markdown_with_callouts` / `render_pdf_chromium` unchanged (S01 owns `markdown.py`); templates unchanged (S03 owns those); `docs_pdf` download route changed only to call the normaliser; routers stay thin (helper is small / lives in `dashboard/utils/` if non-trivial).
6. **Latent-path check** — `update_doc` is called with `html_path` / `pdf_path` on routes that previously didn't write the DB on a GET; confirm that's fine (it is — `docs_pdf` already does it) and doesn't break under the read-only / db-guard middleware the dashboard uses for write actions (a GET writing a cache path is not a "write action" gate concern, but verify there's no `write_button_attrs`-style guard that would reject it).
7. **Conventions / quality / security** — matches `docs.py` style; `Path` used consistently; no hardcoded ports/URLs; no secrets; the "PDF unavailable" HTML has no injection (it's static text).

## Test Verification (NON-NEGOTIABLE)

Run targeted dashboard tests for `docs.py` (`uv run pytest tests/dashboard/ -k docs -v`). Report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00080",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
