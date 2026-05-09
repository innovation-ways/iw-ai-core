### Item Analysis: CR-00039

**Bottom line**: Code review steps (S02, S08) needed fix cycles because the reviewer knew to look for design-doc alignment and found gaps in test coverage and environment data — both correctable without code changes.

**Steps analyzed**: 8 (S01–S08)   **Steps with retries**: 2 (S02, S08)   **Total fix-cycles**: 3 (S02×2, S08×1)   **DB signal**: yes

---

[1] **S02 fix cycles: design-doc not consulted before first code-review run**
Severity: MED   Class: prompt   Frequency: systemic
Evidence:
  - `ai-dev/active/CR-00039/fix-cycles/CR-00039_S02_FIX_cycle1_prompt.md:10` — "prior fix cycles on this codebase have failed because the agent trusted the failure-report's root-cause hypothesis and drifted away from the design doc's explicit fix spec"
  - `ai-dev/active/CR-00039/fix-cycles/CR-00039_S02_FIX_cycle1_prompt.md:16` — test file still asserted old CSS class names (`iw-step-strip/iw-step-seg`) per the design doc's TDD section — first review missed this
Recommendation: Add an explicit "Read design doc BEFORE reviewing code" instruction to the CodeReview prompt template (or an in-prompt reminder that the design doc TDD section mandates test updates alongside code changes). The fix-cycle prompt for S02 correctly surfaced this rule; the first-run prompt should have surfaced it proactively.
Target: `templates/design/CR_Template.md` (or the code-review prompt generator)
Pros: Eliminates a round-trip on every CR that changes CSS class names.
Cons: None identified.
If we don't: Every CR that renames CSS classes will fail code review once, then correct on the fix cycle — wasting ~5–10 min per occurrence.
Effort: S (~5 lines in the prompt template)

---

[2] **S08 fix cycle: browser verification cannot test fix-cycle amber pills in E2E — seed has no `fix_cycle_count > 0` items**
Severity: MED   Class: environment   Frequency: one-off
Evidence:
  - `ai-dev/active/CR-00039/reports/CR-00039_S08_QvBrowser_report.md:13` — "The production pg_dump seed contains zero items with `fix_cycle_count > 0`. All 4 completed items show Fix Cycles = 0."
  - `ai-dev/active/CR-00039/reports/CR-00039_S08_BrowserVerification_Report.md:43` — "The feature cannot be visually verified without an item that has `fix_cycle_count > 0` in the database."
Recommendation: Add an E2E seed fixture that creates an item (or modifies an existing one) with `fix_cycle_count >= 1` so browser verification can exercise the `↺SXX` amber pill branch in `step_pipeline.html`. Alternatively, add a note to the BrowserVerification prompt instructing the agent to skip V3 (fix-cycle pills) when no `fix_cycle_count > 0` items exist, rather than running and returning n/a.
Target: `skills/iw-execute/SKILL.md` or `templates/design/Feature_Design_Template.md`
Pros: Future browser verifications for fix-cycle features can fully verify the feature end-to-end.
Cons: Adds complexity to the seed fixture; one more thing to maintain.
If we don't: Browser verification for fix-cycle features will always return n/a for V3, degrading signal quality.
Effort: M (~10 lines in seed fixture or ~3 lines in prompt)

---

[3] **S02 second fix cycle: design doc TDD section explicitly required test update but tests were not updated in S01**
Severity: MED   Class: design   Frequency: one-off
Evidence:
  - `ai-dev/active/CR-00039/fix-cycles/CR-00039_S02_FIX_cycle1_prompt.md:16` — "Test at tests/dashboard/test_runtime_override_templates.py:278-284 asserts old CSS class names — must be updated to iw-pipeline-strip/iw-pipeline-pill per CR-00039_CR_Design.md TDD section"
Recommendation: Add a checklist item to the Frontend implementation prompt: "Confirm that any test file asserting old CSS class names has been updated to reflect the new class names from the design doc TDD section." This prevents the implementation from being correct but the tests from being stale.
Target: `templates/design/CR_Template.md` or `templates/design/Feature_Design_Template.md` (the implementation step prompt generator)
Pros: Closes the gap between implementation correctness and test coverage.
Cons: Slight prompt verbosity increase.
If we don't: Implementation steps may produce correct code while leaving stale test references, causing code-review fix cycles.
Effort: S (~5 lines in implementation step prompt)

---

[4] **No Docker, no migrations, no convention violations detected**
Severity: LOW   Class: convention   Frequency: recurring
Evidence:
  - All 8 step reports show zero Docker commands attempted, zero migrations executed, zero prohibited commands (`docker compose`, `agent-browser`, `playwright install`).
Recommendation: Current CLAUDE.md docker prohibition is sufficiently surfaced. No change needed.
Target: CLAUDE.md (already correct — just confirming signal)
Effort: N/A (informational only)

---

*3 lower-priority findings omitted; ask to see them.*