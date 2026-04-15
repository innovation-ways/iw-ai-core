# F-00045_S02_CodeReview_prompt

**Work Item**: F-00045 -- Code Understanding: Foundation
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00045/F-00045_Feature_Design.md` — Design document
- `ai-dev/work/F-00045/reports/F-00045_S01_Database_report.md` — S01 implementation report
- All files listed in the S01 report's `files_changed`:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/<revision_id>_add_code_index_jobs.py`
  - `tests/integration/test_code_index_job.py`

## Output Files

- `ai-dev/work/F-00045/reports/F-00045_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the database implementation done in S01 by the database-impl agent for **Code Understanding: Foundation (F-00045)**.

Read the design document to understand what was intended. Read the S01 report to understand what was done. Then review all changed files carefully.

---

## Review Checklist

### 1. Architecture Compliance

- Does `CodeIndexJob` use SQLAlchemy 2.0 `Mapped[]` declarative style (NOT legacy `Column()`)?
- Is `CodeIndexJob` appended to `models.py` without modifying any existing model?
- Does the migration chain from `add_doc_instance_guides` as `down_revision`? (Run `uv run alembic heads` — after applying the new migration there must still be exactly one head, pointing at the new revision.)
- Does the migration use a fresh revision ID (not reusing an existing one)?
- Are all FK constraints correct: `project_id → projects(id)` CASCADE, `doc_id → project_docs(id)` SET NULL?
- Is `_TIMESTAMPTZ` used for timestamp columns (not raw `DateTime(timezone=True)` in the ORM model)?
- Is `from __future__ import annotations` absent from `models.py`? (SQLAlchemy 2.0 forbids it)

### 2. ORM Model Correctness

- Does `CodeIndexJob.__tablename__` equal `"code_index_jobs"`?
- Is `id` configured with `server_default=text("gen_random_uuid()::text")` (UUID as text)?
- Are `status` and `provider` columns using `server_default` with correct SQL literals (`'queued'`, `'local'`)?
- Are `files_discovered`, `files_indexed`, `chunks_created` non-nullable with `server_default=text("0")`?
- Are `languages_detected` and `errors` `JSONB` columns with `server_default=text("'[]'")`?
- Is `completed_at` nullable (`Mapped[datetime | None]`)?
- Is `doc_id` nullable (`Mapped[str | None]`)?
- Are both indexes (`idx_code_index_jobs_project_id`, `idx_code_index_jobs_status`) declared in `__table_args__`?
- Is the `__table_args__` tuple properly formatted (tuple ending with a dict for table kwargs)?

### 3. Migration Correctness

- Does `upgrade()` create the table with all 18 columns?
- Are JSONB columns imported from `sqlalchemy.dialects.postgresql`?
- Does `downgrade()` drop both indexes before dropping the table?
- Does the migration include `comment="Tracks code indexing jobs for a project"` on the table?
- Are `server_default` values in the migration consistent with the ORM model?

### 4. Test Quality

- Do tests use the `db_session` fixture from `conftest.py` (never direct DB connections)?
- Do tests use the `test_project` fixture for `project_id`?
- Are ALL test cases from the S01 prompt implemented?
  - Default values on insert
  - All fields populated
  - Status transitions
  - FK violation on invalid project_id
  - Nullable doc_id
  - JSONB array read-back for languages_detected
  - JSONB dict read-back for errors
- Do test names clearly describe what they verify?
- Are tests isolated (no shared mutable state between tests)?
- Does the FK violation test catch `IntegrityError` from sqlalchemy?

### 5. Code Quality

- No hardcoded credentials or port 5433 anywhere
- No `importlib.reload(orch.config)` calls
- No mocking of the database in integration tests
- `psycopg2` URLs are not used (testcontainers URL must be replaced to `psycopg://`)
- Imports are clean and organized (no unused imports)
- Comments/docstrings are accurate

### 6. Design Document Compliance

Verify each acceptance criterion from the design document:
- AC1: Table exists and row is insertable with defaults
- AC2: Status lifecycle (queued → running → completed)
- AC3: FK constraint enforced on missing project_id

---

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run: `uv run pytest tests/integration/test_code_index_job.py -v`
2. Run: `uv run ruff check orch/db/models.py tests/integration/test_code_index_job.py`
3. Run: `uv run mypy orch/db/models.py`
4. Report actual pass/fail counts — do NOT assume tests pass

---

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

---

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00045",
  "step_reviewed": "S01",
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

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
