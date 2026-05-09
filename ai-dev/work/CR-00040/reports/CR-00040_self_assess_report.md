### Item Analysis: CR-00040

Bottom line: The single most impactful improvement is to clarify in `iw sync-templates` documentation and/or the S01 prompt that the command syncs registered project mirrors (in the main repo) but intentionally skips the worktree's own `ai-dev/templates/` directory — and that agents SHOULD NOT diff worktree-local mirrors against masters to verify AC4.

Steps analyzed: 7 (S01–S07)   Steps with retries: 1 (S01 had 3 runs, only 3rd succeeded due to model-not-found errors)   Total fix-cycles: 1 (S03 fix cycle 1 — AC4 sync-drift false positive)   DB signal: yes

---

[1] Model not found errors on S01 runs 1 and 2 caused 2 wasted runs before recovery
    Severity: MED   Class: platform   Frequency: one-off
    Evidence:
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S01_run1.log:22 — "Error: Model not found: minimax/."
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S01_run2.log:22 — "Error: Model not found: minimax/."
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S01_run3.log:3 — "> template-impl · MiniMax-M2.7" (succeeded)
    Recommendation: The model-not-found error on runs 1/2 is a transient provider/init failure, not a code issue. The platform recovered on run 3. No immediate action needed — this is normal thrash for a brand-new worktree. If it recurs across many items, investigate the minimax provider startup sequence.
    Target: iw-ai-core (orch/provider pool or agent bootstrap)
    Pros: Confirms platform self-heals for transient model failures.
    Cons: Wasted ~2 agent runs on S01.
    If we don't: Transient failures continue to waste 1–2 runs per worktree on first step.
    Effort: L (investigation needed — not a simple fix)

[2] S01 prompt lacked guidance on `iw sync-templates` worktree-local mirror behavior
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S01_run3.log:128 — "diff -u ... EXIT: 1" (S01 thought sync failed because it diffed worktree-local ai-dev/templates/ vs masters — but those weren't the sync targets)
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S02_run1.log:39-82 — Same false positive diff in S02; reported as CRITICAL AC4 failure
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S03_run1.log:39-96 — S03 also saw the same diff; S03 fix cycle resolved it by manual `cp`
    Recommendation: Add a note to the S01 prompt template (and/or the `iw sync-templates --help` output) clarifying that: (1) `sync-templates` updates registered project mirrors in the main repo, NOT the worktree's own `ai-dev/templates/`; (2) the correct way to verify AC4 is to diff the main-repo mirrors (`/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/ai-dev/templates/`), not the worktree-local directory.
    Target: templates/design/Feature_S01_prompt.md, templates/design/CR_S01_prompt.md, and/or `orch/cli/skills_commands.py` (sync-templates help text)
    Pros: Prevents false-positive AC4 failures; reduces unnecessary fix cycles.
    Cons: Small prompt/doc update.
    If we don't: Code review steps continue to raise false CRITICAL AC4 findings when syncing works correctly; fix cycles浪费 time.
    Effort: S (~5 lines in prompt + ~2 lines in sync-templates help text)

[3] S02 and S03 both ran the same file-path resolution thrash
    Severity: MED   Class: agent   Frequency: recurring
    Evidence:
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S02_run1.log:9-12 — Glob search found reports at ai-dev/active/CR-00040/reports/ but agent tried ai-dev/work/CR-00040/ first (File not found)
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S03_run1.log:9-21 — Same glob resolution thrash before finding correct path
    Recommendation: Update CLAUDE.md or the S02/S03 prompt templates to include a "File path cheat sheet" section: active item reports live at `ai-dev/active/<ID>/reports/`, NOT `ai-dev/work/<ID>/reports/`. Adding this shortcut prevents ~2 glob searches per code-review step.
    Target: CLAUDE.md (quick navigation table) or prompt template files for code_review step types
    Pros: Saves ~30s per code-review step; removes one source of confusion.
    Cons: Another cheat-sheet entry to maintain.
    If we don't: Code-review agents continue to glob-search before finding the correct path.
    Effort: S (~3 lines)

[4] S03 fix cycle invoked `script` with wrong arguments (fix1.log only 2 lines)
    Severity: LOW   Class: platform   Frequency: one-off
    Evidence:
      - .worktrees/CR-00040/ai-dev/logs/CR-00040_S03_fix1.log:1 — "script: unexpected number of arguments"
    Recommendation: The fix cycle prompt was apparently malformed — it tried to call `script` directly with wrong args. The executor or step-dispatch should validate fix-cycle prompts before invoking them, or the error message should be clearer. Investigate how the fix cycle was dispatched.
    Target: orch/daemon/step_dispatch.py or the fix-cycle prompt injection logic
    Pros: Prevents broken fix cycles from running.
    Cons: Fix cycle still ran correctly on retry (run3 succeeded), so impact was nil.
    If we don't: Malformed fix cycles waste time and produce confusing logs.
    Effort: M (requires tracing fix-cycle injection end-to-end)

---

**Coverage notes**: All S01–S07 run logs read in full. S07 log (339 KB) was spot-checked at lines 1–100 and tail; no errors found — tests passed cleanly. Fix cycle log S03_fix1.log is 2 lines and contains only the error. Reports read as secondary evidence only. DB telemetry: full (DB:UP confirmed).

**Note on self-referential irony**: CR-00040 is itself the implementation of a self-assess finding from CR-00039 ("design-doc not consulted before first code-review run"). The S02 and S03 agents did consult the design doc and ran cleanly — no design-doc-anchoring retries occurred. This supports the conclusion that the new templates are working as intended. The only retry in S02/S03 was the false-positive AC4 finding (sync drift), which was a path-resolution issue, not a design-doc issue.
