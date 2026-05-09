### Item Analysis: F-00081

Bottom line: Most QV gates required no or only one fix cycle, but S08 (lint), S14 (frontend-tests), S15 (integration-tests), and S16 (browser) needed multiple fix cycles — suggesting the design doc was unclear or underspecified on edge cases that agents discovered only when gates ran.

Steps analyzed: 17   Steps with retries: 4   Total fix-cycles: 21   DB signal: yes

[1] QV gates S08 / S14 / S15 each required multiple fix cycles to pass
    Severity: MED   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/active/F-00081/fix-cycles/F-00081_S08_FIX_cycle3_prompt.md:1 — "S08 QV Fix Cycle 3/3" (3 cycles)
      - ai-dev/active/F-00081/fix-cycles/F-00081_S14_FIX_cycle5_prompt.md:1 — "S14 QV Fix Cycle 5/5" (5 cycles)
      - ai-dev/active/F-00081/fix-cycles/F-00081_S15_FIX_cycle1_prompt.md:16 — "integration-tests failed: exit=2" (1 initial, 4 more cycles = 5 total)
      - ai-dev/active/F-00081/fix-cycles/F-00081_S08_FIX_cycle1_prompt.md:16 — "lint failed: exit=2" (S08 took 3 cycles)
    Recommendation: Design doc should include a "QV gate failure map" — explicit predictions of which steps will likely need multiple fix cycles and why. Add a section listing known fragile areas (e.g., integration tests with complex fixture state, frontend tests with htmx timing sensitivity) so agents budget more fix cycles upfront.
    Target: templates/design/Feature_Design_Template.md (or ai-dev/templates/Feature_Design_Template.md)
    Pros: Agents arrive at fix cycles with more preparation; less thrashing on first failure.
    Cons: Requires upfront design effort to predict fragility.
    If we don't: Agents under-budget fix cycles on hard QV gates; S14 and S15 both reached final-cycle escalation on this item.
    Effort: S (~5 lines in template)

[2] S15 integration tests required 4 fix cycles — pre-existing test suite fragility
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/active/F-00081/fix-cycles/F-00081_S15_FIX_cycle1_prompt.md:42 — "37 failed, 2054 passed, 32 skipped" (S15 first attempt)
      - ai-dev/active/F-00081/reports/F-00081_S15_QvGate_report.md:215 — "2131 passed" after fixes
    Recommendation: Investigate whether `test_batch_manager_self_assess.py`, `test_browser_verification_flow.py`, and `test_f_00076_*` tests have unstable fixture setup or ordering dependencies. The 37 failures on first S15 run vs. 0 after fixes suggests race conditions in testcontainer lifecycle or session cleanup.
    Target: tests/integration/conftest.py, orch/test_runner.py
    Pros: Reduces spurious fix cycles on integration gates.
    Cons: May require nontrivial test refactoring.
    If we don't: Future S15-like integration gates will continue to need multiple fix cycles for reasons unrelated to the new code being tested.
    Effort: M (~3 files, moderate investigation needed)

[3] S16 browser verification reported duplicate CLI options in dropdown
    Severity: LOW   Class: design   Frequency: one-off
    Evidence:
      - ai-dev/active/F-00081/fix-cycles/F-00081_S16_FIX_cycle2_prompt.md:71 — "Each CLI option appears twice in the dropdown (e.g., 'OpenCode', 'OpenCode', 'OpenCode'...)"
    Recommendation: Clarify in the design doc whether the CLI dropdown should deduplicate by `cli_label` or show all catalogue rows. The S16 agent called this a cosmetic issue but the spec should make the intended behavior explicit.
    Target: ai-dev/active/F-00081/F-00081_Feature_Design.md (or the template that generates it)
    Pros: Eliminates ambiguity in a customer-facing UI element.
    Cons: May require a follow-up fix cycle on F-00081 or a follow-up item.
    If we don't: UI will continue to show duplicate CLI options; may be flagged in future browser verifications.
    Effort: S (~2 lines in design doc)

