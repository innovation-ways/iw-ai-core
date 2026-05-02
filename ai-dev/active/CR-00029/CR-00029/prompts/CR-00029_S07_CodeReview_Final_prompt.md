# CR-00029_S07_CodeReview_Final_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Review Step**: S07 (Final Cross-Agent Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md` — AC1–AC7
- All step reports: S01..S06
- All files in any implementation step's `files_changed`

## Output Files

- `ai-dev/active/CR-00029/reports/CR-00029_S07_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** for CR-00029. The change touches the dashboard backend (StepDetail + endpoint + helper extraction), the dashboard templates (macro + conditional branch), and the test suite.

Per-agent reviews caught local issues; your job is to catch cross-cutting issues:

1. **End-to-end chain**: `_synthetic_setup_step` computes restartable → template renders button when restartable=True → button hx-get hits confirm endpoint → confirm dialog POSTs to action endpoint → action endpoint validates precondition + delegates to `_reset_item_to_approved` → emits `setup_restarted` event.
2. **`full_restart_item` regression safety**: the helper extraction must not have changed `full_restart_item`'s observable behavior. Verify by reading both endpoint bodies side-by-side and confirming the only difference is the parametrized event_type/event_message.
3. **No orphan code paths**: any other places in the dashboard that render synthetic S00 rows? (e.g., a different fragment for embedding the step list elsewhere.) If so, they should also see the new button OR explicitly opt out.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in any changed file = CRITICAL.

## Review Checklist

### 1. Completeness vs Design Document

- Walk every section of `CR-00029_CR_Design.md` and confirm the implementation matches.
- Acceptance criteria AC1–AC7 each have a test (S05) or are documented as deferred to S13 (AC7 only).

### 2. Chain Integrity

Trace one full scenario by reading code:

1. Item CR29-A has BatchItem in `setup_failed`, all steps pending
2. `_synthetic_setup_step(bi, steps)` returns StepDetail(`is_synthetic=True, step_id="S00", restartable=True`)
3. `item_overview.html` matches the new branch and renders `restart_setup_button`
4. User clicks → `hx-get /project/<proj>/api/confirm-item/restart-setup/<item_id>` → confirm dialog appears
5. User confirms → htmx POST `/project/<proj>/api/item/<item_id>/restart-setup`
6. Endpoint precondition passes → `_reset_item_to_approved(..., event_type="setup_restarted", ...)`
7. Helper deletes worktree, resets steps, sets item→approved, re-opens batch, emits event, commits
8. Response triggers item-overview reload — synthetic S00 row now has restartable=False (item is approved, not failed) → button gone

Any break in this chain = CRITICAL finding.

### 3. `full_restart_item` Behavior Preservation

Read both functions carefully:

- BEFORE refactor: full_restart_item body included worktree path discovery, log unlink, StepRun delete, WorkflowStep reset, WorkItem→approved, BatchItem reset, batch re-open, daemon_event emit, commit, worktree filesystem delete.
- AFTER refactor: full_restart_item should call `_reset_item_to_approved(..., event_type="item_full_restarted", event_message="Item ... fully restarted by user (worktree deleted, logs cleared)")`.

Confirm:
- Order of operations is preserved (especially: filesystem delete AFTER db.commit)
- All data values match (notes, started_at, etc.)
- `_FULL_RESTART_ALLOWED` precondition is still in `full_restart_item` (NOT in the helper)
- Return value / response shape unchanged

The `test_restart_setup_does_not_alter_full_restart_behavior` test (S05) should give us confidence here — verify it actually exercises both endpoints with parallel state.

### 4. Cross-Agent Consistency

- Daemon event type `setup_restarted` is consistent across emit-site and any sse-registry. Search `dashboard/routers/sse.py` for an event-type allow-list.
- Macro URL prefix matches the route registration (S01 vs S03 — `dashboard/routers/actions.py` prefix vs the macro's `hx-get` URL).
- Naming: "Restart Setup" (button label, dialog title), `restart-setup` (URL path), `setup_restarted` (event type) — consistent capitalization.

### 5. Architecture Compliance

- Dashboard router stays sync
- htmx fragments returned via `templates.TemplateResponse`
- No JS hand-written

### 6. Security & Robustness

- Endpoint returns 422 (not 500) on precondition failures
- `_delete_worktree` is best-effort (suppresses filesystem errors) — preserves the "no data loss on filesystem hiccup" property of the existing code

### 7. Tests Holistic

- `make test-unit` passes
- `make test-integration` passes
- Test count increased by ≥ the number of new test files (no test was accidentally moved)

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass with zero failures. Integration failure = CRITICAL.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "CR-00029",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": "AC chain trace summary; full_restart_item behavior preservation verified"
}
```
