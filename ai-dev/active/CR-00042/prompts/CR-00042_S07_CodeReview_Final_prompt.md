# CR-00042_S07_CodeReview_Final_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step**: S07
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — full design, AC1–AC5
- `dashboard/routers/system.py` — new `/system/docs/{doc_slug}` route
- `dashboard/routers/help.py` — `_SLUG_TO_DOC` dict + context injection
- `dashboard/templates/pages/system/docs_view.html` — new template
- `dashboard/templates/_partials/help/*.html` — 22 updated partials
- `tests/dashboard/test_system_docs_route.py` — new tests
- `tests/dashboard/test_help_router.py` — updated tests
- `ai-dev/active/CR-00042/reports/CR-00042_S02_code_review_report.md` — per-agent review S01
- `ai-dev/active/CR-00042/reports/CR-00042_S04_code_review_report.md` — per-agent review S03
- `ai-dev/active/CR-00042/reports/CR-00042_S06_code_review_report.md` — per-agent review S05

## Output Files

- `ai-dev/active/CR-00042/reports/CR-00042_S07_code_review_final_report.md` — global findings

## Global Review Checklist

### AC Trace

| AC | Criterion | Verified By |
|----|-----------|-------------|
| AC1 | "Open full docs" links resolve to HTTP 200 | `/system/docs/{doc_slug}` route; allow-list populated from `docs/` |
| AC2 | No hardcoded hrefs in 22 partials | `grep -r 'href="/docs/' dashboard/templates/_partials/help/` → 0 results |
| AC3 | Unknown/traversal slugs → 404 | Regex + allow-list validation; tests T2, T3 |
| AC4 | Rendered page contains correct content | T1: body contains rendered HTML heading from the file |
| AC5 | Heading anchors work | T4: `id="` present; `toc` extension active |

### Cross-Layer Consistency

- [ ] `_SLUG_TO_DOC` in `help.py` contains exactly 22 entries, matching the 22 partial filenames
- [ ] All 22 `_SLUG_TO_DOC` values start with `/system/docs/` — none still point to `/docs/` (old broken path)
- [ ] The `code` slug maps to `/system/docs/IW_AI_Core_Architecture` (not `/orch/rag/CLAUDE.md`)
- [ ] The `docs` slug maps to `/system/docs/IW_AI_Core_Dashboard_Design` (not `/docs/implementation/00_INDEX.md`)
- [ ] `_render_help_fragment` passes `docs_link` to Jinja2 context in `help.py`
- [ ] `docs_view.html` extends `base.html` and does NOT set `page_help_slug`

### Security

- [ ] Slug regex `r'^[A-Za-z0-9_]+$'` blocks `.`, `/`, `%`, `-` (dot is critical for traversal)
- [ ] Allow-list built from filesystem (not user input) at module load time
- [ ] File path constructed as `DOCS_DIR / f"{slug}.md"` — user input never joined directly into path
- [ ] `markupsafe.Markup` used on rendered HTML before template context (no XSS from markdown)
- [ ] `subprocess` not used anywhere in new code

### Test Quality

- [ ] Traversal tests cover both raw path segments (`../`) and URL-encoded (`%2F`)
- [ ] `_SLUG_TO_DOC` coverage test uses a set diff (not just length check)
- [ ] Help router test asserts BOTH presence of `href="/system/docs/` AND absence of `href="/docs/` / `href="/orch/` (negative checks anchored to the `href="` prefix — a bare `"/docs/IW_AI_Core"` substring check is a bug, it matches the valid new path)
- [ ] Tests follow project conventions from `tests/CLAUDE.md`

### Completeness

- [ ] Run `grep -r 'href="/docs/' dashboard/templates/_partials/help/` — must show 0 results
- [ ] Run `grep -r 'href="/orch/' dashboard/templates/_partials/help/` — must show 0 results
- [ ] Count files in `dashboard/templates/_partials/help/` that still have a hardcoded `href=` — must be 0

### No Scope Creep

- [ ] No changes to routes outside `system.py` and `help.py` (e.g., no modifications to `docs.py`)
- [ ] No changes to the `docs_detail.html` template (CSS was only read, not edited)
- [ ] No new Python dependencies added

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00042/reports/CR-00042_S07_code_review_final_report.md"
  ],
  "blockers": [],
  "notes": ""
}
```
