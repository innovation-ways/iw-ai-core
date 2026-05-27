### Item Analysis: CR-00089

Bottom line: harden QV retry semantics so deterministic failures trigger targeted fix-cycles, while likely flakes auto-retry once before opening a blocker.

Steps analyzed: 13   Steps with retries: 5   Total fix-cycles: 7   DB signal: yes

[1] QV gates were repeatedly re-executed after completion
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/CR-00089_S08_run1.log:4 — "Completed CR-00089 step S08"
      - ai-dev/logs/CR-00089_S08_run7.log:4 — "Completed CR-00089 step S08" (also seen in S09/S10/S11)
      - ai-dev/logs/CR-00089_S09_run1.log:3 — "935 files already formatted"
      - ai-dev/logs/CR-00089_S09_run6.log:3 — "935 files already formatted"
    Recommendation: deduplicate already-passed QV reruns unless an upstream file change matches that gate’s relevance filter.
    Target: orch/daemon/batch_manager.py
    Pros: reduces redundant gate runtime and queue churn.
    Cons: requires careful invalidation logic for legitimate reruns.
    If we don't: long pipelines continue to spend cycles re-running unchanged gates.
    Effort: M   (~40-80 lines, 2-3 files)

[2] Test flake-like failures consumed full long-gate retries
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00089_S11_run2.log:4008 — "= 1 failed, 3616 passed..."
      - ai-dev/logs/CR-00089_S11_run4.log:3930 — "= 3617 passed..."
      - ai-dev/logs/CR-00089_S12_run7.log:3904 — "= 2 failed, 3259 passed..."
      - ai-dev/logs/CR-00089_S12_run9.log:3813 — "= 3261 passed..."
    Recommendation: add automatic one-shot retry classification for known flaky signatures before escalating to full manual fix-cycle.
    Target: orch/daemon/qv_baseline.py
    Pros: reduces false-negative gate failures and wasted 3-20 minute reruns.
    Cons: can hide real regressions if retry policy is too broad.
    If we don't: expensive QV runs will keep failing transiently and burning agent budget.
    Effort: M   (~60-120 lines, 2-4 files)

[3] Fix-cycle guidance produced a false out-of-scope blocker on unstable integration signal
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00089_S12_fix3.log:37 — "expected Alembic head revision ... actual head is ..."
      - ai-dev/logs/CR-00089_S12_fix3.log:50 — "### blockers"
      - ai-dev/logs/CR-00089_S12_fix4.log:11 — "No code edits were needed."
      - ai-dev/logs/CR-00089_S12_run9.log:3814 — "Completed CR-00089 step S12"
    Recommendation: update fix-cycle prompt template to require one confirmatory rerun for migration-head mismatch failures before declaring out-of-scope blocker.
    Target: templates/prompts/Fix_Cycle_prompt.md
    Pros: fewer false blockers from transient DB/test-state drift.
    Cons: one extra rerun in truly deterministic mismatch cases.
    If we don't: agents will continue filing avoidable blockers during noisy integration gates.
    Effort: S   (~10-20 lines, 1 file)
