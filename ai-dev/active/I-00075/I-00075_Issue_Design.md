# I-00075: Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-09
**Reported By**: CR-00039 self-assess (`ai-dev/active/CR-00039/reports/CR-00039_self_assess_report.md` finding [2])
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.
This incident does NOT touch any docker container, volume, or network state. The new fixture file is loaded by `scripts/e2e_apply_item_fixtures.py` which is invoked by the daemon (`orch/daemon/browser_env.py:_apply_per_item_fixtures`) inside an already-running per-worktree compose stack — no docker commands are issued from agent code.

## ⛔ Migrations: agents generate, daemon applies

This incident leaves migrations unchanged. No alembic revision is generated; no schema changes are required. The fix uses existing tables only (`work_items`, `workflow_steps`, `fix_cycles`, `step_runs`, `batches`, `batch_items`).

## Description

Browser verification of the fix-cycle amber pill (`↺SXX`) feature in `dashboard/templates/components/step_pipeline.html:33-41` is currently unverifiable because no item in the per-worktree E2E DB has `fix_cycle_count > 0`. CR-00039 S08 V3 returned `n/a` with `failure_class=env_data_missing` for this reason. The fix authors a per-item E2E fixture under `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` that creates a synthetic completed item with at least one `FixCycle` row, so I-00075's own browser verification (and any future item that copies the pattern) can exercise the amber-pill rendering branch end-to-end.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Particularly relevant: the per-worktree compose stack opted in via `ai-dev/iw-config/`, the `IW_E2E_SEED=1` guardrail in `orch/db/identity.py`, and the `_apply_per_item_fixtures` flow documented in `orch/daemon/browser_env.py:500-600`.

## Browser Evidence

**Pre-fix evidence**: deferred — the dev environment for the per-worktree compose stack is not running on the design host. The pre-fix state is fully documented in CR-00039's S08 reports:

- `ai-dev/active/CR-00039/reports/CR-00039_S08_QvBrowser_report.md:13` — "The production pg_dump seed contains zero items with `fix_cycle_count > 0`. All 4 completed items show Fix Cycles = 0."
- `ai-dev/active/CR-00039/reports/CR-00039_S08_BrowserVerification_Report.md:43` — "The feature cannot be visually verified without an item that has `fix_cycle_count > 0` in the database."

These two excerpts together prove the bug exists today.

## Steps to Reproduce

1. Approve and execute any work item that ships UI changes to `dashboard/templates/components/step_pipeline.html` (CR-00039 was the trigger).
2. The daemon brings up the per-worktree compose stack via `ai-dev/iw-config/worktree-seed.sh`, which `pg_dump`s the production orch DB into the worktree DB.
3. The daemon then calls `_apply_per_item_fixtures(item_id, …)` which loads only fixtures from `ai-dev/active/<item_id>/e2e_fixtures/`.
4. The qv-browser step opens the History page and clicks an item to inspect its step pipeline.
5. The verification expects to see at least one item rendering an `↺SXX` amber pill.

**Expected**: the History page (or the item-detail page reached from it) shows at least one item with `fix_cycle_count > 0`, and the step pipeline renders one amber pill per fix cycle (`step_pipeline.html` lines 33–41).

**Actual**: every item visible in the History page shows `Fix Cycles = 0` because the production pg_dump captures only items whose original fix-cycle state was either archived away or never present in the production DB. V3 must be reported as `n/a / env_data_missing` and the fix-cycle pill rendering branch is never visually exercised.

## Browser Verification Script

The post-fix verification is run by the qv-browser agent inside the worktree compose stack. The script lives in `prompts/I-00075_S13_BrowserVerification_prompt.md`. The Vs assert that, after `_apply_per_item_fixtures("I-00075", …)` runs, an item exists whose detail page renders at least one `iw-pipeline-pill--fixcycle` div with text `↺S` (per `step_pipeline.html:36-39`).

## Root Cause Analysis

Two-layer environmental gap:

1. `orch/daemon/browser_env.py:537-543` (`_apply_per_item_fixtures`) only resolves fixtures under `ai-dev/active/<verifying-item>/e2e_fixtures/`. The F-00055 archive fixture (`ai-dev/archive/F-00055/e2e_fixtures/001_f00055_workflow.py`) that *would* create fix-cycle rows is **never** applied during browser verification of any other item — its scope is F-00055 only. This is by design (per-item isolation) but means each new item that needs fix-cycle data must author its own fixture.
2. CR-00039 needed a fixture under `ai-dev/active/CR-00039/e2e_fixtures/` to demonstrate the amber pill — none was authored, so V3 was unverifiable. The CR-00039 self-assess report (finding [2]) recommended adding one; this incident files that work as a reusable, copy-pastable pattern under I-00075.

The render path itself (`dashboard/templates/components/step_pipeline.html:33-41`, computed `fix_cycle_count` in `dashboard/routers/items.py:367-374` and `:483`) is correct — confirmed by code inspection in CR-00039 S08. No production code change is needed.

## Affected Components

