# I-00073 Self-Assessment Report

## Item Analysis: I-00073

**iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items**

Bottom line: The structural collision between "agent modifies orch schema" and "agent must call back to orch via `iw` CLI" was not visible at design time; the `iw-item-analyze` skill would have surfaced it if the Issue design template prompted for "what can go wrong at the boundary between agent worktree and orch DB."

Steps analyzed: S01–S13 (implementation, code review, and quality gates). DB signal: yes.

---

Steps analyzed: 13 (S01–S13). Steps with retries: 4 (S02, S06, S07, S13). Total fix-cycles: 9 (S02: 2, S06: 1, S07: 1, S13: 5). DB signal: yes.

---

[1] Schema-drift collision invisible at design time
    Severity: HIGH   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/active/I-00073/I-00073_Issue_Design.md — no mention of "what happens when the agent finishes and tries to call back to the orch DB" despite the entire bug being that exact scenario
      - S13_fix5.log:27498 — "Removed `s.gate` from `item-status` JSON serialization (`item_commands.py:916`)" — final fix was a one-liner; the 5 prior cycles searched for more complex causes
    Recommendation: Add a "failure modes at the agent–orch boundary" subsection to the Issue design template. Specifically: when the fix requires the agent to modify orch-level files (models, migrations, CLI commands), the template should prompt the author to ask "can the agent still call `iw step-done` after these changes?"
    Target: templates/design/Issue_Design_Template.md (or the Issue template under ai-dev/templates/)
    Pros: Prevents the class of bug this item fixed — agents block themselves from completing.
    Cons: Slightly longer template; adds one more question to an already thorough structure.
    If we don't: Future Incident/Feature designs that touch orch schema will reproduce the same stall pattern.
    Effort: S (~5 lines in template)

[2] item-status JSON builder bypassed load_only column set
    Severity: HIGH   Class: platform   Frequency: one-off
    Evidence:
      - .worktrees/I-00073/ai-dev/logs/I-00073_S13_fix5.log:397 — "Removed `s.gate` from `item-status` JSON serialization (`item_commands.py:916`)"
      - .worktrees/I-00073/ai-dev/logs/I-00073_S13_fix5.log:307 — "All 9 drift tests pass, lint and mypy pass"
    Recommendation: Audit `item_commands.py` for any attribute access on workflow-step objects outside the pinned `_WORKFLOW_STEP_CLI_COLUMNS` set. Ensure every `.gate`, `.description`, `.prompt_file`, etc. access is covered by the column list or loaded explicitly.
    Target: orch/cli/item_commands.py
    Pros: Closes the last gap in the drift-tolerance fix; the 9 drift tests validate it.
    Cons: Maintenance burden if new columns are added to WorkflowStep without updating the CLI column set.
    If we don't: A future WorkflowStep column add will reproduce the exact I-00073 crash on `item-status`.
    Effort: S (~1 file, audit only)

[3] S13 integration-tests fix-cycle needed 5 iterations due to non-obvious symptom
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - .worktrees/I-00073/ai-dev/logs/I-00073_S13_fix1.log:282 — 343 failed tests, many ERRORs in merge-queue and FTS tests
      - .worktrees/I-00073/ai-dev/logs/I-00073_S13_fix5.log:27498 — fix was "Removed `s.gate` from `item-status` JSON serialization"
      - Fix cycle prompts I-00073_S13_FIX_cycle{1,2,3,4,5} show the diagnostic hypotheses shifting each round
    Recommendation: When the integration-tests gate fails with many heterogeneous ERRORs across unrelated test files (merge-queue, FTS, reindex), the fix-cycle prompt should specifically call out "pre-existing failures" as a hypothesis to check before assuming the new code is at fault. The first cycle spent significant time looking at the wrong errors.
    Target: skills/iw-execute/SKILL.md or the fix-cycle prompt generator
    Pros: Reduces wasted fix cycles on pre-existing failures; faster turnaround on mixed results.
    Cons: More complex fix-cycle prompt logic; potential over-engineering if this pattern is rare.
    If we don't: Future items hitting heterogeneous integration failures will repeat the diagnostic thrash.
    Effort: S (~10 lines in fix-cycle prompt guidance)

