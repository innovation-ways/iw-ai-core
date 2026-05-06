# I-00071_S03_Tests_prompt

**Work Item**: I-00071 -- Scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item adds NO migrations. You MUST NOT run alembic upgrade/downgrade/stamp.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00071 --json`
- `ai-dev/active/I-00071/I-00071_Issue_Design.md` -- Design document (read fully)
- `ai-dev/active/I-00071/reports/I-00071_S01_Backend_report.md` -- S01 report (what was changed)
- `ai-dev/active/I-00071/reports/I-00071_S02_CodeReview_report.md` -- S02 review report
- `orch/design_doc_parser.py` -- The fixed parser
- `orch/daemon/scope_overlap.py` -- The fixed scope helper
- `orch/batch_planner.py` -- Parity helper (if S01 updated it)
- `tests/unit/test_design_doc_parser.py` -- Existing parser tests (you will EXTEND, not rewrite)
- `tests/unit/daemon/test_scope_overlap.py` -- Existing scope-overlap tests (you will EXTEND, not rewrite)
- `tests/unit/test_batch_planner_dependencies.py` -- Existing batch-planner tests (you will EXTEND with one parity test)
- `tests/CLAUDE.md` -- Test conventions and rules (NON-NEGOTIABLE)

## Output Files

- `ai-dev/active/I-00071/reports/I-00071_S03_Tests_report.md` -- Step report

## Context

You are writing the reproduction tests AND regression tests for **I-00071**. The fix code already landed in S01. Your job is to:

1. Confirm the fix is correct by writing tests that **would fail against the pre-fix code** and **pass against the current (post-S01) code**.
2. Add regression coverage that prevents this class of bug from recurring.

Read `ai-dev/active/I-00071/I-00071_Issue_Design.md` (Test to Reproduce, TDD Approach, Acceptance Criteria) before writing any test code.

## Test File Locations

Per `tests/CLAUDE.md`:

- Pure-Python helpers with no FastAPI/template dependency → `tests/unit/`.
- Tests using the dashboard `client` fixture → `tests/dashboard/` (NOT relevant for this incident).
- Tests requiring the testcontainer DB → `tests/integration/` (NOT relevant for this incident).

All I-00071 tests go in `tests/unit/` — both helpers under test are pure functions.

## Requirements

### 1. Reproduction tests (RED before fix, GREEN after)

Add the following tests verbatim (you may rename or restructure as long as the assertions and comments survive):

**`tests/unit/test_design_doc_parser.py`** — append a new class `class TestImpactedPathsBacktickStripping` with at least these tests:

```python
def test_strips_surrounding_code_span_backticks_in_bullet_lines(self) -> None:
    """I-00071 RED: bullet items wrapped in markdown backticks must be stored bare."""
    content = """## Impacted Paths

- `dashboard/CLAUDE.md`
- `dashboard/static/clipboard.js`
- `tests/dashboard/test_i00071.py`
"""
    result = parse_impacted_paths(content)
    assert result.found is True
    assert result.paths == [
        "dashboard/CLAUDE.md",
        "dashboard/static/clipboard.js",
        "tests/dashboard/test_i00071.py",
    ]

def test_strips_surrounding_code_span_backticks_in_fenced_code_block(self) -> None:
    """I-00071: backticks inside a fenced code block also get stripped."""
    content = """## Impacted Paths

```
`orch/foo.py`
`orch/bar/**`
```
"""
    result = parse_impacted_paths(content)
    assert result.paths == ["orch/foo.py", "orch/bar/**"]

def test_bare_paths_without_backticks_still_parse_unchanged(self) -> None:
    """I-00071 regression: backtick stripping must NOT corrupt bare paths."""
    content = """## Impacted Paths

- orch/foo.py
- orch/bar/**
"""
    result = parse_impacted_paths(content)
    assert result.paths == ["orch/foo.py", "orch/bar/**"]

def test_mixed_wrapped_and_bare_paths(self) -> None:
    """I-00071: a mix of wrapped and bare paths in the same section."""
    content = """## Impacted Paths

- `orch/foo.py`
- orch/bar/baz.py
"""
    result = parse_impacted_paths(content)
    assert result.paths == ["orch/foo.py", "orch/bar/baz.py"]
```

**`tests/unit/daemon/test_scope_overlap.py`** — extend `TestIsTestPath` (or add adjacent tests) with these `pytest.mark.parametrize` cases:

```python
# Append to the existing TestIsTestPath.test_is_test_path parametrize list:
("tests/dashboard/test_x.py", True),       # I-00071: relative tests/ prefix
("test/foo.py", True),                      # I-00071: relative test/ prefix
("__tests__/bar.py", True),                 # I-00071: relative __tests__/ prefix
("tests/conftest.py", True),                # I-00071: relative + conftest
```

ALSO add a new test class that verifies the BATCH-00078 scenario no longer triggers `find_blocking_items`:

```python
class TestI00071RegressionBatch00078:
    """I-00071 regression — BATCH-00078 reproduction.

    Two items in the same execution_group, each declaring a different test file
    under tests/dashboard/, must not block each other via the sibling-directory
    check, because is_test_path correctly classifies relative test paths now.
    """

    def test_two_test_files_under_same_dir_do_not_block_each_other(self) -> None:
        candidate_paths = ["tests/dashboard/test_i00067_recent_activity_truncation.py"]
        in_flight = [
            ("I-00069", ["dashboard/app.py", "tests/dashboard/test_live_db_guard_log_level.py"]),
        ]
        # The non-test path "dashboard/app.py" still does NOT share a parent with the
        # candidate (which has only a test path), so once test paths are stripped on
        # both sides, the function must return [] (no blocking items).
        result = find_blocking_items(candidate_paths, in_flight)
        assert result == [], (
            "Two items declaring only test files under tests/dashboard/ must not "
            "block each other. Was: %r" % (result,)
        )

    def test_non_test_sibling_still_blocks(self) -> None:
        """Sanity: production-code sibling overlap is still detected."""
        candidate_paths = ["dashboard/CLAUDE.md"]
        in_flight = [("I-00069", ["dashboard/app.py"])]
        result = find_blocking_items(candidate_paths, in_flight)
        # Both paths share parent dir `dashboard/`, neither is a test path,
        # so sibling-overlap fires.
        assert len(result) == 1
        assert result[0][0] == "I-00069"
