# I-00053_S03_Tests_prompt

**Work Item**: I-00053 -- Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies. Testcontainers in fixtures are exempt.)

## Input Files

- `ai-dev/active/I-00053/I-00053_Issue_Design.md` — Boundary Behavior table is the spec
- S01–S02 reports
- `orch/design_doc_parser.py` — parser to test
- `orch/batch_planner.py` — `extract_affected_files()` and `analyze_dependencies()`
- `orch/cli/item_commands.py` — `iw register` flow
- `tests/conftest.py` — fixture patterns
- `tests/integration/conftest.py` — testcontainer fixtures
- `tests/CLAUDE.md` — strict rules

## Output Files

- New: `tests/unit/test_design_doc_parser.py`
- New: `tests/unit/test_batch_planner_dependencies.py`
- New: `tests/integration/test_register_persists_dependencies.py`
- `ai-dev/active/I-00053/reports/I-00053_S03_Tests_report.md`

## Context

I-00053 introduced a parser + register integration + planner refactor. Your job is to lock the public surface with tests so the bug cannot recur — both forms (silent declaration drop, false-positive file overlap).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Prior incidents had tests that checked EXISTENCE only and still passed when the feature was broken. For this incident specifically:

- BAD: `assert "depends_on" in vars(work_item)` — just checks the attribute exists.
- BAD: `assert work_item.depends_on != []` — just checks non-empty.
- GOOD: `assert work_item.depends_on == ["F-00069"]` — checks the SPECIFIC value.
- BAD: `assert analysis["F-B"].group > 0` — accidentally passes when group=1 OR group=2.
- GOOD: `assert analysis["F-B"].group == 1` — checks the EXACT wave assignment.
- BAD: `assert "tests/foo.py" not in result` — passes if the path was never extracted at all.
- GOOD: write the test such that the path WOULD be extracted under the bug, but is NOT after the fix — assert both.

Every test below MUST verify specific values, not shape.

## Requirements

### 1. Parser unit tests — `tests/unit/test_design_doc_parser.py`

Cover every row of the Boundary Behavior table in the design. Use parametrize where it reduces duplication. Each test name should describe the case.

Required cases at minimum:

```python
"""Unit tests for I-00053 design-doc parser."""

from __future__ import annotations

import pytest

from orch.design_doc_parser import (
    Dependencies,
    parse_dependencies,
    strip_excluded_sections,
)


# --- parse_dependencies ---

@pytest.mark.parametrize("content, expected", [
    ("- **Depends on**: None\n", Dependencies(depends_on=[], blocks=[])),
    ("- **Depends on**: —\n", Dependencies(depends_on=[], blocks=[])),
    ("- **Depends on**:\n", Dependencies(depends_on=[], blocks=[])),
    ("- **Depends on**: F-00069\n", Dependencies(depends_on=["F-00069"], blocks=[])),
    (
        "- **Depends on**: F-00069, I-00042, CR-99025\n",
        Dependencies(depends_on=["F-00069", "I-00042", "CR-99025"], blocks=[]),
    ),
    (
        "- **Depends on**: F-00069 (provides make test-parallel)\n",
        Dependencies(depends_on=["F-00069"], blocks=[]),
    ),
    (
        "- **Depends on**: F-00069 - reason\n",
        Dependencies(depends_on=["F-00069"], blocks=[]),
    ),
    ("- **Blocks**: F-00073\n", Dependencies(depends_on=[], blocks=["F-00073"])),
    (
        "- **Depends on**: F-00069\n- **Blocks**: F-00073\n",
        Dependencies(depends_on=["F-00069"], blocks=["F-00073"]),
    ),
])
def test_parse_dependencies_table(content: str, expected: Dependencies) -> None:
    assert parse_dependencies(content) == expected


def test_parse_dependencies_section_absent() -> None:
    """No `## Dependencies` section -> empty result, no error."""
    assert parse_dependencies("# Some doc\n\nNo deps section here.\n") == Dependencies([], [])


def test_parse_dependencies_handles_none_input() -> None:
    assert parse_dependencies(None) == Dependencies([], [])
    assert parse_dependencies("") == Dependencies([], [])


def test_parse_dependencies_case_insensitive_heading() -> None:
    content = (
        "## dependencies\n\n"
        "- **Depends on**: F-00069\n"
    )
    assert parse_dependencies(content) == Dependencies(depends_on=["F-00069"], blocks=[])


def test_parse_dependencies_extra_whitespace_tolerated() -> None:
    content = "-   **Depends on**:    F-00069  ,  I-00042   \n"
    assert parse_dependencies(content) == Dependencies(
        depends_on=["F-00069", "I-00042"], blocks=[]
    )


