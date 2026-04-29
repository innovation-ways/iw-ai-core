# F-00067_S07_Backend_IndexPage_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step**: S07
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ No live DB migrations

No schema changes required — existing `ProjectDoc` table stores the index doc.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc (AC5: index page)
- `orch/rag/job.py` — `CodeIndexJob` runner (hook point)
- `orch/rag/mapgen.py` — For reference: how arch diagram is stored
- `orch/doc_service.py` — `DocService.create_doc()` / `update_doc()` patterns
- `orch/db/models.py` — `DocType`, `DocTier`, `EditorialCategory` enums

## Output Files

- `orch/rag/index_gen.py` — New module
- `orch/rag/job.py` — Modified (add index page generation call after code map completion)
- `ai-dev/active/F-00067/reports/F-00067_S07_Backend_IndexPage_report.md`

---

## Context

After a code map generation run, there is no navigable entry point for the generated documentation. This step creates `orch/rag/index_gen.py` — a module that generates a `code-index` ProjectDoc per project, listing all available documentation with section headers and one-line descriptions.

---

## Requirements

### 1. Create `orch/rag/index_gen.py`

Define a function:

```python
def generate_index_page(
    project_id: str,
    session: Session,
) -> None:
    """Generate or update the code-index ProjectDoc for the given project."""
```

The function must:

1. Query all `ProjectDoc` records for the project, grouped by `doc_type`
2. Build a Markdown document with this structure:

```markdown
# Documentation Index — {project_display_name}

<!-- generated: {YYYY-MM-DD} -->

> [!NOTE]
> This index is auto-generated. Click a document to view its full content in the Docs section.

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture Overview](code-map) | High-level system architecture, components, and entry points |
| [Architecture Diagram](diagram-architecture) | Visual component diagram of the full system |

## Module Documentation

| Module | Description |
|--------|-------------|
{for each module doc: | [{title}]({doc_id}) | {first sentence of content or "—"} |}

## Module Diagrams

| Module | Diagram |
|--------|---------|
{for each diagram-module-* doc: | {module name} | [{doc_id}]({doc_id}) |}

## API Reference

{If any doc_type=api docs exist: table of links. Otherwise: "_No API documentation registered yet._"}

## Research

{If any doc_type=research docs exist: table with title + date. Otherwise: "_No research documents._"}
```

3. Store the result using `DocService`:
   - `doc_id = "code-index"`
   - `doc_type = DocType.architecture`
   - `tier = DocTier.fully_automated`
   - `editorial_category = EditorialCategory.technical`
   - `title = f"Documentation Index — {project_id}"`
   - `generated_by = "code-understanding:index_gen"`
   - Use `create_doc()` if the doc doesn't exist, `update_doc()` if it does

4. For the module description, extract the first sentence from `ProjectDoc.content` (strip markdown headers, take the first non-empty paragraph sentence). If content is None, use `"—"`.

### 2. Hook into `orch/rag/job.py`

Locate `CodeIndexJob` runner in `orch/rag/job.py`. After the existing `code_map_completed` event is stored (or at the end of a successful run), add a call:

```python
from orch.rag.index_gen import generate_index_page

# After code map completion
generate_index_page(project_id=project_id, session=session)
```

Wrap in try/except — index page generation failure must NEVER cause the `CodeIndexJob` itself to fail. Log a warning on exception.

### 3. Handle empty project gracefully

If a project has no `ProjectDoc` records at all, generate an index with empty sections and a note:

```markdown
> [!NOTE]
> No documentation has been generated for this project yet. Run "Generate Code Map" from the Code section to get started.
```

---

## Project Conventions

- `DocService` session patterns: follow existing `create_doc()` / `update_doc()` usage in `mapgen.py`
- All DB operations must use the `session` passed in — never create a new session inside `index_gen.py`
- Follow `orch/rag/` module structure: no Flask/FastAPI imports inside `orch/` layer
- Read `orch/CLAUDE.md` for layer boundaries

## TDD Requirement

1. **RED**: Create `tests/unit/test_rag_index_gen.py`:
   - Mock `DocService` and `ProjectDoc` query
   - Assert `generate_index_page()` calls `create_doc()` with `doc_id="code-index"`
   - Assert generated content contains `## Module Documentation`
   - Assert empty project generates content with the "No documentation" note

2. Create `tests/integration/test_rag_index_gen.py`:
   - Use testcontainer DB (see `tests/conftest.py`)
   - Create a project + several ProjectDocs of different types
   - Call `generate_index_page()`
   - Assert the `code-index` doc is created in the DB with valid Markdown content

3. **GREEN**: Implement to pass tests.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "backend-impl",
  "work_item": "F-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/index_gen.py",
    "orch/rag/job.py"
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
