# I-00101_S07_CodeReview_Final_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Input Files

- `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document
- `ai-dev/active/I-00101/I-00101_Functional.md` — functional doc
- `ai-dev/active/I-00101/workflow-manifest.json` — manifest
- All implementation step reports (`I-00101_S01_*` through `I-00101_S05_*`)
- All per-agent code review reports (`I-00101_S02_*`, `I-00101_S04_*`, `I-00101_S06_*`)
- All files listed in any implementation step's `files_changed`

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S07_CodeReview_Final_report.md` — Global review report

## Context

You are running the global cross-agent review for I-00101. Per-agent reviews caught local issues; your job is to catch cross-agent drift, AC satisfaction, and integration correctness.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
make typecheck
```

NEW violations against `main` → CRITICAL.

## Review Procedure

### 1. Independent test run

Run all four new test files end-to-end:

```bash
uv run pytest \
  tests/unit/daemon/test_fix_cycle_budget_exemption.py \
  tests/unit/daemon/test_scope_amendment.py \
  tests/dashboard/test_scope_blocked_badge.py \
  tests/integration/test_scope_amend_endpoints.py \
  -v --no-cov
```

Confirm all pass independently. Any failure is **HIGH** (the per-agent reviews should have caught it).

### 2. Broader suite regression check

```bash
uv run pytest tests/unit/daemon/ tests/dashboard/ -v --no-cov
```

Confirm the existing daemon-unit and dashboard suites still pass — the new badge variant must not break existing `status_badge` rendering for other StepStatus values; the new fix_cycle predicate must not change the count for non-scope-escalated rows; the items.py change must not regress the existing item-detail render path.

### 3. AC traceability

Walk the design's AC1..AC5 and confirm each is satisfied by concrete code AND a concrete test:

| AC | Code site | Test |
|----|-----------|------|
| AC1 (badge surfaces) | `status_badge.html` variant + `item_steps_table.html` branch + `items.py` data wiring + `running.py` global table | `test_scope_blocked_badge.py::test_i00101_scope_blocked_badge_renders_for_escalated_cycle_with_violations` |
| AC2 (amend end-to-end) | `actions.py::scope_amend_and_restart` + `scope_amendment.py::amend_allowed_paths` | `test_scope_amend_endpoints.py::test_i00101_amend_writes_both_manifests_and_emits_event_and_restarts_step` |
| AC3 (revert end-to-end) | `actions.py::scope_revert_and_restart` + `scope_amendment.py::revert_paths_in_worktree` | `test_scope_amend_endpoints.py::test_i00101_revert_runs_git_checkout_and_emits_event_and_restarts` |
| AC4 (budget exemption) | `fix_cycle.py` predicate filter on both `.count()` queries | `test_fix_cycle_budget_exemption.py::test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget` (and the aggregate / non-scope / failed variants) |
| AC5 (regression tests exist) | All four test files | The presence of all four files is the satisfaction |

Any AC without a clear code site OR test is **HIGH**.

### 4. Cross-doc-square drift check

The same vocabulary must appear consistently across the four documentation artifacts. Verify each of the following names matches byte-identically in design doc, functional doc, manifest, and the relevant prompt(s):

- Event names: `scope_amended_by_operator`, `scope_reverted_by_operator`, `scope_violation_escalation` (preexisting)
- Endpoint URL paths: `/scope/amend-modal/`, `/scope/amend-and-restart/`, `/scope/revert-and-restart/`
- Badge label: `Scope blocked`
- Helper module name: `orch/daemon/scope_amendment.py`
- Helper function names: `amend_allowed_paths`, `revert_paths_in_worktree`, `latest_scope_violation`
- Template names: `scope_amend_modal.html`

Drift in any of the above is **HIGH**.

### 5. Endpoint URL conventions

The three new URL paths follow the existing `actions.py` pattern (`/project/{project_id}/actions/item/{item_id}/...`). They are NOT batch endpoints. **HIGH** if the URL shape diverges (would break dashboard nav and the modal `hx-get` URL in the template).

### 6. Modal fragment correctness

`scope_amend_modal.html` does NOT contain `{% extends "base.html" %}` — fragment templates must not extend base (per `dashboard/CLAUDE.md`). **CRITICAL** if it does.

### 7. Helper purity

`orch/daemon/scope_amendment.py` has zero DB writes. The dashboard endpoint composes the helper output with the DB mutations. If the helper module imports `Session.commit` or otherwise touches DB state beyond the read-only `latest_scope_violation`, that is **CRITICAL** (breaks the transaction boundary contract).

### 8. Restart-mutation parity

Both new POST endpoints (`scope_amend_and_restart`, `scope_revert_and_restart`) perform the same DB mutations as the existing `restart_step` at `dashboard/routers/actions.py:323`: new `StepRun` with incremented `run_number`, step.status → pending, started_at/completed_at cleared, item.status → in_progress if it was failed, single `db.commit()`. Drift from `restart_step`'s mutation set is **HIGH** (would leave items in inconsistent state).

### 9. Browser verification prerequisites

S15 (qv-browser) needs an e2e fixture that creates the escalated-FixCycle scenario. Verify the file `ai-dev/active/I-00101/e2e_fixtures/001_*.py` is present and exports `def seed(db: Session) -> None`. **HIGH** if absent — S15 will fail with ENV_DATA_MISSING.

Actually wait — this fixture is S15's responsibility, not the implementation steps. Note in your report whether the fixture is present; if absent, flag as a **MEDIUM_FIXABLE** instruction for the operator to seed during S15 rather than a blocker on S07.

### 10. Manifest scope discipline

Cross-reference every file actually touched (in all reports' `files_changed` aggregated) against `workflow-manifest.json:scope.allowed_paths`. Any touched file outside the manifest's allowed list is **CRITICAL** (would block the merge gate).

## Severity Levels

Standard mapping. `verdict: pass` requires zero CRITICAL / HIGH / MEDIUM_FIXABLE.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00101",
  "step_reviewed": "S01..S06",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (across new test files + regression sweep of unit/daemon and dashboard suites)",
  "notes": ""
}
```