[4] S04 API report noted design-doc/schema mismatch on step editability
    Severity: MED   Class: design   Frequency: recurring
    Evidence:
      - ai-dev/active/F-00081/reports/F-00081_S04_API_report.md:25 — "StepStatus.paused does not exist — paused is a WorkItemStatus, not a StepStatus"
      - ai-dev/active/F-00081/reports/F-00081_S05_Frontend_report.md:117 — "design doc says pending | failed | paused are editable. paused is a WorkItemStatus, not a StepStatus"
    Recommendation: Add a "Schema vs. Design Doc Discrepancy Protocol" section to CLAUDE.md: when an agent finds the design doc specifies behavior that the actual schema doesn't support, it should (a) note the discrepancy in its step report and (b) proceed with the schema-correct implementation rather than trying to match the design doc verbatim.
    Target: CLAUDE.md (Critical Rules or a new "Implementation Conventions" section)
    Pros: Prevents agents from building against a spec that can't be fulfilled; reduces wasted fix cycles.
    Cons: Slightly more judgment required from agents, but the rule is clear.
    If we don't: Agents follow a design doc that references non-existent enum values; S04 and S05 both discovered this independently.
    Effort: S (~8 lines in CLAUDE.md)

[5] S08 lint gate took 3 cycles — minimal detail in initial error output
    Severity: LOW   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/active/F-00081/fix-cycles/F-00081_S08_FIX_cycle1_prompt.md:18 — "lint failed: exit=2" with no parseable output
      - ai-dev/active/F-00081/fix-cycles/F-00081_S08_FIX_cycle3_prompt.md:1 — FINAL cycle for a single lint error
    Recommendation: Enhance the QV fix-cycle prompt generator to surface more diagnostic context from failed lint runs (e.g., which files, which rule, how many violations). The "Unparseable output" note in the fix prompt template suggests this is a known gap.
    Target: orch/daemon/qv_gate_validator.py or the fix cycle generation logic
    Pros: Agents spend less time on trial-and-error in fix cycles.
    Cons: Requires careful formatting to avoid blowing up the prompt file size.
    If we don't: Lint fix cycles remain opaque; agents may take multiple cycles on fixable errors.
    Effort: M (~1 file, moderate)

[6] Worktree log directory not accessible from self-assess context
    Severity: MED   Class: platform   Frequency: one-off
    Evidence:
      - bash output: "no .worktrees dir" when running in the F-00081 worktree context
    Recommendation: Ensure `.worktrees/<ID>/ai-dev/logs/` is present and populated for active items. The self-assessment skill relies on raw run logs as primary evidence; when logs are missing the analysis falls back to secondary evidence (step reports) which are less reliable.
    Target: orch/daemon/worktree_compose.py or the step-launch executor script
    Pros: Full fidelity analysis with raw log evidence.
    Cons: Storage overhead for logs in worktrees.
    If we don't: Future self-assessments on active items may have degraded signal quality.
    Effort: M (~1 file)

[7] Pre-existing test failures in unrelated suites reported as F-00081 context
    Severity: LOW   Class: environment   Frequency: recurring
    Evidence:
      - ai-dev/active/F-00081/reports/F-00081_S07_CodeReviewFinal_report.md:169 — "120 failures in test_step_monitor, test_merge_queue"
    Recommendation: Configure the QV gate aggregator to suppress pre-existing failures when computing whether an item's gates passed. The current behavior tags pre-existing failures as "not caused by F-00081" in the report but still counts them in gate exit codes.
    Target: orch/qv_gate_validator.py, orch/test_runner.py
    Pros: Clean signal on whether the item's code caused gate failures.
    Cons: Requires stable definition of "pre-existing" per-test or per-file.
    If we don't: Gate reports conflate pre-existing failures with new regressions; harder to tell at a glance whether an item is clean.
    Effort: M (~2 files)