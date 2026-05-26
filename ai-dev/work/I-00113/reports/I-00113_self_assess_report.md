### Item Analysis: I-00113

Bottom line: reduce QV-gate retry thrash by adding stronger stop/escalation rules when a gate fails repeatedly on unchanged infrastructure issues.

Steps analyzed: 15   Steps with retries: 7   Total fix-cycles: 12   DB signal: yes

[1] QV gates retried many times before converging
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/I-00113_S10_run1.log:5 — "Failed I-00113 step S10: assertions failed: exit=2"
      - ai-dev/logs/I-00113_S10_run4.log:2 — "Completed I-00113 step S10" (same gate oscillated fail/pass/fail/pass)
      - ai-dev/logs/I-00113_S13_run1.log:25 — "Failed I-00113 step S13: diff-coverage failed: exit=2"
    Recommendation: Add retry/escalation guardrails to gate-fix flow so repeated same-gate failures auto-switch to infra diagnosis instead of repeated full reruns.
    Target: skills/iw-fix-gates/SKILL.md
    Pros: Cuts wasted CI minutes and fix-cycle budget burn.
    Cons: Slightly more workflow logic in gate-fix guidance.
    If we don't: Long retry loops will continue when failures are not code-regression related.
    Effort: M   (~30-60 lines, 1 file)

[2] Unit gate failed on missing optional dependency (`anthropic`)
    Severity: HIGH   Class: environment   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00113_S11_run1.log:14 — "ModuleNotFoundError: No module named 'anthropic'"
      - ai-dev/logs/I-00113_S11_run5.log:14 — "ModuleNotFoundError: No module named 'anthropic'"
    Recommendation: Ensure tests that require optional provider SDKs are consistently guarded/skipped or available in test env by default.
    Target: tests/unit/test_llm_judge_script.py
    Pros: Prevents hard collection failures in `make test-unit`.
    Cons: May hide real integration issues if overused.
    If we don't: Unit gate will intermittently fail at collection before running relevant tests.
    Effort: S   (~5-20 lines, 1 file)

[3] Integration gate repeatedly failed due test DB connection refusal
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00113_S12_run1.log:3380 — "connection to server at \"127.0.0.1\", port 50444 failed: Connection refused"
      - ai-dev/logs/I-00113_S12_run6.log:3380 — "connection to server at \"127.0.0.1\", port 50444 failed: Connection refused"
      - ai-dev/logs/I-00113_S12_run1.log:6273 — "6 failed, 3210 passed"
    Recommendation: Stabilize dashboard test client/engine binding so TimingMiddleware and request handlers share the same live testcontainer DB engine.
    Target: tests/dashboard/test_route_contract_sweep.py
    Pros: Removes a high-cost flaky failure source in `make test-integration`.
    Cons: Requires careful fixture refactor.
    If we don't: Integration gate will continue burning retries on infra-flake failures.
    Effort: M   (~40-120 lines, 2-4 files)
