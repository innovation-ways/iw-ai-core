# I-00105 S01 — Database Report

**Step**: S01
**Agent**: database-impl
**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Completion**: `complete`

---

## What Was Done

Added the `max_output_tokens` column to the `agent_runtime_options` table and generated the
corresponding Alembic migration.

### 1. Model change (`orch/db/models.py`)

Added `max_output_tokens` as a nullable `Integer` column on `AgentRuntimeOption`, directly
after the existing `context_window_tokens` column, with a descriptive comment:

```python
max_output_tokens: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment=(
        "Maximum output tokens this model can generate in a single response. "
        "Used to compute the EFFECTIVE input budget (context_window - max_output - buffer). "
        "NULL = unknown / not yet configured. (I-00105)"
    ),
)
```

The nullable design is intentional: `NULL` means "no reservation known" and is the safe default —
the effective-budget meter (S03) must treat `NULL` as a passthrough to the raw window (today's
behaviour), never as a hard error.

### 2. Migration (`orch/db/migrations/versions/2be8dc12874f_i_00105_add_max_output_tokens_to_agent_.py`)

- **Revision ID**: `2be8dc12874f`
- **Down-revision**: `3a3dfec7bfbd` (head of `alembic heads`)
- `upgrade()`: adds the column, then backfills `pi` / `minimax/MiniMax-M2.7` with `131072`
  (MiniMax-M2.7: 204,800-token window, 131,072-token max output — documented spec).
- `downgrade()`: drops the column.
- Only one `add_column` / one `drop_column` — no spurious `chat_tabs` alterations.
- Unrelated `chat_tabs` comment drift detected by autogenerate was stripped by hand.

### Backfill rationale

| cli_tool | model | `max_output_tokens` | Reason |
|----------|-------|---------------------|--------|
| `pi` | `minimax/MiniMax-M2.7` | `131072` | MiniMax-M2.7 max output spec (204,800 window − 131,072 = ~73K effective input) |
| `claude` / `opencode` | any | `NULL` | Known output limits not confirmed for all current/future claude and opencode model variants — leave `NULL` rather than guess |

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `max_output_tokens` column definition to `AgentRuntimeOption` |
| `orch/db/migrations/versions/2be8dc12874f_i_00105_add_max_output_tokens_to_agent_.py` | New migration file |

---

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ✅ ok — all 867 files pass ruff format |
| `make typecheck` | ✅ ok — no issues in 276 source files |
| `make lint` | ✅ ok — ruff + check_templates.py pass |
| `make migration-check` | ✅ **passed** — all 3 integration tests pass: `test_alembic_upgrade_head_succeeds_from_empty`, `test_alembic_downgrade_base_then_upgrade_head`, `test_alembic_schema_matches_create_all` |

---

## Test Summary

```
make migration-check: PASSED
3/3 tests passed (8.92s)
  ✓ test_alembic_upgrade_head_succeeds_from_empty
  ✓ test_alembic_downgrade_base_then_upgrade_head
  ✓ test_alembic_schema_matches_create_all
```

---

## TDD Red Evidence

n/a — schema + migration only; no production logic implemented yet (S03 will add the
`compute_effective_context_pct` function that the reproduction test targets).

---

## Blockers

None.

---

## Notes

- Autogenerate detected unrelated `chat_tabs` comment drift (pre-existing in the DB, not in the
  model). The migration was hand-edited to contain only the one `add_column` / one `drop_column`
  for `max_output_tokens`. This was verified by `migration-check` passing cleanly.
- The `migration-check` test applies all migrations in a fresh testcontainer — the backfill SQL
  runs against an empty `agent_runtime_options` table, which is valid (0 rows affected is fine;
  on a live DB with existing rows the `pi/MiniMax-M2.7` row would get the correct value).
- Down-revision is `3a3dfec7bfbd` (confirmed by `alembic heads`).