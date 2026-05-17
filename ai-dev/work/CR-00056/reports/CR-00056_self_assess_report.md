# Item Analysis: CR-00056

Bottom line: The QV gates burned 6 fix cycles across S10/S14/S17/S18/S19 — one (S09 colspan=9→11) was a HIGH finding that should have been self-assessed before the next step, not surfaced at the following CodeReview. All other fix cycles were lint/mypy/test-assertion noise resolved in a single pass.

Steps analyzed: 22   Steps with retries: 6 (S09/S10/S14/S17/S18/S19 fix cycles)   Total fix-cycles: 6   DB signal: yes

---

[1] QV gate caught frontend layout error instead of preventing it
    Severity: HIGH   Class: convention   Frequency: systemic
    Evidence:
      - .worktrees/CR-00056/ai-dev/logs/CR-00056_S09_run1.log (tail) — S09 CodeReview report: `colspan="9"` on empty-state row, table has 11 columns
      - .worktrees/CR-00056/ai-dev/logs/CR-00056_S10_fix1.log:8 — S10 fix-cycle reads S09 report, applies one-line colspan fix
    Recommendation: The Frontend step (S08) should run `make lint` and a basic template render check before declaring done. A one-line grep for `colspan=` in the modified template would have caught this. Consider adding a "pre-flight render smoke test" to the frontend-impl prompt as a mandatory self-check before step completion.
    Target: skills/iw-execute/SKILL.md or the frontend-impl prompt template in ai-dev/templates/
    Pros: Reduces fix-cycle churn; QV gates stay focused on substantive issues.
    Cons: Slightly longer frontend step runtime.
    If we don't: QV gates continue to catch obvious layout errors that should have been caught in self-check, burning agent time and gate passes.
    Effort: S (~1 grep command added to prompt)

---

[2] Stale test assertion in `test_load_actual_auto_merge_toml`
    Severity: MED   Class: convention   Frequency: one-off
    Evidence:
      - .worktrees/CR-00056/ai-dev/logs/CR-00056_S18_fix1.log:13 — "The test expects `phase=0` (PHASE_DISABLED) but the actual `executor/auto_merge.toml` has `phase=1` (PHASE_DRY_RUN)"
      - tests/unit/test_auto_merge_config.py:48 — stale assertion `assert config.phase == PHASE_DISABLED`
    Recommendation: When updating a config file (e.g., `executor/auto_merge.toml` advancing from phase 0 to 1), search for and update any hardcoded phase assertions in tests before the item reaches QV gates. Consider a grep for the constant name in test files during the step that updates the config.
    Target: ai-dev/templates/Feature_Design_Template.md or a convention note in CLAUDE.md
    Pros: Prevents QV-gate fix cycles on stale assertions.
    Cons: Requires agents to remember an extra grep step.
    If we don't: Test fails at QV S18, requires a fix cycle.
    Effort: S (~1 grep + 1 edit)

---

[3] Unusual `dir()` sentinel in batch_manager.py
    Severity: MED   Class: convention   Frequency: one-off
    Evidence:
      - .worktrees/CR-00056/ai-dev/logs/CR-00056_S05_run1.log:457 — S05 CodeReview: "batch_manager.py line 1503: `if "prompt" in dir()` is an unusual pattern — a cleaner sentinel (`prompt: str | None = None`) would be more idiomatic"
    Recommendation: Use an explicit `prompt: str | None = None` parameter instead of `dir()` introspection. This is cleaner and mypy-friendly.
    Target: orch/daemon/batch_manager.py (line ~1503)
    Pros: More idiomatic, clearer intent, easier to search/refactor.
    Cons: Minor refactor; not broken.
    If we don't: Code reviewer notes it as unusual but no functional harm.
    Effort: S (~3 lines)
