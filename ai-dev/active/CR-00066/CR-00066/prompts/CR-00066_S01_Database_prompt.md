# CR-00066_S01_Database_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade head` against the live DB. Write the migration file only.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00066 --json`
- `ai-dev/active/CR-00066/CR-00066_CR_Design.md` — Design document
- `orch/db/models.py` — `AgentRuntimeOption` (~line 56) and `StepRun` (~line 779)
- `orch/db/migrations/versions/` — Existing migrations for reference
- `docs/IW_AI_Core_Database_Schema.md` — Schema documentation

## Task

Add three new nullable columns: `context_window_tokens` on `agent_runtime_options`, and `context_tokens_peak` + `context_tokens_last` on `step_runs`. Seed `context_window_tokens` for known models.

---

### 1. Update `orch/db/models.py`

**In `AgentRuntimeOption`**, add after the `sort_order` field:

```python
context_window_tokens: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment=(
        "Maximum context window size in tokens for this model. "
        "Used to compute the context usage percentage shown in the step table. "
        "NULL = unknown / not yet configured. (CR-00066)"
    ),
)
```

**In `StepRun`**, add after the `log_content` field (or after `session_file` if CR-00065 has merged):

```python
context_tokens_peak: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment=(
        "All-time peak totalTokens observed during this run (pi runs only). "
        "Set by step_monitor each poll cycle; never decreases (tracks high-water mark "
        "even across compaction resets). NULL for non-pi runs. (CR-00066)"
    ),
)
context_tokens_last: Mapped[int | None] = mapped_column(
    Integer,
    nullable=True,
    comment=(
        "Most recent totalTokens from the pi session JSONL for this run. "
        "May be lower than context_tokens_peak after a compaction event. "
        "NULL for non-pi runs. (CR-00066)"
    ),
)
```

---

### 2. Generate the Alembic migration

```bash
uv run alembic revision --autogenerate -m "cr00066_add_context_tokens_columns"
```

Review the generated file. It must contain:
1. `op.add_column('agent_runtime_options', sa.Column('context_window_tokens', sa.Integer(), nullable=True, comment='...'))`
2. `op.add_column('step_runs', sa.Column('context_tokens_peak', sa.Integer(), nullable=True, comment='...'))`
3. `op.add_column('step_runs', sa.Column('context_tokens_last', sa.Integer(), nullable=True, comment='...'))`
4. A seed UPDATE for known models in `upgrade()`:

```python
op.execute("""
    UPDATE agent_runtime_options
    SET context_window_tokens = 200000
    WHERE model IN (
        'anthropic/claude-opus-4-7',
        'anthropic/claude-sonnet-4-6',
        'anthropic/claude-haiku-4-5-20251001',
        'minimax/MiniMax-M2.7'
    )
""")
```

5. Corresponding `drop_column` calls in `downgrade()` (no need to undo the seed data — the column is dropped).

Remove any unrelated drift from autogenerate output.

---

### 3. Integration test — `tests/integration/test_context_tokens_migration.py`

Create this file with the following test cases (testcontainers pattern — see `tests/CLAUDE.md`):

```python
def test_migration_adds_context_window_tokens_column(pg_container):
    """agent_runtime_options gains context_window_tokens INT NULL after upgrade."""

def test_migration_adds_step_run_token_columns(pg_container):
    """step_runs gains context_tokens_peak and context_tokens_last INT NULL after upgrade."""

def test_migration_seeds_known_models(pg_container):
    """After upgrade, the 4 known models have context_window_tokens = 200000; others NULL."""

def test_migration_downgrade_removes_columns(pg_container):
    """alembic downgrade -1 drops all three columns cleanly."""

def test_orm_context_tokens_read_write(pg_session):
    """Can write and read context_tokens_peak / context_tokens_last via ORM."""
```

Run RED (tests fail because columns don't exist yet), implement the migration in step 2, then rerun to confirm GREEN.

---

### 4. TDD RED evidence

```bash
uv run python -c "
from orch.db.models import AgentRuntimeOption, StepRun
print(AgentRuntimeOption.context_window_tokens)
print(StepRun.context_tokens_peak)
print(StepRun.context_tokens_last)
"
```

All three must print without error.

---

### 4. Verify migration content

```bash
uv run alembic show head
```

## Output Files

- `orch/db/models.py` — updated with 3 new columns
- `orch/db/migrations/versions/xxxx_cr00066_add_context_tokens_columns.py`
- `tests/integration/test_context_tokens_migration.py` — new integration tests

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S01 \
  --report ai-dev/work/CR-00066/reports/CR-00066_S01_Database_report.md
```

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00066",
  "completion_status": "complete",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_cr00066_add_context_tokens_columns.py",
    "tests/integration/test_context_tokens_migration.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "ORM columns import cleanly; migration file generated with seed",
  "blockers": [],
  "notes": ""
}
```
