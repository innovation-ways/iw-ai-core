### Item Analysis: I-00067

Bottom line: S01's CSS was added to `tailwind.src.css` but never reached `styles.css` — the fix cycle resolved it, but the CLAUDE.md convention about "run `make css` after Tailwind changes" is insufficient when the Tailwind CLI cannot run, causing a preventable FAIL→fix cycle on S05.

Steps analyzed: 5 (S01–S05)   Steps with retries: 3 (S01×2, S03×2, S05×2)   Total fix-cycles: 1   DB signal: yes

[1] S01 spent 3 runs getting tests to pass due to test-location error and over-specific assertions
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - .worktrees/I-00067/ai-dev/logs/I-00067_S01_run1.log:42 — "fixture 'client' not found" (test in wrong dir)
      - .worktrees/I-00067/ai-dev/logs/I-00067_S01_run1.log:498 — "activity-message-truncated" found in HTML from JS string, not HTML element (assertion too broad)
    Recommendation: Tests for dashboard template features should use `tests/dashboard/` directory. The prompt template for S01 should specify `tests/dashboard/` explicitly, and assertion searches for CSS class selectors should scope to HTML attribute values (e.g., `class="activity-message-truncated`) not raw class name strings.
    Target: templates/design/Issue_Design_Template.md or ai-dev/templates/Issue_Design_Template.md
    Pros: Future agents won't waste 2 runs correcting test location and overly broad assertions.
    Cons: Small change to prompt template.
    If we don't: Future frontend steps continue burning 2+ runs on test setup issues.
    Effort: S (~2 lines in S01 prompt)

[2] `make css` is a no-op; CLAUDE.md convention is insufficient when Tailwind CLI cannot run
    Severity: HIGH   Class: convention   Frequency: systemic
    Evidence:
      - .worktrees/I-00067/ai-dev/logs/I-00067_S01_run1.log:392-393 — "$ make css → make: Nothing to be done for 'css'"
      - .worktrees/I-00067/ai-dev/logs/I-00067_S05_run1.log:256-258 — "The `make css` target is declared in .PHONY but has no actual rule body"
      - .worktrees/I-00067/ai-dev/logs/I-00067_S05_fix1.log:28-50 — Tailwind CLI fails with MODULE_NOT_FOUND for postcss-selector-parser; fix cycle appends CSS directly to styles.css
    Recommendation: CLAUDE.md Critical Rules should add: "If `make css` produces 'Nothing to be done' or 'no rule body', append CSS rules directly to `dashboard/static/styles.css` (plain CSS is deployable as-is). Do NOT wait for S05 to discover this."
    Target: CLAUDE.md
    Pros: Prevents S01→S05 FAIL→fix cycle; saves ~1 hour of wall clock time.
    Cons: Slightly longer Critical Rules section.
    If we don't: Every future item that modifies `tailwind.src.css` risks the same FAIL→fix cycle path.
    Effort: S (~8 lines in CLAUDE.md)

[3] S05 fix cycle correctly identified Tailwind CLI broken and appended CSS directly
    Severity: MED   Class: platform   Frequency: one-off
    Evidence:
      - .worktrees/I-00067/ai-dev/logs/I-00067_S05_fix1.log:28-50 — "Cannot find module 'postcss-selector-parser'" → fix cycle correctly falls back to appending CSS directly to styles.css
      - .worktrees/I-00067/ai-dev/logs/I-00067_S05_fix1.log:66 — CSS appended to styles.css, 7 tests pass, lint passes
    Recommendation: Document in `docs/IW_AI_Core_Daemon_Design.md` or a worktree-setup doc that `node_modules` may be incomplete in worktrees (postcss-selector-parser missing), and the fix (append plain CSS directly to styles.css) works when Tailwind CLI cannot.
    Target: docs/IW_AI_Core_Tech_Stack.md or orch/daemon/worktree_compose.py
    Pros: Makes the fix strategy discoverable for future fix cycles.
    Cons: None significant.
    If we don't: Future fix cycle agents may attempt more Tailwind CLI invocations before trying the direct-append strategy.
    Effort: M (~10 lines)

[4] Test assertion fragility for HTML-escaped quotes in `data-full-text` attribute
    Severity: LOW   Class: agent   Frequency: one-off
    Evidence:
      - .worktrees/I-00067/ai-dev/logs/I-00067_S02_run1.log:114-116 — `assert f'data-full-text="{long_msg}"' in html` — passes because long_msg='E'*200 has no quotes; would fail for messages containing `"`
      - S05 review notes this was not fixed in S03, flagged as INFO
    Recommendation: Test should use `html.escape(long_msg)` or a regex-based attribute existence check rather than exact string match on the attribute value.
    Target: tests/dashboard/test_i00067_recent_activity_truncation.py
    Pros: Test becomes robust against messages containing double-quote characters.
    Cons: Test-only change; no production impact.
    If we don't: Test passes today but would silently produce false negatives if future test messages contain `"`.
    Effort: S (~3 lines)

[5] `LiveDbConnectionRefusedError` startup noise in all dashboard test logs
    Severity: LOW   Class: platform   Frequency: recurring
    Evidence:
      - .worktrees/I-00067/ai-dev/logs/I-00067_S01_run1.log:189 — "alembic guard check failed at startup; continuing"
      - .worktrees/I-00067/ai-dev/logs/I-00067_S02_run1.log:207 — same noise in every test run
      - .worktrees/I-00067/ai-dev/logs/I-00067_S03_run2.log:189 — same pattern across S03 and S04 logs
    Recommendation: Suppress `LiveDbConnectionRefusedError` at ERROR level in test context — it is an expected guard in test runs and does not block test execution. Consider downgrading to DEBUG or WARNING, or skipping the alembic guard check entirely in `IW_CORE_TEST_CONTEXT`.
    Target: dashboard/app.py or orch/db/live_db_guard.py
    Pros: Cleaner test output; easier to spot real errors.
    Cons: Small change to startup logging.
    If we don't: Test output continues to show scary-looking ERROR lines that don't indicate actual failures.
    Effort: S (~2 lines)