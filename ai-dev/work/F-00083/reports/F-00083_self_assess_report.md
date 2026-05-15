### Item Analysis: F-00083

Bottom line: The worktree-compose configuration does not include the `opencode` binary, causing the browser-verification step (S18) to fail with a 503 and skip all 11 AC checks — the most impactful gap to fix before the next similar feature.

Steps analyzed: 19   Steps with retries: 4 (S10, S11, S14, S15)   Total fix-cycles: 14   DB signal: yes

---

[1] Worktree-compose missing OpenCode binary — S18 browser verification fully skipped
    Severity: HIGH   Class: environment   Frequency: one-off
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S18_run1.log:39 — "SPEC_MISMATCH: OpenCode runtime unavailable in E2E stack — HTTP 503 at /api/chat/config. Worktree-compose configuration is missing the OpenCode binary."
    Recommendation: Add the `opencode` binary to the worktree-compose bootstrap so the browser verification step can actually run. Until then, every AI-assistant feature that depends on S18 will have zero UX signal from the regression guard.
    Target: orch/daemon/worktree_compose.py or the docker-compose.bootstrap.yml that provisions worktree E2E stacks
    Pros: Unblocks the full acceptance criteria chain for any future OpenCode-backed feature.
    Cons: Requires the daemon's worktree-compose configuration to be updated and tested.
    If we don't: S18 remains a stub that always returns SPEC_MISMATCH, providing no signal on Ctrl+/ collisions, DOM id collisions, chip dismissal, or tab-refresh reconnect behavior.
    Effort: M (~the worktree-compose plumbing)

---

[2] S14 (QV: Unit tests) required 4 fix-cycles — mock side-effect exhaustion in pre-existing cancel-service tests
    Severity: MED   Class: environment   Frequency: recurring
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S14_fix1.log:91 — "The test shows `WorkItemStatus.failed` should be cancellable. Let me fix the frozenset"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S14_fix2.log:118 — "The tests are failing because `_teardown_item_worktree` makes an additional `db.execute` call that the mock doesn't account for"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S14_fix3.log:389 — "The bug is at line 503: when `item is None`, the condition `item is not None and ...` is `False`"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S14_fix4.log:247 — "The issue was missing mock responses for the `steps_to_skip` query"
    Recommendation: Pre-populate mock `db.execute` side-effect lists with a comment noting which line in the production code each mock entry corresponds to. Alternatively, add a shared `_make_db_with_skeleton` helper that always provides at least 2 extra slots beyond what the happy path requires, preventing StopIteration on minor code changes.
    Target: tests/unit/test_cancel_service.py
    Pros: Reduces fix-cycle count on future cancel-service changes; makes test failures easier to diagnose.
    Cons: Test infrastructure churn; might mask real StopIteration bugs.
    If we don't: Any contributor who adds one more db.execute call to cancel_batch or cancel_work_item will trigger another multi-fix-cycle episode.
    Effort: S (~3–5 lines per test helper)

---

[3] S15 (QV: Integration tests) required 3 fix-cycles — semgrep exclusions drift between Makefile and test baseline
    Severity: MED   Class: convention   Frequency: recurring
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S15_fix3.log:36 — "Ran 308 rules on 473 files: 6 findings"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S15_fix3.log:89 — "Both the Makefile and the test need the same 2 additional exclusions. I'll update both"
    Recommendation: Extract semgrep exclusions to a shared config file (e.g., `.semgrep_exclusions.txt`) that both the Makefile and the test read. Enforce parity in the assertion-scanner style.
    Target: Makefile + tests/integration/test_security_sast_baseline.py
    Pros: Single source of truth; cheaper to maintain; prevents desync.
    Cons: Requires changing two files and adding a shared config.
    If we don't: Every time a new semgrep rule fires in CI, the agent must manually discover that both files need updating, burning 2+ fix-cycles.
    Effort: S (~20 lines across 2 files)

---

