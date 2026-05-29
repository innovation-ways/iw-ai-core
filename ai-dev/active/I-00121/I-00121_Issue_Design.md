# I-00121: Allure reports & summaries missing for make-based test categories

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-29
**Reported By**: sergiog (discovered while fixing the Results-tab run-selector bug, commit eefcd837)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This item does **not** touch Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds **no** migration — the `test_runs.allure_report_dir` / `test_runs.allure_results_dir` columns already exist (`orch/db/models.py:2265,2271`). No schema change.

## Description

On the dashboard **Tests > Results** tab, almost every test category shows "Report unavailable" with no pass/fail summary. Only the `unit`, `all`, and `integration` categories produce an Allure HTML report and a parsed `summary`; the ~20 `make`-based categories (`data-layer`, `cli-contract`, `route-sweep`, `isolation`, `smoke`, `properties`, `quarantine`, `e2e`, `perf*`, …) record an `allure_report_dir` in the DB but never generate a report on disk, and their `summary` stays NULL. This is a loss of per-run test evidence/observability across most of the platform's test surface.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The test-run engine is `orch/test_runner.py` (background subprocess engine; runs `allure generate`, parses results). The Results tab is `dashboard/routers/tests.py` + `dashboard/templates/fragments/tests_results.html` (the rendering side was already corrected in commit eefcd837 — this item is about report *generation*).

## Steps to Reproduce

1. Open the dashboard Tests tab for a project whose `test_config` has `make`-based categories: `http://iw-dev-01:9900/project/iw-ai-core/tests?tab=results`.
2. In the **Run** dropdown, pick a run whose category is `make`-based (e.g. `#158 — data-layer`, `#162 — cli-contract`).
3. Observe the Results panel.

**Expected**: Each completed run shows its own Allure report (and, where parseable, pass/fail summary cards).

**Actual**: `make`-based categories show "Report unavailable" and no summary. Inspecting the DB confirms `test_runs.summary IS NULL` and the on-disk `allure_report_dir` contains no `index.html` for those runs (e.g. `allure-report/data-layer/` does not exist), while `allure-report/unit/` and `allure-report/all/` do.

## Root Cause Analysis

Two distinct command shapes flow through `launch_test_run` in `orch/test_runner.py`:

1. **pytest-direct** commands (`unit`, `all`, `integration`) contain `--alluredir=allure-results`. `test_runner.py:89-90` rewrites that flag to a run-scoped dir, so pytest emits Allure results → the `Path(allure_results).is_dir()` guard at `test_runner.py:180` is true → `_generate_allure_report` runs → report + `summary` are populated. ✅

2. **`make <target>`** commands (every other category) hit the `elif "make " in command:` branch at `test_runner.py:91-92`, which only prefixes `ALLURE_RESULTS=<rel>`. **The Makefile targets do not reference `$ALLURE_RESULTS`** — they invoke `uv run pytest … --no-cov -v` with no `--alluredir` (confirmed for `test-route-sweep`, `data-layer-check`, `test-cli-contract`, `smoke`, `test-isolation`, …). So **no `allure-results` directory is produced** → the `Path(allure_results).is_dir()` guard at `test_runner.py:180` is false → `_generate_allure_report` is never called → no report on disk, `summary` stays NULL.

Separately, `run.allure_report_dir` is assigned **unconditionally at `test_runner.py:70-71`, before the run executes** — so the DB always holds a report path even when the report directory is never created (a dangling pointer). The dashboard already mitigates the *display* of this (commit eefcd837 gates the link on on-disk `index.html`), but the DB column remains misleading.

### Fix strategy (approved)

- **Primary** — central, single-file: in the `make` branch, also export `PYTEST_ADDOPTS='--alluredir=<run-scoped-rel>'`. pytest reads `PYTEST_ADDOPTS` from the environment automatically, so pytest invoked inside *any* `make` target emits Allure results into the run-scoped dir → `_generate_allure_report` runs → report + `summary` populated. This fixes all ~20 categories at once without editing any Makefile target. (`allure-pytest` is already a dependency — `unit`/`all` use `--alluredir` today.)
- **Secondary** — data integrity: persist `run.allure_report_dir` **only after** `_generate_allure_report` succeeds, so the DB stops recording paths to reports that were never generated.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/test_runner.py` (`launch_test_run`) | `make`-based categories never emit Allure results → no report, NULL `summary`; `allure_report_dir` set even when no report exists |
| Dashboard Tests > Results tab | Shows "Report unavailable" / no summary for most categories (rendering already gracefully handled in eefcd837) |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Fix `orch/test_runner.py`: (a) inject `PYTEST_ADDOPTS='--alluredir=<rel>'` for `make` commands; (b) persist `run.allure_report_dir` only after report generation succeeds. Extract the command-rewrite into a pure, unit-testable helper. | — |
| S02 | CodeReview | Review S01 | — |
| S03 | Tests | Reproduction + regression tests | — |
| S04 | CodeReview | Review S03 | — |
| S05 | CodeReview_Final | Global review | — |
| S06..S13 | QV Gates | lint, format, typecheck, assertions, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment (`self_assess=true`) | — |

Agent slugs: `backend-impl`, `code-review-impl`, `tests-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. Columns already exist.

