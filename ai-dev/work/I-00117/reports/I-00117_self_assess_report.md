### Item Analysis: I-00117

Bottom line: Make QV gates scope-aware so unrelated/out-of-scope failures do not consume all fix cycles.

Steps analyzed: 14   Steps with retries: 6   Total fix-cycles: 7   DB signal: yes

[1] QV assertion gate deadlocked on out-of-scope failures
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00117_S09_run1.log:1 — "tests/unit/test_llm_usage.py:1745: tautology..."
      - ai-dev/logs/I-00117_S09_run12.log:6 — "Failed I-00117 step S09: assertions failed: exit=2"
      - ai-dev/logs/I-00117_S09_fix5.log:106 — "fails, but only due to out-of-scope file"
    Recommendation: Add pre-check logic in QV/fix-cycle flow to detect out-of-scope failing files and escalate/amend scope instead of retrying the same gate.
    Target: orch/daemon/step_monitor.py
    Pros: Avoids wasted retries and final-cycle stalls; faster item completion.
    Cons: Needs reliable parser for gate output.
    If we don't: Similar items will burn all fix cycles on unrelated files.
    Effort: M   (~2-3 files)

[2] Duplicate successful reruns after step already completed
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/I-00117_S07_run1.log:3 — "Completed I-00117 step S07"
      - ai-dev/logs/I-00117_S07_run2.log:3 — "Completed I-00117 step S07"
      - ai-dev/logs/I-00117_S08_run1.log:3 — "Completed I-00117 step S08"
      - ai-dev/logs/I-00117_S08_run2.log:3 — "Completed I-00117 step S08"
    Recommendation: Enforce idempotency guard before launching a run (skip if step already terminal/completed) and log dedupe reason.
    Target: orch/daemon/batch_manager.py
    Pros: Reduces wasted compute and noisy logs.
    Cons: Requires careful state-check ordering.
    If we don't: Repeated no-op executions continue to mask real retries.
    Effort: S   (~1-2 files)
