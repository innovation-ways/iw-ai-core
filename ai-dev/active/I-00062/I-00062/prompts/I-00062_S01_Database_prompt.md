# I-00062_S01_Database_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Step**: S01
**Agent**: Database (`database-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainer fixtures used by pytest; read-only `docker
ps` / `docker inspect` / `docker logs`; invoking `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB on port 5433 from this agent context. Your job in this
step is to WRITE the migration FILE only. The daemon will apply it as part
of the merge pipeline. **This incident is itself about a violation of this
rule via transitive `make` invocation — do not repeat it. Do not run
`make`, `make install`, or any target whose recipe contains
`alembic upgrade head`.** If `uv run alembic history` / `current` / `show`
is needed for cross-checking, those are read-only and allowed.

Allowed write commands for this step:
  - `uv run alembic revision -m "..."` (writes a file)
  - Hand-editing the produced migration file
  - Editing `orch/db/models.py`

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document (required)
- `orch/db/models.py` — existing `BatchItem` model (already has
  `worktree_db_port`, `worktree_app_port`, `worktree_compose_path`)
- `orch/db/migrations/versions/` — existing migration chain; today's head
  is `4876b3246ff2` (F-00076). Choose a new revision ID; parent it to the
  current head.
- For runtime step state, prefer `uv run iw item-status I-00062 --json`.

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S01_Database_report.md` -- step report
- `orch/db/models.py` — modified
- `orch/db/migrations/versions/<new_id>_i_00062_add_worktree_db_credentials.py` — new migration

## Context

You are implementing the persistence half of I-00062. The downstream Backend
step (S03) will populate these columns at compose-up time and read them in
`_launch_step` to build the agent subprocess env. Without these columns
the per-worktree DB host/name/user/password have no place to live across
the daemon restart boundary, and the daemon cannot inject them into agent
subprocesses.

Read `I-00062_Issue_Design.md` first. Then read `orch/CLAUDE.md` and
`CLAUDE.md` for ORM conventions and migration rules.

## Requirements

### 1. Add four nullable columns to `BatchItem` (orch/db/models.py)

After the existing `worktree_app_port` and `worktree_compose_path` columns
on `BatchItem`, add:

- `worktree_db_host: Mapped[str | None] = mapped_column(Text, nullable=True)`
- `worktree_db_name: Mapped[str | None] = mapped_column(Text, nullable=True)`
- `worktree_db_user: Mapped[str | None] = mapped_column(Text, nullable=True)`
- `worktree_db_password: Mapped[str | None] = mapped_column(Text, nullable=True)`

All four are nullable because items without `ai-dev/iw-config/` (no
per-worktree compose stack) leave them NULL. Use `Text`, not `String`,
matching the existing `worktree_compose_path` column style.

Place the four new columns **immediately after** the existing
`worktree_compose_path` column so the schema reads as a contiguous block of
worktree-stack metadata.

### 2. Create the alembic migration (`orch/db/migrations/versions/`)

Generate the migration filename in the project's existing convention:
`<revision_id>_i_00062_add_worktree_db_credentials.py`. The revision ID
must be a fresh 12-char hex (use `secrets.token_hex(6)` if needed; do NOT
hand-pick a memorable string). `down_revision` MUST be `"4876b3246ff2"`
(the current head on main).

The `upgrade()` function must use `op.add_column()` four times, one per
new column. The `downgrade()` function must use `op.drop_column()` four
times in **reverse order** of additions.

Example skeleton (do not copy verbatim — use the existing repo style):

```python
def upgrade() -> None:
    op.add_column("batch_items", sa.Column("worktree_db_host", sa.Text(), nullable=True))
    op.add_column("batch_items", sa.Column("worktree_db_name", sa.Text(), nullable=True))
    op.add_column("batch_items", sa.Column("worktree_db_user", sa.Text(), nullable=True))
    op.add_column("batch_items", sa.Column("worktree_db_password", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("batch_items", "worktree_db_password")
    op.drop_column("batch_items", "worktree_db_user")
    op.drop_column("batch_items", "worktree_db_name")
    op.drop_column("batch_items", "worktree_db_host")
```

Do NOT include indexes or constraints — these are read-only metadata
columns that flow through the daemon at launch time.

### 3. Verify the migration in a testcontainer (NOT against live DB)

The repo has integration test fixtures (`tests/conftest.py`) that spin up a
testcontainer Postgres and run the full migration chain. Run them and
confirm your new migration applies cleanly:

```bash
make test-integration
```

If the integration tests are too slow for inner loop, you can write a
focused integration test that boots a testcontainer, runs `alembic upgrade
head`, asserts the four columns exist on `batch_items`, then runs
`alembic downgrade -1` and asserts they are gone. The proper home is
`tests/integration/db/test_i_00062_migration.py` — but writing that test
is the **Tests step (S05)**, not yours. Your scope is the migration FILE
and the model change only.

If your testcontainer run fails, fix the migration BEFORE reporting
`completion_status: complete`.

### 4. Do NOT touch live DB

You MUST NOT run `uv run alembic upgrade head` against any DB. The daemon
applies migrations after merge. Restate this in your report.

## Project Conventions

Read `orch/CLAUDE.md` for ORM patterns:
- SQLAlchemy 2.0 declarative `Mapped[]` style
- `Text` (not `String`) for string columns by default
- Composite PKs `(project_id, id)` on most tables, but `BatchItem` uses
  the auto-increment `id` PK plus a unique `(batch_id, work_item_id)`
- Append-only tables exist (`step_runs`, `fix_cycles`, …); `batch_items`
  is NOT append-only — you can `UPDATE` it freely

Read `CLAUDE.md` (root) for the docker / migration rules.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write a failing testcontainer-based migration round-trip test
   IF you keep one local for verification. The Tests step (S05) writes the
   permanent test.
2. **GREEN**: Add the columns to the model and write the migration file
   so the test passes.
3. **REFACTOR**: Re-read the diff, ensure the migration's down_revision
   chains to `4876b3246ff2`, and confirm `alembic history` shows a single
   linear chain (no branches) when run from a temporary worktree.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run and fix:

1. **`make format`** — fix any formatting drift in modified files.
2. **`make typecheck`** — must report zero errors involving the files you
   touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-integration` — assert it passes (or that pre-existing
   failures are unrelated to your migration; document any).
2. Do **NOT** report `tests_passed: true` unless integration tests pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "I-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<id>_i_00062_add_worktree_db_credentials.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Migration revision ID: <new>; down_revision: 4876b3246ff2"
}
```