def test_parse_dependencies_does_not_raise_on_malformed() -> None:
    """Garbage input produces empty result + WARNING log, never raises."""
    parse_dependencies("**Depends on**: this is not a list of IDs\n")
    parse_dependencies("not even close to valid markdown")
    # Should not raise; specific output is implementation-defined for garbage,
    # but the call MUST complete.


# --- strip_excluded_sections ---

def test_strip_excluded_sections_removes_out_of_scope() -> None:
    content = (
        "## In Scope\n"
        "- foo\n"
        "## Out of Scope\n"
        "- bar\n"
        "- `tests/foo.py` (owned by F-B)\n"
        "## Acceptance Criteria\n"
        "- baz\n"
    )
    result = strip_excluded_sections(content)
    assert "tests/foo.py" not in result
    assert "## In Scope" in result
    assert "## Acceptance Criteria" in result
    assert "## Out of Scope" not in result


def test_strip_excluded_sections_removes_notes() -> None:
    content = (
        "## Description\nfoo\n## Notes\n- See `dashboard/qux.py` for details.\n"
    )
    result = strip_excluded_sections(content)
    assert "dashboard/qux.py" not in result
    assert "## Description" in result


def test_strip_excluded_sections_preserves_code_fence_headings() -> None:
    """`## Out of Scope` inside a code fence must NOT trigger section stripping."""
    content = (
        "## File Manifest\n"
        "```\n"
        "## Out of Scope\n"
        "this is example markdown inside a code block\n"
        "```\n"
        "- `dashboard/foo.py`\n"
    )
    result = strip_excluded_sections(content)
    # The real File Manifest content survives
    assert "dashboard/foo.py" in result


def test_strip_excluded_sections_handles_none() -> None:
    assert strip_excluded_sections(None) == ""
    assert strip_excluded_sections("") == ""
```

### 2. Planner regression tests — `tests/unit/test_batch_planner_dependencies.py`

```python
"""Regression tests for I-00053 — declared deps + section-aware extraction."""

from __future__ import annotations

import pytest

from orch.batch_planner import analyze_dependencies, extract_affected_files


def _item(iid: str, depends_on: list[str], content: str = "") -> dict:
    return {
        "id": iid,
        "title": iid,
        "type": "feature",
        "depends_on": depends_on,
        "design_doc_content": content,
        "steps": [],
    }


def test_declared_depends_on_drives_wave_assignment() -> None:
    """BATCH-00064 reproduction: declared dep must produce correct wave."""
    items = [
        _item("F-A", []),
        _item("F-B", ["F-A"]),
    ]
    analysis = analyze_dependencies(items)
    assert analysis["F-A"].group == 0
    assert analysis["F-B"].group == 1


def test_declared_dep_works_regardless_of_argument_order() -> None:
    """The fix must not depend on argument order."""
    for order in (["F-A", "F-B"], ["F-B", "F-A"]):
        items = [
            _item(iid, ["F-A"] if iid == "F-B" else [])
            for iid in order
        ]
        analysis = analyze_dependencies(items)
        assert analysis["F-A"].group == 0
        assert analysis["F-B"].group == 1


def test_blocks_inversion_equivalent_to_depends_on() -> None:
    """`Blocks: F-B` on F-A must produce same wave as `Depends on: F-A` on F-B.

    The Blocks inversion is applied at register time, so by the time the planner
    sees the items, F-B already has F-A in its depends_on list. Verify the
    expected DB state produces the expected wave.
    """
    # Simulating post-register state where Blocks was inverted into depends_on
    inverted = [
        _item("F-A", []),
        _item("F-B", ["F-A"]),  # set by register's inversion logic
    ]
    direct = [
        _item("F-A", []),
        _item("F-B", ["F-A"]),  # set by register parsing F-B's `Depends on`
    ]
    a_inv = analyze_dependencies(inverted)
    a_dir = analyze_dependencies(direct)
    assert a_inv["F-A"].group == a_dir["F-A"].group
    assert a_inv["F-B"].group == a_dir["F-B"].group


def test_paths_in_out_of_scope_section_do_not_create_overlap() -> None:
    """BATCH-00064 second-form reproduction: `tests/unit/test_logging.py`
    mentioned in F-A's Out of Scope (because it's owned by F-B) must NOT count.
    """
    a_doc = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `dashboard/foo.py` | Modified |\n\n"
        "## Out of Scope\n\n"
        "- `tests/unit/test_logging.py` — owned by F-B\n"
    )
    b_doc = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `tests/unit/test_logging.py` | New |\n"
    )
    files_a = set(extract_affected_files(a_doc))
    files_b = set(extract_affected_files(b_doc))
    assert "tests/unit/test_logging.py" not in files_a, (
        "Out-of-Scope mention must NOT be treated as a modification"
    )
    # F-B path is excluded by _is_test_path (`/tests/`-prefixed); test files are
    # routinely excluded from overlap. Adjust assertion if extract_affected_files
    # behavior changes — confirm by reading current implementation first.
    # If tests/ is path-excluded, this should be:
    assert files_a & files_b == set(), "No spurious overlap"


