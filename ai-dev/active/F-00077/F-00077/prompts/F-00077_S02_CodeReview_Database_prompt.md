# F-00077_S02_CodeReview_Database_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY container/volume/network management command.
Allowed: `docker ps/inspect/logs`, testcontainer fixtures (Ryuk-managed), `./ai-core.sh`/`make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live orch DB (port 5433). Allowed: `alembic history/current/show`, `alembic revision --autogenerate` (writes only). Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md`
- `ai-dev/active/F-00077/reports/F-00077_S01_Database_report.md`
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S02_CodeReview_report.md`

## Context

You are reviewing the database-layer implementation for F-00077. Read the design first to understand intent (sections: Database Changes, Invariants 1-3, Boundary Behavior). Then read S01's report for what was actually built.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports NEW violations in S01's `files_changed`, classify each as **CRITICAL** (`category: conventions`).

## Review Checklist

### 1. Architecture Compliance

- ORM uses SQLAlchemy 2.0 `Mapped[]` style consistent with the rest of `orch/db/models.py`.
- Single-column `id` PK pattern matching `CodeIndexJob` (NOT composite PK).
- `ChatMessage.metadata` column is mapped to Python attribute `message_metadata` to avoid the `DeclarativeBase.metadata` collision (per `orch/CLAUDE.md` Gotcha — same as `DaemonEvent.event_metadata`). FAIL if the Python attribute is `metadata`.
- ENUM `chat_message_role` is created and dropped in the migration; not auto-managed by SQLAlchemy on `create_all()` calls (testcontainers raise on duplicate type otherwise).

### 2. Migration Correctness

- `down_revision` matches the current alembic head BEFORE this migration.
- `upgrade()` creates: ENUM → `chat_conversations` → `chat_messages` → `chat_summarization_jobs` → indexes.
- `downgrade()` drops in reverse: jobs → messages → conversations → ENUM. (CRITICAL if any reverse-order error.)
- Migration does NOT touch FTS triggers, unrelated tables, or comment-only diffs from `alembic revision --autogenerate`. Hand-trimming is verified.
- The unique partial index `uq_chat_summarization_jobs_one_in_flight` uses the correct predicate `WHERE status IN ('queued', 'running')` and is created with `unique=True, postgresql_where=...`.
- The partial index on `chat_conversations` filters `WHERE archived_at IS NULL` and sorts by `last_active_at DESC`.

### 3. Code Quality

- All `mapped_column` declarations include a `comment=` string (matches the convention in adjacent classes).
- `JSONB` default uses `text("'{}'::jsonb")`, not `default=lambda: {}`.
- `server_default` for timestamps uses `func.now()` (consistent with project).
- The `chat_messages.metadata` column comment documents the append-only exception (the same-tx error-flag write).
- The token_count column has a non-negative semantics note in the comment (`token_count >= 0`); the actual constraint is enforced at the app layer.
- Cascade delete on `chat_messages.conversation_id` and `chat_summarization_jobs.conversation_id` is declared via `ForeignKey(..., ondelete="CASCADE")`. FAIL if missing — orphan rows otherwise.

### 4. Project Conventions

- File ordering: new classes appended after `CodeIndexJob` (do not break existing order).
- Index naming: `idx_<table>_<column(s)>` for non-unique, `uq_<table>_<column(s)>` for unique.
- `tiktoken` added to `pyproject.toml` `dependencies` (NOT `dev-dependencies`); `uv.lock` updated.
- No psycopg2 references introduced.

### 5. Testing

- All tests use the `db_session` testcontainer fixture (no live DB on port 5433).
- `psycopg2://` → `psycopg://` URL replacement is applied.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `Base.metadata.create_all()`.
- The cascade-delete test exists and passes.
- The unique-partial-index test exists and properly verifies BOTH directions (re-enqueue allowed after status changes; re-enqueue blocked while in flight).
- The `test_chat_message_python_attribute_is_message_metadata` guard test exists.

### 6. Security

- No hardcoded secrets / connection strings.
- No `format-sql` style string concatenation in the migration's data manipulation (none expected — this migration creates schema only).

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

If either fails, classify the new failures as CRITICAL.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Migration breaks rollback, data loss, ENUM mismatch, missing CASCADE, missing partial index, metadata collision | Must fix |
| HIGH | Missing index, missing comment on a public column, naming violation | Must fix |
| MEDIUM (fixable) | Style drift, inconsistent server_default | Fix in fix cycle |
| MEDIUM (suggestion) | Better column ordering, alternative index strategy | Optional |
| LOW | Whitespace, comment wording | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 0,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