```

### 2. Regression coverage — wider parametrize

Extend `TestIsTestPath` and `TestStripTestGlobs` parametrizations to include:
- `pytest/conftest.py` → True (regression)
- `nested/path/__tests__/file.py` → True (regression)
- `tests/integration/test_x.py` → True (relative, deeper)
- `__tests__/integration/foo.py` → True (relative)
- `helpers/test_utils.py` → False (not a test file — utility module)

### 2b. Parity test for `batch_planner._is_test_path`

`orch/batch_planner.py:_is_test_path` MUST behave identically to
`orch/daemon/scope_overlap.py:is_test_path` (the docstring of the latter says
"Mirror …"). S01 updates both in lock-step. Add a small direct test in
`tests/unit/test_batch_planner_dependencies.py` so divergence is caught:

```python
import pytest

from orch.batch_planner import _is_test_path as planner_is_test_path
from orch.daemon.scope_overlap import is_test_path as overlap_is_test_path


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/dashboard/test_x.py", True),    # I-00071: relative tests/
        ("test/foo.py", True),                  # I-00071: relative test/
        ("__tests__/bar.py", True),             # I-00071: relative __tests__/
        ("src/tests/foo.py", True),             # existing: nested
        ("conftest.py", True),                  # existing: conftest
        ("foo.test.ts", True),                  # existing: .test.
        ("test_data.json", False),              # existing: non-test
        ("src/test_utils.py", False),           # existing: non-test
    ],
)
def test_batch_planner_is_test_path_matches_scope_overlap(path: str, expected: bool) -> None:
    """I-00071: the two helpers must stay in lock-step."""
    assert planner_is_test_path(path) is expected
    assert overlap_is_test_path(path) is expected
```

Place this test near the existing `_is_test_path`-related tests in the file
(search for `tests/ paths are excluded by _is_test_path` to find the right
neighbourhood). Do NOT touch any other existing test in the file.

### 3. Semantic correctness — assert specific values

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For I-00071, this means:

- BAD: `assert result.paths` (truthy — passes even if paths still wrapped in backticks).
- BAD: `assert len(result.paths) == 3` (count only — passes if backticks survive).
- BAD: `assert "dashboard" in result.paths[0]` (substring — backtick-wrapped string contains "dashboard" too).
- GOOD: `assert result.paths == ["dashboard/CLAUDE.md", ...]` (exact equality — only passes when the bug is actually fixed).
- BAD: `assert is_test_path("tests/foo.py")` (truthy — None and 0 also fail this assertion already; the bug was returning False, not None).
- GOOD: `assert is_test_path("tests/foo.py") is True` (identity — fails clearly if it returns False).

### 4. Run the full unit suite to confirm

```bash
make test-unit
```

All tests in the suite must pass with zero failures. The new tests must:
- Pass (because S01 fixed the bugs).
- Have meaningful failure messages — every assert in I-00071 tests should describe what was expected vs. what was wrong.

### 5. Do NOT modify the production fix

You may NOT edit `orch/design_doc_parser.py`, `orch/daemon/scope_overlap.py`, or `orch/batch_planner.py`. Those are owned by S01. If you find a bug in S01's fix:
- DO NOT patch it here.
- Raise it as a `blocker` in your report so the orchestrator routes it back to S01 via the fix-cycle.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`. Match the existing test class style (capitalised class names, `test_` method prefix, dataclass-style `pytest.mark.parametrize` lists).

## TDD Requirement

This step IS the TDD verification:

- The reproduction tests above MUST FAIL when run against the pre-S01 code (you can confirm this mentally by reading S01's diff — you do NOT need to revert S01).
- They MUST PASS against the post-S01 code.
- Run `make test-unit` and capture the pass count.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report.

1. **`make format`** — auto-fixes formatting drift in test files.
2. **`make typecheck`** — must report zero errors involving the test files you touched.
3. **`make lint`** — must report zero errors.

Populate the `preflight` object accordingly.

## Test Verification (NON-NEGOTIABLE)

After writing tests:

1. Run `make test-unit` — all tests must pass.
2. Confirm the new I-00071 tests are present and passing (`pytest -k "i00071 or I00071 or I_00071 or impacted_paths or is_test_path or scope_overlap" -v` should show them).
3. Do NOT report `tests_passed: true` unless the full unit suite is green.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00071",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_design_doc_parser.py",
    "tests/unit/daemon/test_scope_overlap.py",
    "tests/unit/test_batch_planner_dependencies.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (incl. N new I-00071 tests)",
  "blockers": [],
  "notes": ""
}
```
