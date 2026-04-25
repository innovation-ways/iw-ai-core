# CR-00022_S02_CodeReview_prompt

**Work Item**: CR-00022 -- OSS Compliance redesign
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Same rules as the implementation prompts. Read-only `docker ps/inspect/logs` only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are reviewing a migration FILE. Do NOT apply it to the live DB. Read-only alembic commands (`history`, `current`, `show`) are allowed.

## Input Files

- `ai-dev/active/CR-00022/CR-00022_CR_Design.md` — design document
- `ai-dev/active/CR-00022/reports/CR-00022_S01_Database_report.md` — implementation report
- `orch/db/migrations/versions/*_cr_00022_*.py` — the new migration file
- `orch/db/models.py` — updated ORM
- `docs/IW_AI_Core_Database_Schema.md` — updated docs

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S02_CodeReview_report.md`

## Review Checklist

### 1. Migration correctness

- Pre-delete order: rows for `kind in ('prepare','publish')` deleted **before** enum recreate?
- Pre-delete for `oss_scan.mode in ('make_oss','publish')` present?
- Pre-delete for `project_oss_job.status in ('awaiting_review','discarded')` present (defensive)?
- Enum recreate uses the create-new → alter-cast → drop-old → rename pattern (not `ALTER TYPE ... DROP VALUE` which Postgres does not support)?
- New enum value `fix` added to `project_oss_job_kind`?
- All four columns dropped from `project_oss_job`: `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary`?
- New column `auto_apply_safe BOOLEAN NOT NULL DEFAULT false` added to `oss_finding`?
- `down_revision` points at the last-applied head (verify via `uv run alembic history`)?
- `downgrade()` raises `NotImplementedError` (hard migration, design § Rollback)?

### 2. ORM consistency

- `ProjectOssJobKind` no longer references `prepare`/`publish`; contains `fix`?
- `OssScanMode` no longer references `make_oss`/`publish`?
- `ProjectOssJobStatus` no longer references `awaiting_review`/`discarded`?
- `ProjectOssJob` model dropped the four columns?
- `OssFinding` has `auto_apply_safe: Mapped[bool]` with correct server_default?
- No stale relationships pointing at dropped fields?
- Class docstrings updated to reflect new shape?

### 3. Schema docs

- `docs/IW_AI_Core_Database_Schema.md` reflects the new column, dropped columns, pruned enums?
- Change-history section names CR-00022?

### 4. Project conventions

- Follows existing migration file style (`orch/db/migrations/versions/9ef17911f546_*.py` is the closest precedent — adding the same columns this CR drops)?
- Uses `op.execute(...)` with parameter-less SQL (no f-strings with user input — N/A here but flag if seen)?
- Imports correct (`alembic`, `sqlalchemy as sa`)?

### 5. Test impact

- Did S01 verify the migration applies cleanly in a fresh testcontainer? Report should describe how.
- Tests likely-broken by S01 (e.g., `test_project_oss_job_migration.py` asserting old enum values, `test_oss_persistence.py` asserting `make_oss` mode) are noted for S17?

## Output Report

Write `CR-00022_S02_CodeReview_report.md` with one section per checklist item, severity per finding (CRITICAL / HIGH / MEDIUM / LOW), and an explicit verdict (`approve` / `request_changes`).

End with `iw step-done CR-00022 --step S02 --report ...` or `iw step-fail`.
