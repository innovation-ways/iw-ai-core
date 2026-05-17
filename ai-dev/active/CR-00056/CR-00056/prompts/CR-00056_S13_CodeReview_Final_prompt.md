# CR-00056_S13_CodeReview_Final_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Review Step**: S13 (Final Review — implementation + tests)
**Implementation Steps Reviewed**: S01..S12

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — full document
- ALL implementation reports S01..S11
- ALL per-agent review reports S02, S05, S07, S09, S10, S12
- All files in all `files_changed` arrays
- Pre-state screenshot: `ai-dev/active/CR-00056/evidences/pre/CR-00056_before_no_prompt_column.png`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S13_CodeReview_Final_report.md`

## Context

This is the **final cross-agent review including tests** for CR-00056. The S10 review covered implementation cross-cut before tests existed; you re-review the whole picture now that tests are in place.

Production-readiness focus: this CR touches the **daemon hot path** (every step launch). A regression here would silently corrupt prompts for every future item.

## Read the Design Document FIRST

- Walk every AC1..AC9.
- Confirm every test file the design names exists.
- Re-check the `Rollback Plan` — would `alembic downgrade -1` + revert commit actually work cleanly?

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

### 1. AC × test matrix (final)

Confirm every AC has at least one passing test (or a documented hand-off to qv-browser for AC6 / AC8). Reference the matrix in `S12`'s prompt.

### 2. Hot-path safety

- **Step launch must NEVER fail because of prompt-snapshot logic.** Open `orch/daemon/batch_manager.py` and `orch/daemon/fix_cycle.py`. Confirm the snapshot read is wrapped in try/except for `OSError`, `UnicodeDecodeError` (or a similarly narrow set). If a bare `try/except Exception` was used, that's a HIGH finding (too broad — masks real bugs).
- The snapshot write happens in the SAME transaction as the StepRun INSERT. Either both land or neither — no half-states.

### 3. Test execution

Do NOT re-run `make test-unit` / `make test-integration` from this step —
duplicating the QV gate work caused the I-00073 timeout and is forbidden for
any `*-impl` step. The S18 (unit-tests) and S19 (integration-tests) QV gates
own full-suite execution.

What to verify instead:

- Read the report at `ai-dev/work/CR-00056/reports/CR-00056_S18_*.md` and
  confirm `tests_passed: true`. Missing or failing → CRITICAL.
- Read the report at `ai-dev/work/CR-00056/reports/CR-00056_S19_*.md` and
  confirm `tests_passed: true`. Missing or failing → CRITICAL.
- Confirm S11's report lists all four test files from the design's `TDD
  Approach` section and each has a green per-file run.

If you need an extra smoke run on the changed-test files only:

```bash
uv run pytest tests/unit/test_step_run_prompt_columns.py tests/integration/test_daemon_prompt_snapshot.py tests/dashboard/test_prompt_modal_route.py tests/dashboard/test_item_steps_table_render.py -v
```

### 4. Cross-agent consistency (re-check)

- Route URL string identical across S06 (definition) and S08 (template `hx-get`).
- Dataclass field name `has_prompt` identical across S06 (`StepDetail`) and S08 (template `{% if step.has_prompt %}`).
- CSS class names match between template and stylesheet.
- Section `label` and `text` keys match between S06 (route builds dict) and S08 (template iterates).

### 5. Integration: end-to-end smoke (mental walkthrough)

Trace one full user journey:
1. Operator approves a new item → daemon launches step → S04's snapshot logic populates `prompt_text`.
2. After merge, worktree is reaped (the file at `WorkflowStep.prompt_file` is gone).
3. Operator opens the item-detail page → S08's template renders the Prompt column with View button (because `has_prompt=True`).
4. Operator clicks View → htmx GET hits S06's route → S06 reads `step_runs.prompt_text` from DB (worktree gone but data is durable) → returns modal fragment.
5. Modal opens, prompt is visible, Escape dismisses.

Any step in this journey that the implementation does not actually support → CRITICAL.

### 6. Rollback plan validation

- The migration's `downgrade()` actually drops both columns? (Re-read the migration file.)
- If `alembic downgrade -1` runs against live DB *after* daemon has written rows with non-NULL values, the DROP COLUMN destroys data — acceptable per design (observability, not load-bearing), but reviewer should confirm the team is fine with this.

### 7. Cross-cutting CLAUDE.md sweep

Run the same greps as S10's checklist 8.

### 8. Browser verification readiness

- The qv-browser prompt (S22) exists and contains concrete V steps.
- It references `$IW_BROWSER_BASE_URL`, not hardcoded ports.
- It uses `playwright-cli`, not `agent-browser`.

## Test Verification (NON-NEGOTIABLE)

Verification is by reading the QV gate reports (S18/S19) — see checklist
section 3 above. Do NOT re-run `make test-unit` or `make test-integration`
from this step (project-wide rule for `*-impl` prompts; I-00073).

## Review Result Contract

```json
{
  "step": "S13",
  "agent": "CodeReview_Final",
  "work_item": "CR-00056",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed",
  "missing_requirements": [],
  "notes": ""
}
```
