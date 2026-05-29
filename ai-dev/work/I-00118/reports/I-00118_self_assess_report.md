### Item Analysis: I-00118

Bottom line: tighten workflow scope + prompt contracts so backend/test split does not trigger avoidable review failures and late diff-coverage churn.

Steps analyzed: 14   Steps with retries: 9   Total fix-cycles: 6   DB signal: yes

[1] Scope contract mismatch created avoidable review/fix churn
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00118_S02_run1.log:88 — "Reason for fail: S01 included an out-of-scope test-file modification..."
      - ai-dev/logs/I-00118_S05_fix1.log:37 — "Global review failed: make test-unit is red..."
    Recommendation: Add a manifest/prompt rule that allows tightly-coupled test updates in S01 when the design ACs require parser-behavior changes, or explicitly defer and auto-ignore those diffs in S02 scope checks.
    Target: templates/design/Issue_Design_Template.md
    Pros: Fewer artificial fail/fix loops; earlier convergence.
    Cons: Slightly more complex scope policy wording.
    If we don't: reviewers will keep failing otherwise-correct steps for workflow-contract mismatch.
    Effort: M   (~20 lines, 1 file)

[2] Late diff-coverage failure indicates missing earlier gate signal
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00118_S12_run1.log:900 — "Failure. Coverage is below 90%."
      - ai-dev/logs/I-00118_S12_run1.log:915 — "Failed I-00118 step S12: diff-coverage failed: exit=2"
    Recommendation: add an earlier lightweight changed-lines coverage precheck after Tests step (or in final review) to catch under-covered touched lines before QV S12.
    Target: orch/daemon/batch_manager.py
    Pros: Prevents late-stage gate surprises; reduces rerun cost.
    Cons: Adds one extra precheck pass.
    If we don't: low-coverage deltas will continue failing near the end of the pipeline.
    Effort: M   (~40 lines, 1-2 files)

[3] Repeated expected live-DB guard tracebacks add noisy false alarms
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/I-00118_S11_run1.log:3490 — "LiveDbConnectionRefusedError: Connection to live orch DB refused..."
      - ai-dev/logs/I-00118_S11_run2.log:3566 — "LiveDbConnectionRefusedError: Connection to live orch DB refused..."
    Recommendation: suppress/mark known expected thread exceptions in integration tests that intentionally probe live-db guard behavior, so gate logs stay signal-dense.
    Target: tests/integration/test_oss_dashboard_routes.py
    Pros: Cleaner diagnostics; faster triage when real failures happen.
    Cons: Requires careful filtering to avoid hiding real regressions.
    If we don't: engineers keep spending time scanning noisy traceback blocks.
    Effort: S   (~10-20 lines, 1-2 files)