[4] S10 (QV: Lint) required 2 fix-cycles — password noqa comments and line-length in a pre-existing test file
    Severity: LOW   Class: environment   Frequency: recurring
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S10_fix1.log:100 — "All 6 lint errors fixed: Added `# noqa: S105` to password string literals"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S10_fix2.log:34 — "Lint passes. The fix was wrapping the assertion message across two lines to meet the 100-char limit"
    Recommendation: Add a project-level noqa comment for S105/S106 at the top of `tests/dashboard/test_app_lifespan_opencode.py` (or the conftest that imports it) so new password-containing test fixtures don't require per-instance noqa comments.
    Target: tests/dashboard/test_app_lifespan_opencode.py
    Pros: Reduces per-feature lint fix-cycle noise.
    Cons: Minor; S105/S106 suppression in test files is already well-known.
    If we don't: Each new feature that adds password-mocking tests will spend 1 fix-cycle cleaning up these violations.
    Effort: S (~1 line)

---

[5] S02 pre-step spike: permission.asked payload not wire-captured; used documented shape instead
    Severity: MED   Class: design   Frequency: systemic
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S02_run1.log:26 — "Pre-step spike succeeded against opencode 1.14.50. Captured verbatim SSE payloads in the step report — critical wire-format finding: opencode emits data-only SSE frames (no event:/id: lines), type+id live inside the JSON payload. permission.asked payload could NOT be wire-captured (MiniMax model returned synthetic text instead of triggering a real bash tool-call); flagged as MEDIUM-confidence gap for S08 review."
      - ai-dev/active/F-00083/prompts/F-00083_S02_Backend_prompt.md:52 — "If the spike is impossible (no opencode binary in the worktree), document this in the report and proceed using the documented shape from R-00071 §4 — flag this as a MEDIUM-confidence gap for S08 review."
    Recommendation: Make the S02 prompt pre-flight spike a **blocking precondition** rather than optional: if `opencode serve` is not available in the worktree, the step must fail with a clear SPEC_MISMATCH rather than proceeding on documented-but-unverified payload shapes. This prevents an unverified contract from propagating through the relay and filters.
    Target: ai-dev/active/F-00083/prompts/F-00083_S02_Backend_prompt.md (or the design-doc generator template for backend-impl prompts)
    Pros: Forces verification before commitment; surfaces worktree environment gaps earlier.
    Cons: May cause more step failures on worktrees without opencode binary.
    If we don't: permission.asked relay behavior remains partially unverified in production.
    Effort: S (~5 words in the spike instruction)

---

[6] Regression guard: zero accidental edits to dashboard/templates/chat/** — CLEAN
    Severity: LOW   Class: convention   Frequency: recurring
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S04_run1.log:10 — "make lint passed; regression-guard confirmed zero diff under `dashboard/templates/chat/` and `dashboard/static/chat/`"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S06_run1.log:4 — "Regression-guard: PASS (no changes to `dashboard/templates/chat/` or `dashboard/static/chat/`)"
      - .worktrees/F-00083/ai-dev/logs/F-00083_S07_run1.log:5 — "Regression guard: No changes to `dashboard/templates/chat/` or `dashboard/static/chat/` — PASS"
    Recommendation: No change needed. The regression guard worked as designed.
    Target: N/A
    Pros: Strong signal that the prompt emphasis on invariant 1 was effective.
    Cons: None.
    If we don't: N/A.
    Effort: N/A

---

[7] S18 was skipped — cross-item pattern with CR-00053 not observable
    Severity: LOW   Class: design   Frequency: one-off
    Evidence:
      - .worktrees/F-00083/ai-dev/logs/F-00083_S18_run1.log:39 — "SPEC_MISMATCH: OpenCode runtime unavailable in E2E stack"
    Recommendation: Document the worktree-compose OpenCode dependency requirement in the pre-flight checklist for browser-verification steps (S18-type) so it surfaces as a pre-condition at step start rather than mid-run.
    Target: docs/IW_AI_Core_Daemon_Design.md or the workflow-manifest schema for browser_verification step types
    Pros: Faster failure with clearer root cause.
    Cons: None for this feature.
    If we don't: S18 will continue to skip silently on future features, and the CR-00053 retry/idempotency cross-item pattern will remain unverified.
    Effort: S (~10 lines)