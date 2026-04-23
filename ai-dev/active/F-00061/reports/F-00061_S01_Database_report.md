# F-00061 S01 Database — Step Report

## What Was Done

Added `QvBaseline` ORM model and alembic migration for the `qv_baselines` table.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `QvBaseline` class after `FixCycle`; added `baselines` relationship on `WorkflowStep` |
| `orch/db/migrations/versions/3035dfc20db5_add_qv_baselines_table_f_00061.py` | New alembic migration |

## Model Summary

**`QvBaseline`** — columns:

- `id` — `BigInteger` PK, autoincrement
- `step_id` — `Integer` FK → `workflow_steps.id` ON DELETE CASCADE, indexed
- `gate_name` — `Text` (e.g. "lint", "unit-tests")
- `base_sha` — `Text` (40-char git SHA)
- `fingerprint` — `JSONB`, server_default `{"failures": []}`
- `computed_at` — `TIMESTAMPTZ`, server_default `now()`

**Constraints**: `UniqueConstraint(step_id, gate_name, base_sha)` named `uq_qv_baselines_step_gate_sha`

**Relationships**: `WorkflowStep.baselines` (back_populates → `QvBaseline.step`, cascade delete-orphan)

## Migration

- Revision ID: `3035dfc20db5`
- Parent: `13014259ab68`
- Marker: `iw_core_baseline` in docstring
- Up: creates `qv_baselines` table with FK, unique constraint, index on `step_id`
- Down: drops index then table

## Verification

| Check | Result |
|-------|--------|
| `alembic history` shows `3035dfc20db5` at head | ✅ |
| `uv run mypy orch/db/models.py` | ✅ Success: no issues found |
| `uv run ruff check orch/db/models.py` | ✅ All checks passed |
| `uv run ruff check` on migration file | ✅ All checks passed |

## Notes

- No spurious diffs from autogenerate — migration is clean additive only
- All column types follow existing `_TIMESTAMPTZ` / `JSONB` patterns from the codebase
- Spent time analyzing the autogenerate output to strip spurious index/constraint changes to unrelated tables