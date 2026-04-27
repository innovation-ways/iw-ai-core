# I-00042_S03_Tests_prompt

**Work Item**: I-00042 — PostgreSQL `batch_item_status` enum missing `migration_invalid` and `migration_rolled_back` labels
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB
(port 5433). Tests run against a testcontainer fixture that applies migrations
automatically — your tests bind to that fixture, never to the live DB.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00042/I-00042_Issue_Design.md` — Design document (read first; the "Test to Reproduce" section has the test skeleton)
- `ai-dev/active/I-00042/reports/I-00042_S01_Database_report.md` — S01 report (which migration file was created)
- `ai-dev/active/I-00042/reports/I-00042_S02_CodeReview_Database_report.md` — S02 review verdict
- `tests/integration/conftest.py` — Existing testcontainer fixture; your test binds to its `db_engine` fixture
- `tests/integration/test_oss_migration.py` — Reference pattern for a migration-focused integration test that uses `db_engine` and `pg_enum` introspection
- `orch/db/models.py` (lines 139–160) — Python `BatchItemStatus` enum

## Output Files

- `tests/integration/test_batch_item_status_enum_drift.py` — New integration test (reproduction + drift-prevention)
- `ai-dev/active/I-00042/reports/I-00042_S03_Tests_report.md` — Step report

## Context

S01 wrote the migration. S02 reviewed it. Your job is to write the test that:

1. **Proves the bug is fixed**. Before the migration ran, the PG `batch_item_status`
   enum was missing `migration_invalid` and `migration_rolled_back`. After the migration
   runs (which the testcontainer fixture does automatically by calling `alembic upgrade head`),
   the labels must be present.
2. **Prevents the bug from recurring**. The Python `BatchItemStatus` enum and the live
   PG enum can drift again the next time someone adds a Python value without writing
   a matching migration. The drift-prevention assertion catches this in CI.

Read the design document first. The test skeleton in its "Test to Reproduce" section
is your starting point — flesh it out to match the project's testing conventions in
`tests/CLAUDE.md` and `tests/integration/conftest.py`.

## Requirements

### 1. Write `tests/integration/test_batch_item_status_enum_drift.py`

The file must contain a single test function that:

- Uses the `db_engine` fixture from `tests/integration/conftest.py` (already runs
  `alembic upgrade head` against a fresh testcontainer for every test session).
- Queries `pg_enum` for the `batch_item_status` type and collects the set of labels.
- Asserts that **`migration_invalid`** and **`migration_rolled_back`** are present
  individually (semantic checks — not just "non-empty").
- Asserts the drift-prevention condition: `{e.value for e in BatchItemStatus} ⊆ pg_enum_labels`
  with a clear assertion message that names any missing values. Note: `BatchItemStatus`
  is a plain `enum.Enum` and has no `.values` attribute — derive the value set with the
  set comprehension above (or `[e.value for e in BatchItemStatus]`).

**Do NOT** assert exact equality (`pg_labels == py_labels`). PostgreSQL may have
labels that the Python enum no longer references (CR-00019 left `awaiting_review` and
`discarded` as dormant orphans, for example). The check is one-directional: every
Python value must be in PG; PG may have extras.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and
passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert pg_labels` (only checks non-empty)
- BAD: `assert len(pg_labels) >= 13` (only checks count — would pass with the wrong 13 labels)
- GOOD: `assert "migration_invalid" in pg_labels` (semantic — verifies the specific expected value)
- GOOD: `assert "migration_rolled_back" in pg_labels` (semantic — verifies the second specific value)
- GOOD: `assert not ({e.value for e in BatchItemStatus} - pg_labels)` with a message naming the missing values

### 2. Use the testcontainer fixture, not the live DB

Look at `tests/integration/test_oss_migration.py` or any other integration test for
the exact fixture wiring. The test must bind to `db_engine` (or whatever the
project's testcontainer fixture is named — confirm by reading
`tests/integration/conftest.py`). It must NOT call `get_db_url()` directly, must NOT
import from `orch/config.py` to read the live DB credentials, and must NOT connect
to port 5433.

### 3. Follow existing test conventions

Read `tests/CLAUDE.md` for test patterns:

- Test naming: `test_<scenario>_<outcome>`
- Imports at top of file, not inside functions
- Plain `pytest` — no class-based grouping unless the file already uses that style
- Use `text("...")` from `sqlalchemy` for raw SQL queries
- One assertion concept per test — but multiple `assert` lines that contribute to the
  same concept are fine (e.g., the two `in` checks plus the drift assertion together
  prove "PG enum is in sync with Python enum").

### 4. Do NOT modify any other files

Do NOT touch the migration from S01, do NOT touch `orch/db/models.py`, do NOT touch
the testcontainer fixture. Your output is a single new test file.

## Project Conventions

Read `tests/CLAUDE.md` for the project's testing rules. Most relevantly:

- **NEVER** connect tests to the live DB (port 5433) — use the testcontainer fixture.
- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- **NEVER** mock the database in integration tests.
- The testcontainer fixture replaces `psycopg2://` URLs with `psycopg://` and runs
  `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`. You don't
  need to do any of that — `db_engine` hands you a ready-to-use engine.

## TDD Requirement

This step is itself the test. The "RED" phase happens at design time — before S01's
migration ran, this test would have failed. The "GREEN" phase is verified now: with
S01's migration applied, your test must pass.

If your test passes against the post-S01 testcontainer **and** would have failed
against the pre-S01 testcontainer (you can verify this by temporarily renaming the
S01 migration file, running the test, watching it fail, then restoring the file),
you have written a correct reproduction test.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — must pass with zero failures (no unit-test regressions from
   imports or fixtures).
2. `make lint` — must pass on the new file.
3. Run your new test directly:
   ```bash
   uv run pytest tests/integration/test_batch_item_status_enum_drift.py -v
   ```
   Must pass with zero failures.

Do **NOT** report `tests_passed: true` unless all three pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_batch_item_status_enum_drift.py"
  ],
  "tests_passed": true,
  "test_summary": "1 new integration test passed; X total unit passed; lint clean",
  "blockers": [],
  "notes": ""
}
```
