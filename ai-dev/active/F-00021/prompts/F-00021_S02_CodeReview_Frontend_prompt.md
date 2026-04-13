# F-00021_S02_CodeReview_Frontend_prompt

**Work Item**: F-00021 — Research Panel in AI Dashboard
**Step**: S02
**Reviewing**: S01 Frontend implementation
**Agent**: code-reviewer

---

## Input Files

- `ai-dev/active/F-00021/F-00021_Feature_Design.md`
- `ai-dev/active/F-00021/reports/F-00021_S01_Frontend_report.md`
- All files created/modified in S01

## Output Files

- `ai-dev/active/F-00021/reports/F-00021_S02_CodeReview_Frontend_report.md`

## Context

Review the dashboard Research panel implementation. Focus on correctness of the `DocType.research`
filter, template quality, sidebar navigation, and router registration.

**Repository**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core`

## Files to Review

- `dashboard/routers/research.py`
- `dashboard/templates/research_library.html`
- `dashboard/templates/research_detail.html`
- `dashboard/templates/base.html` (sidebar link addition only)
- `dashboard/app.py` (router registration only)

## Review Checklist

### Correctness

- [ ] List route filters by `DocType.research` — not all docs
- [ ] Detail route guards against non-research docs (returns 404 if `doc.doc_type != DocType.research`)
- [ ] Empty state renders correctly when no research docs exist (no 500)
- [ ] Detail page handles `content = None` gracefully (no 500)
- [ ] Breadcrumb and back link point to `/project/{project_id}/research`

### Pattern Compliance (mirrors docs.py)

- [ ] Same `_get_project_or_404` helper used
- [ ] Same `DocService` methods used (`list_docs`, `get_doc`, `list_doc_versions`)
- [ ] Same `render_markdown` import and usage
- [ ] `HTMLResponse` return type on all routes
- [ ] `templates.TemplateResponse` used correctly

### Sidebar Navigation

- [ ] "Research" link only shown when `current_project` is set
- [ ] Active state correctly highlights when path contains `/research`
- [ ] Link does not interfere with the "Docs" link active state
- [ ] SVG icon is appropriate and correctly sized (`w-4 h-4`)

### Template Quality

- [ ] `{{ content_html | safe }}` used for rendered markdown (XSS safe — content is server-rendered)
- [ ] Status filter and category filter present in library template
- [ ] Empty state has helpful message pointing to `/iw-research` skill
- [ ] Table columns: ID, Title, Category, Status, Created
- [ ] Consistent Tailwind CSS classes with existing docs templates

### Router Registration

- [ ] `research.router` imported and registered in `app.py`
- [ ] Router registered after `docs.router` (maintain ordering)

### Security

- [ ] No user-supplied content rendered without sanitization
- [ ] `doc_id` from URL is validated by DB lookup (not blindly trusted)

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview_Frontend",
  "work_item": "F-00021",
  "completion_status": "complete",
  "verdict": "PASS|NEEDS_FIX",
  "findings": {
    "critical": 0,
    "high": 0,
    "medium_fixable": 0,
    "medium_suggestion": 0,
    "low": 0
  },
  "mandatory_fix_count": 0,
  "finding_details": [],
  "notes": ""
}
```
