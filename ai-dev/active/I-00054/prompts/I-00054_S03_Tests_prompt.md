# I-00054_S03_Tests_prompt

**Work Item**: I-00054 -- Coverage Page Toggle Label Does Not Update on Expand/Collapse
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00054 --json`
- `ai-dev/active/I-00054/I-00054_Issue_Design.md` — Design document (read this first)
- `ai-dev/active/I-00054/reports/I-00054_S01_Frontend_report.md` — S01 implementation report
- `dashboard/templates/pages/system/coverage.html` — Modified template
- `tests/dashboard/test_coverage_page.py` — Existing test file to extend
- `dashboard/CLAUDE.md` — Dashboard conventions
- `tests/CLAUDE.md` — Test conventions

## Output Files

- `tests/dashboard/test_coverage_page.py` — Extended with new tests
- `ai-dev/active/I-00054/reports/I-00054_S03_Tests_report.md` — Step report

## Context

You are writing tests for **I-00054: Coverage Page Toggle Label Does Not Update on Expand/Collapse**.

The fix modified `dashboard/templates/pages/system/coverage.html` to add toggle state attributes (`data-pkg-toggle`, `data-expanded`), a label id (`id="expand-label-..."`), a guard in `hx-trigger`, and a `<script>` block with collapse/expand JS logic.

The actual toggle behavior (label flip, collapse on second click) is pure client-side JavaScript and can only be tested end-to-end with a browser (handled by QV Browser step S11). Your job is to write **server-side rendering tests** that prove the template emits all the attributes the JS toggle logic depends on.

## Requirements

### 1. Reproduction Test (TDD RED phase)

Add the following test to `tests/dashboard/test_coverage_page.py` inside the existing `TestCoveragePage` class. This test MUST have been failing before S01 and MUST pass after S01:

```python
def test_i00054_coverage_page_toggle_attributes_present(self, client: TestClient) -> None:
    """Reproduction test: template must render data attributes for JS toggle.

    FAILS before I-00054 fix (attributes absent).
    PASSES after fix (attributes present and correct).
    """
    populated = CoverageView(
        available=True,
        error=None,
        overall_line_pct=75.0,
        overall_branch_pct=None,
        threshold=80,
        gap_pct=-5.0,
        mtime_iso="2026-04-30T00:00:00Z",
        test_count=100,
        packages=[
            PackageRow(name="orch", line_pct=80.0, branch_pct=None, missing_lines=10, badge="green"),
        ],
        files_by_package={"orch": []},
    )
    with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
        resp = client.get("/system/coverage")
    assert resp.status_code == 200
    html = resp.text

    # data-pkg-toggle identifies each toggle row for the JS collapse handler
    assert 'data-pkg-toggle="orch"' in html
    # data-expanded initial state must be false
    assert 'data-expanded="false"' in html
    # label cell must have an id so JS can update its text
    assert 'id="expand-label-orch"' in html
    # hx-trigger must guard against firing when already expanded
    assert "this.dataset.expanded!='true'" in html
    # initial label text must be "click to expand"
    assert "click to expand" in html
    # "click to collapse" must NOT appear in the initial server-rendered HTML
    assert "click to collapse" not in html
```

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I-00002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "data-pkg-toggle" in html` (only checks attribute name exists somewhere)
- GOOD: `assert 'data-pkg-toggle="orch"' in html` (checks the specific attribute=value pair)
- BAD: `assert "expand-label" in html` (could match anything)
- GOOD: `assert 'id="expand-label-orch"' in html` (checks the exact id for the correct package)

Every assertion in these tests MUST check specific expected values, not just presence of a key or substring.

### 2. Regression Test — Multiple Packages

Add a second test verifying the attributes are rendered for ALL packages, not just one:

```python
def test_i00054_coverage_toggle_attributes_per_package(self, client: TestClient) -> None:
    """Each package row must have its own scoped toggle attributes."""
    populated = CoverageView(
        available=True,
        error=None,
        overall_line_pct=70.0,
        overall_branch_pct=None,
        threshold=80,
        gap_pct=-10.0,
        mtime_iso="2026-04-30T00:00:00Z",
        test_count=50,
        packages=[
            PackageRow(name="orch", line_pct=80.0, branch_pct=None, missing_lines=5, badge="green"),
            PackageRow(name="dashboard", line_pct=60.0, branch_pct=None, missing_lines=20, badge="amber"),
        ],
        files_by_package={"orch": [], "dashboard": []},
    )
    with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
        resp = client.get("/system/coverage")
    assert resp.status_code == 200
    html = resp.text

    # Both packages must have their own scoped attributes
    assert 'data-pkg-toggle="orch"' in html
    assert 'data-pkg-toggle="dashboard"' in html
    assert 'id="expand-label-orch"' in html
    assert 'id="expand-label-dashboard"' in html
    # hx-target must be scoped per package
    assert 'hx-target="#files-orch"' in html
    assert 'hx-target="#files-dashboard"' in html
    # guard condition must appear (at least once, for each row)
    assert html.count("this.dataset.expanded!='true'") >= 2
```

### 3. Regression Test — Script Block Present

Add a third test verifying the JS toggle script block is rendered:

```python
def test_i00054_coverage_page_toggle_script_present(self, client: TestClient) -> None:
    """The toggle script block must be present in the rendered HTML."""
    populated = CoverageView(
        available=True,
        error=None,
        overall_line_pct=75.0,
        overall_branch_pct=None,
        threshold=80,
        gap_pct=-5.0,
        mtime_iso="2026-04-30T00:00:00Z",
        test_count=100,
        packages=[
            PackageRow(name="orch", line_pct=80.0, branch_pct=None, missing_lines=10, badge="green"),
        ],
        files_by_package={"orch": []},
    )
    with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
        resp = client.get("/system/coverage")
    assert resp.status_code == 200
    html = resp.text

    # The htmx:afterSwap listener must be present to update state after expand
    assert "htmx:afterSwap" in html
    # The collapse logic identifier
    assert "data-pkg-toggle" in html  # referenced in querySelectorAll
    assert "click to collapse" not in html  # must not appear in initial render
```

### 4. Existing Tests Must Still Pass

Do NOT modify any existing tests in `tests/dashboard/test_coverage_page.py`. Run the full test file and confirm all existing tests pass alongside your new tests.

## Project Conventions

Read `tests/CLAUDE.md` for test organization and fixture patterns. Key points:
- Dashboard tests use `TestClient` with `get_db` overridden — follow the same pattern as the existing `client` fixture in this file
- Use `unittest.mock.patch` to mock `load_coverage`, as existing tests do
- Tests go inside `TestCoveragePage` class

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — runs `ruff format --check .`. If it fails, run `uv run ruff format .` to auto-fix any drift in the test file, then re-run the check.
2. **`make typecheck`** — zero errors in files you touched
3. **`make lint`** — zero errors
4. **`make test-unit`** — ALL tests pass, including your new ones

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_coverage_page.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
