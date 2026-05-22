# I-00102 Self-Assessment Report

## Item Analysis: I-00102

**Title**: iw register silently ignores design-package drift; approve must auto-refresh workflow_steps

**Bottom Line**: The CRITICAL regression introduced by S02 (unconditional manifest-check in `approve`) was caught by the code-review layer, but the narrow test harness used in implementation steps allowed it to slip through, and the fix-cycle system then consumed ~7 cycles on S13 with pre-existing test noise that was not flagged as out-of-scope early enough.

**Steps analyzed**: 14 (S01–S14)
**Steps with retries**: 2 (S09, S13)
**Total fix-cycles**: 8 (1 for S09, 7 for S13)
**DB signal**: yes

---

## Findings

[1] **S02 regression caught only by code review — implementation steps should run the full relevant integration suite**

Severity: HIGH | Class: environment | Frequency: systemic

Evidence:
- `ai-dev/active/I-00102/reports/I-00102_S03_Tests_report.md:1` — "The S03 report noted the S02 phantom-gate regression in Observations"
- `ai-dev/active/I-00102/reports/I-00102_S04_CodeReview_report.md:1` — "CRITICAL: Phantom gate regression: `iw approve` requires manifest for all items"
- `ai-dev/active/I-00102/reports/I-00102_S05_CodeReviewFix_report.md:1` — "Fix: Restructured §2 and §3 of `approve` so that manifest_required = (old_digest is not None or design_doc_path is not None)"

Recommendation: When an implementation step changes a core CLI command (especially `approve`), the step should be required to run not just the new regression tests it creates, but also the existing test suite for that command (`tests/integration/test_phantom_gate_auto_skip.py`, `tests/integration/test_cli_core.py` for `approve`). A targeted smoke run of `pytest tests/integration/test_phantom_gate_auto_skip.py tests/integration/test_cli_core.py -k approve` costs ~30s and would have caught the CRITICAL regression before S03's self-report shipped it to the review layer.

Target: `ai-dev/templates/Implementation_Template.md` or `skills/iw-implementation/SKILL.md`

Pros: Catches CRITICAL regressions earlier; reduces the feedback loop from "end of review" to "end of implementation step."
Cons: Slightly longer implementation steps.
If we don't: CRITICAL regressions keep reaching the code-review layer, adding a full step's overhead to fix issues that could have been caught in the implementing step.
Effort: S (~5 lines added to step template)

---

[2] **Fix-cycle system wastes effort on pre-existing test flakiness — needs out-of-scope signal**

Severity: MED | Class: platform | Frequency: recurring

Evidence:
- `ai-dev/active/I-00102/fix-cycles/I-00102_S13_FIX_cycle1_prompt.md:1` — "FAILED tests/integration/test_cli_core.py::test_full_flow_next_id_register_approve"
- `ai-dev/active/I-00102/fix-cycles/I-00102_S13_FIX_cycle1_prompt.md:1` — "FAILED tests/integration/test_phantom_gate_auto_skip.py" (4 failures)
- `ai-dev/active/I-00102/fix-cycles/I-00102_S13_FIX_cycle2_prompt.md:1` — "FAILED tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_replays_buffered_events_via_last_event_id"
- `ai-dev/active/I-00102/fix-cycles/I-00102_S13_FIX_cycle2_prompt.md:1` — Allowed_paths expanded to include `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` — but `test_phase2_apply_no_self_deadlock.py` was a lint-only issue, not an integration test scope issue

Recommendation: The QV fix-cycle dispatcher should classify each failing test as:
- **in-scope** (introduced by this item, fixable within allowed_paths)
- **out-of-scope pre-existing** (existed before this item, no fix in scope)
- **flaky** (fails non-deterministically across runs)

When ≥50% of failures in a fix-cycle prompt are out-of-scope or flaky, the cycle should fail with a signal to skip the remaining out-of-scope tests and retry only the in-scope failures. The S13 cycle 1 dump showed 11 failures, but only 1 (`test_phantom_gate_auto_skip`) was directly related to I-00102's `approve` changes; the other 10 were either lint issues in a test file or pre-existing unrelated failures. The system made all 11 failures appear equally actionable.

