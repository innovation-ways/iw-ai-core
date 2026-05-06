# CR-00035_S02_CodeReview_Database_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt; `docker ps/inspect/logs` allowed. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are reviewing a migration FILE, not applying one. Do NOT run `alembic upgrade/downgrade/stamp` against port 5433. Read-only `alembic history / current / show` is fine.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` — design.
- `ai-dev/active/CR-00035/reports/CR-00035_S01_Database_report.md` — S01 report.
- All files in S01's `files_changed`.

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S02_CodeReview_report.md`

## Context

Review S01: a single Alembic migration adding `report JSONB NULL` to `doc_generation_jobs`, plus the corresponding `Mapped[]` field on `DocGenerationJob`. This must be additive, reversible, and not collide with any other in-flight migration.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation on a file in S01's `files_changed` is a **CRITICAL** finding (`category: conventions`).

## Review Checklist

### Migration safety

- `down_revision` points at the prior head. Run `uv run alembic history --verbose | head -20` to confirm chain integrity.
- `op.add_column(...)` uses `JSONB` (`postgresql.JSONB(astext_type=sa.Text())` import or `JSONB` from dialects), `nullable=True`, no default. Default-less + nullable is what we want — no table rewrite.
- `op.drop_column(...)` is in `downgrade()`.
- No spurious `alter_column` lines (autogenerate sometimes hallucinates these against TSVECTOR + FTS triggers — flag any).
- Comment string on the column matches the design doc's intent (post-mortem schema).

### ORM model

- `report: Mapped[dict[str, Any] | None]` field added to `DocGenerationJob`. Type is `JSONB` (already imported in `models.py`).
- Field is placed in a sensible spot (after `lint_warnings`, before `duration_seconds` per the design).
- `nullable=True` on the column; no default.
- The new attribute is not named anything SQLAlchemy reserves (`metadata`, `query`, etc.).

### Doc parity

- If `docs/IW_AI_Core_Database_Schema.md` enumerates columns of this table, ensure `report` is added there. If only high-level — no doc change is required.

### No collateral damage

- No other models / tables / migrations were touched.
- FTS DDL constants (`FTS_FUNCTION_SQL`, `FTS_TRIGGER_SQL`) are unchanged.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```
Report results accurately. The integration suite re-creates the schema in a testcontainer and exercises FTS — your migration must not break it.

## Severity Levels

Standard. CRITICAL/HIGH/MEDIUM_FIXABLE trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
