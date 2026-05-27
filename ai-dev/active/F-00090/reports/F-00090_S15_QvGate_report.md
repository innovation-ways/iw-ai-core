# F-00090 S15 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make allure-integration` |
| Exit code    | 2             |
| Result       | FAIL         |
| Duration (s) | 323       |

## Output (tail)

```
  
  Traceback (most recent call last):
    File "/usr/lib/python3.12/threading.py", line 1073, in _bootstrap_inner
      self.run()
    File "/usr/lib/python3.12/threading.py", line 1010, in run
      self._target(*self._args, **self._kwargs)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/dashboard/routers/oss.py", line 369, in <lambda>
      target=lambda: asyncio.run(_run_oss_job(job.id)),
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
      return runner.run(main)
             ^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
      return self._loop.run_until_complete(task)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
      return future.result()
             ^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/dashboard/routers/oss.py", line 413, in _run_oss_job
      from orch.db.session import SessionLocal
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 98, in __getattr__
      return _get_session_local()
             ^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 62, in _get_session_local
      bind=_get_engine(),
           ^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 47, in _get_engine
      _engine = safe_create_engine(
                ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/live_db_guard.py", line 163, in safe_create_engine
      assert_engine_url_allowed(url)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/live_db_guard.py", line 134, in assert_engine_url_allowed
      raise LiveDbConnectionRefusedError(
  orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

tests/integration/test_oss_dashboard_routes.py::TestOssInstall::test_install_creates_job_with_install_kind
tests/integration/test_oss_dashboard_routes.py::TestOssInstall::test_install_returns_stream_url
tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_install_job_has_no_worktree_columns
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/_pytest/threadexception.py:58: PytestUnhandledThreadExceptionWarning: Exception in thread oss-install-O-00001
  
  Traceback (most recent call last):
    File "/usr/lib/python3.12/threading.py", line 1073, in _bootstrap_inner
      self.run()
    File "/usr/lib/python3.12/threading.py", line 1010, in run
      self._target(*self._args, **self._kwargs)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/dashboard/routers/oss.py", line 284, in <lambda>
      target=lambda: asyncio.run(_run_oss_job(job.id)),
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
      return runner.run(main)
             ^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
      return self._loop.run_until_complete(task)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
      return future.result()
             ^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/dashboard/routers/oss.py", line 413, in _run_oss_job
      from orch.db.session import SessionLocal
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 98, in __getattr__
      return _get_session_local()
             ^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 62, in _get_session_local
      bind=_get_engine(),
           ^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 47, in _get_engine
      _engine = safe_create_engine(
                ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/live_db_guard.py", line 163, in safe_create_engine
      assert_engine_url_allowed(url)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/live_db_guard.py", line 134, in assert_engine_url_allowed
      raise LiveDbConnectionRefusedError(
  orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

tests/integration/test_code_index_pipeline.py::test_full_index_cycle
tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    page = list(self._connection.table_names(page_token))

tests/integration/test_code_index_pipeline.py::test_full_index_cycle
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_replays_buffered_events_via_last_event_id
tests/integration/test_chat_endpoint_permission_flow.py::test_permission_deny_blocks_tool
tests/integration/test_chat_endpoint_session_lifecycle.py::test_concurrent_sessions_independent_streams
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/websockets/legacy/__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see https://websockets.readthedocs.io/en/stable/howto/upgrade.html for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_replays_buffered_events_via_last_event_id
tests/integration/test_chat_endpoint_permission_flow.py::test_permission_deny_blocks_tool
tests/integration/test_chat_endpoint_session_lifecycle.py::test_concurrent_sessions_independent_streams
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/uvicorn/protocols/websockets/websockets_impl.py:17: DeprecationWarning: websockets.server.WebSocketServerProtocol is deprecated
    from websockets.server import WebSocketServerProtocol

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x713d4b603aa0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x713d4b603c20>
    db_session.flush()

tests/integration/db/test_F00077_migration.py::TestF00077Migration::test_unique_in_flight_constraint_blocks_concurrent_jobs
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/tests/integration/db/test_F00077_migration.py:264: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/dashboard/test_session_cookie_middleware.py::TestSessionCookieMiddleware::test_second_request_uses_existing_cookie
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

tests/integration/test_boundary_behavior_f00060.py::TestBoundarySemanticIndexMissing::test_missing_lancedb_table_treated_as_empty
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryZeroWorkItems::test_empty_project_returns_empty_bundle_no_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/rag/qa.py:436: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb.table_names():

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryNoFileOverlap::test_no_git_log_items_when_no_file_overlap
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryQuestionTooLong::test_prompt_truncation_preserves_question_not_docs
  <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).

tests/integration/test_dashboard_remaining.py::test_system_status_returns_200
  <string>:0: RuntimeWarning: coroutine 'sleep' was never awaited
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_oss_dashboard_routes.py::TestOssFix::test_fix_apply_returns_job_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/.venv/lib/python3.12/site-packages/_pytest/threadexception.py:58: PytestUnhandledThreadExceptionWarning: Exception in thread oss-fix-O-00001
  
  Traceback (most recent call last):
    File "/usr/lib/python3.12/threading.py", line 1073, in _bootstrap_inner
      self.run()
    File "/usr/lib/python3.12/threading.py", line 1010, in run
      self._target(*self._args, **self._kwargs)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/dashboard/routers/oss.py", line 495, in <lambda>
      target=lambda: asyncio.run(_run_oss_job(job.id)),
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
      return runner.run(main)
             ^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
      return self._loop.run_until_complete(task)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
      return future.result()
             ^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/dashboard/routers/oss.py", line 413, in _run_oss_job
      from orch.db.session import SessionLocal
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 98, in __getattr__
      return _get_session_local()
             ^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 62, in _get_session_local
      bind=_get_engine(),
           ^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/session.py", line 47, in _get_engine
      _engine = safe_create_engine(
                ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/live_db_guard.py", line 163, in safe_create_engine
      assert_engine_url_allowed(url)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/live_db_guard.py", line 134, in assert_engine_url_allowed
      raise LiveDbConnectionRefusedError(
  orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_batch_overlap_ignore.py::TestBatchOverlapIgnoreModel::test_composite_pk_uniqueness
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00090/tests/integration/test_batch_overlap_ignore.py:162: SAWarning: New instance <BatchOverlapIgnore at 0x77354018d1c0> with identity key (<class 'orch.db.models.BatchOverlapIgnore'>, ('test-proj', 'BATCH-002', 'CR-00072', 'CR-00057', 'orch/daemon/batch_manager.py'), None) conflicts with persistent instance <BatchOverlapIgnore at 0x773540be0a40>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
= 2 failed, 3294 passed, 29 skipped, 4 xfailed, 3 xpassed, 190 warnings in 316.59s (0:05:16) =
make: *** [Makefile:469: allure-integration] Error 1
```

## Verdict

```
fail
```
