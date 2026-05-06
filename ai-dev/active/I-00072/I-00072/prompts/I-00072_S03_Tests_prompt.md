# I-00072_S03_Tests_prompt

**Work Item**: I-00072 -- iw merge-queue retry-merge rejects items in merge_failed status
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed: testcontainers from pytest fixtures (they self-label and self-destruct via Ryuk); read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. This step is tests-only — alembic is not in your scope.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00072 --json` (canonical).
- `ai-dev/active/I-00072/I-00072_Issue_Design.md` — Design document. The "Test to Reproduce" section gives the reproduction-test skeleton; the "TDD Approach" section enumerates every regression case.
- `ai-dev/active/I-00072/reports/I-00072_S01_Backend_report.md` — to know which production files changed.
- `tests/unit/test_merge_queue_cli.py` — existing CLI test module; the new tests append to it. Read the file's `cli_runner` fixture and existing patterns before writing anything.
- `tests/CLAUDE.md` — pattern guide for testcontainer DB seeding, `BatchItem`/`DaemonEvent` factories, and the "no live DB in tests" rule.

## Output Files

- `ai-dev/active/I-00072/reports/I-00072_S03_Tests_report.md` — Step report.
- Modified: `tests/unit/test_merge_queue_cli.py` — new test class for `merge-queue retry-merge`.

## Context

S01 has aligned the CLI's retry filter with the dashboard via a new shared `OPERATOR_RECOVERABLE_MERGE_STATUSES` constant in `orch/daemon/merge_queue.py`. Your job is to lock that alignment in with tests that:

1. **Would have failed against pre-fix code** (this is what makes them "regression tests" rather than "happy-path tests").
2. **Verify semantic outcomes**, not response shape (see the I003 warning below — non-negotiable).
3. **Cover all four recoverable statuses** plus the legacy back-compat path plus the rejection path for non-merge `failed` rows.
4. **Pin parity** between the CLI's accepted set and the dashboard's via a direct import comparison.

## Requirements

### 1. Reproduction test (the GREEN-after-fix test)

Add a test that fails against `main` (pre-S01) and passes after S01:

```python
def test_i00072_retry_merge_accepts_merge_failed_status(
    self, cli_runner: CliRunner, seeded_batch_item, ...
) -> None:
    """RED before fix, GREEN after."""
```

The test must:

- Seed a `BatchItem` with `status=BatchItemStatus.merge_failed` and a valid (existing-on-disk) `worktree_info["path"]`.
- Invoke `iw merge-queue retry-merge <ITEM_ID>` via the existing `cli_runner`.
- Assert exit code is `0`.
- Assert the BatchItem row in the DB now has `status == BatchItemStatus.completed`.
- Assert a row in `daemon_events` exists with `event_type == "merge_retry_requested"` and `entity_id == <ITEM_ID>`.

If you change the test name from the design doc's example (`test_i00072_retry_merge_accepts_merge_failed_status`), keep the `i00072` prefix so the failing test is grep-able from the work item ID later.

### 2. Regression tests — full status coverage

Add one parametrised test (or one test per case — your call) covering each of these inputs:

| Status | Expected exit | Expected final status | DaemonEvent |
|--------|---------------|------------------------|-------------|
| `merge_failed` | 0 | `completed` | `merge_retry_requested` written |
| `migration_invalid` | 0 | `completed` | `merge_retry_requested` written |
| `migration_rebase_failed` | 0 | `completed` | `merge_retry_requested` written |
| `migration_rolled_back` | 0 | `completed` | `merge_retry_requested` written |

If you parametrise, use `@pytest.mark.parametrize` with the **enum members**, not their string values — that way adding a new status to the constant without adding a parametrised case will fail loudly via the coverage assertion below.

### 3. Legacy back-compat tests

Two cases:

**3a — accepted:** legacy `failed` row with merge-failure notes:

- Seed a BatchItem with `status=BatchItemStatus.failed` and `notes="Merge failed: rebase conflict on orch/db/migrations/versions/abc.py"`.
- Run `retry-merge`.
- Assert exit code 0, status flips to `completed`, audit event written.

**3b — rejected:** non-merge `failed` row:

- Seed a BatchItem with `status=BatchItemStatus.failed` and `notes="Setup failed: clone timeout"` (or any string not starting with `"Merge failed"`).
- Run `retry-merge`.
- Assert exit code is **non-zero**.
- Assert the BatchItem row's status is **unchanged** (still `failed`).
- Assert the error message names `"Merge failed"` (so the operator can grep for it in their shell history) **and** points to a different recovery path (e.g., "use item-restart" — cross-check S01's actual error string and use that exact wording).

### 4. CLI / dashboard parity test

Add a test that imports from both surfaces and asserts they agree:

```python
def test_i00072_cli_and_dashboard_share_recoverable_status_set() -> None:
    """The CLI and dashboard must accept the same set of statuses.

    Future drift is prevented by both surfaces importing
    OPERATOR_RECOVERABLE_MERGE_STATUSES from the same module.
    """
    from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES
    import orch.cli.merge_queue_commands as cli_module
    import dashboard.routers.actions as dash_module

    # Both modules import the constant by name.
    assert cli_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES
    assert dash_module.OPERATOR_RECOVERABLE_MERGE_STATUSES is OPERATOR_RECOVERABLE_MERGE_STATUSES

    # The set has exactly the four expected members.
    assert OPERATOR_RECOVERABLE_MERGE_STATUSES == frozenset({
        BatchItemStatus.merge_failed,
        BatchItemStatus.migration_invalid,
        BatchItemStatus.migration_rebase_failed,
        BatchItemStatus.migration_rolled_back,
    })
