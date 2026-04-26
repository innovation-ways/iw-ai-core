# I-00043_S03_Tests_prompt

**Work Item**: I-00043 — doc_index_poller crashes with DetachedInstanceError on every poll cycle
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp`. The testcontainer fixture
applies migrations automatically; your tests bind to it.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00043/I-00043_Issue_Design.md` — Design document (the "Test to Reproduce" section has the test skeleton)
- `ai-dev/active/I-00043/reports/I-00043_S01_Backend_report.md` — S01 report
- `ai-dev/active/I-00043/reports/I-00043_S02_CodeReview_Backend_report.md` — S02 review verdict
- `orch/daemon/doc_index_poller.py` — File under test (post-fix)
- `tests/integration/conftest.py` — Testcontainer fixture (provides `db_engine`, `session_factory`)
- `tests/CLAUDE.md` — Test conventions
- `tests/unit/daemon/` — Existing daemon unit tests (look for any that exercise pollers — borrow the fixture pattern)

## Output Files

- `tests/unit/daemon/test_doc_index_poller_session_boundary.py` — New test file
- `ai-dev/active/I-00043/reports/I-00043_S03_Tests_report.md` — Step report

## Context

S01 fixed the lifecycle bug. Your job is to write a regression test that:

1. **Proves the bug is fixed** — the test must call `DocIndexPoller.poll()`
   against a real session factory with seeded enabled projects, and verify that
   `_process_project` is invoked once per project with no DetachedInstanceError.
2. **Would have failed before the fix** — the test must use a real
   testcontainer-backed session, not a mocked session. A mocked session that
   returns plain attribute values would never trigger DetachedInstanceError, so a
   mock-based test would pass against the bug — that is exactly the kind of false
   green this incident is meant to prevent.

Read the design document first. Read `tests/CLAUDE.md`. Read existing daemon
unit tests under `tests/unit/daemon/` to find the standard fixture pattern for
"daemon component + real session factory".

## Requirements

### 1. Write `tests/unit/daemon/test_doc_index_poller_session_boundary.py`

The file lives under `tests/unit/daemon/` (not `tests/integration/`) per the
project's existing pattern — even though it uses a testcontainer-backed session,
it tests a single poller method in isolation. Follow the placement of
`tests/unit/daemon/test_migration_rebase.py` and similar files as a reference.

The test must:

- Use a real session factory backed by the testcontainer (the `session_factory`
  or `db_engine` fixture from `tests/integration/conftest.py`, depending on the
  project's actual fixture name — confirm by reading the conftest).
- Seed two `Project` rows with `enabled=True` and one with `enabled=False`.
- Construct a `DocIndexPoller` with that session factory and a minimal
  `DaemonConfig`.
- Replace `_process_project` with a recorder that appends the received
  `project_id` to a list (no real work).
- Call `poller.poll()`.
- Assert that the recorder list contains the IDs of the two enabled projects (in
  any order) and does NOT contain the disabled project's ID.
- Assert no exception was raised. (This is implicit — if `poll()` raises, the
  test fails. But a comment in the docstring should make it explicit that
  catching DetachedInstanceError is part of what's being verified.)

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty)
and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert seen` (only checks non-empty — would pass if some unrelated code
  appends one entry by coincidence)
- BAD: `assert len(seen) == 2` (count only — passes if `_process_project` is called
  with the wrong IDs)
- GOOD: `assert sorted(seen) == sorted(["project_a", "project_b"])` (semantic —
  verifies the specific expected IDs)
- GOOD: `assert "project_disabled" not in seen` (semantic — verifies the
  enabled-filter is honoured)

### 2. Use a real session, not a mocked one

This is the linchpin of the test. If you mock the session
(`MagicMock(spec=Session)`) and have it return a `MagicMock` for `Project`,
calling `mock_project.id` will return another `MagicMock`, NOT raise
DetachedInstanceError. The test would pass against the bug.

Use the real testcontainer fixture. Seed real `Project` rows. Let SQLAlchemy
manage real session lifecycle. The test will then exercise the actual codepath
that bites in production.

### 3. Falsifiability

Mentally confirm: if you reverted S01's fix (i.e., put `project.id` back
outside the `with` block), this test should FAIL with DetachedInstanceError.
If a reverted fix would still let the test pass, the test is not falsifiable
and is useless.

### 4. Do NOT modify any other files

Do NOT modify the production code in `orch/daemon/`, do NOT modify the
testcontainer fixture, do NOT add new fixtures unless absolutely required (and
even then, add them locally inside the test file rather than `conftest.py`).

## Project Conventions

Read `tests/CLAUDE.md` for the project's testing rules:

- **NEVER** connect tests to the live DB (port 5433) — testcontainer only.
- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- **NEVER** mock the database in integration tests — for this lifecycle bug,
  the rule applies to this unit test too: a mocked database hides the bug.
- **MUST** replace psycopg2 URLs in testcontainers (handled by the existing
  fixture; you don't need to do this manually).
- The testcontainer fixture runs `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after
  `Base.metadata.create_all()` (handled by the fixture).

## TDD Requirement

This step IS the test. The "RED" phase happened during S01's pre-fix
verification; the "GREEN" phase is what you verify now.

To prove falsifiability locally (optional but recommended): temporarily revert
the fix in `orch/daemon/doc_index_poller.py`, run your new test, watch it fail
with DetachedInstanceError, then restore the fix and watch it pass. Restore
the file before reporting the step complete.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make lint` — must pass on the new file.
2. `make typecheck` — must pass.
3. Run your new test directly:
   ```bash
   uv run pytest tests/unit/daemon/test_doc_index_poller_session_boundary.py -v
   ```
   Must pass.
4. `make test-unit` — must pass with zero failures.

Do **NOT** report `tests_passed: true` unless all four pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00043",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_doc_index_poller_session_boundary.py"
  ],
  "tests_passed": true,
  "test_summary": "1 new unit test passed; X total unit passed; lint clean; typecheck clean",
  "blockers": [],
  "notes": ""
}
```
