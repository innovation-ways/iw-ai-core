# F-00045: Code Understanding: Foundation

**Type**: Feature
**Priority**: Critical
**Created**: 2026-04-15
**Status**: Approved

---

## Description

Creates the database foundation and Python package skeleton for the Code Understanding feature. Adds the `CodeIndexJob` table to track indexing jobs, extends the project config JSONB column with a `code_understanding` block, adds the `IW_CORE_INDEX_PATH` environment variable, and creates the `orch/rag/` package with Pydantic config models and tier-based model resolution. All downstream Code Understanding features (F-00046 through F-00049) depend on this foundation being in place.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key points:
- SQLAlchemy 2.0 `Mapped[]` declarative style (NOT psycopg2, NOT async)
- All tests use testcontainers — NEVER connect to live DB on port 5433
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` must be run after `Base.metadata.create_all()`
- Config is a frozen `DaemonConfig` dataclass in `orch/config.py`
- Migrations live in `orch/db/migrations/versions/` — the repo uses a mix of 12-char hex revision strings and slug-style strings. For this feature, pick a fresh 12-char hex revision that does not collide with any existing filename or `revision = "..."` literal

## Scope

### In Scope

- New `code_index_jobs` table with all columns defined in the Database Changes section
- ORM model `CodeIndexJob` added to `orch/db/models.py`
- Alembic migration creating `code_index_jobs` table
- `orch/rag/` package: `__init__.py` + `config.py` with Pydantic models
- `IW_CORE_INDEX_PATH` field added to `DaemonConfig` in `orch/config.py`
- Unit tests for `CodeUnderstandingConfig` validation and model resolution
- Integration tests for `CodeIndexJob` ORM model (create, read, status transitions)

### Out of Scope

- Actual file indexing logic (F-00046)
- Ollama integration or embedding calls (F-00047)
- Dashboard UI for indexing status (F-00048)
- CLI commands for triggering indexing (F-00049)
- Any changes to existing models other than adding the new model

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `CodeIndexJob` ORM model + Alembic migration | — |
| S02 | code-review-impl | Review S01 database work | — |
| S03 | backend-impl | `orch/rag/` package + config models + `IW_CORE_INDEX_PATH` | — |
| S04 | code-review-impl | Review S03 backend work | — |
| S05 | code-review-final-impl | Final cross-agent review of S01+S03 | — |
| S06 | qv-gate (lint) | `uv run ruff check .` | — |
| S07 | qv-gate (format) | `uv run ruff format --check .` | — |
| S08 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S09 | qv-gate (unit-tests) | `uv run pytest tests/unit/ -v` | — |
| S10 | qv-gate (integration-tests) | `uv run pytest tests/integration/ -v --alluredir=allure-results` | — |

### Database Changes

- **New tables**: `code_index_jobs`
- **Modified tables**: None (the `projects.config` JSONB column already exists; we add Pydantic validation in `orch/rag/config.py` only — no DDL change to `projects`)
- **Migration notes**: New migration must chain from the current head (`add_doc_instance_guides`). Use a fresh 12-char hex revision ID. The table uses `VARCHAR` (mapped to `Text` in SQLAlchemy) for `id` (UUID as text, server default `gen_random_uuid()`), FK to `projects(id)`, and optional FK to `project_docs(id)` with `ON DELETE SET NULL`.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None

## Database Schema: code_index_jobs

```sql
CREATE TABLE code_index_jobs (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    project_id VARCHAR NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR NOT NULL DEFAULT 'queued',
    provider VARCHAR NOT NULL DEFAULT 'local',
    llm_model VARCHAR,
    embed_model VARCHAR,
    index_tier VARCHAR,
    files_discovered INTEGER NOT NULL DEFAULT 0,
    files_indexed INTEGER NOT NULL DEFAULT 0,
    chunks_created INTEGER NOT NULL DEFAULT 0,
    languages_detected JSONB NOT NULL DEFAULT '[]',
    errors JSONB NOT NULL DEFAULT '[]',
    doc_id VARCHAR REFERENCES project_docs(id) ON DELETE SET NULL,
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_code_index_jobs_project_id ON code_index_jobs(project_id);
CREATE INDEX idx_code_index_jobs_status ON code_index_jobs(status);
```

**Status values**: `queued` | `running` | `completed` | `failed` | `cancelled`

> `queued` is the initial status set by F-00047's POST trigger handlers before `start_index_job` schedules the runner, which then flips the row to `running`. `cancelled` is a terminal status used by F-00046's cooperative-cancel path (`CodeIndexJobRunner.request_cancel()`) and F-00047's `DELETE /api/code/index` endpoint. The column is plain `VARCHAR` (no Postgres ENUM), so no schema change is needed — it is a convention only. Unit tests that enumerate valid statuses must include both `queued` and `cancelled`.
**Provider values**: `local` (only value in v1)
**Index tier values**: `fast` | `balanced` | `quality`

## orch/rag/config.py Design

```python
from enum import Enum
from pydantic import BaseModel

class CodeUnderstandingProvider(str, Enum):
    LOCAL = "local"

class IndexTier(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"

TIER_DEFAULTS = {
    IndexTier.FAST:     {"llm_model": "gemma4:e4b",  "embed_model": "qwen3-embedding:8b"},
    IndexTier.BALANCED: {"llm_model": "gemma4:26b",  "embed_model": "qwen3-embedding:8b"},
    IndexTier.QUALITY:  {"llm_model": "gemma4:31b",  "embed_model": "manutic/nomic-embed-code"},
}

class CodeUnderstandingConfig(BaseModel):
    provider: CodeUnderstandingProvider = CodeUnderstandingProvider.LOCAL
    llm_model: str | None = None        # None = use tier default
    embed_model: str | None = None      # None = use tier default
    index_tier: IndexTier = IndexTier.BALANCED
    ollama_url: str = "http://localhost:11434"

    def resolved_llm_model(self) -> str:
        return self.llm_model or TIER_DEFAULTS[self.index_tier]["llm_model"]

    def resolved_embed_model(self) -> str:
        return self.embed_model or TIER_DEFAULTS[self.index_tier]["embed_model"]
```

## orch/config.py Extension

Add to `DaemonConfig`:
```python
index_path: str = "~/.iw-ai-core/indexes"
```

Add to `load_config()`:
```python
index_path=os.environ.get("IW_CORE_INDEX_PATH", "~/.iw-ai-core/indexes"),
```

Note: `IW_CORE_INDEX_PATH` is optional — it has a default. Do NOT use `_require()` for it.

## File Manifest

All files for this work item live under `ai-dev/active/F-00045/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00045_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00045_S01_Database_prompt.md` | Prompt | S01: DB model + migration |
| `prompts/F-00045_S02_CodeReview_prompt.md` | Prompt | S02: Review S01 |
| `prompts/F-00045_S03_Backend_prompt.md` | Prompt | S03: orch/rag/ package |
| `prompts/F-00045_S04_CodeReview_prompt.md` | Prompt | S04: Review S03 |
| `prompts/F-00045_S05_CodeReview_Final_prompt.md` | Prompt | S05: Final cross-agent review |

Reports are created during execution in `ai-dev/work/F-00045/reports/`.

## Acceptance Criteria

### AC1: CodeIndexJob table exists and is queryable

```
Given a running test PostgreSQL instance
When Base.metadata.create_all() is called
Then the code_index_jobs table exists with all expected columns
 And a CodeIndexJob row can be inserted with project_id referencing an existing Project
 And the row can be read back with correct default values
```

### AC2: CodeIndexJob status lifecycle

```
Given an existing CodeIndexJob with status='queued'
When the status is updated to 'running', then 'completed'
Then each status change persists correctly
 And completed_at can be set to a non-null timestamp
```

### AC3: CodeIndexJob FK constraints

```
Given a CodeIndexJob referencing a project_id
When the referenced project does not exist
Then the insert raises an IntegrityError (FK violation)
```

### AC4: CodeUnderstandingConfig tier defaults

```
Given a CodeUnderstandingConfig with index_tier=FAST and no llm_model/embed_model
When resolved_llm_model() and resolved_embed_model() are called
Then they return 'gemma4:e4b' and 'qwen3-embedding:8b' respectively
```

### AC5: CodeUnderstandingConfig explicit override

```
Given a CodeUnderstandingConfig with index_tier=BALANCED and llm_model='custom:7b'
When resolved_llm_model() is called
Then it returns 'custom:7b' (explicit value wins over tier default)
```

### AC6: IW_CORE_INDEX_PATH optional config

```
Given an environment with IW_CORE_INDEX_PATH unset
When load_config() is called
Then DaemonConfig.index_path equals '~/.iw-ai-core/indexes'
```

```
Given an environment with IW_CORE_INDEX_PATH='/data/indexes'
When load_config() is called
Then DaemonConfig.index_path equals '/data/indexes'
```

### AC7: Invalid provider rejected

```
Given a dict with provider='openai'
When CodeUnderstandingConfig is constructed
Then a Pydantic ValidationError is raised
```

### AC8: Invalid index_tier rejected

```
Given a dict with index_tier='ultra'
When CodeUnderstandingConfig is constructed
Then a Pydantic ValidationError is raised
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Unknown provider | `provider="openai"` | Pydantic `ValidationError` |
| Unknown tier | `index_tier="ultra"` | Pydantic `ValidationError` |
| Explicit model overrides | `llm_model="custom:7b"`, `index_tier=BALANCED` | resolved_llm_model() returns `"custom:7b"` |
| Null doc_id FK | `doc_id=None` | Insert succeeds; NULL stored |
| Valid doc_id FK | doc_id references existing project_docs row | Insert succeeds |
| Invalid doc_id FK | doc_id references non-existent project_docs row | IntegrityError |
| IW_CORE_INDEX_PATH unset | env var absent | Default `~/.iw-ai-core/indexes` used |
| IW_CORE_INDEX_PATH set | env var = `/data/idx` | `DaemonConfig.index_path == "/data/idx"` |
| files_discovered default | No value provided | Stored as 0 |
| CodeIndexJob without project | project_id references missing project | IntegrityError |

## Invariants

1. Every `CodeIndexJob` row has a valid `project_id` referencing `projects(id)` — enforced by FK constraint.
2. `CodeIndexJob.status` is always one of: `queued`, `running`, `completed`, `failed`, `cancelled`.
3. `CodeUnderstandingConfig.resolved_llm_model()` always returns a non-empty string.
4. `CodeUnderstandingConfig.resolved_embed_model()` always returns a non-empty string.
5. `DaemonConfig.index_path` is always a non-empty string (defaults to `~/.iw-ai-core/indexes`).
6. `TIER_DEFAULTS` covers all three `IndexTier` values — no `KeyError` possible at runtime.

## Dependencies

- **Depends on**: None
- **Blocks**: F-00046, F-00047, F-00048, F-00049

## TDD Approach

- **Unit tests** (`tests/unit/test_rag_config.py`):
  - `CodeUnderstandingConfig` defaults
  - `resolved_llm_model()` for each tier
  - `resolved_embed_model()` for each tier
  - Explicit model overrides
  - Invalid provider raises `ValidationError`
  - Invalid tier raises `ValidationError`
  - `IW_CORE_INDEX_PATH` optional env var (using `monkeypatch.setenv` / `monkeypatch.delenv`)

- **Integration tests** (`tests/integration/test_code_index_job.py`):
  - Insert `CodeIndexJob` with minimal fields (status defaults)
  - Insert `CodeIndexJob` with all fields populated
  - FK violation on missing project_id
  - FK violation on invalid doc_id
  - Status update from `queued` → `running` → `completed`
  - `completed_at` set on completion

- **Edge cases**:
  - `languages_detected` and `errors` default to empty JSONB arrays
  - `files_discovered`, `files_indexed`, `chunks_created` default to 0

## Notes

- The `projects.config` JSONB column already exists in DDL — no migration needed for it. The `CodeUnderstandingConfig` Pydantic model in `orch/rag/config.py` serves as the validation layer when application code reads/writes the `code_understanding` key.
- Use `str` (Text) for the `id` column (not `UUID` type) to match the existing project_docs pattern: `gen_random_uuid()::text` as server default.
- The migration revision ID must be a fresh 12-char hex string chained from `add_doc_instance_guides` (the current alembic head). Verify with `uv run alembic heads` before writing the migration.
- `IW_CORE_INDEX_PATH` uses `os.environ.get()` with a default — it is NOT a required var, so do NOT use `_require()`.
