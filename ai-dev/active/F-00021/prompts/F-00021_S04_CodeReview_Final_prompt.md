# F-00021_S04_CodeReview_Final_prompt

**Work Item**: F-00021 — Research Panel in AI Dashboard
**Step**: S04
**Agent**: code-reviewer
**Reviewing**: All implementation steps (S01–S03)

---

## Input Files

- `ai-dev/active/F-00021/F-00021_Feature_Design.md`
- `ai-dev/active/F-00021/reports/F-00021_S01_Frontend_report.md`
- `ai-dev/active/F-00021/reports/F-00021_S02_CodeReview_Frontend_report.md`
- `ai-dev/active/F-00021/reports/F-00021_S03_Tests_report.md`

## Output Files

- `ai-dev/active/F-00021/reports/F-00021_S04_CodeReview_Final_report.md`

## Context

Global review of all F-00021 changes. **Repository**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core`

## All Files Changed

| File | Agent |
|------|-------|
| `dashboard/routers/research.py` | S01 Frontend |
| `dashboard/templates/research_library.html` | S01 Frontend |
| `dashboard/templates/research_detail.html` | S01 Frontend |
| `dashboard/templates/base.html` | S01 Frontend |
| `dashboard/app.py` | S01 Frontend |
| `tests/integration/test_dashboard_pages.py` | S03 Tests |

## Global Review Checklist

### Completeness — verify ALL acceptance criteria

- [ ] AC1: Research list page renders + filters — test exists and passes
- [ ] AC2: Research detail page with markdown — test exists and passes
- [ ] AC3: Empty state — test exists and passes
- [ ] AC4: 404 on unknown ID — test exists and passes
- [ ] AC5: Sidebar navigation — verified visually or via page content assertion

### Consistency

- [ ] `research.py` follows `docs.py` pattern exactly (no new patterns introduced)
- [ ] Templates follow the same Tailwind CSS structure as docs templates
- [ ] `DocType.research` filter is applied at the service layer (not in the template or route)

### Security

- [ ] Detail route guards against type mismatch (non-research doc_id → 404)
- [ ] No SQL injection: all queries go through `DocService` / SQLAlchemy ORM
- [ ] `{{ content_html | safe }}` used correctly (content is server-rendered markdown, not user input)

### Full test suite

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/ -x --timeout=300 -q
.venv/bin/python -m ruff check dashboard/ tests/
.venv/bin/python -m mypy dashboard/routers/research.py
```

- [ ] All existing tests pass
- [ ] All 6 new tests pass
- [ ] Zero ruff errors
- [ ] Zero mypy errors

### Boundary coverage

| Boundary | Test Exists |
|----------|-------------|
| No research docs | test_research_library_page_empty |
| Unknown doc_id | test_research_detail_page_not_found |
| Null content | test_research_detail_null_content |
| Non-research doc via research route | test_research_detail_wrong_doc_type_returns_404 |

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_Final",
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
