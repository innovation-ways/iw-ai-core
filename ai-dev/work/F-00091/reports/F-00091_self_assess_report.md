### Item Analysis: F-00091

Bottom line: tighten implementation-step prompts/template to require updating adjacent contract tests in the same step whenever payload/UI contracts change, to avoid downstream QV thrash.

Steps analyzed: 20   Steps with retries: 9   Total fix-cycles: 11   DB signal: yes

[1] Cross-step contract drift leaked into downstream gates
    Severity: HIGH   Class: prompt   Frequency: recurring
    Evidence:
      - ai-dev/logs/F-00091_S17_run1.log:1797 — "FAILED tests/dashboard/test_chat_context_pct_template.py::TestComposerDom::test_context_pct_element_exists"
      - ai-dev/logs/F-00091_S18_run1.log:7270 — "FAILED tests/integration/test_chat_tabs_api.py::test_get_tab_omits_context_pct_when_no_token_data"
      - ai-dev/logs/F-00091_S17_run1.log:1802 — "Failed F-00091 step S17: frontend-tests failed: exit=2"
    Recommendation: Add an explicit prompt-template checklist item for behavior steps that alter payload/DOM contracts: update or intentionally retire all affected legacy tests in-step, not deferred to QV/fix cycles.
    Target: templates/design/Feature_Design_Template.md
    Pros: Reduces multi-gate fallout and late-stage fixes; keeps S06/S07 contract changes self-contained.
    Cons: Slightly longer implementation-step checklist.
    If we don't: QV gates will continue to discover predictable contract regressions after code-review has already passed.
    Effort: S   (~10-20 lines, 1 file)

[2] Browser verification needed repeated reruns due unstable/under-seeded setup
    Severity: MED   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00091_S19_run1.log:5 — '"overall_status": "fail"'
      - ai-dev/logs/F-00091_S19_run1.log:11 — '"Could not reliably verify per-project active-tab restore and post-reload persistence in same stable session."'
      - ai-dev/active/F-00091/reports/F-00091_S19_QvBrowser_report.md:16 — "Known-context numeric `%` branch was not available from current seed"
    Recommendation: For qv-browser steps that require known/unknown state branches, require fixture availability checks (and explicit fallback fixture IDs) before V0-V6 execution.
    Target: skills/iw-workflow/SKILL.md
    Pros: Fewer browser-step reruns; clearer first-pass determinism.
    Cons: Slightly more up-front fixture prep in browser prompts.
    If we don't: Similar browser steps will continue to burn retries proving seed-dependent branches.
    Effort: M   (~20-40 lines, 1-2 files)

[3] RED-evidence contract inconsistent across behavior steps
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/active/F-00091/reports/F-00091_S01_Api_report.md:21 — "RED: ... failed with assert response.status_code == 200, got 404"
      - ai-dev/active/F-00091/reports/F-00091_S06_Backend_report.md:26 — "9 passed, 0 failed" (no explicit RED-first failure snippet recorded)
    Recommendation: Require a mandatory `tdd_red_evidence` field in all behavior-implementing step report templates, with validation that the snippet is a real behavioral failure (not import/collection/setup noise).
    Target: templates/design/Implementation_Report_Template.md
    Pros: Enforces consistent RED-first auditability across parallel implementation steps.
    Cons: Minor template/validator update overhead.
    If we don't: Self-assess and review steps will keep inferring RED quality from inconsistent prose.
    Effort: S   (~10-25 lines, 1-2 files)

Additional checks requested by prompt:
- Migration sequencing (S04 -> S05 -> S06 -> S07): gate passed; no sequencing break detected.
- Scope creep: no clear evidence of out-of-scope code edits in surfaced logs/reports.
- TDD RED quality: S01/S02/S03/S04/S07 explicit plausible RED evidence present; S06 lacks explicit RED snippet field.
