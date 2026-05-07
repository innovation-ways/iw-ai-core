### Item Analysis: F-00080

Bottom line: The item completed successfully but incurred 6 fix cycles (S06, S15, S16, S18×3) across 4 distinct steps — driven by template/macro integration gaps rather than agent reasoning failures. Adding a per-scope validation check before code-review steps and surfacing macro-signature constraints in the prompt template would eliminate most retry cycles at low effort.

Steps analyzed: 19   Steps with retries: 4   Total fix-cycles: 6   DB signal: yes

[1] Missing `slug` parameter in `empty_state` macro calls caused 3 successive S18 browser fix cycles
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/active/F-00080/fix-cycles/F-00080_S18_FIX_cycle1_prompt.md:46 — "tour.steps is empty ([]), causing Driver.js to show 'Tour unavailable'"
      - ai-dev/active/F-00080/fix-cycles/F-00080_S18_FIX_cycle2_prompt.md:76 — "The empty_state macro IS used in the template (batches) but called without the slug arg, so data-empty-state is absent"
      - ai-dev/active/F-00080/fix-cycles/F-00080_S18_FIX_cycle3_prompt.md:76 — same root cause repeated in cycle 3
    Recommendation: Add a macro-signature checklist to the S05 (Template) prompt and the S18 (BrowserVerification) prompt: every `empty_state(...)` call must pass `slug` as the first positional arg. Add a "macro call audit" step before browser verification so the agent can catch the missing arg before the slow E2E run.
    Target: prompts/F-00080_S05_template_prompt.md, prompts/F-00080_S18_BrowserVerification_prompt.md
    Pros: Fixes the most expensive failure mode (3 cycles × ~8 min each = ~24 min wasted); single audit step catches it early.
    Cons: Slightly longer prompt; added checklist friction.
    If we don't: Every future feature that uses `empty_state` macro risks the same 3-cycle browser-regression loop.
    Effort: S (~5 lines per prompt, 2 files)

[2] S05→S06 code review lacked integration-path validation, causing S06 to miss a broken tab nav in tests.html
    Severity: HIGH   Class: prompt   Frequency: one-off
    Evidence:
      - ai-dev/active/F-00080/fix-cycles/F-00080_S06_FIX_cycle1_prompt.md:16 — "tests.html had its tab navigation + tab content destroyed (replaced with a hard-coded div)"
    Recommendation: Add "verify tab navigation + macro call signatures" to the S05 template self-review checklist before declaring done. Alternatively, add a fast smoke test that renders all 22 wired pages and asserts the `empty_state` macro was called with the right signature.
    Target: prompts/F-00080_S05_template_prompt.md
    Pros: Catches structural template regressions before code review, which is faster and cheaper.
    Cons: One more checklist item; small time cost per step.
    If we don't: Future template-heavy features risk the same S05→S06 ping-pong.
    Effort: S (~3 lines)

[3] S15 (unit-tests) required a fix cycle despite passing on retry
    Severity: MED   Class: platform   Frequency: one-off
    Evidence:
      - ai-dev/active/F-00080/fix-cycles/F-00080_S15_FIX_cycle1_prompt.md:16 — "unit-tests failed: exit=2"
    Recommendation: Investigate whether the S15 exit=2 was a test infrastructure flakiness issue (timing, fixture ordering) or a genuine code defect. If infrastructure: add a retry-on-exit-2 rule to the QV gate executor. If code: the fix-cycle prompt was sufficient.
    Target: orch/test_runner.py or executor scripts
    Pros: If it is flakiness, this would prevent future spurious fix cycles on stable code.
    Cons: May not be reproducible; investigation cost.
    If we don't: Potentially flaky unit-test gates continue to generate unnecessary fix cycles.
    Effort: M (investigation + possible executor change)

[4] S16 (integration-tests) fix cycle revealed that E2E seed data was insufficient for empty-state pages
    Severity: MED   Class: environment   Frequency: one-off
    Evidence:
      - ai-dev/active/F-00080/fix-cycles/F-00080_S16_FIX_cycle1_prompt.md:44-49 — 6 integration tests failed: test_queue_empty_state, test_history_empty_state, test_history_empty_state_with_filter, test_all_active_empty_state, test_docs_library_empty_state, test_e2e_seed_runs_against_fresh_db
    Recommendation: Seed more rows into the E2E fixture so pages that render empty states (queue, history, batches, docs_library) are non-empty by default. Alternatively, if the empty-state pages need to be empty by design, ensure the integration test fixtures explicitly assert the empty-state markup rather than relying on populated DB state.
    Target: ai-dev/active/F-00080/e2e_fixtures/ or the integration test fixture setup
    Pros: Reduces test fixtures maintenance burden; integration tests become deterministic.
    Cons: More seed data = longer E2E setup time; not always controllable if feature requires truly empty state.
    If we don't: Future empty-state integration tests may be skipped or produce false failures.
    Effort: M (~10 rows of seed data, 1 file)

[5] S18 browser verification took 3 fix cycles, each rebuilding the full E2E stack (~8 min each)
    Severity: MED   Class: prompt   Frequency: recurring
    Evidence:
      - ai-dev/active/F-00080/fix-cycles/F-00080_S18_FIX_cycle1_prompt.md — V4 + V5 failed
      - ai-dev/active/F-00080/fix-cycles/F-00080_S18_FIX_cycle2_prompt.md — V6 partial failure (missing slug)
      - ai-dev/active/F-00080/fix-cycles/F-00080_S18_FIX_cycle3_prompt.md — same V6 persisted
    Recommendation: Add a "pre-flight check" before launching the browser: render the E2E pages with `data-empty-state` and `data-tour-seen` attributes visible in a static HTML snapshot and assert all expected slugs are present. This catches macro-signature and tour-definition gaps in seconds rather than minutes.
    Target: prompts/F-00080_S18_BrowserVerification_prompt.md
    Pros: 2 of 3 S18 fix cycles were preventable with a fast static check; cuts ~16 min from future browser verification rounds.
    Cons: Additional prompt complexity; small.
    If we don't: Every browser verification with a macro integration issue wastes a full E2E rebuild cycle.
    Effort: S (~6 lines)

[6] QV gates (S10–S17) all passed without fix cycles — no findings
    Severity: LOW   Class: n/a   Frequency: n/a
    Evidence: All QV gate reports (S10–S17) show exit code 0 and PASS result with no fix cycle prompts generated.
    Recommendation: No change needed.
    Target: n/a
    Pros: N/A
    Cons: N/A
    If we don't: N/A
    Effort: n/a

[7] Implementation steps (S01, S03, S05, S07) + code reviews (S02, S04, S06, S08, S09) all completed cleanly — no findings
    Severity: LOW   Class: n/a   Frequency: n/a
    Evidence: All step self-reports show completed status with no retries or fix cycles.
    Recommendation: No change needed.
    Target: n/a
    Pros: N/A
    Cons: N/A
    If we don't: N/A
    Effort: n/a