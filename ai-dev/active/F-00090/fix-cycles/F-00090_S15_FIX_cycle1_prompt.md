# F-00090 S15 QV Fix Cycle 1/7

Quality gate S15 for work item F-00090 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/db/models.py
  orch/db/migrations/versions/**
  orch/regression_link_service.py
  orch/cli/**
  dashboard/routers/items.py
  dashboard/routers/batches.py
  dashboard/routers/project_dashboard.py
  dashboard/templates/fragments/**
  dashboard/templates/pages/**
  dashboard/static/styles.css
  scripts/backfill_regression_classification.py
  tests/integration/test_regression_link_service.py
  tests/integration/test_backfill_regression_classification.py
  tests/dashboard/test_regression_classification_form.py
  tests/dashboard/test_quality_kpis_section.py
  docs/IW_AI_Core_Testing_Strategy.md
  docs/IW_AI_Core_Database_Schema.md
  docs/IW_AI_Core_Dashboard_Design.md
  skills/iw-ai-core-testing/**
  .claude/skills/iw-ai-core-testing/**
  ai-dev/work/TESTS_ENHANCEMENT.md
  docs/IW_AI_Core_CLI_Spec.md
  tests/integration/test_cli_spec_conformance.py
  dashboard/templates/_partials/help/quality-kpis.html

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/F-00090/**
  ai-dev/archive/F-00090/**
  ai-dev/work/F-00090/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/ai-dev/active/F-00090/F-00090_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
or
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    page = list(self._connection.table_names(page_token))

tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/integration/dashboard/test_session_cookie_middleware.py::TestSessionCookieMiddleware::test_second_request_uses_existing_cookie
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

tests/integration/db/test_F00077_migration.py::TestF00077Migration::test_unique_in_flight_constraint_blocks_concurrent_jobs
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/tests/integration/db/test_F00077_migration.py:264: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_n1_bounded_queries.py::TestBatchDetailBoundedQueries::test_batch_item_rows_query_count_bounded
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
= 3 failed, 3293 passed, 29 skipped, 5 xfailed, 2 xpassed, 190 warnings in 332.95s (0:05:32) =
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
