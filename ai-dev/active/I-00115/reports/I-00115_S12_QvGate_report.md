# I-00115 S12 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | integration-tests      |
| Command      | `make allure-integration` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 310       |

## Output (tail)

```
[gw8] [ 99%] PASSED tests/dashboard/test_chat_context_pct_template.py::TestContextPctJsHelpers::test_apply_context_pct_exists 
tests/integration/rag/test_qa_with_conversation.py::TestQAWithConversation::test_system_prompt_contains_hardening_lines 
[gw5] [ 99%] PASSED tests/integration/rag/test_qa_with_conversation.py::TestQAWithConversation::test_system_prompt_contains_hardening_lines 
[gw12] [ 99%] PASSED tests/dashboard/test_runtime_overrides_api.py::TestPatchItemRuntimeOverride::test_emits_daemon_event 
[gw4] [ 99%] PASSED tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_preserves_last_pill_color 
tests/integration/test_oss_freshness.py::TestOssFreshness::test_fresh_when_head_matches 
[gw4] [ 99%] PASSED tests/integration/test_oss_freshness.py::TestOssFreshness::test_fresh_when_head_matches 
tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit 
[gw4] [ 99%] PASSED tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit 
tests/dashboard/routers/test_conversations.py::TestCrossSession::test_cross_session_returns_404 
[gw20] [ 99%] PASSED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock 
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock 
[gw3] [ 99%] PASSED tests/integration/db/test_safe_migrate_self_blocker.py::test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock 
tests/integration/db/test_safe_migrate_self_blocker.py::test_lock_timeout_env_var_honored_by_get_helper 
[gw3] [ 99%] PASSED tests/integration/db/test_safe_migrate_self_blocker.py::test_lock_timeout_env_var_honored_by_get_helper 
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock 
[gw4] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestCrossSession::test_cross_session_returns_404 
tests/dashboard/routers/test_conversations.py::TestConversationCreate::test_post_with_module_path 
[gw4] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationCreate::test_post_with_module_path 
tests/dashboard/routers/test_conversations.py::TestConversationCreate::test_post_creates_conversation 
[gw4] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationCreate::test_post_creates_conversation 
tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_returns_ordered_messages 
[gw3] [ 99%] PASSED tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock 
[gw20] [ 99%] PASSED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock 
[gw4] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_returns_ordered_messages 
tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_404_if_not_found 
tests/integration/db/test_safe_migrate_self_blocker.py::test_assert_no_self_blockers_no_pending_falls_back_to_relevant_tables 
[gw4] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationMessages::test_get_messages_404_if_not_found 
tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_returns_conversations 
[gw4] [ 99%] PASSED tests/dashboard/routers/test_conversations.py::TestConversationList::test_list_returns_conversations 
[gw3] [ 99%] PASSED tests/integration/db/test_safe_migrate_self_blocker.py::test_assert_no_self_blockers_no_pending_falls_back_to_relevant_tables 
tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_patch_toggle_not_found 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_patch_toggle_not_found 
tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_valid 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_valid 
tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_invalid_format 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_invalid_format 
tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_delete_slot_not_found 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_delete_slot_not_found 
tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_duplicate 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_duplicate 
tests/dashboard/test_keep_alive_routes.py::TestRunsApi::test_get_runs_returns_200 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestRunsApi::test_get_runs_returns_200 
tests/dashboard/test_keep_alive_routes.py::TestKeepAlivePage::test_get_keep_alive_page_returns_200 
[gw3] [ 99%] PASSED tests/dashboard/test_keep_alive_routes.py::TestKeepAlivePage::test_get_keep_alive_page_returns_200 
tests/dashboard/test_keep_alive_routes.py::TestConfigApi::test_post_config_invalid_duration 
[gw3] [100%] PASSED tests/dashboard/test_keep_alive_routes.py::TestConfigApi::test_post_config_invalid_duration 

=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:858: 32 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:858: PytestAssertRewriteWarning: Module already imported so cannot be rewritten; tests.integration.auto_merge_fixtures
    self.import_plugin(import_spec)

tests/integration/test_doc_indexer.py: 9 warnings
tests/integration/test_doc_index_job_runner.py: 5 warnings
tests/integration/test_doc_index_poller.py: 2 warnings
tests/integration/test_invariants_f00060.py: 1 warning
tests/integration/test_boundary_behavior_f00060.py: 7 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/doc_indexer.py:141: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    return self._table_name() in db.table_names()

tests/integration/test_doc_indexer.py: 25 warnings
tests/integration/test_doc_index_job_runner.py: 8 warnings
tests/integration/test_code_index_pipeline.py: 8 warnings
tests/integration/test_doc_index_poller.py: 4 warnings
tests/integration/test_invariants_f00060.py: 2 warnings
tests/integration/test_boundary_behavior_f00060.py: 16 warnings
  /usr/lib/python3.12/asyncio/events.py:88: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    self._context.run(self._callback, *self._args)

tests/integration/test_doc_indexer.py: 8 warnings
tests/integration/test_doc_index_job_runner.py: 3 warnings
tests/integration/test_doc_index_poller.py: 2 warnings
tests/integration/test_invariants_f00060.py: 1 warning
tests/integration/test_boundary_behavior_f00060.py: 6 warnings
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/doc_indexer.py:208: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_doc_indexer.py:144: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in lancedb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb_uri.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryEmbedModelChange::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/doc_indexer.py:173: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if self._table_name() in db.table_names():

tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    assert table_name in db.table_names()

tests/integration/test_batch_overlap_ignore.py::TestBatchOverlapIgnoreModel::test_composite_pk_uniqueness
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_batch_overlap_ignore.py:162: SAWarning: New instance <BatchOverlapIgnore at 0x787d7c8b3f80> with identity key (<class 'orch.db.models.BatchOverlapIgnore'>, ('test-proj', 'BATCH-002', 'CR-00072', 'CR-00057', 'orch/daemon/batch_manager.py'), None) conflicts with persistent instance <BatchOverlapIgnore at 0x787d7c8b3f50>
    db_session.flush()

tests/integration/db/test_F00077_migration.py::TestF00077Migration::test_unique_in_flight_constraint_blocks_concurrent_jobs
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/db/test_F00077_migration.py:264: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_row_update_event_data_shape
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_row_update_events
tests/integration/test_oss_dashboard_routes.py::TestOssSseEventOrder::test_stream_emits_status_and_complete_events
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    page = list(self._connection.table_names(page_token))

tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_chat_endpoint_permission_flow.py::test_permission_asked_event_renders_and_reply_forwards
tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_replays_buffered_events_via_last_event_id
tests/integration/test_chat_endpoint_session_lifecycle.py::test_session_lifecycle_create_prompt_stream_abort
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/websockets/legacy/__init__.py:6: DeprecationWarning: websockets.legacy is deprecated; see https://websockets.readthedocs.io/en/stable/howto/upgrade.html for upgrade instructions
    warnings.warn(  # deprecated in 14.0 - 2024-11-09

tests/integration/test_chat_endpoint_permission_flow.py::test_permission_asked_event_renders_and_reply_forwards
tests/integration/test_chat_endpoint_reconnect.py::test_reconnect_replays_buffered_events_via_last_event_id
tests/integration/test_chat_endpoint_session_lifecycle.py::test_session_lifecycle_create_prompt_stream_abort
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/uvicorn/protocols/websockets/websockets_impl.py:17: DeprecationWarning: websockets.server.WebSocketServerProtocol is deprecated
    from websockets.server import WebSocketServerProtocol

tests/integration/dashboard/test_session_cookie_middleware.py::TestSessionCookieMiddleware::test_second_request_uses_existing_cookie
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7bd191d40140> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7bd191d43b90>
    db_session.flush()

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/api/test_docs_diff_api.py::TestOriginalDiffEndpoint::test_existing_diff_endpoint_still_returns_html
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/.venv/lib/python3.12/site-packages/pydantic/_internal/_generate_schema.py:297: RuntimeWarning: coroutine 'sleep' was never awaited
    def _add_custom_serialization_from_json_encoders(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/integration/test_boundary_behavior_f00060.py::TestBoundarySemanticIndexMissing::test_missing_lancedb_table_treated_as_empty
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryZeroWorkItems::test_empty_project_returns_empty_bundle_no_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/rag/qa.py:436: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in ldb.table_names():

tests/integration/test_boundary_behavior_f00060.py::TestBoundaryNoFileOverlap::test_no_git_log_items_when_no_file_overlap
tests/integration/test_boundary_behavior_f00060.py::TestBoundaryQuestionTooLong::test_prompt_truncation_preserves_question_not_docs
  <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).

tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_lock_timeout_failure_under_short_timeout
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
tests/integration/db/test_safe_migrate_self_blocker.py::test_apply_returns_self_blocker_failure_when_caller_holds_share_lock
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/orch/db/safe_migrate.py:626: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
    _assert_not_agent_context(live_db_url)

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/rag/test_qa_with_conversation.py::TestQAWithConversation::test_condense_invoked_on_second_turn
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00115/tests/integration/rag/test_qa_with_conversation.py:123: RuntimeWarning: coroutine 'TestQAWithConversation.test_condense_invoked_on_second_turn.<locals>.mock_astream_chat' was never awaited
    mock_ollama_instance.astream_chat = AsyncMock(mock_astream_chat())
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
= 3256 passed, 29 skipped, 4 xfailed, 3 xpassed, 186 warnings in 308.55s (0:05:08) =
[allure-integration] Run 'make allure-serve' to view report
```

## Verdict

```
pass
```
