# F-00065_S01_API_prompt

**Work Item**: F-00065 — Diagram display in code view
**Step**: S01
**Agent**: api-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `dashboard/routers/code.py`
- `dashboard/routers/code_ui.py`
- `orch/doc_service.py`
- `dashboard/dependencies.py`

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S01_API_report.md`
- `dashboard/routers/code.py` (modified)
- `dashboard/routers/code_ui.py` (modified)

## Context

You are implementing the API layer for **F-00065: Diagram display in code view**.

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, and the design document. Routers are thin — business logic belongs in `orch/`. Use `DocService` for DB access.

## Requirements

### 1. New endpoint in `dashboard/routers/code.py`

Add to the existing router:

```
GET /api/projects/{project_id}/code/modules/{slug}/diagram
```

- Returns an HTML fragment (`code_module_diagram.html`) via `TemplateResponse`
- Looks up `ProjectDoc` where `doc_id = f"diagram-module-{slug}"` using `DocService(db).get_doc(project_id, f"diagram-module-{slug}")`
- If project does not exist: raise `HTTPException(status_code=404)`
- If diagram doc does not exist (returns None): render fragment with `diagram_dsl=None` (empty state)
- If diagram doc exists: render fragment with `diagram_dsl=doc.content`
- Template variables: `project_id`, `slug`, `diagram_dsl` (str | None)
- Follow the existing pattern in `code.py` for project validation and template responses

### 2. Load architecture diagram in `dashboard/routers/code_ui.py`

In the `code_page` handler (the `GET /code` route) and in the architecture view handler (if there is a separate htmx handler for `code_architecture_view.html`):

- After loading `arch_doc`, also load the architecture diagram doc:
  ```python
  arch_diagram_doc = DocService(db).get_doc(project_id, "diagram-architecture")
  arch_diagram_dsl = arch_diagram_doc.content if arch_diagram_doc else None
  ```
- Pass `arch_diagram_dsl` to the template context for `code_architecture_view.html` and the main code page template

Look at the existing handler carefully — find where `content_html` is generated and add `arch_diagram_dsl` alongside it.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fixes formatting
2. `make typecheck` — zero errors on touched files
3. `make lint` — zero errors

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "api-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code.py",
    "dashboard/routers/code_ui.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
