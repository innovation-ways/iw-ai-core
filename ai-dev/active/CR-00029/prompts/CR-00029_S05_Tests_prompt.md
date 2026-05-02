# CR-00029_S05_Tests_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Allowed: testcontainers spun up by pytest fixtures (Ryuk-managed), read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB. Migrations apply automatically inside testcontainer fixtures.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md` (AC1–AC6)
- All implementation reports: S01, S03
- `tests/CLAUDE.md` — test conventions

## Output Files

- `tests/unit/test_synthetic_setup_step_restartable.py` — new
- `tests/unit/test_actions_restart_setup_endpoint.py` — new
- `tests/unit/test_actions_restart_setup_confirm_dialog.py` — new
- `tests/integration/test_restart_setup_full_flow.py` — new
- `ai-dev/active/CR-00029/reports/CR-00029_S05_Tests_report.md`

## Context

You are authoring the test suite for **CR-00029**. Read `tests/CLAUDE.md` for project test patterns:

- Use testcontainers, never live DB (port 5433)
- After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
- Replace `psycopg2://` with `psycopg://`
- `DaemonEvent.metadata` is `event_metadata` in Python
- Use `monkeypatch.delenv()`, never `importlib.reload(orch.config)`

## Requirements

### Unit tests

#### `tests/unit/test_synthetic_setup_step_restartable.py`

Cover AC1 + AC2:

Parametrize over scenarios:

| BatchItem.status | All steps pending? | Expected restartable |
|------------------|--------------------|----------------------|
| `setup_failed` | yes | True |
| `failed` | yes | True |
| `failed` | no (one in_progress) | False |
| `failed` | no (one completed) | False |
| `pending` | yes | False |
| `setting_up` | yes | False |
| `executing` | yes | False |
| `completed` | yes | False |
| `merging` | yes | False |
| `merged` | yes | False |
| (no BatchItem at all — bi=None) | n/a | False |

```python
@pytest.mark.parametrize("bi_status,steps_state,expected", [
    (BatchItemStatus.setup_failed, "all_pending", True),
    (BatchItemStatus.failed, "all_pending", True),
    (BatchItemStatus.failed, "one_in_progress", False),
    ...
])
def test_synthetic_setup_step_restartable(bi_status, steps_state, expected, ...):
    ...
```

If the `_synthetic_setup_step` signature requires step states, build them in the fixture; otherwise rely on the implementation's DB-query path and seed accordingly.

#### `tests/unit/test_actions_restart_setup_endpoint.py`

Cover AC5 + AC6:

1. `test_restart_setup_happy_path` — given BatchItem in `setup_failed` and all steps pending, POST to the endpoint:
   - Returns 200 (htmx fragment)
   - WorkItem.status = `approved`
   - BatchItem.status = `pending`, notes None, started_at None
   - All WorkflowStep rows reset (status=pending, started_at=None, completed_at=None, report_file=None)
   - StepRun rows for the item are deleted
   - DaemonEvent of type `setup_restarted` exists with `entity_id=item_id`, `entity_type='work_item'`
2. `test_restart_setup_rejects_no_batch_item` — given no BatchItem in setup_failed/failed → 422
3. `test_restart_setup_rejects_progressed_step` — given BatchItem in `failed` but one step `in_progress` → 422
4. `test_restart_setup_rejects_executing` — given BatchItem in `executing` → 422
5. `test_restart_setup_reopens_completed_with_errors_batch` — given parent Batch in `completed_with_errors`, the action transitions it back to `approved`
6. `test_restart_setup_does_not_alter_full_restart_behavior` — call `full_restart_item` and `restart_setup` against parallel fixtures, assert outcomes are identical except for the daemon event type

Use the existing dashboard test fixture (TestClient + in-memory testcontainer DB pattern). Search `tests/dashboard/` for examples.

#### `tests/unit/test_actions_restart_setup_confirm_dialog.py`

Cover AC4:

1. `test_confirm_dialog_returns_html_with_expected_text` — GET `/project/{project_id}/api/confirm-item/restart-setup/{item_id}` (the generic dispatcher route) returns HTML containing the title `"Restart setup {item_id}?"` and the description "This deletes the worktree and resets every step." (S01 wires this into `_ITEM_ACTION_LABELS`; the dispatcher renders the title via `f"{title.rstrip('?')} {item_id}?"`).
2. `test_confirm_dialog_targets_post_endpoint` — the returned HTML contains `hx-post="/project/{project_id}/api/item/{item_id}/restart-setup"` (or the equivalent in `confirm_url`).

### Integration tests

#### `tests/integration/test_restart_setup_full_flow.py`

End-to-end (filesystem + DB):

1. Set up a Project with a real `repo_root` pointing to a temp git repo (use the existing testcontainer pattern + tmp_path).
2. Create a `.worktrees/CR29-A/` directory under that repo with some files in it (simulating a partial worktree).
3. Create a BatchItem in `setup_failed` for CR29-A with `worktree_info = {"path": str(worktree_dir)}`.
4. Create some StepRun rows pointing at log files in tmp_path (write the log files).
5. Call the `restart_setup` endpoint via TestClient.
6. Assert:
   - Worktree directory is removed (`worktree_dir.exists()` is False)
   - Log files are unlinked
   - StepRun rows are deleted
   - WorkflowStep rows are reset
   - WorkItem and BatchItem status flipped per AC5
   - DaemonEvent of type `setup_restarted` exists

Use the existing integration-test fixtures (testcontainer + tmp_path) — see `tests/integration/test_full_restart_item_flow.py` if it exists, or other integration tests touching `full_restart_item`, for the pattern.

### Updated tests

Search for any existing template-rendering tests that assert the action column for synthetic S00 rows is empty. Update them to expect the new button when restartable=True.

`grep -r "is_synthetic\|restart_setup_button\|S00" tests/` — review hits and update where relevant.

## Project Conventions

Read `tests/CLAUDE.md`:

- Testcontainer fixture pattern (PostgreSQL on a random port)
- FTS function/trigger SQL run after `create_all()`
- `psycopg://` URL replacement
- `monkeypatch.delenv()` for env-var changes

## TDD Requirement

Use TDD:

1. RED: write each test against the current code; confirm it fails (or already passes for tests of new behavior added in S01/S03)
2. GREEN: code is already written by S01+S03 — tests should pass after correct authoring
3. REFACTOR: simplify with fixtures and parametrize

If a test reveals a bug in S01/S03, raise it as a blocker rather than fixing the implementation here.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

After writing all tests:

1. `make test-unit` — all unit tests pass
2. `make test-integration` — all integration tests pass

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00029",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_synthetic_setup_step_restartable.py",
    "tests/unit/test_actions_restart_setup_endpoint.py",
    "tests/unit/test_actions_restart_setup_confirm_dialog.py",
    "tests/integration/test_restart_setup_full_flow.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (N new)",
  "blockers": [],
  "notes": "AC coverage matrix: AC1→<test>, AC2→<test>, ..., AC7→deferred to S13 (browser)"
}
```
