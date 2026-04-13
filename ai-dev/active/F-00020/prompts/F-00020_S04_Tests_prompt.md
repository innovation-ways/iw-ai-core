# F-00020_S04_Tests_prompt

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S04
**Agent**: Tests
**Parallel With**: None — sequential after S03

---

## Input Files

- `ai-dev/active/F-00020/F-00020_Feature_Design.md` — Design document
- `ai-dev/active/F-00020/reports/F-00020_S02_Backend_report.md` — Backend implementation report
- `ai-dev/active/F-00020/reports/F-00020_S03_CodeReview_Backend_report.md` — Code review report

## Output Files

- `ai-dev/active/F-00020/reports/F-00020_S04_Tests_report.md`

## Context

You are adding integration tests for the Research work item type in the **iw-ai-core**
repository. The tests extend the existing test suite in `tests/integration/test_cli_core.py`.

**Repository**: ``

## Architecture References

Read before implementing:

- `tests/integration/test_cli_core.py` — Existing CLI tests, especially:
  - `test_next_id_all_types` (line ~91) — must be updated to include research
  - `test_next_id_json_output` (line ~71) — pattern for JSON tests
  - `test_full_flow_next_id_register_approve` (line ~521) — pattern for full-flow tests
  - Test fixtures: `db_session`, `test_project`, `cli_get_session`
- `tests/integration/conftest.py` — Integration test fixtures and testcontainer setup

## Previous Steps

- S01 Database: Two Alembic migrations created
- S02 Backend: Enum values and CLI extensions added
- S03 CodeReview_Backend: Review passed (check report for any outstanding items)

## Requirements

### 1. Update `test_next_id_all_types`

Add `"research": "R-"` to the `expected_prefixes` dict:

```python
expected_prefixes = {
    "feature": "F-",
    "incident": "I-",
    "cr": "CR-",
    "batch": "BATCH-",
    "research": "R-",   # ← add this
}
```

### 2. `test_next_id_research_sequential`

Verify research IDs are sequential and properly formatted:

```python
def test_next_id_research_sequential(db_session, test_project, cli_get_session):
    """Research IDs are allocated sequentially with R- prefix."""
    runner = CliRunner()
    result1 = invoke(runner, ["next-id", "--type", "research"], cli_get_session)
    result2 = invoke(runner, ["next-id", "--type", "research"], cli_get_session)
    assert result1.exit_code == 0
    assert result2.exit_code == 0
    id1 = result1.output.strip()
    id2 = result2.output.strip()
    assert id1.startswith("R-")
    assert id2.startswith("R-")
    num1 = int(id1.split("-")[1])
    num2 = int(id2.split("-")[1])
    assert num2 == num1 + 1
```

### 3. `test_next_id_research_json_output`

Verify the `--json` flag works for research:

```python
def test_next_id_research_json_output(db_session, test_project, cli_get_session):
    """JSON output for research includes correct prefix."""
    import json
    runner = CliRunner()
    result = invoke(runner, ["--json", "next-id", "--type", "research"], cli_get_session)
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data["prefix"] == "R"
    assert data["id"].startswith("R-")
```

### 4. `test_register_research_type`

Verify a research item can be registered:

```python
def test_register_research_type(db_session, test_project, cli_get_session):
    """Research work items can be registered with WorkItemType.Research."""
    from orch.db.models import WorkItem, WorkItemType
    from sqlalchemy import select
    runner = CliRunner()
    # Allocate a research ID
    id_result = invoke(runner, ["next-id", "--type", "research"], cli_get_session)
    assert id_result.exit_code == 0
    research_id = id_result.output.strip()
    # Register the item
    result = invoke(
        runner,
        ["register", research_id, "Test Research Title", "--type", "research"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output
    # Verify stored correctly
    with cli_get_session() as session:
        item = session.scalar(
            select(WorkItem).where(WorkItem.id == research_id)
        )
    assert item is not None
    assert item.type == WorkItemType.Research
    assert item.title == "Test Research Title"
```

### 5. `test_register_research_prefix_mismatch`

Verify ID prefix validation rejects mismatched types:

```python
def test_register_research_prefix_mismatch(db_session, test_project, cli_get_session):
    """Registering an R- ID as feature type is rejected."""
    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "R-00001", "Should Fail", "--type", "feature"],
        cli_get_session,
    )
    assert result.exit_code != 0
    assert "R-" in result.output or "mismatch" in result.output.lower() or "prefix" in result.output.lower()
```

### 6. `test_doc_update_research_doc_type`

Verify doc-update accepts `research` as doc type:

```python
def test_doc_update_research_doc_type(db_session, test_project, cli_get_session):
    """iw doc-update accepts --doc-type research."""
    from orch.db.models import DocType, ProjectDoc
    from sqlalchemy import select
    import tempfile, os
    runner = CliRunner()
    # Create a research item first
    id_result = invoke(runner, ["next-id", "--type", "research"], cli_get_session)
    research_id = id_result.output.strip()
    invoke(runner, ["register", research_id, "Doc Test Research", "--type", "research"], cli_get_session)
    # Write a temp content file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Research Content\nSome findings.")
        tmp_path = f.name
    try:
        result = invoke(
            runner,
            ["doc-update", research_id,
             "--doc-type", "research",
             "--title", "Doc Test Research",
             "--content-file", tmp_path],
            cli_get_session,
        )
        assert result.exit_code == 0, result.output
        with cli_get_session() as session:
            doc = session.scalar(
                select(ProjectDoc).where(ProjectDoc.doc_id == research_id)
            )
        assert doc is not None
        assert doc.doc_type == DocType.research
    finally:
        os.unlink(tmp_path)
```

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Applied to this feature: do not merely assert `result.exit_code == 0` — assert the specific
stored value (e.g. `item.type == WorkItemType.Research`, `data["prefix"] == "R"`).

## TDD Requirement

Follow TDD: write tests first (they will initially fail if the DB hasn't been migrated in the test container), then confirm they pass after the testcontainer applies all migrations.

## Test Verification

Run the full integration suite:

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/integration/test_cli_core.py -x --timeout=120 -q
```

All new tests must pass. All existing tests must continue to pass.

Also run linting on the test file:
```bash
.venv/bin/python -m ruff check tests/integration/test_cli_core.py
.venv/bin/python -m mypy tests/integration/test_cli_core.py
```

## Constraints

- Only modify `tests/integration/test_cli_core.py`
- Do not modify any source files
- All test names must follow `test_<unit>_<scenario>_<expected_result>` convention
- Tests must use existing fixtures — do not create new conftest entries

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "F-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_cli_core.py"
  ],
  "tests_passed": true,
  "test_summary": "N passed, 0 failed — all existing + 6 new tests pass",
  "coverage": "N/A — test-only step",
  "blockers": [],
  "notes": ""
}
```
