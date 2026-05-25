# CR-00081 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make allure-integration` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 321       |

## Output (tail)

```
tests/integration/test_archive.py::test_archive_stores_step_reports 
[gw17] [ 99%] PASSED tests/integration/test_archive.py::test_archive_stores_step_reports 
tests/dashboard/routers/test_conversations.py::TestCrossSession::test_cross_session_returns_404 
tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_rejects_make_oss_mode 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestCrossSession::test_cross_session_returns_404 
tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_404_if_not_found 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_404_if_not_found 
tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_returns_ordered_messages 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_returns_ordered_messages 
tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_ordered_by_last_active_at_desc 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_ordered_by_last_active_at_desc 
tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_returns_conversations 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_returns_conversations 
tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_excludes_archived 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_excludes_archived 
tests/dashboard/routers/test_conversations.py::TestCrossProject::test_cross_project_returns_404 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestCrossProject::test_cross_project_returns_404 
tests/dashboard/routers/test_conversations.py::TestArchive::test_archive_idempotent 
[gw2] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestArchive::test_archive_idempotent 
[gw17] [ 99%] PASSED tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_rejects_make_oss_mode 
tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row 
[gw1] [ 99%] PASSED tests/integration/test_security_sast_baseline.py::test_semgrep_baseline_is_zero_blocking_findings 
tests/dashboard/test_item_overview_action_buttons.py::TestStepRowFragmentRenders::test_step_row_renders_kill_button 
[gw1] [ 99%] PASSED tests/dashboard/test_item_overview_action_buttons.py::TestStepRowFragmentRenders::test_step_row_renders_kill_button 
tests/dashboard/test_item_overview_action_buttons.py::TestRunningPageRenders::test_running_table_fragment_renders_with_in_progress_row 
[gw1] [ 99%] PASSED tests/dashboard/test_item_overview_action_buttons.py::TestRunningPageRenders::test_running_table_fragment_renders_with_in_progress_row 
tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_failed_merge_renders_restart_merge_button 
[gw1] [ 99%] PASSED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_failed_merge_renders_restart_merge_button 
tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_completed_step_renders_no_action_buttons 
[gw17] [ 99%] PASSED tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row 
tests/integration/test_register_to_item_status_roundtrip.py::test_register_then_item_status_returns_manifest_superset 
[gw1] [ 99%] PASSED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_completed_step_renders_no_action_buttons 
tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_in_progress_step_renders_kill_button 
[gw1] [ 99%] PASSED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_in_progress_step_renders_kill_button 
tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_failed_step_renders_restart_and_skip 
[gw1] [ 99%] PASSED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_failed_step_renders_restart_and_skip 
[gw17] [ 99%] PASSED tests/integration/test_register_to_item_status_roundtrip.py::test_register_then_item_status_returns_manifest_superset 
tests/integration/test_register_to_item_status_roundtrip.py::test_round_trip_preserves_scope_block 
[gw17] [ 99%] PASSED tests/integration/test_register_to_item_status_roundtrip.py::test_round_trip_preserves_scope_block 
tests/integration/test_register_to_item_status_roundtrip.py::test_item_status_json_null_columns_serialize_as_null 
[gw17] [ 99%] PASSED tests/integration/test_register_to_item_status_roundtrip.py::test_item_status_json_null_columns_serialize_as_null 
tests/integration/test_register_to_item_status_roundtrip.py::test_register_invalid_timeout_fails_clearly 
[gw17] [ 99%] PASSED tests/integration/test_register_to_item_status_roundtrip.py::test_register_invalid_timeout_fails_clearly 
tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamps_manifest_with_note 
[gw17] [ 99%] PASSED tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamps_manifest_with_note 
tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamping_preserves_unicode 
[gw17] [100%] PASSED tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamping_preserves_unicode 

=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:858: 32 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:858: PytestAssertRewriteWarning: Module already imported so cannot be rewritten; tests.integration.auto_merge_fixtures
    self.import_plugin(import_spec)

tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/integration/test_chat_endpoint_session_lifecycle.py::test_session_error_event_surfaces_to_sse_stream
tests/integration/test_chat_endpoint_permission_flow.py::test_permission_deny_blocks_tool
tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_past_ring_buffer_emits_gap_warning
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/websockets/legacy/__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see https://websockets.readthedocs.io/en/stable/howto/upgrade.html for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

tests/integration/test_chat_endpoint_session_lifecycle.py::test_session_error_event_surfaces_to_sse_stream
tests/integration/test_chat_endpoint_permission_flow.py::test_permission_deny_blocks_tool
tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_past_ring_buffer_emits_gap_warning
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/uvicorn/protocols/websockets/websockets_impl.py:17: DeprecationWarning: websockets.server.WebSocketServerProtocol is deprecated
    from websockets.server import WebSocketServerProtocol

tests/integration/test_oss_dashboard_routes.py::TestOssSseEventOrder::test_stream_emits_status_and_complete_events
tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_row_update_events
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_row_update_event_data_shape
tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/db/test_F00077_migration.py::TestF00077Migration::test_unique_in_flight_constraint_blocks_concurrent_jobs
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/db/test_F00077_migration.py:264: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryZeroWorkItems::test_empty_project_returns_empty_bundle_no_error
tests/integration/test_boundary_behavior_f00060.py::TestBoundarySemanticIndexMissing::test_missing_lancedb_table_treated_as_empty
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/qa.py:436: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb.table_names():

tests/integration/test_boundary_behavior_f00060.py: 16 warnings
tests/integration/test_doc_indexer.py: 25 warnings
tests/integration/test_doc_index_job_runner.py: 8 warnings
tests/integration/test_code_index_pipeline.py: 8 warnings
tests/integration/test_invariants_f00060.py: 2 warnings
tests/integration/test_doc_index_poller.py: 4 warnings
  /usr/lib/python3.12/asyncio/events.py:88: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    self._context.run(self._callback, *self._args)

tests/integration/test_boundary_behavior_f00060.py: 7 warnings
tests/integration/test_doc_indexer.py: 9 warnings
tests/integration/test_doc_index_job_runner.py: 5 warnings
tests/integration/test_invariants_f00060.py: 1 warning
tests/integration/test_doc_index_poller.py: 2 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/doc_indexer.py:141: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    return self._table_name() in db.table_names()

tests/integration/test_boundary_behavior_f00060.py: 6 warnings
tests/integration/test_doc_indexer.py: 8 warnings
tests/integration/test_doc_index_job_runner.py: 3 warnings
tests/integration/test_invariants_f00060.py: 1 warning
tests/integration/test_doc_index_poller.py: 2 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/doc_indexer.py:208: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryNoFileOverlap::test_no_git_log_items_when_no_file_overlap
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryQuestionTooLong::test_prompt_truncation_preserves_question_not_docs
  <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryEmbedModelChange::test_embed_model_change_drops_and_reindexes
tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/doc_indexer.py:173: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if self._table_name() in db.table_names():

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7b3eeda5b2f0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7b3eeda5b350>
    db_session.flush()

tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in lancedb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_doc_indexer.py:144: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_batch_overlap_ignore.py::TestBatchOverlapIgnoreModel::test_composite_pk_uniqueness
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_batch_overlap_ignore.py:162: SAWarning: New instance <BatchOverlapIgnore at 0x77eb6646c590> with identity key (<class 'orch.db.models.BatchOverlapIgnore'>, ('test-proj', 'BATCH-002', 'CR-00072', 'CR-00057', 'orch/daemon/batch_manager.py'), None) conflicts with persistent instance <BatchOverlapIgnore at 0x77eb6646e120>
    db_session.flush()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/dashboard/test_prompt_modal_route.py::TestStepDetailHasPrompt::test_synthetic_step_returns_404
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/sqlalchemy/event/base.py:177: RuntimeWarning: coroutine 'sleep' was never awaited
    def _listen(self, event_key: _EventKey[_ET], **kw: Any) -> None:
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/integration/rag/test_qa_with_conversation.py::TestQAWithConversation::test_condense_invoked_on_second_turn
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/rag/test_qa_with_conversation.py:123: RuntimeWarning: coroutine 'TestQAWithConversation.test_condense_invoked_on_second_turn.<locals>.mock_astream_chat' was never awaited
    mock_ollama_instance.astream_chat = AsyncMock(mock_astream_chat())
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    page = list(self._connection.table_names(page_token))

tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/dashboard/test_session_cookie_middleware.py::TestSessionCookieMiddleware::test_second_request_uses_existing_cookie
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/.venv/lib/python3.12/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00081/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
= 3198 passed, 28 skipped, 5 xfailed, 3 xpassed, 186 warnings in 317.95s (0:05:17) =
[allure-integration] Run 'make allure-serve' to view report
```

## Verdict

```
pass
```
