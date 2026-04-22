# CR-00017_S02_CodeReview_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- `ai-dev/active/CR-00017/reports/CR-00017_S01_Database_report.md`
- All files in S01's `files_changed`
- `tests/CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S02_CodeReview_report.md`

## Review Checklist

### 1. Migration correctness
- `down_revision` chains from the prior head (likely CR-00014's revision).
- Columns, types, nullability, defaults, CHECK constraints, indexes match the design doc exactly.
- `ON DELETE SET NULL` on the `batch_id` FK — test proves it.
- Downgrade drops the table cleanly.
- Autogenerate-clean.

### 2. ORM model correctness
- Typed `Mapped[]` style.
- Placement near audit tables (`MigrationLock`, `DaemonEvent`).
- Optional relationship to `Batch` (no back_populates required).
- No reserved-word collisions (`metadata` etc.).
- `CheckConstraint(name="...")` in `__table_args__`.

### 3. Test quality
- Testcontainer-only, no live-DB connection.
- psycopg v3 URL replacement present.
- FTS triggers applied after `create_all()`.
- CHECK constraints tested (invalid enum INSERT raises IntegrityError).
- FK ON DELETE SET NULL tested.
- Tests fail on pre-change code (would fail against CR-00014's head).

### 4. Scope / hygiene
- No unrelated changes.
- Migration-lock released cleanly.
- No agent-invoked `alembic upgrade head` in scripts introduced by S01.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW. Fix in place.

## Subagent Result Contract

Standard code-review JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S02
uv run iw step-done CR-00017 --step S02 --report ai-dev/active/CR-00017/reports/CR-00017_S02_CodeReview_report.md
```
