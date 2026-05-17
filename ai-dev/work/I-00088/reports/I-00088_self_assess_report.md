### Item Analysis: I-00088

Bottom line: fix the prompt-template report-path contract (`ai-dev/work/...` vs `ai-dev/active/...`) first; it caused most of the avoidable thrash in this item.

Steps analyzed: 11   Steps with retries: 8   Total fix-cycles: 12   DB signal: yes

[1] Prompt templates point reviewers to non-existent report paths
    Severity: MED   Class: prompt   Frequency: recurring
    Evidence:
      - ai-dev/active/I-00088/prompts/I-00088_S02_CodeReview_Backend_prompt.md:25 - "ai-dev/work/I-00088/reports/I-00088_S01_Backend_report.md"
      - ai-dev/logs/I-00088_S02_run1.log:9 - "Error: File not found: .../ai-dev/work/I-00088/reports/I-00088_S01_Backend_report.md"
      - ai-dev/active/I-00088/prompts/I-00088_S04_CodeReview_Tests_prompt.md:22 - "ai-dev/work/I-00088/reports/I-00088_S03_Tests_report.md"
      - ai-dev/logs/I-00088_S04_run3.log:22 - "Error: File not found: .../ai-dev/work/I-00088/reports/I-00088_S03_Tests_report.md"
    Recommendation: update design and prompt templates so runtime step reports are read from `ai-dev/active/<ID>/reports/` (or explicitly tell agents to probe both active/work paths before failing).
    Target: ai-dev/templates/Implementation_Prompt_Template.md, ai-dev/templates/CodeReview_Prompt_Template.md, ai-dev/templates/CodeReview_Final_Prompt_Template.md, ai-dev/templates/SelfAssess_Prompt_Template.md
    Pros: removes repeated file-not-found loops in review/fix cycles; cuts wasted retries quickly.
    Cons: requires template sync/regeneration for new items.
    If we don't: code-review steps will keep spending cycles rediscovering the correct report location.
    Effort: S   (~10-20 lines, 4 files)

[2] Integration QV gate showed one high-cost flaky failure before passing on rerun
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00088_S10_run3.log:3186 - "6 failed ... in 909.99s"
      - ai-dev/logs/I-00088_S10_run3.log:2710 - "KeyError: 'request_id'"
      - ai-dev/logs/I-00088_S10_run3.log:3188 - "Failed I-00088 step S10: integration-tests failed: exit=2"
      - ai-dev/logs/I-00088_S10_run5.log:2995 - "Completed I-00088 step S10"
    Recommendation: harden the SSE event-order assumptions in the e2e opencode-stub integration tests and/or add deterministic wait/assert helpers for `request_id` emission.
    Target: tests/integration/test_e2e_opencode_stub.py
    Pros: fewer 15-minute integration reruns; more stable QV signal.
    Cons: test harness changes may take investigation to avoid masking real regressions.
    If we don't: long-running integration gates will continue to fail intermittently and consume fix cycles.
    Effort: M   (~30-80 lines, 1 file)
