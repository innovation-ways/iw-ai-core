# F-00001_S06_Tests_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Step**: S06
**Agent**: Tests

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- `ai-dev/work/F-00001/reports/F-00001_S01_Backend_report.md` -- Backend report
- `ai-dev/work/F-00001/reports/F-00001_S03_API_report.md` -- API report
- `ai-dev/work/F-00001/reports/F-00001_S04_Frontend_report.md` -- Frontend report

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S06_Tests_report.md` -- Step report

## Context

You are adding test coverage for **Batch Archive with Post-Merge Actions**.

Read the design document first to understand the full scope. Then read `CLAUDE.md` for project-specific testing patterns and conventions.

S01 created unit tests for the batch archiver. Your job is to add **integration tests** that exercise the full flow end-to-end with a real database, plus any additional unit tests for edge cases.

## Requirements

### 1. Integration tests: `tests/integration/test_batch_archive.py`

These tests use testcontainers PostgreSQL (see `CLAUDE.md` testing rules). Follow the exact fixture patterns from existing integration tests like `tests/integration/test_models.py`.

**Test cases:**

- `test_archive_completed_batch_transitions_to_archived` — Create a project, batch, and batch items in `completed` status. Call the archive endpoint. Verify `batch.status == archived` and all merged work items have `archived_at` set.

- `test_archive_completed_with_errors_batch` — Create a batch with mixed merged/failed items. Archive it. Verify merged items are archived, failed items are skipped.

- `test_archive_batch_invalid_status_returns_422` — Try to archive a batch in `executing` status. Verify HTTP 422 is returned.

- `test_archive_batch_emits_daemon_event` — Archive a batch and verify a `DaemonEvent` with `event_type="batch_archived"` exists in the DB.

- `test_archive_batch_post_commands_run` — Create a project with `config = {"post_archive_commands": ["echo hello"]}`. Archive a batch. Verify the command was executed (check via side effects or logs).

### 2. Additional unit test edge cases: `tests/unit/test_batch_archiver.py`

Add any edge cases not covered by S01:

- `test_archive_batch_no_items` — Batch with zero items still transitions to archived
- `test_archive_batch_project_not_found` — Project missing from DB → appropriate error
- `test_archive_batch_concurrent_attempt` — Second call when batch is already archived → raise or skip gracefully

### 3. Test conventions

From `CLAUDE.md`:

- **NEVER** connect tests to the live database (port 5433)
- **ALL** DB tests use `testcontainers` (random Docker port)
- After `Base.metadata.create_all()`, execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
- testcontainers returns `psycopg2` URLs — always replace with `psycopg`
- **NEVER** mock the database in integration tests

## Project Conventions

Read the project's `CLAUDE.md` for:

- Test organization and fixtures
- Build and run commands
- Framework-specific patterns

Follow all rules defined there exactly. When in doubt, match existing tests in the repository.

## Semantic Correctness Warning (I003 Lesson)

Do NOT write tests that merely check "the function returns what it returns." Every assertion must verify **intended behavior from the design document**, not just mirror the implementation. If a test would pass even when the code is wrong, it is not a real test. Compare expected values against the acceptance criteria and boundary behaviors defined in the design document.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first
2. **GREEN**: If tests require additional implementation changes to pass, make those changes
3. **REFACTOR**: Clean up while keeping tests green

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` and `make test-integration`
2. Run lint and type checking
3. Do **NOT** report `tests_passed: true` unless ALL tests pass with zero failures

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "Tests",
  "work_item": "F-00001",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_batch_archive.py",
    "tests/unit/test_batch_archiver.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
