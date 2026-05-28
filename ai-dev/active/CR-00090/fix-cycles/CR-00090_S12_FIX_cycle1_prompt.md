# CR-00090 S12 QV Fix Cycle 1/7

Quality gate S12 for work item CR-00090 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/config.py
  dashboard/app.py
  dashboard/templates/base.html
  dashboard/templates/fragments/staleness_dot.html
  dashboard/templates/pages/project_selector.html
  ai-dev/iw-config/worktree-compose.template.yml
  tests/unit/test_config.py
  tests/dashboard/test_e2e_mode.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/CR-00090/**
  ai-dev/archive/CR-00090/**
  ai-dev/work/CR-00090/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00090/ai-dev/active/CR-00090/CR-00090_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
ev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00090/tests/integration/test_batch_overlap_ignore.py:162: SAWarning: New instance <BatchOverlapIgnore at 0x7b8c66cc5dc0> with identity key (<class 'orch.db.models.BatchOverlapIgnore'>, ('test-proj', 'BATCH-002', 'CR-00072', 'CR-00057', 'orch/daemon/batch_manager.py'), None) conflicts with persistent instance <BatchOverlapIgnore at 0x7b8c66cc5d60>
    db_session.flush()

tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00090/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00090/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotUpToDate::test_renders_grey_dot_when_up_to_date
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotUpToDate::test_grey_dot_has_hx_get
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotUpToDate::test_grey_dot_has_hx_trigger
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotUpToDate::test_grey_dot_has_hx_swap_outer_html
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotStale::test_renders_red_dot_when_stale
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotStale::test_red_dot_has_title_attribute
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotStale::test_red_dot_has_iw_staleness_dot_base_class
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotStale::test_red_dot_has_hx_get
FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotNotRunning::test_not_running_renders_grey_not_red
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
= 11 failed, 3292 passed, 29 skipped, 4 xfailed, 3 xpassed, 190 warnings in 302.51s (0:05:02) =
make: *** [Makefile:469: allure-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.
5. **Post-edit cross-gate check (MANDATORY before exit).** When the
   failing gate is NOT lint/format, your edits may still introduce a
   new ruff violation that the next review run trips on. Before exiting,
   run `make format-check` and `make lint` and resolve any NEW violation
   your edits introduced (`uv run ruff format <file>` for format issues;
   targeted edit for lint). Diagnosed 2026-05-25 from CR-00082 S04's
   ping-pong between fix cycles where each agent re-broke the gate the
   previous one fixed.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
