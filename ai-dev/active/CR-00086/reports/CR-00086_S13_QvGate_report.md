# CR-00086 S13 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make allure-integration` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 311       |

## Output (tail)

```
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
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/dashboard/routers/oss.py", line 413, in _run_oss_job
      from orch.db.session import SessionLocal
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/session.py", line 98, in __getattr__
      return _get_session_local()
             ^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/session.py", line 62, in _get_session_local
      bind=_get_engine(),
           ^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/session.py", line 47, in _get_engine
      _engine = safe_create_engine(
                ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/live_db_guard.py", line 163, in safe_create_engine
      assert_engine_url_allowed(url)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/live_db_guard.py", line 134, in assert_engine_url_allowed
      raise LiveDbConnectionRefusedError(
  orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)

  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

tests/integration/test_oss_dashboard_routes.py::TestOssScan::test_scan_returns_job_id_and_stream_url
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/.venv/lib/python3.12/site-packages/_pytest/threadexception.py:58: PytestUnhandledThreadExceptionWarning: Exception in thread oss-scan-O-00001

  Traceback (most recent call last):
    File "/usr/lib/python3.12/threading.py", line 1073, in _bootstrap_inner
      self.run()
    File "/usr/lib/python3.12/threading.py", line 1010, in run
      self._target(*self._args, **self._kwargs)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/dashboard/routers/oss.py", line 369, in <lambda>
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
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/dashboard/routers/oss.py", line 413, in _run_oss_job
      from orch.db.session import SessionLocal
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/session.py", line 98, in __getattr__
      return _get_session_local()
             ^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/session.py", line 62, in _get_session_local
      bind=_get_engine(),
           ^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/session.py", line 47, in _get_engine
      _engine = safe_create_engine(
                ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/live_db_guard.py", line 163, in safe_create_engine
      assert_engine_url_allowed(url)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/db/live_db_guard.py", line 134, in assert_engine_url_allowed
      raise LiveDbConnectionRefusedError(
  orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)

  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnhandledThreadExceptionWarning(msg))

tests/integration/db/test_F00077_migration.py::TestF00077Migration::test_unique_in_flight_constraint_blocks_concurrent_jobs
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/db/test_F00077_migration.py:264: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryQuestionTooLong::test_prompt_truncation_preserves_question_not_docs
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryNoFileOverlap::test_no_git_log_items_when_no_file_overlap
  <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).

tests/integration/test_boundary_behavior_f00060.py: 7 warnings
tests/integration/test_doc_index_poller.py: 2 warnings
tests/integration/test_doc_indexer.py: 9 warnings
tests/integration/test_doc_index_job_runner.py: 5 warnings
tests/integration/test_invariants_f00060.py: 1 warning
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/doc_indexer.py:141: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    return self._table_name() in db.table_names()

tests/integration/test_boundary_behavior_f00060.py: 16 warnings
tests/integration/test_doc_index_poller.py: 4 warnings
tests/integration/test_doc_indexer.py: 25 warnings
tests/integration/test_doc_index_job_runner.py: 8 warnings
tests/integration/test_invariants_f00060.py: 2 warnings
tests/integration/test_code_index_pipeline.py: 8 warnings
  /usr/lib/python3.12/asyncio/events.py:88: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    self._context.run(self._callback, *self._args)

tests/integration/test_boundary_behavior_f00060.py: 6 warnings
tests/integration/test_doc_index_poller.py: 2 warnings
tests/integration/test_doc_indexer.py: 8 warnings
tests/integration/test_invariants_f00060.py: 1 warning
tests/integration/test_doc_index_job_runner.py: 3 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/doc_indexer.py:208: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_batch_overlap_ignore.py::TestBatchOverlapIgnoreModel::test_composite_pk_uniqueness
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_batch_overlap_ignore.py:162: SAWarning: New instance <BatchOverlapIgnore at 0x70699fdfcd70> with identity key (<class 'orch.db.models.BatchOverlapIgnore'>, ('test-proj', 'BATCH-002', 'CR-00072', 'CR-00057', 'orch/daemon/batch_manager.py'), None) conflicts with persistent instance <BatchOverlapIgnore at 0x70699cc89430>
    db_session.flush()

tests/integration/test_boundary_behavior_f00060.py::TestBoundarySemanticIndexMissing::test_missing_lancedb_table_treated_as_empty
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryZeroWorkItems::test_empty_project_returns_empty_bundle_no_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/qa.py:436: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb.table_names():

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryEmbedModelChange::test_embed_model_change_drops_and_reindexes
tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/doc_indexer.py:173: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if self._table_name() in db.table_names():

tests/integration/rag/test_qa_with_conversation.py::TestQAWithConversation::test_condense_invoked_on_second_turn
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/rag/test_qa_with_conversation.py:123: RuntimeWarning: coroutine 'TestQAWithConversation.test_condense_invoked_on_second_turn.<locals>.mock_astream_chat' was never awaited
    mock_ollama_instance.astream_chat = AsyncMock(mock_astream_chat())
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in lancedb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_doc_indexer.py:144: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7f21d16d37a0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7f21d16d02f0>
    db_session.flush()

tests/dashboard/test_cr00068_model_bar_removed.py::TestModelBarJsRemoved::test_model_bar_functions_absent_from_js
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/.venv/lib/python3.12/site-packages/_pytest/fixtures.py:767: RuntimeWarning: coroutine 'sleep' was never awaited
    def _check_scope(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/integration/dashboard/test_session_cookie_middleware.py::TestSessionCookieMiddleware::test_second_request_uses_existing_cookie
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/.venv/lib/python3.12/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

tests/integration/test_scope_amend_endpoints.py::TestScopeAmendAndRestartEndpoint::test_i00101_amend_is_idempotent_at_the_endpoint_level
tests/integration/test_scope_amend_endpoints.py::TestScopeAmendAndRestartEndpoint::test_i00101_amend_modal_get_returns_correct_html
tests/integration/test_scope_amend_endpoints.py::TestScopeAmendAndRestartEndpoint::test_i00101_revert_runs_git_checkout_and_emits_event_and_restarts
tests/integration/test_scope_amend_endpoints.py::TestScopeAmendAndRestartEndpoint::test_i00101_amend_writes_both_manifests_and_emits_event_and_restarts_step
tests/integration/test_scope_amend_endpoints.py::TestScopeAmendAndRestartEndpoint::test_i00101_amend_endpoint_returns_422_on_non_scope_blocked_step
tests/integration/test_scope_amend_endpoints.py::TestScopeAmendAndRestartEndpoint::test_i00101_amend_endpoint_rejects_paths_not_in_violation_set
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/.venv/lib/python3.12/site-packages/lancedb/__init__.py:294: UserWarning: lance is not fork-safe. If you are using multiprocessing, use spawn instead.
    warnings.warn(

tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    page = list(self._connection.table_names(page_token))

tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00086/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
= 3335 passed, 29 skipped, 5 xfailed, 2 xpassed, 232 warnings in 303.22s (0:05:03) =
[allure-integration] Run 'make allure-serve' to view report
```

## Verdict

```
pass
```
