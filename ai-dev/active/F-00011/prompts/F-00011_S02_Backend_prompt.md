# F-00011_S02_Backend_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S02
**Agent**: Backend

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document (read fully)
- `ai-dev/work/F-00011/reports/F-00011_S01_Database_report.md` — S01 report (models created)
- `orch/db/models.py` — New models from S01
- `orch/db/` — Existing repository/service patterns
- `CLAUDE.md` — Project rules

## Output Files

- `orch/services/doc_service.py` — New DocService class (create if `orch/services/` exists, else `orch/doc_service.py`)
- `ai-dev/work/F-00011/reports/F-00011_S02_Backend_report.md` — Step report

## Context

You are implementing the backend service layer for **F-00011: Project-Level Documentation System**.

First, check how other services are structured in the project (look for any `*_service.py` or repository pattern files in `orch/`). Match that pattern exactly. If no service layer exists and logic is inline in CLI commands, create `orch/doc_service.py` at the root of the `orch/` package.

## Requirements

### 1. DocService Class

Create `DocService` as a class that takes a SQLAlchemy `Session` in its constructor. All methods are synchronous (matching existing project patterns — check if async is used before deciding).

```python
class DocService:
    def __init__(self, session: Session) -> None: ...
```

### 2. `create_doc()`

```python
def create_doc(
    self,
    project_id: str,
    doc_id: str,
    title: str,
    doc_type: DocType,
    tier: DocTier,
    editorial_category: EditorialCategory,
    status: DocStatus = DocStatus.planned,
    slug: str | None = None,          # auto-derived from title if None
    audience: list[str] | None = None,
    source_paths: list[str] | None = None,
    content: str | None = None,
    generated_by: str | None = None,
    trigger_reason: str | None = None,
) -> ProjectDoc
```

- Constructs `id = f"{project_id}:{doc_id}"`
- Auto-derives `slug` from `title` using `slugify()` if not provided (use `python-slugify` if available, else manual: lowercase, replace spaces with `-`, strip non-alphanumeric)
- If `content` is provided, creates an initial `ProjectDocVersion` snapshot (version=1) with `trigger_reason`
- Raises `ValueError` if project does not exist (check via `session.get(Project, project_id)`)
- Raises `IntegrityError` (let propagate) if `(project_id, doc_id)` already exists — callers use `update_doc` for updates

### 3. `update_doc()`

```python
def update_doc(
    self,
    project_id: str,
    doc_id: str,
    *,
    title: str | None = None,
    status: DocStatus | None = None,
    tier: DocTier | None = None,
    editorial_category: EditorialCategory | None = None,
    audience: list[str] | None = None,
    source_paths: list[str] | None = None,
    content: str | None = None,
    generated_by: str | None = None,
    html_path: str | None = None,
    pdf_path: str | None = None,
    trigger_reason: str | None = None,
) -> ProjectDoc
```

- Fetches existing `ProjectDoc` by `id = f"{project_id}:{doc_id}"`; raises `KeyError` if not found
- Updates only fields that are not `None` (partial update)
- If `content` is provided AND differs from current `content` (compare by hash: `hashlib.sha256`):
  - Increments `version` by 1
  - Sets `generated_at = datetime.utcnow()`
  - Creates a new `ProjectDocVersion` snapshot
  - Clears `html_path` and `pdf_path` (cached renders are stale after content change) — unless new paths are explicitly provided
- If `content` is provided but identical to current → updates metadata only, NO new version snapshot
- Returns updated `ProjectDoc`

### 4. `upsert_doc()`

Convenience wrapper:

```python
def upsert_doc(self, project_id: str, doc_id: str, **kwargs) -> tuple[ProjectDoc, bool]:
    """
    Returns (doc, created) where created=True if this was a new record.
    """
```

- Tries `get_doc(project_id, doc_id)` first
- If not found → calls `create_doc()`
- If found → calls `update_doc()`

### 5. `get_doc()`

```python
def get_doc(self, project_id: str, doc_id: str) -> ProjectDoc | None
```

### 6. `list_docs()`

```python
def list_docs(
    self,
    project_id: str,
    doc_type: DocType | None = None,
    status: DocStatus | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectDoc]
```

- Base query: `WHERE project_id = :project_id`
- If `doc_type` provided: add `AND doc_type = :doc_type`
- If `status` provided: add `AND status = :status`
- If `search` provided: add FTS filter `AND content_search @@ plainto_tsquery('english', :search)` and order by `ts_rank(content_search, plainto_tsquery('english', :search)) DESC`
- Otherwise order by `updated_at DESC`

### 7. `list_doc_versions()`

```python
def list_doc_versions(self, project_id: str, doc_id: str) -> list[ProjectDocVersion]
```

- Fetches all `ProjectDocVersion` for the composite doc id, ordered by `version DESC`

### 8. `get_stale_docs()`

```python
def get_stale_docs(self, project_id: str, threshold_hours: int = 24) -> list[ProjectDoc]
```

- Returns `ProjectDoc` records where:
  - `source_paths` is non-empty
  - `generated_at` is not null
  - `generated_at < now() - threshold_hours` (simple time-based staleness for Phase 1; Phase 3 will add mtime checking)
  - `status != DocStatus.archived`

### 9. `delete_doc()`

```python
def delete_doc(self, project_id: str, doc_id: str) -> bool
```

- Deletes `ProjectDoc` and cascades to versions and jobs
- Returns `True` if deleted, `False` if not found

## Project Conventions

Read `CLAUDE.md` carefully. Also look at:
- How existing services/repositories in `orch/` handle sessions (context manager? passed in? async?)
- How existing code raises errors for not-found vs. validation errors
- Whether the project uses `select()` with `scalars()` or the legacy `session.query()` style (use whichever is already in use)

Match existing patterns exactly. Do not introduce new patterns unless nothing exists to follow.

## TDD Requirement

Write tests in `tests/unit/test_doc_service.py` (unit tests with testcontainer DB, no mocks):

- `test_create_doc_creates_record_and_version`
- `test_create_doc_no_content_no_version_snapshot`
- `test_create_doc_unknown_project_raises_value_error`
- `test_update_doc_content_changed_creates_version`
- `test_update_doc_content_unchanged_no_new_version`
- `test_update_doc_content_change_clears_pdf_path`
- `test_upsert_doc_creates_when_missing`
- `test_upsert_doc_updates_when_exists`
- `test_list_docs_filter_by_type`
- `test_list_docs_fts_search`
- `test_list_doc_versions_ordered`
- `test_get_stale_docs`

## Test Verification (NON-NEGOTIABLE)

After implementation:
1. `make test-unit` — all unit tests must pass
2. `make quality` — ruff + mypy must pass

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "F-00011",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/doc_service.py",
    "tests/unit/test_doc_service.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