| Component | Impact |
|-----------|--------|
| `ai-dev/active/I-00075/e2e_fixtures/` (new) | Source-of-truth fixture seeding a synthetic item with `WorkflowStep` + `FixCycle` rows so I-00075's qv-browser step can render the amber pill. |
| `orch/daemon/browser_env.py:_apply_per_item_fixtures` (read-only) | Already loads any `*.py` matching `ai-dev/active/<item_id>/e2e_fixtures/*.py` — no change needed; this incident validates the existing mechanism with the first dedicated fix-cycle fixture. |
| `dashboard/templates/components/step_pipeline.html` (read-only) | Render branch on lines 33–41 becomes verifiable once the fixture is loaded. |
| `tests/integration/test_i00075_fix_cycle_fixture.py` (new) | Regression test asserting the fixture is idempotent and seeds the expected `WorkflowStep` + `FixCycle` rows; prevents this fixture from drifting silently. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Author `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` mirroring the F-00055 fixture pattern. | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | tests-impl | Add `tests/integration/test_i00075_fix_cycle_fixture.py` — verifies the fixture seeds a `WorkItem` + ≥1 `WorkflowStep` + ≥1 `FixCycle` row, and is idempotent on re-run. Reproduction test: pre-fix, no fixture file existed and `fix_cycle_count` for any seeded item was 0. | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Global review across S01..S04 | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make type-check` | — |
| S09 | qv-gate | `make arch-check` | — |
| S10 | qv-gate | `make security-sast` | — |
| S11 | qv-gate | `make test-unit` | — |
| S12 | qv-gate | `make allure-integration` (full integration suite, includes the new test) | — |
| S13 | qv-browser | Browser verification of the amber-pill render branch using the new fixture | — |
| S14 | self-assess-impl | Post-execution self-assessment (`projects.toml: self_assess = true`) | — |

Agent slugs: `backend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration is generated. Fixture inserts only at runtime against the per-worktree DB (and against the testcontainer in the integration test).

### Code Changes

- **Files to modify**: None (production code is correct)
- **Nature of change**: Add new test-data files only — `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` and `tests/integration/test_i00075_fix_cycle_fixture.py`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00075_Issue_Design.md` | Design | This document |
| `I-00075_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00075_S01_Backend_prompt.md` | Prompt | Author the fixture file |
| `prompts/I-00075_S02_CodeReview_Backend_prompt.md` | Prompt | Per-agent review of S01 |
| `prompts/I-00075_S03_Tests_prompt.md` | Prompt | Author the regression test |
| `prompts/I-00075_S04_CodeReview_Tests_prompt.md` | Prompt | Per-agent review of S03 |
| `prompts/I-00075_S05_CodeReview_Final_prompt.md` | Prompt | Cross-agent final review |
| `prompts/I-00075_S13_BrowserVerification_prompt.md` | Prompt | qv-browser verification script |
| `prompts/I-00075_S14_SelfAssess_prompt.md` | Prompt | Self-assessment via iw-item-analyze |
| `e2e_fixtures/001_fix_cycle_demo.py` | Fixture | (Created in S01) Synthetic item with fix cycles |

## Test to Reproduce

The pre-fix state is "the file does not exist". The reproducing test that proves the bug exists is therefore:

```python
# tests/integration/test_i00075_fix_cycle_fixture.py
from pathlib import Path

from sqlalchemy import select

from orch.db.models import FixCycle, WorkflowStep
from scripts.e2e_seed import _run_fixture


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "ai-dev" / "active" / "I-00075" / "e2e_fixtures" / "001_fix_cycle_demo.py"


def test_i00075_fixture_file_exists():
    """Pre-fix this assertion FAILS (file is absent); post-fix it PASSES."""
    assert FIXTURE_PATH.is_file(), (
        f"Fixture {FIXTURE_PATH} must exist so qv-browser can render fix-cycle "
        f"amber pills against a seeded item — see I-00075 root cause analysis."
    )


def test_i00075_fixture_seeds_at_least_one_fix_cycle(integration_db):
    """After the fixture runs, the per-worktree DB must contain ≥1 FixCycle row
    attached to a WorkflowStep that belongs to the synthetic demo item."""
    _run_fixture(FIXTURE_PATH, integration_db)
    integration_db.flush()

    fix_cycle_count = integration_db.scalar(
        select(FixCycle).join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
        .where(WorkflowStep.work_item_id == "I-99001")
    )
    assert fix_cycle_count is not None, (
        "Fixture must seed at least one FixCycle row for I-99001 so the "
        "step_pipeline.html amber-pill branch (lines 33-41) can render."
    )