[4] QV lint/format gates failed on code the Tests agent added
    Severity: MED   Class: prompt   Frequency: one-off
    Evidence:
      - .worktrees/I-00073/ai-dev/logs/I-00073_S06_fix1.log:9 — "E402 Module level import not at top of file"
      - .worktrees/I-00073/ai-dev/logs/I-00073_S06_fix1.log:37 — "E501 Line too long (101 > 100)"
      - S07_fix1.log:6 — "`orch/cli/step_commands.py` was reformatted"
    Recommendation: The S03 (Tests) prompt should include a "run `make lint && make format` before marking step done" reminder, since any new test file added to the repo must pass the project's style gates. This is especially important for integration test files that import ORM models.
    Target: ai-dev/templates/Feature_Design_Template.md (S03 agent prompt section) or the tests-impl agent spec
    Pros: Prevents trivial style failures from generating fix cycles.
    Cons: One more reminder in an already long prompt.
    If we don't: Future Tests steps on any project will risk generating style-fix fix cycles.
    Effort: S (~3 lines)

[5] S02 CodeReview required 2 fix cycles to fully verify drift-test suite
    Severity: MED   Class: prompt   Frequency: one-off
    Evidence:
      - .worktrees/I-00073/ai-dev/logs/I-00073_S02_fix1.log:27 — only 1 of 9 drift tests passed initially
      - .worktrees/I-00073/ai-dev/logs/I-00073_S02_fix2.log:8230 — 9 tests passed after second review
    Recommendation: The S02 (CodeReview) prompt for tests should explicitly require the reviewer to run `pytest tests/integration/cli/test_step_commands_drift.py --no-cov` and confirm all 9 tests pass, not just verify the code exists.
    Target: templates/design/Feature_Design_Template.md (S04 section) or the code-review-impl agent spec
    Pros: Catches incomplete implementations earlier in the chain.
    Cons: Slightly longer review checklist.
    If we don't: Future code-review steps for test additions may pass prematurely.
    Effort: S (~5 lines)

---

## Coverage Notes

Sampled tail (last 50–100 lines) of all large logs (S01, S03, S05, S02 runs 1–3, S13 fix cycles 1–5). Read S06_run1, S06_run6, S07_run1, S13_run1, S14_run1 in full. DB telemetry: full (`iw db-identity check` returned UP, `iw item-status --json` confirmed item state). Logs from `.worktrees/I-00073/ai-dev/logs/` and reports from `ai-dev/active/I-00073/reports/`. The worktree was deleted by the time S14 ran, but the active directory was intact at `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00073/ai-dev/logs/`. Fix-cycle prompt files read to understand diagnostic hypothesis progression across S13's 5 cycles.

## Step-by-step Signal Summary

| Step | Runs | Fix cycles | Key observation |
|------|------|------------|----------------|
| S01  | 1    | 0          | Backend agent found already-patched code; verified via grep |
| S02  | 3    | 2          | CodeReview initially missed failing drift tests; second review cycle verified all 9 pass |
| S03  | 1    | 0          | Tests written; 9 drift tests created against testcontainer |
| S04  | 1    | 0          | CodeReview verified tests |
| S05  | 1    | 0          | Final cross-step review passed |
| S06  | 8    | 1          | Lint failed on new test file (E402 import order, E501 line length) |
| S07  | 7    | 1          | Format failed on step_commands.py auto-reformat |
| S08  | 6    | 0          | Typecheck passed |
| S09  | 6    | 0          | Arch-check passed |
| S10  | 6    | 0          | Security SAST passed |
| S11  | 6    | 0          | Unit tests passed |
| S12  | 6    | 0          | Frontend tests passed |
| S13  | 6    | 5          | Integration tests — pre-existing failures masked the real fix; `item-status s.gate` lazy-load bug found in cycle 5 |