# CR-00010_S05_Tests_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step**: S05
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md` — design document (read first)
- `ai-dev/active/CR-00010/reports/CR-00010_S01_Backend_report.md` — S01 backend contract + list of pre-existing failing tests
- `ai-dev/active/CR-00010/reports/CR-00010_S03_Frontend_report.md` — S03 frontend contract
- `tests/unit/test_state_machine.py`
- `tests/unit/test_cli_core.py`
- `tests/integration/test_cli_core.py`
- `tests/integration/test_cli_batches.py`
- `tests/integration/test_doc_commands.py` (or the integration test file that currently covers `doc-update`)
- `tests/conftest.py`
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S05_Tests_report.md`

## Context

S01 and S03 implemented the research auto-complete change. Some pre-existing tests that assert research follows the approval flow are now failing (S01 listed them in its report). You must:

1. Update every pre-existing test that conflicts with the new behavior.
2. Add new unit tests covering state-machine and validator changes.
3. Add new integration tests covering the end-to-end research flow, approve/unapprove rejection, batch rejection, and `doc-update` auto-complete.
4. Ensure every AC (AC1–AC10) is covered by at least one passing test — except AC8/AC9, which are primarily covered by the S14 browser verification (but a backend-query test for AC9 is still required).

## Requirements

### 1. Find and update existing research-flow tests

1. Read the S01 report's `notes` section for the list of pre-existing failing tests.
2. For each failing test:
   - If the test asserts that `iw approve` on a research item succeeds: rewrite it to assert the error message per AC1.
   - If the test asserts that a research item transitions through `approved` or `in_progress`: rewrite it to test the new `draft → completed` path via `iw doc-update`.
   - If the test asserts `can_transition_work_item_status(draft, approved)` is valid for research: remove the test (no longer true for research) OR rename it to reflect the non-research case.
3. Do NOT delete tests unless the tested behavior no longer exists. Prefer rewriting.
4. Grep more broadly to catch tests the S01 report missed:
   - `grep -rn "WorkItemType.Research" tests/`
   - `grep -rn "--type research" tests/`
   - `grep -rn "R-0000" tests/`

### 2. New unit tests — `tests/unit/test_state_machine.py`

Add parameterized tests covering AC7:

```python
@pytest.mark.parametrize("from_s,to_s,item_type,expected", [
    # Research: only draft → completed is valid
    (WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Research, True),
    (WorkItemStatus.draft, WorkItemStatus.approved, WorkItemType.Research, False),
    (WorkItemStatus.draft, WorkItemStatus.in_progress, WorkItemType.Research, False),
    (WorkItemStatus.completed, WorkItemStatus.draft, WorkItemType.Research, False),
    # Non-research: existing table unchanged
    (WorkItemStatus.draft, WorkItemStatus.approved, WorkItemType.Feature, True),
    (WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Feature, False),
    (WorkItemStatus.approved, WorkItemStatus.in_progress, WorkItemType.ChangeRequest, True),
    # Backward compat: item_type=None routes to the generic table
    (WorkItemStatus.draft, WorkItemStatus.approved, None, True),
    (WorkItemStatus.draft, WorkItemStatus.completed, None, False),
])
def test_work_item_status_transitions_type_aware(from_s, to_s, item_type, expected):
    assert can_transition_work_item_status(from_s, to_s, item_type) is expected
```

Add a parallel test that `validate_work_item_status` raises `InvalidTransition` on the `False` cases and passes silently on the `True` cases.

### 3. New unit tests — `tests/unit/test_cli_core.py`

Add:

```python
def test_validate_approve_transition_rejects_research():
    msg = validate_approve_transition(WorkItemStatus.draft, WorkItemType.Research)
    assert msg is not None
    assert "Cannot approve research items" in msg

def test_validate_approve_transition_non_research_draft_ok():
    # backward compat — no item_type arg returns None for draft
    assert validate_approve_transition(WorkItemStatus.draft) is None
    # explicit Feature — still returns None
    assert validate_approve_transition(WorkItemStatus.draft, WorkItemType.Feature) is None

def test_validate_approve_transition_research_check_fires_before_status_check():
    # Even if a research item is in 'approved' state, the research rejection fires first.
    msg = validate_approve_transition(WorkItemStatus.approved, WorkItemType.Research)
    assert msg is not None
    assert "Cannot approve research items" in msg
```

Mirror the same three tests for `validate_unapprove_transition` with the appropriate message substring (`"Cannot unapprove research items"`).

### 4. New integration tests — end-to-end research flow

In `tests/integration/test_cli_core.py` (or a new `tests/integration/test_research_flow.py` — match existing organization), add:

