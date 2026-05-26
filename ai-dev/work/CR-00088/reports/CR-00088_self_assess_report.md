### Item Analysis: CR-00088

Bottom line: add a guard in the step runner to avoid re-executing already-passed QV gates when no new code changes occurred between retries.

Steps analyzed: 13   Steps with retries: 6   Total fix-cycles: 5   DB signal: yes

[1] Duplicate QV reruns after success (no visible delta)
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/CR-00088_S06_run1.log:1-4 — "uv run python scripts/check_templates.py ... Completed CR-00088 step S06"
      - ai-dev/logs/CR-00088_S06_run2.log:1-4 — same command sequence and completion text repeated
      - ai-dev/logs/CR-00088_S08_run1.log:1-3 and ai-dev/logs/CR-00088_S08_run2.log:1-3 — identical format-check rerun
      - ai-dev/logs/CR-00088_S09_run1.log:1-3 and ai-dev/logs/CR-00088_S09_run2.log:1-3 — identical typecheck rerun
    Recommendation: In gate orchestration, short-circuit reruns when previous run is successful and no new commit/diff exists for the worktree.
    Target: orch/daemon/batch_manager.py
    Pros: Saves repeated CI time and reduces noisy logs.
    Cons: Needs careful invalidation when fix-cycle changes files.
    If we don't: QV wall-clock and log volume keep growing from redundant re-execution.
    Effort: M   (~40-80 lines, 1-2 files)

[2] Unit gate blocked early by optional dependency import path
    Severity: HIGH   Class: environment   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00088_S10_run1.log:14-22 — "ERROR collecting tests/unit/test_llm_judge_script.py ... ModuleNotFoundError: No module named 'anthropic'"
      - ai-dev/logs/CR-00088_S10_run1.log:33-34 — "make: *** [Makefile:121: test-unit] Error 2 ... unit-tests failed"
      - ai-dev/logs/CR-00088_S10_fix1.log:5 — same root cause documented in fix summary
    Recommendation: Keep optional-provider imports guarded and add a tiny preflight test that enforces "unit test modules must import without optional SDKs installed".
    Target: tests/unit/test_llm_judge_script.py
    Pros: Prevents collection-time hard failures; catches regressions fast.
    Cons: One more boundary test to maintain.
    If we don't: Similar optional-dependency imports can halt the whole unit gate before tests run.
    Effort: S   (~10-20 lines, 1 file)
