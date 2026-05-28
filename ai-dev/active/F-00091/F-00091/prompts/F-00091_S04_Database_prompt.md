# F-00091_S04_Database_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S04
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade` / `downgrade` / `stamp` against the live orch DB (port 5433). Your job here is to WRITE the migration file. The daemon will apply it.

Allowed: `alembic revision --autogenerate -m "..."` (writes file only), `alembic history`, running migrations inside testcontainer fixtures (via `make migration-check`).

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design (read Scope → S04, AC4, Invariant 5, and the Database Changes section)
- `orch/db/models.py` — `AgentRuntimeOption` model at line 56 (already has `context_window_tokens INT NULL`)
- `projects.toml` — Source of truth for which Pi models are currently allow-listed per project
- `orch/db/migrations/versions/` — Existing migration files; pick the head as the `down_revision`

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S04_Database_report.md`

## Context

The AI Assistant's context-usage progress bar (added in S07) needs `agent_runtime_options.context_window_tokens` populated for every (cli_tool='pi', model) pair that any project's `ai_assistant.allowed_models` list can reach. Today some rows are NULL, which is why the context-% indicator silently never renders on those tabs (the OpenCode path has its own provider-based lookup; the Pi path requires this column).

This is a **data-only migration**. No DDL. The column already exists.

Read the design doc Sections **Scope → S04**, **Database Changes**, **AC4**, and **Invariant 5** before writing the migration.

## Requirements

### 1. Enumerate the Pi models to backfill

Read `projects.toml`. For every project whose `[projects.<id>.ai_assistant]` table exists, collect `allowed_models` entries shaped `"pi/<name>"`. Deduplicate. Confirm during impl that this is the right config path; if the actual key is different (e.g., `ai_assistant.models` or `ai_assistant.pi_models`), follow whatever `projects.toml` actually uses. List the discovered (cli_tool='pi', model) pairs in the migration's docstring for auditability.

### 2. Look up canonical context-window sizes

For each Pi model in the list, source its `context_window_tokens` from public, citable specs. Document each in the migration file's docstring (e.g., `# pi/minimax/MiniMax-M2.7 → 200_000 tokens (per MiniMax docs)`). If a value is uncertain, prefer the conservative (smaller) figure and explicitly note the source. Models without a publishable canonical figure must NOT be included in the backfill — leave them NULL so they continue to render the explicit `unknown_window` state.

### 3. Generate the Alembic revision

```bash
uv run alembic revision -m "f_00091_backfill_pi_context_window_tokens"
```

Hand-author the `upgrade()` and `downgrade()` bodies. Do NOT use `--autogenerate` — there is no DDL diff.

Skeleton:

```python
def upgrade() -> None:
    pairs = [
        ("pi", "minimax/MiniMax-M2.7", 200_000),
        # ...one row per discovered Pi model with a citable window size
    ]
    bind = op.get_bind()
    for cli_tool, model, window in pairs:
        bind.execute(
            sa.text(
                """
                UPDATE agent_runtime_options
                   SET context_window_tokens = :window
                 WHERE cli_tool = :cli_tool
                   AND model    = :model
                   AND context_window_tokens IS NULL
                """
            ),
            {"cli_tool": cli_tool, "model": model, "window": window},
        )


def downgrade() -> None:
    pairs = [
        ("pi", "minimax/MiniMax-M2.7", 200_000),
        # same list
    ]
    bind = op.get_bind()
    for cli_tool, model, window in pairs:
        bind.execute(
            sa.text(
                """
                UPDATE agent_runtime_options
                   SET context_window_tokens = NULL
                 WHERE cli_tool = :cli_tool
                   AND model    = :model
                   AND context_window_tokens = :window
                """
            ),
            {"cli_tool": cli_tool, "model": model, "window": window},
        )
```

- The `WHERE context_window_tokens IS NULL` clause makes the upgrade idempotent (Invariant 5).
- The downgrade only reverts the rows it set — it does NOT delete rows or null-out columns it did not write. This preserves any value an operator may have written manually between upgrade and downgrade.

### 4. Verify locally with the migration-check gate (testcontainer only)

```bash
make migration-check
```

This spins a fresh testcontainer Postgres, runs `alembic upgrade head` from base, asserts schema-drift compliance, and round-trips through `downgrade base → upgrade head`. The gate must pass before you report completion. (S05 re-runs it as the official QV gate.)

### 5. TDD — integration test for the migration

Add `tests/integration/test_alembic_chat_context_backfill.py`:

- Use the standard testcontainer fixture from `tests/conftest.py`.
- Before applying the new migration: insert `AgentRuntimeOption` rows for two of the Pi models you are backfilling — one with `context_window_tokens = NULL`, one with a pre-existing custom value (e.g., 999_999).
- Apply the new migration via `alembic_command.upgrade(cfg, "head")` against the testcontainer.
- Assert the NULL row was filled with the expected value.
- Assert the custom-value row was NOT overwritten (the `WHERE ... IS NULL` clause is what guarantees this).
- Apply `alembic_command.downgrade(cfg, "-1")`.
- Assert the originally-NULL row is NULL again.
- Assert the custom-value row is STILL the custom value.

Run RED → GREEN → REFACTOR. Record RED in `tdd_red_evidence`.

### 6. Do NOT touch the model file

`AgentRuntimeOption` in `orch/db/models.py` is already correct — `context_window_tokens` is `Integer | None`. No model change is needed.

## Project Conventions

Read `orch/CLAUDE.md` for the migration patterns and the testcontainer rules. Read `tests/CLAUDE.md` for the FTS trigger/function rebuild pattern (not required here, but standard).

- SQLAlchemy 2.0 sync, psycopg v3 (NOT psycopg2).
- Migrations live in `orch/db/migrations/versions/`.
- Always replace `postgresql+psycopg2://` with `postgresql+psycopg://` if it appears in any test fixture (per CLAUDE.md).

## TDD Requirement

Standard RED → GREEN → REFACTOR.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Migration Verification (Database steps only — NON-NEGOTIABLE)

`make migration-check` MUST pass before reporting completion. This is non-negotiable per CR-00023.

## Test Verification (NON-NEGOTIABLE)

Run only the test file you wrote plus the migration-check gate:

```bash
uv run pytest tests/integration/test_alembic_chat_context_backfill.py -v
make migration-check
```

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "database-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/<new_revision_id>_f_00091_backfill_pi_context_window_tokens.py",
    "tests/integration/test_alembic_chat_context_backfill.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed; make migration-check passed",
  "tdd_red_evidence": "tests/integration/test_alembic_chat_context_backfill.py::test_backfills_null_only — AssertionError: row.context_window_tokens is None (expected 200000)",
  "blockers": [],
  "notes": "List of (cli_tool, model, window_tokens) pairs included in the backfill, with citation per row."
}
```