```python
def test_research_auto_complete_end_to_end(cli_runner, project, session):
    # AC3: register → doc-update → completed
    result = cli_runner.invoke(cli, ["next-id", "--type", "research"])
    research_id = result.output.strip()
    assert research_id.startswith("R-")

    result = cli_runner.invoke(cli, ["register", research_id, "Test Research", "--type", "research"])
    assert result.exit_code == 0

    # Verify item is in draft
    result = cli_runner.invoke(cli, ["-j", "item-status", research_id])
    assert result.exit_code == 0
    assert '"status": "draft"' in result.output

    # AC1: approve errors
    result = cli_runner.invoke(cli, ["approve", research_id])
    assert result.exit_code != 0
    assert "Cannot approve research items" in (result.stderr or result.output)

    # AC3: doc-update auto-completes
    result = cli_runner.invoke(cli, [
        "doc-update", research_id,
        "--doc-type", "research",
        "--title", "Test Research",
        "--content", "# Research content",
    ])
    assert result.exit_code == 0
    assert '"work_item_auto_completed": true' in result.output

    # Verify item is now completed
    result = cli_runner.invoke(cli, ["-j", "item-status", research_id])
    assert '"status": "completed"' in result.output
```

Add:

```python
def test_research_doc_update_idempotent(...):
    # AC4: second doc-update on a completed research item returns work_item_auto_completed=false
```

```python
def test_research_unapprove_errors(...):
    # AC2: unapprove a research item errors with the correct message
```

```python
def test_doc_update_non_research_does_not_autocomplete(...):
    # AC5: register feature F-00001 in draft, run doc-update with --doc-type tech and doc_id=F-00001
    # Assert feature is still in draft, work_item_auto_completed is false
```

### 5. New integration test — `batch-create` rejects research

In `tests/integration/test_cli_batches.py`:

```python
def test_batch_create_rejects_research_item(cli_runner, project, session):
    # AC6: register a research item, try to batch it, expect error
    research_id = _register_research(cli_runner, project)
    feature_id = _register_and_approve_feature(cli_runner, project)

    result = cli_runner.invoke(cli, ["batch-create", research_id, feature_id])
    assert result.exit_code != 0
    err = (result.stderr or result.output)
    assert "research item" in err
    assert "cannot be added to a batch" in err

    # Assert no batch row created
    batches = session.execute(select(Batch).where(Batch.project_id == project.id)).scalars().all()
    assert len(batches) == 0
```

### 6. Backend-query test for batch-queue exclusion (AC9)

If the batch-queue backend query lives in a helper (per S03's report), unit-test the helper directly. If it's inline in a route, add an integration test that hits the route via `TestClient` and asserts the response body does not contain the research item ID.

### 7. Pass rules

- Every new test MUST pass. No `@pytest.mark.skip`, no `@pytest.mark.xfail`. If a test cannot pass, the implementation is wrong — file it as a finding for the next review step, do not silently skip.
- Every AC must map to at least one test. List the mapping in your report:
  ```
  AC1 → tests/integration/test_cli_core.py::test_research_auto_complete_end_to_end
  AC2 → tests/integration/test_cli_core.py::test_research_unapprove_errors
  ...
  AC8 → covered by S14 browser verification (backend code for the guard is trivial; template test added in tests/integration/test_dashboard.py::test_research_item_detail_hides_approve)
  ...
  ```
- Follow the TDD hard rules from `tests/CLAUDE.md`:
  - **NEVER** connect tests to the live DB on port 5433. Use testcontainers only.
  - **MUST** replace `postgresql+psycopg2://` → `postgresql+psycopg://` in testcontainer URLs.
  - **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in integration tests (not needed if the existing `session` fixture already handles this — check `tests/conftest.py`).
  - **NEVER** mock the database in integration tests.
  - **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- Use the existing fixtures in `tests/conftest.py`. Do NOT add new fixtures unless the existing set cannot express the test.

## Project Conventions

Read `tests/CLAUDE.md` before writing. Follow the project's test-organization pattern:

- Unit tests in `tests/unit/` (no DB).
- Integration tests in `tests/integration/` (testcontainer DB).
- Test names: `test_<behavior>_<condition>`.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all new + updated tests pass.
2. `make test-integration` — all new + updated tests pass.
3. `uv run ruff check tests/`
4. `uv run ruff format --check tests/`
5. `uv run mypy tests/` if the project enables mypy on tests (check `pyproject.toml` / `mypy.ini`).

Do NOT report `tests_passed: true` unless all of the above pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00010",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_state_machine.py",
    "tests/unit/test_cli_core.py",
    "tests/integration/test_cli_core.py",
    "tests/integration/test_cli_batches.py"
  ],
  "tests_added": [],
  "tests_updated": [],
  "ac_coverage": {
    "AC1": "test path",
    "AC2": "test path",
    "AC3": "test path",
    "AC4": "test path",
    "AC5": "test path",
    "AC6": "test path",
    "AC7": "test path",
    "AC8": "browser verification (S14) + optional template test path",
    "AC9": "test path (backend query)",
    "AC10": "manual read of skill — no automated test"
  },
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