def test_paths_in_notes_section_do_not_create_overlap() -> None:
    a_doc = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `dashboard/foo.py` | Modified |\n\n"
        "## Notes\n\n"
        "- See `dashboard/bar.py` for context.\n"
    )
    files = set(extract_affected_files(a_doc))
    assert "dashboard/bar.py" not in files, (
        "Notes-section mention must NOT be treated as a modification"
    )
    assert "dashboard/foo.py" in files


def test_pre_existing_empty_depends_on_still_works() -> None:
    """Backwards compatibility: items with no declared deps and no overlap
    just go in group 0.
    """
    items = [_item("F-A", []), _item("F-B", []), _item("F-C", [])]
    analysis = analyze_dependencies(items)
    assert analysis["F-A"].group == 0
    assert analysis["F-B"].group == 0
    assert analysis["F-C"].group == 0
```

### 3. Register integration test — `tests/integration/test_register_persists_dependencies.py`

Use the existing testcontainer fixture pattern from `tests/integration/conftest.py`. Do NOT touch the live DB.

```python
"""Integration test for I-00053 — `iw register` persists declared dependencies."""

from __future__ import annotations

import pytest

from orch.cli.item_commands import register   # or whatever the public entrypoint is
from orch.db.models import WorkItem


@pytest.mark.integration
def test_register_persists_declared_depends_on(tmp_path, db_session, ...) -> None:
    """A design doc with declared `Depends on:` results in WorkItem.depends_on populated."""
    design_doc = tmp_path / "F-99001_Feature_Design.md"
    design_doc.write_text(
        "# F-99001: Test\n\n"
        "## Description\nx\n\n"
        "## Dependencies\n\n"
        "- **Depends on**: F-99000\n"
        "- **Blocks**: None\n"
    )
    # Pre-create F-99000 so the inversion target exists if Blocks were used elsewhere.
    # (Adapt to the test fixtures available; consult tests/integration/conftest.py.)
    ...
    # Call the register flow with the appropriate signature.
    register(...)

    wi = db_session.get(WorkItem, ("iw-ai-core", "F-99001"))
    assert wi is not None
    assert wi.depends_on == ["F-99000"], (
        f"Expected depends_on=['F-99000'], got {wi.depends_on}"
    )
    assert wi.blocks == []


@pytest.mark.integration
def test_register_inverts_blocks_into_other_items_depends_on(...) -> None:
    """When F-A declares `Blocks: F-B`, F-B's depends_on must gain F-A."""
    # Pre-register F-B with empty deps.
    # Register F-A whose design doc says "Blocks: F-B".
    # Assert F-B.depends_on now contains "F-A".
    ...


@pytest.mark.integration
def test_register_blocks_missing_target_logs_warning(caplog, ...) -> None:
    """Declaring `Blocks: F-99999` (unregistered) logs a WARNING and does not raise."""
    ...
    assert "not registered" in caplog.text or "skipping inversion" in caplog.text


@pytest.mark.integration
def test_register_self_dependency_filtered(caplog, ...) -> None:
    """A design doc declaring `Depends on: <self>` filters it out and logs a WARNING."""
    ...
    wi = db_session.get(WorkItem, ("iw-ai-core", "F-99002"))
    assert "F-99002" not in wi.depends_on
    assert "Self-dependency" in caplog.text


@pytest.mark.integration
def test_register_no_dependencies_section_persists_empty(...) -> None:
    """A design doc with no `## Dependencies` section results in empty depends_on."""
    ...
    assert wi.depends_on == []
    assert wi.blocks == []
```

Adapt the fixture wiring to whatever `tests/integration/conftest.py` actually provides — the fixture names above are illustrative. Read the conftest first.

### 4. Live-DB safety

Every test in this step MUST honor `tests/CLAUDE.md`:
- No connection to port 5433.
- Use `pg_engine` / `db_session` testcontainer fixtures.
- No `importlib.reload(orch.config)`.
- Use `psycopg` (not `psycopg2`) — string replacement if needed.

## Project Conventions

- Test file locations: `tests/unit/` and `tests/integration/` per existing layout.
- Use `pytest.mark.parametrize` to reduce duplication.
- Use `caplog` for log assertions.
- Type hints required; mypy clean.

## TDD Requirement

For each test:
1. Run RED first against pre-fix code (or stub the parser/register call to behave like pre-fix) to confirm the test would have caught the bug.
2. Then run GREEN against the post-fix code from S01 — must pass.

If any test passes against pre-fix code, it's a shape test, not a semantic test — rewrite it.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit` — passes including new tests
5. `make test-integration` — passes including new tests

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_design_doc_parser.py",
    "tests/unit/test_batch_planner_dependencies.py",
    "tests/integration/test_register_persists_dependencies.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
