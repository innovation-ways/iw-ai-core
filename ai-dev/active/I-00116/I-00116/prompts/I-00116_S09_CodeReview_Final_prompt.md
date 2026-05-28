# I-00116_S09_CodeReview_Final_prompt

**Work Item**: I-00116
**Step**: S09
**Agent**: CodeReview_Final (cross-layer global review)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration in this item; verify none exists.

## Scope of review

ALL files modified across S01/S03/S05/S07. Verify scope adherence to the manifest's `scope.allowed_paths`:

```
orch/daemon/step_monitor.py
orch/daemon/fix_cycle.py
orch/daemon/batch_manager.py
agents/code-review-impl.md
commands/code-review-impl.md
skills/iw-workflow/SKILL.md
tests/unit/daemon/test_step_monitor_i00116_review_recovery.py
tests/integration/test_fix_cycle_review_relaunch_cap.py
tests/unit/test_review_prompt_scope.py
```

Any file outside this list is a CRITICAL scope violation.

## Input Files

- **Runtime state**: `uv run iw item-status I-00116 --json`
- **Design**: `ai-dev/active/I-00116/I-00116_Issue_Design.md` (especially Acceptance Criteria AC1..AC5)
- **Functional**: `ai-dev/active/I-00116/I-00116_Functional.md`
- **All per-agent review reports**: `ai-dev/active/I-00116/reports/I-00116_S02_*.md`, `S04_*.md`, `S06_*.md`, `S08_*.md`
- **All implementation reports**: S01/S03/S05/S07 reports

## Output Files

- Global review report: `ai-dev/active/I-00116/reports/I-00116_S09_CodeReviewFinal_report.md`

## AC Verification (MANDATORY — each AC must be linked to evidence)

| AC | What to verify | Evidence to cite |
|----|----------------|------------------|
| AC1 | Review steps with on-disk reports are recovered | `_try_recover_completed_review_step` in `step_monitor.py` + `test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed` passing |
| AC2 | Review steps without reports still detect real crashes | `test_i00116_review_step_without_report_still_marked_crashed` passing + `_handle_crashed` unchanged for non-review step types |
| AC3 | Cumulative review-relaunch cap breaks loops | `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` in `fix_cycle.py`/`batch_manager.py` + `test_i00116_at_cap_review_relaunch_transitions_item_failed_and_emits_event` passing |
| AC4 | Review-prompt diff scope is anchored to allowed_paths | Both `agents/code-review-impl.md` AND `commands/code-review-impl.md` reference `allowed_paths`; `tests/unit/test_review_prompt_scope.py` passing |
| AC5 | All three test files exist and pass | Targeted pytest output |

## Cross-layer Checks

| # | Check |
|---|-------|
| 1 | `step_monitor.py` recovery helper and `fix_cycle.py` cap do NOT have conflicting state assumptions (e.g. both trying to transition the item simultaneously) |
| 2 | DaemonEvent payload uses `event_metadata` (Python attribute name) — never `metadata` — in both `step_monitor.py` and `fix_cycle.py` (CLAUDE.md critical rule) |
| 3 | Both new DaemonEvent types (`step_run_recovered_from_report`, `review_relaunch_cap_exceeded`) are documented somewhere (CLAUDE.md, daemon design doc, or model docstring). If not, flag a HIGH finding asking S0X to add a one-line entry to `docs/IW_AI_Core_Daemon_Design.md`. |
| 4 | The new env var `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` is documented in `CLAUDE.md`'s "Configuration" section. If not, flag a MEDIUM finding. |
| 5 | The prompt-scope change in `commands/code-review-impl.md` matches the one in `agents/code-review-impl.md` (the sync source-of-truth pair) |
| 6 | Functional doc accurately predicts user-observable changes (no implementation jargon — read the file) |
| 7 | Scope adherence: every changed file is in the manifest's `scope.allowed_paths` |
| 8 | No test mocks past the bug-class boundary (mocking `_try_recover_completed_review_step` itself would defeat the test purpose — verify S07's tests mock at the OS/DB boundary) |
| 9 | All agent reports include the `iw step-done` confirmation in their notes (the whole point of this item is to make step-done failures visible — verify the impl agents themselves did not skip the call) |

## Required Pre-flight Gates

```bash
make lint
make format-check
make test-unit
make migration-check
```

`make migration-check` should pass because no migration was added; if it surfaces a drift, that's a CRITICAL finding (someone touched the schema and shouldn't have).

## Verdict Contract (REQUIRED)

Your report MUST end with:

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "I-00116",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass" | "fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: ... | make lint: ... | make format-check: ...",
  "missing_requirements": [],
  "ac_evidence": {
    "AC1": "...", "AC2": "...", "AC3": "...", "AC4": "...", "AC5": "..."
  },
  "notes": "..."
}
```

## Step Done Contract

Call `iw step-done S09 --report ai-dev/active/I-00116/reports/I-00116_S09_CodeReviewFinal_report.md` before exit. Never exit without calling `iw step-done` or `iw step-fail`.
