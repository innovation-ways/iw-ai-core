# CR-00042_S02_CodeReview_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — acceptance criteria and requirements
- `dashboard/routers/system.py` — new `/system/docs/{doc_slug}` route
- `dashboard/routers/help.py` — `_SLUG_TO_DOC` dict and context injection
- `dashboard/templates/pages/system/docs_view.html` — new template
- `tests/dashboard/test_system_docs_route.py` — new tests
- `ai-dev/active/CR-00042/reports/CR-00042_S01_backend-impl_report.md` — S01 implementation report

## Output Files

- `ai-dev/active/CR-00042/reports/CR-00042_S02_code_review_report.md` — findings with severities

## Review Checklist

### Critical checks

- [ ] `GET /system/docs/{doc_slug}` returns HTTP 200 for a valid slug
- [ ] `GET /system/docs/{doc_slug}` returns HTTP 404 for an unknown slug (not in allow-list)
- [ ] Slug is validated against `re.compile(r'^[A-Za-z0-9_]+$')` — no `.`, `/`, `%`, or `..` permitted
- [ ] File path is constructed as `REPO_ROOT / "docs" / f"{doc_slug}.md"` — not from user input directly
- [ ] Allow-list is built from the actual `docs/` directory at module load time — not hardcoded
- [ ] No `shell=True`, no `os.system`, no `subprocess` in the docs route (no exec injection risk)
- [ ] `rendered_html` is wrapped in `markupsafe.Markup` before passing to Jinja2 template context (prevent double-escaping)
- [ ] `_render_help_fragment` signature updated to accept and forward `docs_link`
- [ ] `_SLUG_TO_DOC` covers all 22 slugs matching the 22 help partial filenames

### High checks

- [ ] `_ALLOWED_DOC_SLUGS` is populated at module load (not per-request) for performance
- [ ] Route is registered on the existing `system` router (prefix `/system`) — not a new router
- [ ] `docs_view.html` extends `base.html` and renders `rendered_html` inside `.prose-doc` container
- [ ] `docs_view.html` does NOT define `page_help_slug` (no recursive help button)
- [ ] `markdown.markdown()` called with `extensions=["toc", "tables", "fenced_code"]`
- [ ] Fallback in `get_help_fragment` when slug not in `_SLUG_TO_DOC` (future-proofing)
- [ ] Back button present in template

### Medium checks

- [ ] `doc_title` passed to template is human-readable (underscores replaced with spaces)
- [ ] `REPO_ROOT` is derived from `__file__` (not `os.getcwd()`)
- [ ] Logger warning if `docs/` directory not found at startup
- [ ] Type annotations correct: `doc_slug: str`, return `HTMLResponse`
- [ ] All 22 `_SLUG_TO_DOC` values start with `/system/docs/` (not `/docs/` which is the old broken path)

### Low checks

- [ ] No stray TODO/FIXME left in new code
- [ ] `re` module imported (needed for `_DOCS_SLUG_RE`)
- [ ] `markdown` imported at module level in `system.py`, not inside the handler

## Severity Guide

- **CRITICAL**: Directory traversal possible; missing allow-list validation; `Markup` not used (XSS via rendered content); `_render_help_fragment` not updated (S03 would fail)
- **HIGH**: Route on wrong router; template missing `prose-doc`; docs_link fallback missing
- **MEDIUM**: Non-human-readable title; REPO_ROOT from cwd; missing logger warning
- **LOW**: Style/naming issues; missing imports at module level

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00042/reports/CR-00042_S02_code_review_report.md"
  ],
  "blockers": [],
  "notes": "List any CRITICAL/HIGH findings that must be fixed before S03 proceeds."
}
```
