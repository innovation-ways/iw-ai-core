# CR-00026: Allure report dirs scoped per-category instead of per-run

**Type**: Change Request
**Priority**: Medium
**Reason**: Per-run report directories (`allure-report-{N}`) accumulate unboundedly in the project root (~35 MB each), cannot be covered by a single `.gitignore` glob, and are never cleaned up.
**Created**: 2026-04-28
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

When the dashboard triggers a test run, `orch/test_runner.py` generates an HTML Allure report
in a per-run directory like `allure-report-71`, `allure-report-72`, … at the project root.
These directories are never deleted, accumulate ~35 MB per run, and pollute the root.
This CR changes the report directory to be per-category (`allure-report/unit/`,
`allure-report/integration/`, etc.); the existing `_generate_allure_report` helper already
deletes the old directory before regenerating, so the last-run report always overwrites the
previous one for that category automatically.

## Project Context

Read `CLAUDE.md` at the project root for architecture, conventions, and hard rules.
Key file: `orch/test_runner.py` — contains `_resolve_allure_dirs` (the only function that
needs changing) and the surrounding `launch_test_run` runner.
Tests live in `tests/unit/test_test_runner.py` (class `TestResolveAllureDirs`).

## Current Behavior

`_resolve_allure_dirs(run, db, execution_dir, run_id)` appends `-{run_id}` to both the
results base and the report base:

```
allure-results-71   ← raw pytest JSON (deleted after allure generate)
allure-report-71    ← HTML report (kept forever, never cleaned up)
allure-results-72
allure-report-72
…
```

Both directories are created directly under `execution_dir` (the project root for
iw-ai-core). The `allure_report_dir` config key in `projects.toml` overrides the base name
(`allure-report`) but the run_id suffix is always appended.

## Desired Behavior

- **Results dir** — unchanged: still `{results_base}-{run_id}` (per-run isolation prevents
  concurrent runs from clobbering each other's raw JSON).
- **Report dir** — changed: `{report_base}/{category}/` (e.g. `allure-report/unit/`).
  No run_id suffix. Because `_generate_allure_report` already removes the target directory
  before calling `allure generate`, each new run for a category automatically replaces
  the previous report.
- The `allure_report_dir` config override is still respected as the base; the category
  subdirectory is always appended.
- Existing `TestRun.allure_report_dir` rows pointing to old `allure-report-{N}` paths are
  harmless — the dashboard's `has_report` check uses `Path(...).is_dir()`, which returns
  False for non-existent paths, so stale rows silently degrade to "no report".

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/test_runner.py` · `_resolve_allure_dirs` | Appends `-{run_id}` to report base | Appends `/{category}` to report base |
| `orch/test_runner.py` · `launch_test_run` | Comment says "persistent HTML report keeps the run_id" | Comment updated |
| `tests/unit/test_test_runner.py` · `TestResolveAllureDirs` | Asserts `allure-report` (no suffix when run_id=None) or `allure-report-{N}` | Asserts `allure-report/{category}` |

### Breaking Changes

- None to external API or DB schema.
- `TestRun.allure_report_dir` for future runs will store a category-scoped path.
  Old rows are unaffected (stale paths silently fail the `is_dir()` check).

### Data Migration

- None required. Old filesystem directories (`allure-report-71`, etc.) should be deleted
  manually after deployment (`rm -rf allure-report-*/`). No DB migration needed.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Change `_resolve_allure_dirs`; update + add unit tests | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | code-review-fix-impl | Fix CRITICAL/HIGH findings from S02 | — |
| S04 | code-review-final-impl | Cross-agent global review | — |
| S05 | code-review-fix-final-impl | Fix final findings | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make test-unit` | — |

### Database Changes

- None.

### API Changes

- None.

### Frontend Changes

- None.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00026_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00026_S01_Backend_prompt.md` | Prompt | S01 backend implementation instructions |
| `prompts/CR-00026_S02_CodeReview_prompt.md` | Prompt | S02 code review of S01 |
| `prompts/CR-00026_S03_CodeReviewFix_prompt.md` | Prompt | S03 fix CRITICAL/HIGH findings from S02 |
| `prompts/CR-00026_S04_CodeReviewFinal_prompt.md` | Prompt | S04 cross-agent final review |
| `prompts/CR-00026_S05_CodeReviewFixFinal_prompt.md` | Prompt | S05 fix final review findings |

## Acceptance Criteria

### AC1: Report dir uses category subdirectory

```
Given a test run with category "unit" and default config (no override)
When _resolve_allure_dirs is called with run_id=42
Then allure_results == "{exec_dir}/allure-results-42"
 And allure_report  == "{exec_dir}/allure-report/unit"
```

### AC2: Report dir uses category subdirectory with config override

```
Given a test run with category "integration" and allure_report_dir="my-reports" in test_config
When _resolve_allure_dirs is called
Then allure_report == "{exec_dir}/my-reports/integration"
```

### AC3: Results dir still scoped per run_id

```
Given a test run with category "e2e" and run_id=99
When _resolve_allure_dirs is called
Then allure_results == "{exec_dir}/allure-results-99"
  (run_id suffix preserved for concurrent-run isolation)
```

### AC4: quality runs unaffected (still no report)

```
Given a test run with run_type="quality"
When launch_test_run completes
Then _generate_allure_report is NOT called
 And allure_report_dir stores the category-scoped path (unused)
```

### AC5: Stale old-format paths don't break the dashboard

```
Given a TestRun row with allure_report_dir="…/allure-report-71" (old format, dir deleted)
When the dashboard renders the run list
Then has_report == False  (Path.is_dir() returns False)
 And no exception is raised
```

## Rollback Plan

- **Database**: N/A — no schema changes.
- **Code**: Revert the commit that changes `_resolve_allure_dirs`. The old per-run
  directories won't exist, so old runs will show "no report" in the dashboard, but no
  data is lost.
- **Data**: No data loss. Old `allure-report-{N}` directories (if not yet manually
  removed) will simply remain unused.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/test_test_runner.py` · `TestResolveAllureDirs`):
  - Update all existing assertions that check report path to expect `{base}/{category}`.
  - Add `test_report_dir_uses_category_subdir` — default config, verifies `allure-report/unit`.
  - Add `test_report_dir_uses_config_override_with_category` — custom base + category.
  - Add `test_results_dir_retains_run_id_suffix` — verifies results path is unchanged.
  - Add `test_report_dir_no_run_id_suffix` — verifies the run_id is NOT appended to report path.
- **Integration tests**: None required (filesystem logic is fully unit-testable with mocks).
- **Updated tests**: All assertions in `TestResolveAllureDirs` that currently assert the
  report path without a category suffix need updating.

## Notes

- The `_generate_allure_report` helper (line 658) already does
  `shutil.rmtree(report_path, ignore_errors=True)` before calling `allure generate`, so no
  additional cleanup code is needed — the category dir is automatically replaced on each run.
- The `allure-results-{run_id}` directory (raw JSON) is still deleted after report
  generation (line 182: `shutil.rmtree(allure_results, ignore_errors=True)`). This is
  unchanged.
- Old `allure-report-{N}` directories at the project root should be cleaned up manually
  after deploying: `rm -rf allure-report-*/`. They are not tracked in git and pose no
  correctness risk if left in place.
