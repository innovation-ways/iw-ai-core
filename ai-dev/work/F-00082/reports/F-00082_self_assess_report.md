### Item Analysis: F-00082

Bottom line: Fix-cycle thrash on two QvGates (S07 lint and S13 frontend-tests) consumed ~45 minutes of wall time, largely because the lint gate is fragile (pre-existing findings from main) and the S13 failures were environment-dependent; tightening the test fixture seeding logic would reduce S13 fix-cycle iterations.

Steps analyzed: 16   Steps with retries: 7 (S07, S08, S09, S10, S11×2, S13)   Total fix-cycles: 4 (S07×2, S11×2, S13×1)   DB signal: yes

[1] S07 lint fix-cycle on pre-existing code style issues wastes agent time
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00082_S07_run2.log:9 — "E501 Line too long (125 > 100) --> orch/test_runner.py:113:101"
      - ai-dev/logs/F-00082_S07_fix1.log (passes locally but run2 still fails) — "Found 8 errors"
    Recommendation: Audit `make lint` / `ruff` line-length ignore directives for `orch/test_runner.py` and add `# ruff: noqa: E501` for the intentionally-long `# nosemgrep` comment lines. Alternatively, tighten the line-length max in `ruff.toml` to force new code to be short but allow pre-existing violations to pass CI. This prevents a false-positive lint failure for code the agent did not author in S07.
    Target: Makefile, ruff.toml or .ruff.toml
    Pros: Eliminates a spurious lint failure that forces a fix cycle; reduces agent time waste on gate re-runs.
    Cons: May mask genuinely long lines that should be shortened.
    If we don't: Every worktree touching `orch/test_runner.py` (a commonly edited daemon file) risks a spurious S07 fix cycle.
    Effort: S (~2 lines)

[2] S13 frontend-test fix-cycle — test helper seeding logic doesn't match real-world batch/item state combinations
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - ai-dev/logs/F-00082_S13_run1.log — "test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.executing] FAILED"
      - ai-dev/logs/F-00082_S13_fix1.log — tests pass in isolation but fail under `make test-frontend` due to shared fixture pollution or test-order dependency
      - ai-dev/logs/F-00082_S13_run3.log — "808 passed, 14 skipped, 2 xfailed" on third run with no code changes
    Recommendation: Add a pytest `--forked` or explicit `db_session.rollback()` between test classes in the cancel-button visibility tests to prevent fixture pollution. Also add a random seed to `make test-frontend` to detect order-dependent failures earlier.
    Target: tests/dashboard/conftest.py or Makefile (add `--forked` to pytest invocation)
    Pros: Reduces S13 fix cycles to zero for environment-dependent test failures.
    Cons: Adds overhead to test collection; may slow down the test suite marginally.
    If we don't: S13 remains a flaky gate that sometimes requires a fix cycle even when the implementation is correct.
    Effort: M (~5 lines, 1-2 files)

[3] S11 security-sast gate: pre-existing semgrep findings on main block all worktrees
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/F-00082_S11_fix1.log — "Findings: 95 (95 blocking)" vs main shows "94 (94 blocking)"
      - ai-dev/logs/F-00082_S11_fix2.log — "Findings: 91 (91 blocking)" after excluding rules via Makefile edit
      - Fix required editing Makefile to add 7 `--exclude-rule` flags for generic HTML template findings
    Recommendation: Instead of excluding rules in every worktree's Makefile, add a project-level `.semgrepignore` or `pyproject.toml` semgrep section that applies the exclusions globally. This prevents each worktree from independently needing to fix or suppress the same 91 pre-existing findings.
    Target: Makefile, .semgrepignore, or pyproject.toml [tool.semgrep]
    Pros: S11 becomes a true delta-gate (only new findings block); avoids per-worktree Makefile drift.
    Cons: Pre-existing findings remain unfixed in the baseline.
    If we don't: Every worktree that touches dashboard templates, Flask `| safe` filters, or daemon subprocess calls will need a local Makefile edit to pass S11 — a recurring tax on every developer.
    Effort: M (~10 lines, 1 file)