```

The `is` identity assertion is intentional — it ensures the modules **import** the constant rather than re-declaring an equal copy. If S01 left a stale local definition behind, the `is` check will fail.

### 5. Enum-coverage assertion

Add one more test that fails loudly if a new status is added to the constant without a corresponding case in the parametrised regression test:

```python
def test_i00072_every_recoverable_status_has_a_regression_case() -> None:
    """Adding a status to OPERATOR_RECOVERABLE_MERGE_STATUSES requires a test row."""
    covered = {merge_failed, migration_invalid, migration_rebase_failed, migration_rolled_back}
    assert OPERATOR_RECOVERABLE_MERGE_STATUSES == covered, (
        "Add a parametrised regression case for the new status before merging."
    )
```

(If you've parametrised case 2 by enum-members, you can derive `covered` from the parametrize argument list rather than hardcoding it. Either is fine.)

### 6. Worktree-missing case (existing behaviour preserved)

Add one regression test confirming an item in `merge_failed` whose `worktree_info["path"]` no longer exists on disk is rejected with a clear "Worktree not found" error and non-zero exit. This already works on `main` (the S01 fix doesn't touch this branch) — the test pins it so a future refactor can't drop the check.

### 7. Test placement

All new tests go in `tests/unit/test_merge_queue_cli.py` — the existing `cli_runner` fixture and seeding helpers live there. Do **NOT** put these in `tests/dashboard/` or `tests/integration/`. Reasons:

- The `client` fixture used by `tests/dashboard/` is for dashboard route tests (FastAPI TestClient). The CLI doesn't need it. (See the I-00067 lesson in `Issue_Design_Template.md`.)
- The bug is fully observable from a CLI invocation against a seeded session — no testcontainer DB cycle is required, so `tests/integration/` is over-kill and would slow CI.
- Existing CLI tests in `tests/unit/test_merge_queue_cli.py` already use the same `cli_runner` pattern — match it.

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

**Applied to this work item, this means:**

- BAD: `assert result.exit_code != 0` (shape — any non-zero passes)
- GOOD: `assert result.exit_code == 0` (semantic — specific success expectation)
- BAD: `assert "events" in [e.event_type for e in events]` (shape)
- GOOD: `assert any(e.event_type == "merge_retry_requested" for e in events)` (semantic)
- BAD: `assert item.status != BatchItemStatus.merge_failed` (shape — any other status passes, including a wrong one)
- GOOD: `assert item.status == BatchItemStatus.completed` (semantic — pins the exact expected outcome)

Apply this rule to every assertion you write.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for:

- testcontainer DB fixtures — required for any test that touches `BatchItem` / `DaemonEvent` / `WorkItem` rows.
- The hard rule: **never** point tests at the live DB on port 5433. Use only the testcontainer.
- The psycopg URL replacement: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- After `Base.metadata.create_all()`, you must execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`. The existing fixtures in this file already do this — reuse them.
- `DaemonEvent.metadata` is `event_metadata` in Python.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix.
2. `make typecheck` — zero new errors in `tests/unit/test_merge_queue_cli.py`.
3. `make lint` — zero new errors. Pay attention to `ARG001` (unused fixture) and `F811` (re-imports).

In your Subagent Result Contract, populate the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit`.
2. Confirm all your new tests pass.
3. Confirm all pre-existing tests still pass.
4. Do **NOT** report `tests_passed: true` unless ALL tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_merge_queue_cli.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Reproduction + 4 status regression cases + 2 legacy back-compat cases + parity test + enum-coverage assertion + worktree-missing case."
}
```

- `completion_status: complete` only when every requirement (1)–(7) is implemented and `make test-unit` is green.
- `notes`: list any tests you considered but excluded with reasons (e.g., a daemon end-to-end test you decided was redundant).
