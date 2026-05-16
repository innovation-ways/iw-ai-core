### Item Analysis: I-00082

Bottom line: After I-00082 merges, trigger a canary fix-cycle to confirm the scope block appears in the prompt — the S12 fix cycle in this item ran **without** `allowed_paths` enforcement because the daemon (running from `main`) had not yet received the new code.

Steps analyzed: 14   Steps with retries: 6 (S06–S11 each ran twice)   Total fix-cycles: 1 (QV) + 2 (code-review) = 3   DB signal: yes

---

[1] S12 QV fix-cycle prompt missing `allowed_paths` scope block — daemon version lag
    Severity: HIGH   Class: platform   Frequency: systemic

    Evidence:
      - ai-dev/active/I-00082/fix-cycles/I-00082_S12_FIX_cycle1_prompt.md — no scope section present; `grep -n 'allowed_paths\|scope' I-00082_S12_FIX_cycle1_prompt.md` returns only the generic "step's scope" line from the boilerplate
      - ai-dev/active/I-00082/workflow-manifest.json — `"allowed_paths": ["orch/daemon/fix_cycle.py", "tests/integration/test_fix_cycle_scope_enforcement.py"]` (non-empty; block injection should have fired)
      - .worktrees/I-00082/orch/daemon/fix_cycle.py:1974 — `f"{scope_block}"` is present in `_build_qv_fix_prompt_content`; the daemon on `main` lacks this line

    Meta-test result (Focus area #3): NEGATIVE. The new escalation code did NOT engage during this item's own execution. The S12 fix-cycle agent added 4 tests exclusively to `tests/integration/test_fix_cycle_scope_enforcement.py` (which IS in `allowed_paths`) by inference alone — there was no prompt constraint and no escalation guard active. Had the agent drifted to a neighbouring test file, no scope violation would have been detected or escalated.

    Recommendation: Add a post-merge smoke step to the I-00082 merge checklist (or a new `iw verify-scope-injection <item-id>` command) that launches a minimal test item with a tight `allowed_paths`, triggers one deliberate QV failure, and confirms the fix-cycle prompt contains the `## Scope` block. Document this in `CLAUDE.md` under a "Post-merge validation for `fix_cycle.py` changes" heading.

    Target: CLAUDE.md (post-merge validation procedure) + orch/daemon/fix_cycle.py (the main-branch QV fix-cycle builder is the fix itself)
    Pros: Makes the self-referential limitation explicit; prevents the next version drift from going undetected.
    Cons: Adds one manual verification step to the post-merge checklist.
    If we don't: The first post-merge fix cycle on any item could still silently drift without scope enforcement, and operators would have no signal until the merge-time scope gate (executor/scope_gate.py) fires.
    Effort: S (~15 lines: CLAUDE.md doc + optional iw subcommand stub)

---

[2] Full QV re-run (S06–S11) triggered by S12 diff-coverage fix cycle — redundant static-analysis passes
    Severity: MED   Class: platform   Frequency: systemic

    Evidence:
      - .worktrees/I-00082/ai-dev/logs/ timestamps: S06_run2=07:37, S07_run2=07:38, S08_run2=07:39, S09_run2=07:40 — all written immediately after S12_fix1 at 07:37
      - S10_run2=07:43 (unit tests, 355 KB log, ~5 min), S11_run2=07:54 (integration tests, 342 KB log, ~10 min) — also repeated
      - S12_fix1.log:1 — "The gate passes with 100% diff coverage… four new tests I added cover…" — fix only added test files to test_fix_cycle_scope_enforcement.py; no production code changed

    S06 (lint), S07 (assertions), S08 (format), S09 (typecheck) are fully deterministic on production code. When a diff-coverage fix cycle adds only test files, these four gates cannot change outcome. The repeated runs added ~8 min of idle gate time with zero signal.

    Recommendation: In the fix-cycle re-run scheduler, classify whether the fix touched only test files (patterns: `tests/**`, `test_*.py`) vs. production code. If test-only, skip static-analysis gates (S06–S09) and run only unit-tests, integration-tests, and diff-coverage.

    Target: orch/daemon/fix_cycle.py (gate re-run scheduling after fix cycle completes)
    Pros: Saves 8–15 min per diff-coverage fix cycle on test-only additions; no signal lost (lint on new tests runs at the next natural full pass or can be kept as a targeted per-file check).
    Cons: If the new test file happens to introduce a lint violation, it won't be caught until the next full-suite run.
    If we don't: Every diff-coverage fix cycle that adds tests repeats the full 15-min QV chain unnecessarily — a cost that compounds with every future item.
    Effort: M (~20 lines: classify changed files post-fix, condition gate list)

---

[3] S02 per-agent and S05 final review independently re-discovered the same C1 budget-filter bug
    Severity: MED   Class: prompt   Frequency: systemic

    Evidence:
      - .worktrees/I-00082/ai-dev/logs/I-00082_S02_run1.log:3 — "CRITICAL (C1) — both `.count()` queries must add `.filter(FixCycle.status != FixStatus.escalated)`"
      - .worktrees/I-00082/ai-dev/logs/I-00082_S05_run1.log:5 — "Finding 1 (HIGH) — `should_attempt_fix` (line 482) counts ALL FixCycle rows … plus the aggregate budget check (lines 498–503) has the same gap"
      - S02's fix cycle applied to `should_attempt_fix` but missed the aggregate budget sub-query at lines 498–503; S05 then re-found the same pattern at those exact lines

    The code-review-fix agent applied a partial fix (one of the two query sites), leaving the other for S05 to catch. This consumed a second independent review cycle on a bug that had already been identified.

    Recommendation: Add an explicit "carry-forward" check to the CodeReviewFinal (S05) prompt: "Load the S02 and S04 finding reports and list each CRITICAL/HIGH finding with its resolution status. Verify the fix was applied at ALL call sites before re-reviewing from scratch." This prevents S05 from re-discovering partially applied fixes.

    Target: skills/iw-new-incident/SKILL.md (CodeReviewFinal prompt template section) — or the project's ai-dev/templates/ copy of the Issue_Design_Template.md which generates S05's prompt.
    Pros: Cheap; a 3-line addition to the S05 prompt template; reduces duplicate review effort on partial fixes.
    Cons: S05 needs to read the S02/S04 reports before starting its own pass — slightly more complex task setup.
    If we don't: Partially-applied review fixes will continue to be caught by the final review rather than failing fast at the code-review-fix stage, wasting one full review cycle per occurrence.
    Effort: S (~5 lines in the CodeReviewFinal prompt template)

---

**Focus area summary (I-00082-specific)**

| Focus | Result |
|-------|--------|
| 1. New escalation path produced thrash? | No — escalation code NOT active in this item's daemon; no false-positive scope blocks |
| 2. `allowed_paths` block survived all fix cycles? | No — S12 FIX cycle1 prompt lacks the block (daemon version lag); agent stayed in scope by inference only |
| 3. Any QV gate hit the new escalation code? | No — meta-test NEGATIVE; new code is in worktree, not in the daemon that generated the fix cycle |
| 4. Cost vs CR-00053 (~14 wasted cycles)? | 3 total cycles (1 QV diff-coverage + 2 code-review), all resolved in 1 pass — no scope-drift loops |
| 5. Before/after pattern vs CR-00053 S09/S10/S15? | CR-00053: 3+4+3=10 cycles lost to scope drift/revert. I-00082: 0 scope cycles (S12 fix stayed in scope unforced). The pre/post comparison is latent — live validation requires a post-merge item. |
