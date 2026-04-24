# CR-00020_S02_CodeReview_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits
Same rules as S01. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
Same rules as S01. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design
- `ai-dev/active/CR-00020/reports/CR-00020_S01_Database_report.md` — S01 report
- All files listed in the S01 report's `files_changed`

## Output Files

- `ai-dev/active/CR-00020/reports/CR-00020_S02_CodeReview_report.md`

## Context

Review the `EvidencePhase` enum + `WorkItemEvidence` model + Alembic migration + schema doc produced by S01. The downstream steps rely on this schema being correct; catch issues here before they propagate.

## Review Checklist

### 1. Schema correctness

- `EvidencePhase` enum uses `SAEnum(EvidencePhase, name="evidence_phase")` and matches values `('pre', 'post')` in the DB.
- `WorkItemEvidence` has all columns from the design (id, project_id, work_item_id, phase, filename, content_type, content, size_bytes, captured_at, step_id) with **exact** types and nullability.
- `UUID` column has both a Python-side default (`uuid.uuid4`) AND a server_default (`gen_random_uuid()`) for resilience.
- `captured_at` has `server_default=func.now()` and `DateTime(timezone=True)`.

### 2. Foreign key — NO CASCADE

This is the core durability requirement. Verify:

- `ForeignKeyConstraint(["project_id", "work_item_id"], ["work_items.project_id", "work_items.id"], ...)` has **NO `ondelete="CASCADE"`** (either omitted or explicitly `None`).
- The autogen migration's `op.create_table(...)` reflects the same — no `ondelete='CASCADE'` string in the generated FK.

If cascade is present, this is a CRITICAL finding (AC6 breaks silently).

### 3. Unique constraint & index

- Unique: `(project_id, work_item_id, phase, filename)` with a named constraint (`uq_evidence_per_file` or similar). This is used by the `ON CONFLICT` upsert in S03.
- List index: `(project_id, work_item_id, phase)` named `ix_evidence_project_item_phase`.

### 4. Alembic migration

- Both `upgrade()` and `downgrade()` are implemented (downgrade drops the table THEN drops the enum type).
- Enum creation uses `sa.Enum(...)` or explicit `CREATE TYPE` — verify the generated SQL is idempotent (does not fail if run twice in the same transaction path).
- `upgrade()` and `downgrade()` round-trip cleanly — ask the S01 agent how they verified this; if they did not, run the round-trip yourself against a testcontainer (`make test-integration` should exercise it).
- The migration's `down_revision` points to the current head at S01 start time.

### 5. Project conventions

- `orch/db/models.py` does NOT gain `from __future__ import annotations` (SQLAlchemy 2.0 requires annotations resolved at import time).
- Column style matches existing models — `Mapped[str]` declarative, not the legacy `Column(...)` style.
- Docstring on the new class briefly explains durability (no cascade) and the upsert-key intent.

### 6. Docs update

- `docs/IW_AI_Core_Database_Schema.md` includes the new table with columns, enum values, FK without cascade explicitly called out, and the table-count updated from 19 → 20.

### 7. Test verification

- `make test-integration` passes.
- `make lint`, `make format --check`, `make typecheck` all pass against S01's files.
- The `pg_engine` fixture + `Base.metadata.create_all()` path is unaffected (no FTS regressions).

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | FK has cascade / migration breaks / schema missing a column | Must fix before merge |
| HIGH | Wrong types, missing index, wrong enum name | Must fix before merge |
| MEDIUM (fixable) | Convention violation, missing docstring, unclear comment | Should fix in fix cycle |
| MEDIUM (suggestion) | Nicer-to-have refactor | Optional |
| LOW | Nit | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00020",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "...",
  "notes": ""
}
```

- `verdict: pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
- `mandatory_fix_count` = count of CRITICAL + HIGH + MEDIUM_FIXABLE.
