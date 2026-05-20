# CR-00065_S01_Database_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` or any alembic mutation command against the live DB (port 5433). Your job is to **write the migration file only**.

Allowed: `alembic revision --autogenerate -m "..."`, `alembic history`, `alembic current`, `alembic show`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00065 --json`
- `ai-dev/active/CR-00065/CR-00065_CR_Design.md` — Design document
- `orch/db/models.py` — ORM models (StepRun class, ~line 779)
- `orch/db/migrations/versions/` — Existing migrations for reference
- `docs/IW_AI_Core_Database_Schema.md` — Schema documentation

## Task

Add a new nullable `session_file` column to the `step_runs` table and update the SQLAlchemy ORM model.

### 1. Update `orch/db/models.py`

In the `StepRun` class, add the following column after the existing `log_content` field (around line 836):

```python
session_file: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "Absolute path to the pi session .jsonl file for this run. "
        "Set by step_monitor on the first poll cycle after step launch. "
        "NULL for claude/opencode runs and pre-CR-00065 rows. (CR-00065)"
    ),
)
```

### 2. Generate the Alembic migration

```bash
uv run alembic revision --autogenerate -m "cr00065_add_session_file_to_step_runs"
```

Review the generated file to confirm it contains:
- `op.add_column('step_runs', sa.Column('session_file', sa.Text(), nullable=True, comment='...'))`
- A corresponding `op.drop_column('step_runs', 'session_file')` in `downgrade()`

If autogenerate produces extra unrelated changes (drift), remove them from the migration — only include the `session_file` column.

### 3. TDD RED evidence

Before the daemon applies the migration, verify the column does not exist yet and the ORM model change is syntactically valid:

```bash
# Confirm model imports cleanly
uv run python -c "from orch.db.models import StepRun; print(StepRun.session_file)"
```

### 4. Verify migration content

```bash
uv run alembic show head
```

Confirm the revision file is present and references `step_runs.session_file`.

### 5. Write integration test `tests/integration/test_step_run_session_file.py`

Using a testcontainer (see `tests/conftest.py` for the `db_session` fixture pattern), write:

```python
def test_session_file_column_readable_writable(db_session):
    """session_file column can be set and retrieved via the ORM."""

def test_session_file_column_nullable(db_session):
    """session_file defaults to NULL for a StepRun created without it."""
```

Run to confirm GREEN (testcontainer applies the new migration):

```bash
uv run pytest tests/integration/test_step_run_session_file.py -v
```

## Output Files

- `orch/db/models.py` — updated with `session_file` column on `StepRun`
- `orch/db/migrations/versions/xxxx_cr00065_add_session_file_to_step_runs.py` — migration file
- `tests/integration/test_step_run_session_file.py` — integration tests for the new column

## Subagent Result Contract

When your work is complete, call:

```bash
uv run iw step-done CR-00065 --step S01 \
  --report ai-dev/work/CR-00065/reports/CR-00065_S01_Database_report.md
```

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00065",
  "completion_status": "complete",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_cr00065_add_session_file_to_step_runs.py",
    "tests/integration/test_step_run_session_file.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "ORM model imports cleanly; migration file generated",
  "blockers": [],
  "notes": ""
}
```