Target: `orch/daemon/fix_cycle.py` or `orch/qv_gate_validator.py`

Pros: Fix cycles stop spending effort on noise; engineers get to the real failures faster.
Cons: Classification logic is imperfect; may mis-classify some genuine regressions as out-of-scope.
If we don't: Every QV fix cycle continues to surface pre-existing failures alongside genuine regressions, diluting the signal and wasting agent time.
Effort: M (~2 files, 50-100 lines)

---

[3] **Allowed-paths gap between lint gate (S09) and integration gate (S13)**

Severity: MED | Class: platform | Frequency: systemic

Evidence:
- `ai-dev/active/I-00102/fix-cycles/I-00102_S09_FIX_cycle1_prompt.md` — Scope: `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` not listed; lint E501 line-too-long in that file was out of scope
- `ai-dev/active/I-00102/fix-cycles/I-00102_S13_FIX_cycle1_prompt.md` — Scope now includes `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py`; lint passes

Recommendation: When a test file appears in a lint gate failure, the fix-cycle dispatcher should include it in allowed_paths automatically, since lint is a text-formatting constraint that can always be fixed in any file. The scope for lint gates should be the union of the item's explicit allowed_paths plus any file containing a lint error.

Target: `orch/daemon/fix_cycle.py`

Pros: Eliminates the round-trip of "add file to allowed_paths, then run fix cycle again."
Cons: Slightly broader scope on lint gates (but lint is safe — it only touches formatting).
If we don't: Items waste a fix cycle when lint catches an error in a file that was not pre-listed in allowed_paths.
Effort: S (~10 lines in fix-cycle dispatcher)

---

[4] **S05 investigation of the pre-existing `ensure_active_files_committed` regression wasted a cycle**

Severity: LOW | Class: platform | Frequency: systemic

Evidence:
- `ai-dev/active/I-00102/reports/I-00102_S05_CodeReviewFix_report.md:1` — "The C1 fix itself is verified by the fact that the error changed from 'Manifest file not found' (C1) to 'Active directory not found' (the separate pre-existing issue)"
- `ai-dev/active/I-00102/reports/I-00102_S06_CodeReviewFinal_report.md:1` — "M1 — ensure_active_files_committed is pre-existing, not I-00102 regression"
- `ai-dev/active/I-00102/reports/I-00102_S07_CodeReviewFixFinal_report.md:1` — "M1 deferred as MEDIUM_INFO: unrelated to I-00102, tracked separately under I-00083"

Recommendation: When a fix-cycle step's fix correctly changes the error from "manifest-missing" to a different error ("active-dir-missing"), and the new error is clearly in a different code path (`ensure_active_files_committed` vs. `approve`'s manifest check), the dispatcher should flag this as "error improved but root-cause is pre-existing" rather than "fix inconclusive." The fix was correct; the remaining error is for a different work item.

Target: `orch/daemon/fix_cycle.py` or `skills/iw-qv-gate/SKILL.md`

Pros: Prevents wasted investigation time on pre-existing regressions that happen to appear after an in-scope fix.
Cons: Requires classification logic; imperfect classification may mask genuine incomplete fixes.
If we don't: Fix-cycle agents investigate pre-existing regressions and waste cycles trying to fix out-of-scope errors.
Effort: M (~20 lines in fix-cycle dispatcher)

---

## Coverage Notes

No raw run logs available (worktree `.worktrees/I-00102/ai-dev/logs/` does not exist — the worktree was reaped before this analysis step). All evidence is drawn from:
- Agent self-reports (`ai-dev/active/I-00102/reports/*.md`) — treated as secondary evidence
- Fix-cycle prompts (`ai-dev/active/I-00102/fix-cycles/`) — primary source for fix-cycle signal
- Step manifests (`uv run iw item-status I-00102 --json`) — step list and durations
- DB telemetry (`uv run iw db-identity check` → UP) — confirmed DB available but raw execution telemetry (run durations, retry counts) not queried directly since no raw logs existed

DB telemetry: partial — step list from `item-status` confirms fix-cycle counts (S09: 1 cycle, S13: 7 cycles visible in fix-cycle prompts).
