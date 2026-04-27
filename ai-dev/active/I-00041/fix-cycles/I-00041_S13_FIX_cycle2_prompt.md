# I-00041 S13 QV Fix Cycle 2/5

Quality gate S13 for work item I-00041 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Timeout after 600s (limit: 600s)

**Command output**:
```
...(truncated)...
rent transaction is aborted, commands ignored until end of transaction block
E           [SQL: SELECT batch_items.id AS batch_items_id, batch_items.project_id AS batch_items_project_id, batch_items.batch_id AS batch_items_batch_id, batch_items.work_item_id AS batch_items_work_item_id, batch_items.execution_group AS batch_items_execution_group, batch_items.status AS batch_items_status, batch_items.pid AS batch_items_pid, batch_items.started_at AS batch_items_started_at, batch_items.merged_at AS batch_items_merged_at, batch_items.notes AS batch_items_notes, batch_items.stall_count AS batch_items_stall_count, batch_items.last_progress AS batch_items_last_progress, batch_items.worktree_info AS batch_items_worktree_info, batch_items.merge_info AS batch_items_merge_info, batch_items.worktree_db_port AS batch_items_worktree_db_port, batch_items.worktree_app_port AS batch_items_worktree_app_port, batch_items.worktree_compose_path AS batch_items_worktree_compose_path 
E           FROM batch_items 
E           WHERE batch_items.project_id = %(project_id_1)s::VARCHAR AND batch_items.status = %(status_1)s 
E            LIMIT %(param_1)s::INTEGER]
E           [parameters: {'project_id_1': 'test-proj', 'status_1': 'merging', 'param_1': 1}]
E           (Background on this error at: https://sqlalche.me/e/20/2j85)

.venv/lib/python3.12/site-packages/psycopg/cursor.py:117: InternalError
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00041/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_batch_manager.py::TestMergeQueueIntegration::test_merge_queue_oldest_first
FAILED tests/integration/test_batch_manager.py::TestMergeQueueIntegration::test_merge_queue_one_at_a_time
========================= 2 failed, 1 warning in 3.95s =========================
[0m
[0m→ [0mRead tests/integration/test_batch_manager.py[90m [offset=375, limit=50][0m
[0m✱ [0mGrep "def manager"[90m 3 matches[0m
[0m→ [0mRead tests/integration/test_batch_manager.py[90m [offset=1, limit=50][0m
[0m→ [0mRead tests/integration/test_batch_manager.py[90m [offset=78, limit=30][0m
[0m→ [0mRead orch/daemon/merge_queue.py[90m [offset=51, limit=30][0m
[0m✱ [0mGrep "def _cleanup_worktree"[90m 1 match[0m
[0m→ [0mRead orch/daemon/merge_queue.py[90m [offset=270, limit=30][0m
[0m✱ [0mGrep "def run_post_merge_apply"[90m 1 match[0m
[0m→ [0mRead orch/daemon/migration_pipeline.py[90m [offset=118, limit=35][0m
[0m→ [0mRead orch/daemon/merge_queue.py[90m [offset=14, limit=30][0m
[0m→ [0mRead tests/conftest.py

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