```

The exact `integration_db` fixture name and import path follow the conventions in `tests/conftest.py` and `tests/integration/conftest.py` — the Tests step author MUST verify these against the existing fixtures and adjust accordingly.

## Browser Verification Test

After the fixture is loaded into the per-worktree DB by `_apply_per_item_fixtures("I-00075", …)`, the qv-browser agent (S13) will:

1. Navigate to `${IW_BROWSER_BASE_URL}/project/iw-ai-core/work/I-99001` (the synthetic item's detail page).
2. Snapshot the step pipeline element and confirm at least one DOM node with class `iw-pipeline-pill--fixcycle` is present.
3. Confirm the title attribute on that pill matches the regex `/^↺S\d{2}: fix cycle \d+$/` (per `step_pipeline.html:37`).
4. Capture an evidence screenshot under `evidences/post/I-00075_v1_fix_cycle_amber_pill.png`.
5. Visit at least one **non-fixture** item (e.g. CR-00001 from the production pg_dump) to confirm no regression on items with zero fix cycles — those items must NOT render any `iw-pipeline-pill--fixcycle` element.

See `prompts/I-00075_S13_BrowserVerification_prompt.md` for the exact V1..V3 spec.

## Acceptance Criteria

### AC1: Bug is fixed

```
Given the per-worktree E2E compose stack is up for an I-00075 browser verification
And ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py is committed in the worktree
When the daemon runs _apply_per_item_fixtures("I-00075", …) and the qv-browser agent navigates to /project/iw-ai-core/work/I-99001
Then the step pipeline renders at least one element with class "iw-pipeline-pill--fixcycle" carrying a title attribute matching /^↺S\d{2}: fix cycle \d+$/
```

### AC2: Regression test exists

```
Given the fix is applied
When `make test-integration` runs
Then `tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_file_exists` passes
And `tests/integration/test_i00075_fix_cycle_fixture.py::test_i00075_fixture_seeds_at_least_one_fix_cycle` passes
And re-running the fixture twice in the same session does not raise IntegrityError (idempotency)
```

### AC3: No regression on items with zero fix cycles

```
Given an item without any FixCycle rows (e.g. CR-00001 from the production pg_dump)
When the qv-browser agent loads its detail page during V2 of S13
Then the step pipeline renders ZERO elements with class "iw-pipeline-pill--fixcycle"
And no new console errors appear in `.playwright-cli/console-*.log`
```

## Regression Prevention

- **Pattern documentation**: this incident's fixture file is the canonical, copy-pastable example for any future item whose qv-browser step needs to verify fix-cycle UI. Future CRs/Features touching `step_pipeline.html` lines 33–41 (or any element keyed off `WorkflowStep.fix_cycle_count`) should reference `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py` in their own design's `e2e_fixtures` section.
- **Integration test net**: `tests/integration/test_i00075_fix_cycle_fixture.py` is the regression net — if a future change to `scripts/e2e_seed.py:_run_fixture` or `scripts/e2e_apply_item_fixtures.py` breaks fixture loading semantics, this test will fail.
- **Out of scope (deferred to a separate CR)**: updating `templates/design/CR_Template.md` / `Feature_Design_Template.md` / `Issue_Design_Template.md` to add a "Browser-verification fixtures" subsection that references this pattern. That would systematically remind future authors to add a fixture when the verification needs historical data — but it is a template change that affects the design-time skills, not this incident's bug. File as a follow-up CR.

## Dependencies

- **Depends on**: None
- **Blocks**: None (CR-00039 has already merged; this is the post-mortem cleanup recommended by its self-assess)

## Impacted Paths

- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py`
- `tests/integration/test_i00075_fix_cycle_fixture.py`

## TDD Approach

- **Reproducing test**: `test_i00075_fixture_file_exists` — fails pre-fix because the fixture file does not exist; passes post-fix.
- **Unit tests**: none required — the fixture is integration-shaped (needs DB).
- **Integration tests**:
  - `test_i00075_fixture_file_exists` (file-presence guard)
  - `test_i00075_fixture_seeds_at_least_one_fix_cycle` (semantic assertion — verifies an actual `FixCycle` row is created and is reachable from `WorkflowStep.work_item_id == "I-99001"`)
  - `test_i00075_fixture_idempotent` (run the fixture twice, assert no IntegrityError and the same row count after the second run)

**CSS-class assertion note (per I-00067 lesson)**: the qv-browser V1 step asserts on the rendered HTML attribute `class="iw-pipeline-pill iw-pipeline-pill--fixcycle"`, not the bare substring `iw-pipeline-pill--fixcycle`. The bare substring would also match the `.iw-pipeline-pill--fixcycle { … }` rule inside `dashboard/static/styles.css` if the page ever inlined CSS — so anchor on the attribute form.

## Notes

- The synthetic item ID is `I-99001` to keep it well outside the live `iw next-id` allocation range and avoid any future collision.
- The fixture deliberately uses `iw-ai-core` as `project_id` because that's the project under which the per-worktree stack runs for iw-ai-core's own browser verification.
- The fixture authors a *minimal* topology: a single `Batch` (`BATCH-I00075DEMO`), one `BatchItem`, one `WorkItem`, three `WorkflowStep` rows (so the pipeline strip is meaningfully wide), and exactly **2** `FixCycle` rows on **1** of those steps (so the amber pill branch renders 2 connectors + 2 pills, exercising both the `loop.index` formatting and the "more than one fix cycle" multiplicity).
- The fixture is loaded by `scripts/e2e_apply_item_fixtures.py` inside the compose stack (NOT by `scripts/e2e_seed.py`); the integration test imports `_run_fixture` from `scripts/e2e_seed` because that is the shared fixture-runner helper.
