### Item Analysis: CR-00087

**Bottom line**: The item shipped cleanly with all QV gates green, but the integration tests in S04 caught a real bug in S03's implementation (wrong SQLAlchemy API for a composite-PK model) that unit tests alone would not have caught — strengthening the case for running integration tests earlier or alongside unit tests in the S04 step.

**Steps analyzed: 13 (S01–S13)   Steps with retries: 4 (S04, S05, S09, S10, S11, S12)   Total fix-cycles: 1 (S05)   DB signal: yes**

---

[1] Integration tests caught a composite-PK bug that unit tests missed
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/active/CR-00087/reports/CR-00087_S04_TestsImpl_report.md:14–17 — "db.get(WorkItem, step.work_item_id) called with single key against composite-PK model → InvalidRequestError"
      - ai-dev/logs/CR-00087_S04_run1.log:0 (empty — run 1 failed before logging began)
      - ai-dev/active/CR-00087/reports/CR-00087_S04_TestsImpl_report.md — RED evidence shows `FixStatus.in_progress` instead of `FixStatus.escalated`; root cause was fixture + composite-PK bug combined
    Recommendation: The integration tests in S04 (which correctly found the composite-PK bug) should be mirrored in the unit test layer for `fix_cycle.py` as a targeted regression test: a test that creates a WorkItem with a composite PK, calls `_try_auto_amend_after_escalation`, and verifies no `InvalidRequestError` is raised. Alternatively, add a `db.get_or_404`-style helper in the test fixture that raises if given a composite-PK model with a single key.
    Target: tests/unit/test_fix_cycle.py
    Pros: Regression prevention; composite-PK misuse is a recurring pattern in SQLAlchemy 2.x projects.
    Cons: Small maintenance burden; the integration test already covers it.
    If we don't: Future S03-equivalent steps could repeat the same composite-PK mistake and only catch it at the slower S04 integration layer.
    Effort: S (~15 lines, 1 test method)

[2] TDD stub tests went stale after S03 wired the real implementation
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00087_S05_fix1.log — "stale TDD stub tests in tests/unit/test_fix_cycle.py (lines 674–728) replaced _try_auto_amend_after_escalation with a stub that raised NotImplementedError"
      - ai-dev/active/CR-00087/reports/CR-00087_S05_CodeReview_report.md — MEDIUM_FIXABLE finding; fix cycle required
    Recommendation: Add a convention that TDD stub tests (RED-phase placeholder tests) must include a comment tag like `# STUB: upgrade when S{N+1} wires real implementation` and add an linter rule (in `scripts/check_templates.py` or a new script) that flags any test method containing `NotImplementedError` that also has a sibling test that exercises the same function without patching. Alternatively, move stub tests to a separate file (`test_fix_cycle_STUBS.py`) that gets deleted after the real implementation lands.
    Target: skills/iw-workflow/SKILL.md (or equivalent workflow convention doc)
    Pros: Prevents fix cycles caused by stale stubs; easy to implement as a linter rule.
    Cons: Additional linter maintenance.
    If we don't: Every CR with TDD stubs that have a multi-step S03→S04 cadence will require a fix cycle to upgrade the stubs.
    Effort: S (~20 lines, 1 new lint script)

[3] QV gates S09–S11 each ran twice, all runs passed
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00087_S09_run1.log and ai-dev/logs/CR-00087_S09_run2.log — identical output, both exit 0
      - ai-dev/logs/CR-00087_S10_run1.log and ai-dev/logs/CR-00087_S10_run2.log — identical, both exit 0
      - ai-dev/logs/CR-00087_S11_run1.log and ai-dev/logs/CR-00087_S11_run2.log — identical, both exit 0
      - ai-dev/active/CR-00087/reports/CR-00087_S09_QvGate_report.md — duration 0s (run 1); 1174s (run 3 = S13)
      - ai-dev/active/CR-00087/reports/CR-00087_S13_QvGate_report.md — S13 integration tests took 1174s
    Recommendation: Investigate why the executor runs QV gate commands twice when they already pass on the first attempt. Possible causes: (a) the step-start command triggers an automatic retry mechanism that is redundant when the gate already passes, (b) a timing issue where the executor marks the step "in progress" before the gate finishes and immediately tries again, or (c) the log file is being written by both the failed attempt and the successful attempt. Check the executor code in `executor/` and the step command handler in `orch/cli/step_commands.py`.
    Target: orch/cli/step_commands.py, executor/ (upstream)
    Pros: Saves ~1–3 minutes of redundant execution per item; avoids confusing "2 runs, same result" pattern.
    Cons: Requires tracing the executor's retry logic.
    If we don't: Every item continues spending ~1–3 extra minutes on redundant QV gate re-runs.
    Effort: M (~tracing + fix, 2–5 files)

[4] S04 caught a git fixture bug (no HEAD) in the worktree helper
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/active/CR-00087/reports/CR-00087_S04_TestsImpl_report.md — "_write_worktree_with_git staged but never committed pre-cycle files → worktree had no HEAD → _captured_paths returned ∅ → violations never detected"
      - ai-dev/logs/CR-00087_S04_run2.log — corrected fixture with proper HEAD setup; 10 tests pass
    Recommendation: Add a `git rev-parse HEAD` smoke test to the `_write_worktree_with_git` fixture (and its siblings in other integration test files) that asserts the worktree has a valid HEAD before the test body runs. Also add a ruff/flake8 rule or a `conftest.py` assertion that catches `git ls-files --others` returning unexpected paths when the worktree should be clean.
    Target: tests/conftest.py (new fixture assertion helper), tests/integration/test_scope_amend_endpoints.py
    Pros: Prevents silent test failures that pass assertions for the wrong reason; self-documenting.
    Cons: Adds ~3 lines per fixture.
    If we don't: Future integration tests that forget to commit the manifest or seed files will silently pass, testing nothing.
    Effort: S (~10 lines, 2 files)
