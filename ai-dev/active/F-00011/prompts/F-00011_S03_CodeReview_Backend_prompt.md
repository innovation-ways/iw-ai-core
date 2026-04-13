# F-00011_S03_CodeReview_Backend_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Steps Being Reviewed**: S01 (Database) + S02 (Backend)
**Review Step**: S03

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document
- `ai-dev/work/F-00011/reports/F-00011_S01_Database_report.md` — S01 implementation report
- `ai-dev/work/F-00011/reports/F-00011_S02_Backend_report.md` — S02 implementation report
- All files listed in `files_changed` of both reports
- `CLAUDE.md` — Project conventions

## Output Files

- `ai-dev/work/F-00011/reports/F-00011_S03_CodeReview_Backend_report.md` — Review report

## Context

You are reviewing the database models, migration, and backend service layer built in S01 and S02 for **F-00011: Project-Level Documentation System**.

Read the design document thoroughly (especially the "Data Models", "Invariants", and "Boundary Behavior" sections). Then read both implementation reports and every file they changed.

## Review Checklist

### 1. Schema Correctness

- Do all three models match the design document exactly? (field names, types, nullable rules, defaults)
- Is `ProjectDoc.id` the composite `"{project_id}:{doc_id}"` — not a UUID?
- Is `content_search` named `content_search` (not a reserved SQLAlchemy name)?
- Does `ProjectDocVersion.content` disallow NULL?
- Does `DocGenerationJob` use a UUID string PK with Python-side `default=lambda: str(uuid4())`?
- Are all ENUMs defined as both Python `str, enum.Enum` and SQLAlchemy `ENUM(name=..., create_type=False)`?

### 2. Migration Completeness

- Does the migration create all 5 ENUMs before the tables that use them?
- Are `project_docs`, `project_doc_versions`, and `doc_generation_jobs` all created?
- Is the FTS trigger function and trigger created via `op.execute()`?
- Does the `downgrade()` drop triggers, tables, and ENUMs in reverse order?
- Is the `UniqueConstraint` on `(project_id, doc_id)` present?
- Are appropriate indexes created for `project_id` lookups?

### 3. FTS Trigger

- Does the trigger combine `title` and `content` via `coalesce()` (handles NULLs correctly)?
- Are the FTS SQL constants (`PROJECT_DOCS_FTS_FUNCTION_SQL`, `PROJECT_DOCS_FTS_TRIGGER_SQL`) defined in `models.py`?
- Are they executed in test fixtures (conftest.py) after `Base.metadata.create_all()`?

### 4. DocService Correctness

- Does `create_doc()` raise `ValueError` for unknown project (not silently insert)?
- Does `update_doc()` use SHA-256 content hash comparison before creating a version snapshot?
- Does `update_doc()` clear `html_path` and `pdf_path` when content changes (unless explicitly provided)?
- Does `update_doc()` raise `KeyError` for unknown doc?
- Does `upsert_doc()` return `(doc, created)` tuple correctly?
- Does `list_docs()` apply FTS ranking when `search` is provided?
- Is `get_stale_docs()` correctly filtering by `generated_at` threshold?

### 5. Invariant Enforcement

Verify each invariant from the design document is enforced:
- Invariant 2: `version` counter matches count of version snapshots (enforced in `update_doc()`)
- Invariant 3: new snapshot only when content hash differs
- Invariant 7: `pdf_path` only set on successful generation (not tested here, but service must not set it)

### 6. Architecture Compliance

- Is the service class in the correct module location (matches existing project patterns)?
- Does it use the same ORM query style as existing code (`select()` + `scalars()` vs `session.query()`)?
- Are there any cross-layer imports (service importing from routers, etc.)?

### 7. Code Quality

- No hardcoded strings that should be constants
- Error messages are descriptive and include the failing value
- No bare `except:` clauses
- No unused imports

### 8. Test Quality

- Do tests use testcontainers (not live DB, not mocks)?
- Do tests cover all methods of `DocService`?
- Are the FTS tests actually testing FTS (inserting real content and querying with `plainto_tsquery`)?
- Is `test_update_doc_content_unchanged_no_new_version` present and correctly verifying no new snapshot?

## Test Verification (NON-NEGOTIABLE)

Run before submitting:
1. `make test-unit` — all tests must pass
2. `make quality` — ruff + mypy must pass

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, data loss, security issue, missing required field |
| **HIGH** | Significant bug, invariant not enforced, migration incomplete |
| **MEDIUM (fixable)** | Code quality issue, missing edge case test, convention violation |
| **MEDIUM (suggestion)** | Better pattern available, optional improvement |
| **LOW** | Nitpick, minor readability |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview",
  "work_item": "F-00011",
  "step_reviewed": "S01+S02",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
