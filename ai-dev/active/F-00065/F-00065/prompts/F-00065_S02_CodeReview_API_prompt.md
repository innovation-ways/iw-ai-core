# F-00065_S02_CodeReview_API_prompt

**Work Item**: F-00065 — Diagram display in code view
**Step Being Reviewed**: S01 (api-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `ai-dev/active/F-00065/reports/F-00065_S01_API_report.md`
- `dashboard/routers/code.py`
- `dashboard/routers/code_ui.py`

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S02_CodeReview_API_report.md`

## Review Checklist

- [ ] New endpoint path matches design: `GET /api/projects/{project_id}/code/modules/{slug}/diagram`
- [ ] Returns 404 for unknown project (not 200 with error state)
- [ ] Returns 200 with empty-state template context (`diagram_dsl=None`) when no diagram doc
- [ ] Uses `DocService` for DB read — no raw SQL
- [ ] Router is thin — no business logic inline
- [ ] `arch_diagram_dsl` is passed to template context in both the main code page handler and any htmx refresh handler for the architecture view
- [ ] Response type is `HTMLResponse` or `TemplateResponse` (not JSON)
- [ ] Preflight gates passed per S01 report

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
