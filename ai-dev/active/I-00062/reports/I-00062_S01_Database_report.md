# I-00062 S01 Database Report

## What Was Done

Added four nullable `TEXT` columns to `BatchItem` for per-worktree Postgres connection credentials, plus the corresponding Alembic migration file.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `worktree_db_host`, `worktree_db_name`, `worktree_db_user`, `worktree_db_password` to `BatchItem` |
| `orch/db/migrations/versions/4cc043748e92_i_00062_add_worktree_db_credentials.py` | New migration — `upgrade()` adds 4 columns; `downgrade()` drops them in reverse order |

## Schema Changes

- **Table**: `batch_items`
- **New columns** (all `TEXT NULL`):
  - `worktree_db_host` — hostname/IP of per-worktree Postgres; NULL in legacy mode
  - `worktree_db_name` — database name of per-worktree Postgres; NULL in legacy mode
  - `worktree_db_user` — username for per-worktree Postgres; NULL in legacy mode
  - `worktree_db_password` — password for per-worktree Postgres; NULL in legacy mode

Columns placed immediately after the existing `worktree_compose_path` column in `models.py`, forming a contiguous block of worktree-stack metadata.

## Migration Verification

- **Revision ID**: `4cc043748e92` (12-char hex, generated via `secrets.token_hex(6)`)
- **Parent**: `4876b3246ff2` (current head — F-00076)
- **`alembic history`**: Confirmed linear chain — no branches
- **`alembic show`**: Confirmed migration is at head
- **`uv run ruff check`**: Clean (no errors on modified files)
- **`make typecheck`**: Success on 217 source files
- **ORM model load**: `BatchItem.worktree_db_*` columns accessible at runtime

## Constraints Respected

- **No `docker` commands** — not invoked
- **`alembic upgrade` NOT run** against live DB (port 5433). Migration file is written; daemon will apply it at merge time per standard pipeline. This is exactly the pattern this incident was meant to prevent.
- **No new dependencies** added
- **No destructive changes** — all four columns are nullable and reversible

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | Clean — modified files formatted |
| `make typecheck` | OK — 217 source files, no errors |
| `make lint` | OK on modified files (8 pre-existing errors in unrelated files) |

## Migration Chain (linear)

```
4876b3246ff2 (F-00076) → 4cc043748e92 (I-00062, head)
```

## Notes

- The migration follows the exact pattern of `550aecbbd42b_f_00062_add_worktree_compose_stack_` (same table, same column type, same nullable style).
- All four columns are intentionally nullable — items without `ai-dev/iw-config/` (legacy mode) will have NULLs. The S03 `_launch_step` injection block raises `RuntimeError` if a compose-stack item is launched with incomplete creds, refusing to silently fall back to inherited env.
- `alembic check` fails because the live orch DB (5433) has not yet been upgraded. This is expected — the daemon will apply the migration post-merge.

## Next Step

S03 (backend-impl) will populate these columns at compose-up time and read them in `_launch_step` to build the agent subprocess env. No further DB changes needed for this work item.