# F-00076_S01_Database_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orch
DB (port 5433). Your job in this step is to WRITE the migration FILE.
The daemon applies it during the merge pipeline.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

If the migration is broken, the daemon will refuse to merge the batch.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00076 --json`
- `ai-dev/active/F-00076/F-00076_Feature_Design.md` — design document (sections: Database Changes, Acceptance Criteria AC3/AC4, Invariants 1-2)
- `orch/db/models.py:403-518` — current `WorkItem` ORM model
- `orch/db/migrations/versions/` — existing migration history (run `alembic history` to find the head)
- `orch/batch_planner.py:90-132` — existing `extract_affected_files()` regex extractor (used by the backfill)

## Output Files

- `ai-dev/active/F-00076/reports/F-00076_S01_Database_report.md` — step report
- `orch/db/migrations/versions/<rev>_add_impacted_paths_to_work_items.py` — new alembic revision
- `orch/db/models.py` — updated `WorkItem` ORM with the new column

## Context

You are adding a first-class `WorkItem.impacted_paths` JSONB column to support the cross-batch file-conflict gate (F-00076). The column stores a list of glob strings declared by the design doc. A second JSONB convention `WorkItem.config["scope_extraction"]` records provenance (declared vs regex_fallback) but does NOT need a new column.

Read the design document FIRST — sections "Description", "Database Changes", "Acceptance Criteria AC3/AC4", and "Invariants" set the contract. Then read `orch/CLAUDE.md` for SQLAlchemy 2.0 / Alembic conventions and `tests/CLAUDE.md` for testcontainer rules (FTS triggers etc.).

## Requirements

### 1. ORM column on `WorkItem`

In `orch/db/models.py` (the `WorkItem` class around line 403), add a new column AFTER the existing `blocks` column to keep grouping with dependency-related metadata:

```python
impacted_paths: Mapped[list[str]] = mapped_column(
    JSONB,
    nullable=False,
    server_default=text("'[]'"),
    comment=(
        "Globs declaring files this work item is expected to touch. "
        "Source of truth for the cross-batch launch-time conflict gate "
        "(F-00076) and the workflow-manifest.json:scope.allowed_paths "
        "merge gate. Populated by orch/cli/item_commands.py:register() "
        "from the design doc's 'Impacted Paths' section, with a regex "
        "fallback over design_doc_content when the section is absent."
    ),
)
```

Use `JSONB` (already imported in the file) — NOT `ARRAY(Text)` — because pathspec patterns may contain characters that complicate array storage and JSONB is more forward-compatible if the field grows.

### 2. Alembic migration

Create one new revision via `alembic revision --autogenerate -m "Add impacted_paths to work_items (F-00076)"`. The autogenerate may emit extra noise (FTS-trigger DDL drift); you MUST hand-trim the migration to ONLY contain:

- `op.add_column("work_items", sa.Column("impacted_paths", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False))`
- The backfill block described in (3).
- `downgrade()` drops the column.

Do NOT touch any FTS triggers, indexes, or other tables. If autogenerate proposes anything else, remove it from the script.

### 3. Backfill in `upgrade()`

After `op.add_column(...)`, populate `impacted_paths` for items that are still actionable. Use a Python loop with the connection from `op.get_bind()`. The backfill must:

- Select rows where `status NOT IN ('completed', 'archived')` AND `design_doc_content IS NOT NULL`. Use raw SQL (`sa.text`) to keep the migration independent of ORM evolution.
- For each row, compute `extract_affected_files(design_doc_content)` by importing the helper:
  ```python
  from orch.batch_planner import extract_affected_files
  ```
  This is acceptable — `batch_planner` is a pure helper module with no DB import side effects. The migration runs at upgrade time, by which point `orch/` is on the path.
- Update the row with `UPDATE work_items SET impacted_paths = :paths::jsonb WHERE project_id = :pid AND id = :iid` passing a JSON-encoded list. Use `json.dumps(paths)` for the bound parameter.
- Skip rows where the regex returned an empty list (column already defaults to `[]`).
- Log a summary at the end: `"Backfilled N items"`.

### 4. Pyproject dependency

`pathspec` is required by S04 (pipeline) for glob intersection. Run `uv add pathspec` in the worktree (this writes `pyproject.toml` and updates `uv.lock`). If `pathspec` is already a transitive dep, the change is a no-op except for promoting it to a direct dep. Document the version chosen in your report.

### 5. Tests

Add a unit test at `tests/unit/db/test_work_item_impacted_paths.py` (create the file) that:

- Creates a `WorkItem` row without specifying `impacted_paths` and asserts the SQLAlchemy default is `[]` (use the `db_session` testcontainer fixture per `tests/CLAUDE.md`).
- Creates a `WorkItem` with `impacted_paths=["orch/foo.py", "orch/bar/**"]` and round-trips through query.
- Asserts NOT NULL: trying to insert with `impacted_paths=None` raises `IntegrityError`.

Add an integration test at `tests/integration/db/test_migration_impacted_paths_backfill.py` that:

- Spins up a fresh testcontainer.
- Runs `alembic upgrade <prev_head>` to land before this migration.
- Inserts a fixture `WorkItem` with `design_doc_content` mentioning two production paths and one test path.
- Runs `alembic upgrade head`.
- Asserts the row's `impacted_paths` matches `extract_affected_files()` output (production paths only — test paths are filtered by the helper).
- Inserts a `completed` item with `design_doc_content` and asserts its `impacted_paths` stays `[]` (backfill skips it).

Follow the testcontainer rules in `tests/CLAUDE.md` strictly — psycopg URL replacement, FTS_FUNCTION_SQL/FTS_TRIGGER_SQL after `Base.metadata.create_all()`, no `importlib.reload(orch.config)`.

## Project Conventions

Read `orch/CLAUDE.md` and `tests/CLAUDE.md`. Specifically:

- SQLAlchemy 2.0 `Mapped[]` style (NOT legacy column declaration).
- psycopg v3 only.
- Composite PK `(project_id, id)` on `work_items`.
- JSONB defaults via `text("'[]'")` (NOT `default=lambda: []`).
- Migration file naming: alembic generates the revision hash; the message becomes the slug.

## TDD Requirement

Follow TDD: write the unit test (RED) before adding the column to `models.py` (GREEN). For the migration backfill, write the integration test FIRST against a fresh testcontainer, run it (it must fail because the migration doesn't exist), then write the migration.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix and re-stage if needed.
2. `make typecheck` — zero errors involving the files you touched.
3. `make lint` — zero errors.

If a tool isn't available, STOP and raise a blocker.

## Test Verification

1. `make test-unit` (Fast unit tests).
2. `make test-integration` for the migration backfill test.
3. Do NOT report `tests_passed: true` unless ALL pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_add_impacted_paths_to_work_items.py",
    "pyproject.toml",
    "uv.lock",
    "tests/unit/db/test_work_item_impacted_paths.py",
    "tests/integration/db/test_migration_impacted_paths_backfill.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "pathspec version pinned to <X.Y.Z>"
}
```
