# CR-00083 S11 QV Fix Cycle 1/7

Quality gate S11 for work item CR-00083 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  tests/perf/**
  tests/perf/baselines/**
  Makefile
  pyproject.toml
  uv.lock
  .github/workflows/perf-budgets.yml
  docs/IW_AI_Core_Testing_Strategy.md
  skills/iw-ai-core-testing/**
  .claude/skills/iw-ai-core-testing/**
  ai-dev/work/TESTS_ENHANCEMENT.md
  orch/daemon/fix_cycle.py
  tests/assertion_free_baseline.txt
  tests/unit/test_llm_judge_script.py
  scripts/llm_judge_test_review.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/CR-00083/**
  ai-dev/archive/CR-00083/**
  ai-dev/work/CR-00083/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/ai-dev/active/CR-00083/CR-00083_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
bles() instead
    if table_name in ldb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/tests/integration/test_doc_indexer.py:144: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/db/test_F00077_migration.py::TestF00077Migration::test_unique_in_flight_constraint_blocks_concurrent_jobs
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/tests/integration/db/test_F00077_migration.py:264: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00083/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/dashboard/test_doc_job_log_endpoints.py::TestDocJobLogStream::test_returns_sse_content_type
FAILED tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /system/nav/worktree-badge]
FAILED tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_heartbeat
FAILED tests/integration/test_doc_job_log_endpoints.py::TestLogStream::test_log_stream_emits_lines_then_terminal
FAILED tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_banner_appears_when_db_behind_head
FAILED tests/dashboard/test_alembic_guard_banner.py::TestAlembicGuardBanner::test_no_banner_at_head
= 6 failed, 3234 passed, 29 skipped, 5 xfailed, 2 xpassed, 194 warnings in 301.72s (0:05:01) =
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
make test-unit
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
