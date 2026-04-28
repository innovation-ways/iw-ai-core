# CR-00026 · S01 · Backend Implementation

## Context

You are implementing CR-00026: change Allure report directories from per-run
(`allure-report-{run_id}`) to per-category (`allure-report/{category}/`).

Read the design document before starting:
`ai-dev/active/CR-00026/CR-00026_CR_Design.md`

Also read `CLAUDE.md` for hard rules (Docker, migrations, testcontainers).

## Input Files

- `ai-dev/active/CR-00026/CR-00026_CR_Design.md`
- `orch/test_runner.py` — `_resolve_allure_dirs` (line ~597) and `launch_test_run`
- `tests/unit/test_test_runner.py` — `TestResolveAllureDirs`

## Output Files

- `orch/test_runner.py` (modified)
- `tests/unit/test_test_runner.py` (modified)
- `ai-dev/active/CR-00026/reports/CR-00026_S01_Backend_report.md`

## Scope

Modify **`orch/test_runner.py`** and **`tests/unit/test_test_runner.py`** only.
Do NOT touch any other file. Do NOT add error handling, fallbacks, or abstractions
beyond what the task requires.

## What to Change

### 1. `orch/test_runner.py` — `_resolve_allure_dirs` (line ~597)

**Current logic** (simplified):

```python
suffix = f"-{run_id}" if run_id is not None else ""
results_abs = str(Path(execution_dir) / f"{results_base}{suffix}")
report_abs  = str(Path(execution_dir) / f"{report_base}{suffix}")
return results_abs, report_abs
```

**New logic**:

- Results dir: unchanged — still appends `-{run_id}` suffix when run_id is not None.
- Report dir: use `{report_base}/{run.category}` instead (no run_id suffix, category subdir).

```python
suffix = f"-{run_id}" if run_id is not None else ""
results_abs = str(Path(execution_dir) / f"{results_base}{suffix}")
report_abs  = str(Path(execution_dir) / report_base / run.category)
return results_abs, report_abs
```

Update the docstring of `_resolve_allure_dirs` to reflect the new behavior.
Remove the mention of "persistent HTML report keeps the run_id too" from the
inline comment in `launch_test_run` (around line 67-68).

### 2. `tests/unit/test_test_runner.py` — `TestResolveAllureDirs`

Follow **TDD RED-GREEN-REFACTOR**:

**RED** — update existing tests so they fail with the current code:

All existing assertions about the report path that expect `"/exec/test-report"`,
`"/exec/quality-report"`, or `"/exec/allure-report"` (without a category subdir)
must be updated to expect `"/exec/test-report/{category}"`,
`"/exec/quality-report/{category}"`, or `"/exec/allure-report/{category}"`.

The `_make_run(run_type=...)` helper must also supply a `category` value so the
new path can be asserted correctly. Use `category="unit"` as the default in
`_make_run` when a category is not explicitly set, or pass it explicitly in tests
that need a specific category.

Add four new test methods to `TestResolveAllureDirs`:

```python
def test_report_dir_uses_category_subdir(self) -> None:
    """Default config: report dir is allure-report/<category>."""

def test_report_dir_uses_config_override_with_category(self) -> None:
    """Custom allure_report_dir base: report dir is <override>/<category>."""

def test_results_dir_retains_run_id_suffix(self) -> None:
    """Results dir still appends run_id suffix for concurrent-run isolation."""

def test_report_dir_no_run_id_suffix(self) -> None:
    """Report dir does NOT contain the run_id — verifies old behavior is gone."""
```

**GREEN** — implement the changes in `_resolve_allure_dirs` so all tests pass.

**REFACTOR** — clean up: remove stale comments only (no logic changes).

## Verification

Run unit tests to confirm all pass:

```bash
make test-unit
```

All tests in `TestResolveAllureDirs` must pass. No other test class should regress.

## Definition of Done

- [ ] `_resolve_allure_dirs` returns `{report_base}/{category}` for the report dir
- [ ] Results dir still uses `-{run_id}` suffix
- [ ] All existing `TestResolveAllureDirs` tests updated and passing
- [ ] Four new tests added and passing
- [ ] `make test-unit` exits 0
- [ ] No other files modified