### Code Changes

- **Files to modify**: `orch/test_runner.py`
- **Nature of change**: Add `PYTEST_ADDOPTS` injection for `make` commands; gate `run.allure_report_dir` persistence on successful report generation; refactor the inline command-rewrite (lines 86-92) into a pure helper for testability.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00121_Issue_Design.md` | Design | This document |
| `I-00121_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00121_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00121_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00121_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00121_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00121_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00121_S14_SelfAssess_prompt.md` | Prompt | S14 self-assessment |

Reports are created during execution in `ai-dev/active/I-00121/reports/`.

## Test to Reproduce

The primary symptom (no Allure results from `make` commands) is fully captured by unit-testing the command-rewrite helper that S01 extracts. This test FAILS before the fix (no `PYTEST_ADDOPTS` injected for `make` commands) and PASSES after.

```python
# tests/unit/test_test_runner_allure_env.py
def test_make_command_injects_pytest_addopts_alluredir():
    """A `make` test command must export PYTEST_ADDOPTS=--alluredir=<run-scoped>
    so pytest inside the target emits Allure results."""
    cmd = _build_run_command(
        "make test-route-sweep",
        allure_results="/proj/allure-results-42",
        execution_dir="/proj",
    )
    # Run-scoped results dir must reach pytest via PYTEST_ADDOPTS:
    assert "PYTEST_ADDOPTS=" in cmd
    assert "--alluredir=allure-results-42" in cmd
    # And the legacy env var is still exported for Makefiles that read it:
    assert "ALLURE_RESULTS=allure-results-42" in cmd


def test_pytest_direct_command_rewrites_alluredir_without_addopts():
    """pytest-direct commands keep the inline --alluredir rewrite and do NOT
    get a duplicate PYTEST_ADDOPTS (avoids a doubled --alluredir)."""
    cmd = _build_run_command(
        "uv run pytest tests/unit/ -v --alluredir=allure-results",
        allure_results="/proj/allure-results-42",
        execution_dir="/proj",
    )
    assert "--alluredir=allure-results-42" in cmd
    assert "PYTEST_ADDOPTS=" not in cmd
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a test category whose command is `make <target>`
When the test run executes via launch_test_run
Then pytest inside the target receives --alluredir (via PYTEST_ADDOPTS),
  an allure-results directory is produced, _generate_allure_report runs,
  and run.summary is populated (when widgets/statistic.json is emitted)
```

### AC2: Dangling pointer removed

```
Given a run for which no Allure report is generated
When the run finishes
Then run.allure_report_dir is NULL (not a path to a nonexistent directory)
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test (PYTEST_ADDOPTS injection for make commands) passes,
  and the report-persistence regression test passes
```

## Regression Prevention

- The command-rewrite logic is extracted into a **pure, unit-tested helper** (`_build_run_command`), so the env-var injection contract is now locked by tests rather than living as untested inline string-building.
- An integration test asserts `run.allure_report_dir` is only set when a report is actually generated, preventing the dangling-pointer class of bug from returning.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/test_runner.py`
- `tests/unit/test_test_runner_allure_env.py`
- `tests/integration/test_test_runner_report_persistence.py`

## TDD Approach

- Reproducing test: `tests/unit/test_test_runner_allure_env.py::test_make_command_injects_pytest_addopts_alluredir` — fails before fix (no `PYTEST_ADDOPTS` for make commands), passes after.
- Unit tests: command-rewrite helper behaviour for both command shapes (make vs pytest-direct), and the no-alluredir / non-pytest command case (unchanged passthrough).
- Integration tests: `tests/integration/test_test_runner_report_persistence.py` — monkeypatch `subprocess.Popen` (no real test run) and `_generate_allure_report`; assert (a) when generation succeeds and an `index.html` exists, `run.allure_report_dir` is set + `summary` parsed; (b) when no `allure-results` dir is produced, `run.allure_report_dir` stays NULL.

## Notes

- The dashboard rendering of this symptom ("Report unavailable", on-disk gating of the report link) was already fixed in commit `eefcd837` (branch `fix/tests-results-run-selector`). This incident is strictly about **report generation** in `orch/test_runner.py`.
- Quality runs (`run_type == "quality"`) never generate Allure reports (guarded at `test_runner.py:180`); after this change their `allure_report_dir` will be NULL instead of a dangling path — strictly more correct. The Backend step must confirm `dashboard/routers/quality.py` does not depend on `allure_report_dir` being set for quality runs.
- `PYTEST_ADDOPTS` injection should be append-safe if a value is already present in the environment, and must not introduce a *second* `--alluredir` for pytest-direct commands (those already rewrite the flag inline).
