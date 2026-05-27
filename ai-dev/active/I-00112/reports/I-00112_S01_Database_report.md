# I-00112 S01 — Database Report

## What was done

Added four nullable columns to the `keep_alive_runs` table to capture CLI output for diagnostic audit of silent no-op fires (the bug: scheduler logged `status=success` when `claude` exited 0 with empty stdout / near-zero elapsed).

**Files changed:**
- `orch/db/migrations/versions/42be5962ebf7_i_00112_keep_alive_runs_capture_cli_output.py` — Alembic revision
- `orch/db/models.py` — extended `KeepAliveRun` with four `Mapped[...]` columns

## Migration details

- Revision: `42be5962ebf7`
- Down-revision: `2be8dc12874f` (current head at time of autogenerate)
- Upgrade adds four nullable columns to `keep_alive_runs`:
  - `stdout TEXT NULL`
  - `stderr TEXT NULL`
  - `elapsed_ms INTEGER NULL`
  - `returncode INTEGER NULL`
- Downgrade drops in reverse order (returncode → elapsed_ms → stderr → stdout)
- All four columns are nullable — existing rows survive with NULL; no backfill

## ORM model changes

Added to `KeepAliveRun` after the existing `error` column:

```python
# I-00112 — CLI output capture for diagnostic audit of silent no-op fires.
# All nullable so existing rows survive the migration with NULL (no backfill).
stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
returncode: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

## Pre-flight results

| Check | Result |
|-------|--------|
| `make format` | ok |
| `make typecheck` | ok (0 errors) |
| `make lint` | ok |

## Migration verification

`make migration-check` — all 3 tests PASSED:
- `test_alembic_downgrade_base_then_upgrade_head` — PASS
- `test_alembic_upgrade_head_succeeds_from_empty` — PASS
- `test_alembic_schema_matches_create_all` — PASS

## Notes

- The autogenerate seed included unrelated `chat_tabs` comment-alter noise from the live DB; stripped entirely — only the four `keep_alive_runs` add-column ops remain.
- Stale autogenerate seed file (`42be5962ebf7_i_00112_keep_alive_runs_capture_cli_.py`) removed before formatting.
- Down-revision (`2be8dc12874f`) will be rewritten by the daemon's pre-merge rebase step (CR-00021) if the head moves before merge — do not pre-emptively update.
- This step is schema + ORM only; no behavioral code, no tests touched.
