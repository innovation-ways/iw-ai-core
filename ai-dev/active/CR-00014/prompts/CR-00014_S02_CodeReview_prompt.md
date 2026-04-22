# CR-00014_S02_CodeReview_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md` — Design document
- `ai-dev/active/CR-00014/reports/CR-00014_S01_Database_report.md` — S01 step report
- All files listed in the S01 report's `files_changed`
- `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S02_CodeReview_report.md` — review report

## Context

Review the schema changes from S01. The deliverable is one alembic migration + one ORM model + one integration test. This is a small but high-stakes change because it becomes a hard gate for every process connecting to the DB.

## Review Checklist

### 1. Migration correctness

- `down_revision` points to `824e6e6f34ee` (the actual previous head).
- Upgrade creates the table exactly as specified in the design doc: columns, types (SMALLINT / UUID / TIMESTAMPTZ), NOT NULLs, default `now()`, check constraint `id = 1`, table comment.
- Seed uses `gen_random_uuid()` and is idempotent (`ON CONFLICT (id) DO NOTHING`).
- `CREATE EXTENSION IF NOT EXISTS pgcrypto` is present if not already declared elsewhere. If the initial schema declares it, duplication is harmless but worth noting.
- Downgrade drops the table cleanly. Downgrade does NOT drop the `pgcrypto` extension (it may be used by other tables).
- Migration is autogenerate-clean: a fresh `alembic revision --autogenerate` immediately after upgrade produces no diff. **If the reviewer can't verify this locally, flag it as HIGH for the S01 agent to prove in their report.**

### 2. ORM model correctness

- Uses SQLAlchemy 2.0 `Mapped[]` typed style — consistent with other models in the file.
- `CheckConstraint("id = 1", name="ck_iw_core_instance_single_row")` present in `__table_args__`.
- `instance_id` uses `UUID(as_uuid=True)` so Python code gets `uuid.UUID` objects, not strings.
- `created_at` has `server_default=func.now()` (not Python-side `default=datetime.utcnow`).
- No FKs, no back-populates (this is a singleton, standalone table).
- Model placed near `MigrationLock` — infrastructure grouping.
- Imports added cleanly (no wildcard imports, existing import groups respected).

### 3. Single-row invariant

- The CHECK constraint `id = 1` guarantees at most one row exists.
- Consider: could an INSERT with explicit `id = 2` ever bypass the check? (No — CHECK constraints fire before commit.)
- Consider: does `ON CONFLICT (id) DO NOTHING` on the seed actually prevent double-seed on repeated upgrades? (Yes — alembic won't re-run a revision once applied, but the idempotent INSERT is belt-and-braces for manual re-runs.)

### 4. Tests quality

- Test file at `tests/integration/test_iw_core_instance_migration.py`.
- Uses testcontainer (not live DB on port 5433) — enforce `tests/CLAUDE.md` rule.
- Testcontainer URL replacement `postgresql+psycopg2://` → `postgresql+psycopg://` is present.
- Asserts: table exists, exactly one row, UUID format valid, check constraint blocks a second row, downgrade drops table, upgrade re-creates with a **different** UUID (proves seed runs anew — important for "fresh DB = fresh identity" semantics).
- Tests fail on pre-change code — i.e., they would fail against the repo's state *before* this S01 landed. (Reviewer can verify by temporarily removing the migration file and running the test — optional but ideal.)

### 5. Project conventions

- Migration file name follows convention (`{hash}_add_iw_core_instance.py`).
- File structure: `from __future__ import annotations`, `from collections.abc import Sequence`, etc. — match recent migrations.
- `CLAUDE.md` rules respected: no FTS change, no `metadata` reserved-word pitfall, psycopg v3 in tests.
- No extraneous changes outside the S01 scope (no unrelated edits to other models, daemon code, etc.).

### 6. Migration lock hygiene

- S01 report mentions: stale F-00058 lock released (or blocker raised if no force-release), CR-00014 lock acquired and released.
- No dangling lock after S01 completes.

## Severity Grading

Use the standard:

- **CRITICAL**: breaks correctness, data safety, or irreversible. MUST fix before proceeding.
- **HIGH**: violates project convention or introduces latent bug. Fix before merge.
- **MEDIUM**: code-quality / readability. Fix if cheap; defer if not.
- **LOW**: nit / preference.

## If fixes are required

Apply them directly in this step (code-review-impl has edit rights). Re-run `make test-integration` and `make lint` after fixes. Update the S02 report with the list of fixes applied.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "...",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "...", "line": NNN, "issue": "...", "fix_applied": true|false}
  ],
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S02
# ... review + apply fixes ...
uv run iw step-done CR-00014 --step S02 --report ai-dev/active/CR-00014/reports/CR-00014_S02_CodeReview_report.md
```
