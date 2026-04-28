# F-00065_S05_Tests_prompt

**Work Item**: F-00065 — Diagram display in code view
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `dashboard/routers/code.py`
- `dashboard/routers/code_ui.py`
- `tests/conftest.py`
- `tests/dashboard/` (existing dashboard tests for convention)

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S05_Tests_report.md`
- `tests/unit/dashboard/test_preprocess_mermaid.py` (new)
- `tests/dashboard/test_code_diagram_endpoint.py` (new)

## ⚠️ I003 Semantic Correctness Warning

**Test intent, not implementation.** Verify that the code does the right thing for the user — not just that methods were called or that internal state matches. Avoid:
- Asserting only on method call counts or mock call signatures
- Mirroring the implementation instead of testing behavior
- Tests that pass because mocks return the "right" value without exercising the real path

Each test must assert something a real user would observe (HTTP status, fragment content, element presence/absence).

## Context

Read `tests/CLAUDE.md`. Dashboard tests use `TestClient` and mock the DB. Unit tests use `monkeypatch`. No live DB connections.

## Requirements

### 1. `tests/unit/dashboard/test_preprocess_mermaid.py`

Test the fixed `_preprocess_mermaid` function.

#### `test_preprocess_mermaid_outputs_pre_tag`
- Input: `"Some text\n\n```mermaid\ngraph TD\n  A --> B\n```\n"`
- Assert output contains `<pre data-lang="mermaid">`
- Assert output does NOT contain `<div class="mermaid">`

#### `test_preprocess_mermaid_preserves_dsl_content`
- Input: `"```mermaid\ngraph TD\n  A --> B\n```"`
- Assert output contains `graph TD` inside the `<pre>` element

#### `test_preprocess_mermaid_no_mermaid_block`
- Input: `"Just some markdown text"`
- Assert output equals input (no transformation)

### 2. `tests/dashboard/test_code_diagram_endpoint.py`

Use `TestClient` with dependency overrides (see existing dashboard test pattern for DB mocking).

#### `test_diagram_endpoint_returns_fragment_when_doc_exists`
- Override DB dependency to return a mock project and a mock `ProjectDoc` with `content="graph TD\n  A --> B"`
- `GET /api/projects/test-proj/code/modules/test-mod/diagram`
- Assert 200
- Assert `"graph TD"` in response text
- Assert `data-lang="mermaid"` in response text

#### `test_diagram_endpoint_returns_empty_state_when_no_doc`
- Override DB to return mock project but `DocService.get_doc` returns `None`
- `GET /api/projects/test-proj/code/modules/test-mod/diagram`
- Assert 200
- Assert empty-state indicator in response (e.g., "No diagram yet" text or the CSS class `code-diagram-empty`)

#### `test_diagram_endpoint_returns_404_for_unknown_project`
- Override DB to return `None` for project lookup
- `GET /api/projects/unknown/code/modules/test-mod/diagram`
- Assert 404

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — zero errors on touched files
3. `make lint`
4. `make test-unit` — all pass

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/dashboard/test_preprocess_mermaid.py",
    "tests/dashboard/test_code_diagram_endpoint.py"
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
