# I-00121 S11 QV Fix Cycle 2/7

Quality gate S11 for work item I-00121 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/test_runner.py
  tests/unit/test_test_runner_allure_env.py
  tests/integration/test_test_runner_report_persistence.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/I-00121/**
  ai-dev/archive/I-00121/**
  ai-dev/work/I-00121/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00121/ai-dev/active/I-00121/I-00121_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
pped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 50.0% reached. Total coverage: 65.16%
=========================== short test summary info ============================
FAILED tests/integration/test_live_db_guard_reproduction.py::test_subprocess_under_test_context_can_connect_to_testcontainer
ERROR tests/integration/data_layer/test_test_health_snapshots.py::test_health_snapshots_table_upgrades_cleanly
ERROR tests/integration/data_layer/test_test_health_snapshots.py::test_health_snapshots_model_round_trip
ERROR tests/integration/data_layer/test_test_health_snapshots.py::test_health_snapshots_downgrade_then_upgrade
ERROR tests/integration/data_layer/test_test_health_snapshots.py::test_health_snapshots_index_exists
ERROR tests/integration/test_agent_migrate_guard.py::test_agent_cannot_apply_migration
ERROR tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
ERROR tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
ERROR tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_assert_no_self_blockers_clean_when_no_blocker
ERROR tests/integration/test_iw_core_instance_migration.py::test_check_constraint_prevents_second_row
ERROR tests/integration/test_iw_core_instance_migration.py::test_table_created_and_seeded
ERROR tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip
ERROR tests/integration/test_doc_index_jobs_migration.py::test_indexes_exist
ERROR tests/integration/test_doc_index_jobs_migration.py::test_downgrade_and_upgrade_round_trip
ERROR tests/integration/test_doc_index_jobs_migration.py::test_table_exists
ERROR tests/integration/test_doc_index_jobs_migration.py::test_insert_with_required_columns
ERROR tests/integration/test_doc_index_jobs_migration.py::test_columns_and_types
ERROR tests/integration/test_cross_project_isolation.py::test_axis4_sessions_see_only_their_own_rows
ERROR tests/integration/test_cross_project_isolation.py::test_axis4_get_db_url_resolves_worktree_get_orch_db_url_resolves_orch
ERROR tests/integration/test_cross_project_isolation.py::test_axis4_orch_url_prefers_db_when_orch_env_unset
ERROR tests/integration/test_e2e_ollama_stub.py::TestStubChatShape::test_show_endpoint_satisfies_llama_index_context_probe
ERROR tests/integration/test_e2e_ollama_stub.py::TestStubChatShape::test_chat_stream_emits_tokens_via_llama_index
ERROR tests/integration/test_e2e_ollama_stub.py::TestStubEmbeddingShape::test_batch_input_returns_one_vector_per_text
= 1 failed, 3340 passed, 28 skipped, 2 deselected, 4 xfailed, 3 xpassed, 159 warnings, 22 errors in 1252.66s (0:20:52) =
make: *** [Makefile:129: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
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

## Post-Edit Gate (MANDATORY before exit)

After your final edit, run these two commands and fix any NEW violation
your edits introduced:

```bash
make format-check
make lint
```

If either command reports a violation in a file you touched this cycle,
resolve it before exiting — `uv run ruff format <file>` for format-check
failures, targeted edit for lint failures. Re-run both commands to confirm
green. The next review run WILL fail on these gates and burn another fix
cycle, so closing them now is strictly cheaper.

(Diagnosed 2026-05-25: in CR-00082 S04, cycle N reformatted
`playwright_wrapper.py` while cycle N+1 introduced a new line-length
violation in the same file; the loop never converged because no fix
agent self-checked these gates. This gate exists to break that loop.)



**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
