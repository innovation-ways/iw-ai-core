# F-00065 S12 QV Fix Cycle 1/5

Quality gate S12 for work item F-00065 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 1 integration test failed: test_merge_queue_oldest_first has a pre-existing mock issue where subprocess.run stdout 'squash ok' is misinterpreted as a file path

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00065 --step S12
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started F-00065 step S12 (already in progress)
  $ make test-integration
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dd876bfe800124r62xxF8arufi
  tests/integration/test_oss_dashboard_routes.py::TestOssPublish::test_publish_returns_404 PASSED [ 75%]
  tests/integration/test_oss_dashboard_routes.py::TestOssFix::test_fix_preview_returns_200 PASSED [ 75%]
  tests/integration/test_oss_dashboard_routes.py::TestOssFix::test_fix_apply_returns_job_id PASSED [ 75%]
  tests/integration/test_oss_dashboard_routes.py::TestOssRecheck::test_recheck_returns_200 PASSED [ 75%]
  tests/integration/test_oss_dashboard_routes.py::TestOssAccept::test_accept_returns_204 PASSED [ 75%]
  tests/integration/test_oss_dashboard_routes.py::TestOssAccept::test_accept_rejects_empty_reason PASSED [ 75%]
  tests/integration/test_oss_dashboard_routes.py::TestOssApplyAllSafe::test_apply_all_safe_preview_returns_200 PASSED [ 76%]
  tests/integration/test_oss_dashboard_routes.py::TestOssApplyAllSafe::test_apply_all_safe_rejects_unsafe PASSED [ 76%]
  tests/integration/test_oss_dashboard_routes.py::TestOssStream::test_stream_404_for_unknown_project PASSED [ 76%]
  tests/integration/test_oss_dashboard_routes.py::TestOssStream::test_stream_404_for_nonexistent_job PASSED [ 76%]
  tests/integration/test_oss_dashboard_routes.py::TestOssStream::test_stream_returns_sse_media_type PASSED [ 76%]
  tests/integration/test_oss_dashboard_routes.py::TestOssStream::test_stream_404_for_job_wrong_project PASSED [ 76%]
  tests/integration/test_oss_dashboard_routes.py::TestOssSseEventOrder::test_stream_emits_status_and_complete_events PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestEnqueueJob::test_enqueue_scan_job PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestEnqueueJob::test_enqueue_install_job_worktree_is_null PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_worktree_kinds_not_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_run_worktree_not_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_discard_job_not_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_prep_branch_name_not_in_oss_service PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRunFixWorksInRepoRoot::test_run_fix_writes_to_project_repo_root PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestNoTempfilePaths::test_no_tmp_oss_paths_in_oss_service PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRunJob::test_run_scan_job_transitions_to_complete PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRunJob::test_run_install_job_no_worktree PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRunJob::test_run_install_nonzero_exit_sets_error_with_tail PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestCancelJob::test_cancel_running_job PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestCancelJob::test_cancel_queued_job PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRecoverOrphanedJobs::test_orphan_recovery_marks_jobs_error PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestJobEventStream::test_sse_stream_yields_status_and_progress PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestJobEventStream::test_sse_stream_replay_restreams_tail PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestProbeTier1Wrapper::test_probe_tier1_dashboard_returns_dict PASSED [ 78%]
  tests/integration/test_oss_dashboard_service.py::TestComputeFreshness::test_freshness_matches_head_sha PASSED [ 78%]
  tests/integration/test_oss_dashboard_service.py::TestComputeFreshness::test_freshness_no_scans_yet PASSED [ 78%]
  tests/integration/test_oss_dashboard_service.py::TestLatestScanAndSummary::test_latest_scan_returns_none_when_empty PASSED [ 78%]
  tests/integration/test_oss_dashboard_service.py::TestLatestScanAndSummary::test_scan_summary_not_yet_scanned PASSED [ 78%]
  tests/integration/test_oss_dashboard_service.py::TestLatestScanAndSummary::test_scan_summary_with_existing_scan PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_row_update_events PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_row_update_event_data_shape PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_progress_events_for_stdout_tail PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseReconnectReplaysTail::test_stream_replay_on_reconnect_precedes_live_events PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseReconnectReplaysTail::test_reconnect_replays_before_live_stream PASSED [ 79%]
  tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_emitted_at_20s_interval PASSED [ 79%]
  tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_comment_format PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_green_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_yellow_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_red_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_gray_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_stale_pill_has_warning_annotation PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTabVisibilityInvariant::test_oss_tab_present_when_enabled PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTabVisibilityInvariant::test_oss_tab_absent_when_disabled PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTabVisibilityInvariant::test_oss_enabled_flag_controls_tab_visibility PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_in_dashboard_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_tests_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_quality_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_in_oss_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_batches_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_is_htmx_loaded PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_install_job_has_no_worktree_columns PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_worktree_columns_removed_from_schema PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoScanGrayPillInvariant::test_no_scan_renders_gray_pill_not_yet_scanned PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoScanGrayPillInvariant::test_no_scan_gray_pill_in_full_oss_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestDomainCardEmptyStateInvariant::test_no_findings_renders_empty_state_message PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestDomainCardEmptyStateInvariant::test_domain_card_with_findings_renders_correctly PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallModalEnableButtonInvariant::test_enable_button_disabled_when_tools_missing PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallModalEnableButtonInvariant::test_enable_button_enabled_when_all_tools_installed PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTableColumnOrder::test_table_has_correct_column_headers PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssFindingModalCatalogContent::test_modal_fragment_included_in_oss_page PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssFilterChips::test_filter_chips_present_with_defaults PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestCliBlockRemoved::test_no_prepare_cli_block PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestCliBlockRemoved::test_no_publish_cli_block PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_code_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_tests_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_quality_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_documentation_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_detail_rows_created PASSED [ 81%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_evidence_json_strips_results PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_no_results_means_no_detail_rows PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_cascade_delete_on_finding PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_returns_paginated_results PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_default_limit PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_capped_flag_propagated PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_unknown PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_belongs_to_other_project PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_no_detail_table_returns_empty PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestSchema::test_oss_finding_detail_table_exists PASSED [ 82%]
  tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit PASSED [ 82%]
  tests/integration/test_oss_freshness.py::TestOssFreshness::test_fresh_when_head_matches PASSED [ 83%]
  tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_preserves_last_pill_color PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_scan_table_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_finding_table_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_tool_run_table_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_project_oss_enabled_column_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_scan_columns PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_finding_columns PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_tool_run_columns PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_scan_indexes PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_finding_indexes PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_tool_run_indexes PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_scan_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_project_oss_job_kind_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_scan_mode_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_project_oss_job_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_finding_auto_apply_safe_column PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_project_oss_job_no_worktree_path_column PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_pill_color_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_finding_severity_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_finding_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_tool_run_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_scan_defaults PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_scan_all_fields PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_finding_defaults PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_tool_run_defaults PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_to_oss_scan PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_to_oss_scan PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_to_project PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_project_cascades_to_scans PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_findings PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_tool_runs PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssRelationships::test_project_oss_scans_relationship PASSED [ 86%]
  tests/integration/test_oss_migration.py::TestOssRelationships::test_oss_scan_findings_relationship PASSED [ 86%]
  tests/integration/test_oss_migration.py::TestOssRelationships::test_oss_scan_tool_runs_relationship PASSED [ 86%]
  tests/integration/test_oss_migration.py::TestProjectOssEnabled::test_project_oss_enabled_default PASSED [ 86%]
  tests/integration/test_oss_migration.py::TestProjectOssEnabled::test_project_oss_enabled_can_be_set PASSED [ 86%]
  tests/integration/test_oss_migration.py::TestOssMigrationDowngrade::test_downgrade_drops_tables PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_must_fail_returns_red PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_must_human_required_returns_red PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_should_fail_returns_yellow PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_should_human_required_returns_yellow PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_all_pass_returns_green PASSED [ 86%]
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_empty_returns_green PASSED [ 87%]
  tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row PASSED [ 87%]
  tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_rejects_make_oss_mode PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_item_detail_has_mermaid PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_running_page_does_not_have_mermaid PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_running_page_does_not_have_hljs PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_project_dashboard_does_not_have_mermaid PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_base_html_comment_about_lazy_loading PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_rebase_idempotent_when_main_not_advanced PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_rebase_multi_file_chain_only_root_rewritten PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_batch_rebase_emits_daemon_event PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_parallel_batches_rebase_rewrites_stale_down_revision PASSED [ 88%]
  tests/integration/test_parallel_migrations.py::test_rebase_and_dry_run_succeed_for_stale_worktree PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_table_exists_with_columns PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_direction_check_constraint PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_phase_check_constraint PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_valid_enum_values_accepted PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_indexes_exist PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_batch_id_accepts_values PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_downgrade_drops_table PASSED [ 88%]
  tests/integration/test_pending_migration_log_migration.py::test_upgrade_recreates_table_empty PASSED [ 88%]
  tests/integration/test_per_worktree_isolation.py::test_two_parallel_iw_ai_core_worktrees_do_not_interfere PASSED [ 88%]
  tests/integration/test_project_docs.py::test_project_doc_create PASSED   [ 88%]
  tests/integration/test_project_docs.py::test_project_doc_version_defaults PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_jsonb_fields PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_unique_constraint PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_cascade_on_project_delete PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_version_create PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_version_cascade_on_doc_delete PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_version_multiple_versions PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_create PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_status_default PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_doc_id_nullable PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_cascade_on_project_delete PASSED [ 89%]
  tests/integration/test_project_docs.py::test_invalid_doc_type_rejected PASSED [ 90%]
  tests/integration/test_project_docs.py::test_invalid_doc_status_rejected PASSED [ 90%]
  tests/integration/test_project_docs.py::test_invalid_job_status_rejected PASSED [ 90%]
  tests/integration/test_project_docs.py::test_project_doc_fts_trigger_on_insert PASSED [ 90%]
  tests/integration/test_project_docs.py::test_project_doc_fts_trigger_on_update PASSED [ 90%]
  tests/integration/test_project_docs.py::test_project_doc_fts_trigger_title_only PASSED [ 90%]
  tests/integration/test_project_docs.py::test_project_doc_fts_full_text_search PASSED [ 90%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_returns_200 PASSED [ 90%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_has_form PASSED [ 90%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_has_project_id_input PASSED [ 90%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_has_display_name_input PASSED [ 90%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_has_repo_root_input PASSED [ 90%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_has_browse_button PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_renders_with_empty_form_values PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestProjectSlugRoute::test_returns_200 PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestProjectSlugRoute::test_slugifies_simple_name PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestProjectSlugRoute::test_slugifies_with_spaces PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestProjectSlugRoute::test_returns_empty_for_missing_path PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestProjectSlugRoute::test_returns_empty_for_path_outside_safe_root PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_returns_200 PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_has_breadcrumbs PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_has_directory_entries_section PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_show_hidden_param_accepted PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_path_param_filters_entries PASSED [ 91%]
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_navigates_to_subdirectory PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_missing_project_id_returns_modal_with_error PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_invalid_project_id_returns_modal_with_error PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_duplicate_project_id_returns_error PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_missing_display_name_returns_error PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_nonexistent_repo_root_returns_error PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_valid_repo_without_git_returns_error PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_valid_creation_redirects PASSED [ 92%]
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_project_created_in_db PASSED [ 92%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_table_exists PASSED [ 92%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_columns PASSED [ 92%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_kind_enum PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_status_enum PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_insert_scan_job PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_insert_all_fields PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_insert_scan_job_all_fields PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_insert_install_job PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_complete_job PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_error_job PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_to_project PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_scan_id PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_scan_id_set_null_on_delete PASSED [ 93%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobCascadeDeletes::test_delete_project_cascades_to_jobs PASSED [ 94%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobRelationships::test_project_oss_jobs_relationship PASSED [ 94%]
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade::test_downgrade_drops_table PASSED [ 94%]
  tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_code_only_question_yields_no_workitem_context PASSED [ 94%]
  tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_code_only_question_yields_no_phase_events_for_workitem_steps PASSED [ 94%]
  tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_code_only_question_yields_no_citation_events PASSED [ 94%]
  tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_classifier_routes_signature_question_as_code_only PASSED [ 94%]
  tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_classifier_routes_how_do_i_use_as_code_only PASSED [ 94%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_populates_command_gate_timeout_columns PASSED [ 94%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamps_manifest_with_note PASSED [ 94%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamping_is_idempotent PASSED [ 94%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamping_preserves_unicode PASSED [ 95%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_invalid_timeout_fails_clearly PASSED [ 95%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_then_item_status_returns_manifest_superset PASSED [ 95%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_round_trip_preserves_scope_block PASSED [ 95%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_item_status_json_null_columns_serialize_as_null PASSED [ 95%]
  tests/integration/test_register_to_item_status_roundtrip.py::test_item_status_surfaces_db_only_step_not_in_manifest PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_no_running_job_returns_200 PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_no_running_job_fragment_contains_project_id PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_when_job_queued_returns_409 PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_when_job_running_returns_409 PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_unknown_project_returns_404 PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_writes_exactly_one_row PASSED [ 95%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_row_has_correct_config_fields PASSED [ 96%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_with_completed_job_succeeds PASSED [ 96%]
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_with_failed_job_succeeds PASSED [ 96%]
  tests/integration/test_search.py::test_search_returns_matching_items PASSED [ 96%]
  tests/integration/test_search.py::test_search_ranking_by_relevance PASSED [ 96%]
  tests/integration/test_search.py::test_search_project_filter PASSED      [ 96%]
  tests/integration/test_search.py::test_search_type_filter PASSED         [ 96%]
  tests/integration/test_search.py::test_search_returns_empty_for_no_match PASSED [ 96%]
  tests/integration/test_search.py::test_search_human_output PASSED        [ 96%]
  tests/integration/test_sse_events.py::test_status_update_events_in_watched_set PASSED [ 96%]
  tests/integration/test_sse_events.py::test_all_status_update_events_are_toast_events PASSED [ 96%]
  tests/integration/test_sse_events.py::test_all_toast_events_have_severity PASSED [ 96%]
  tests/integration/test_sse_events.py::test_running_update_events_unchanged PASSED [ 97%]
  tests/integration/test_sse_events.py::test_status_update_events_cover_action_emitted_types PASSED [ 97%]
  tests/integration/test_sse_events.py::test_no_overlap_between_running_and_status_events PASSED [ 97%]
  tests/integration/test_sse_events.py::test_event_generator_surfaces_init_failures_as_error_frame PASSED [ 97%]
  tests/integration/test_sse_events.py::test_event_generator_surfaces_loop_failures_as_error_frame PASSED [ 97%]
  tests/integration/test_step_monitor_lifecycle.py::test_full_lifecycle_emits_single_warn_then_idempotent PASSED [ 97%]
  tests/integration/test_step_monitor_lifecycle.py::test_lifecycle_below_50pct_emits_no_warn PASSED [ 97%]
  tests/integration/test_step_monitor_lifecycle.py::test_lifecycle_past_timeout_emits_timeout_not_warn PASSED [ 97%]
  tests/integration/test_work_item_evidence.py::TestEvidencePhaseEnum::test_evidence_phase_has_pre_value PASSED [ 97%]
  tests/integration/test_work_item_evidence.py::TestEvidencePhaseEnum::test_evidence_phase_has_post_value PASSED [ 97%]
  tests/integration/test_work_item_evidence.py::TestEvidencePhaseEnum::test_evidence_phase_count PASSED [ 97%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_pre_phase PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_post_phase PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_blob_content_stored_and_retrieved PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_multiple_evidences_same_work_item_different_phase PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_multiple_evidences_same_phase_different_filename PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_step_id_is_optional PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_step_id_can_be_set PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_captured_at_defaults_to_now PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_same_filename_different_phase_allowed PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletion_blocked_when_evidence_exists PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_when_no_evidence PASSED [ 98%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_after_evidence_removed PASSED [ 99%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceIndex::test_index_on_project_work_item_phase PASSED [ 99%]
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceEnumConstraint::test_invalid_evidence_phase_rejected PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_insert_populates_search_vector PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_update_functional_doc_content_regenerates_search PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_update_title_regenerates_search PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_query_returns_row PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_independence_from_design_doc_search PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_bulk_insert_search_vectors PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_used_for_search_query PASSED [ 99%]
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocMigrationRoundTrip::test_functional_doc_migration_round_trip PASSED [ 99%]
  tests/integration/test_worktree_reaper_real_containers.py::test_reaper_classifies_and_reaps_orphan PASSED [100%]
  ___________ TestMergeQueueIntegration.test_merge_queue_oldest_first ____________
  self = <integration.test_batch_manager.TestMergeQueueIntegration object at 0x7d85a9650560>
  db_session = <sqlalchemy.orm.session.Session object at 0x7d85a8144ec0>
  manager = <orch.daemon.batch_manager.BatchManager object at 0x7d85a81459d0>
  test_project = <orch.db.models.Project object at 0x7d85a8146630>
      def test_merge_queue_oldest_first(
          self, db_session: Session, manager: BatchManager, test_project
      ):
          make_work_item(db_session, "F-00001")
          make_work_item(db_session, "F-00002")
          make_batch(db_session, "B001", status=BatchStatus.executing)
          older_item = make_batch_item(
              db_session, "B001", "F-00001", status=BatchItemStatus.completed
          )
          older_item.started_at = datetime(2024, 1, 1, tzinfo=UTC)
          older_item.worktree_info = {"path": "/wt/F-00001"}
          newer_item = make_batch_item(
              db_session, "B001", "F-00002", status=BatchItemStatus.completed
          )
          newer_item.started_at = datetime(2024, 1, 2, tzinfo=UTC)
          newer_item.worktree_info = {"path": "/wt/F-00002"}
          db_session.flush()
          def fake_commit_script(*args, **kwargs):
              result = MagicMock()
              result.returncode = 0
              result.stdout = "squash ok"
              result.stderr = ""
              return result
          with (
              patch("orch.daemon.merge_queue.subprocess.run", side_effect=fake_commit_script),
              patch("orch.daemon.merge_queue._cleanup_worktree"),
              patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
              patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
          ):
              mock_dry.return_value = MagicMock(
                  success=True, message="ok", final_batch_state="proceed_to_merge"
              )
              mock_apply.return_value = MagicMock(success=True, message="ok")
              manager.process_merge_queue()
          db_session.refresh(older_item)
          db_session.refresh(newer_item)
  >       assert older_item.status == BatchItemStatus.merged
  E       AssertionError: assert <BatchItemStatus.migration_rebase_failed: 'migration_rebase_failed'> == <BatchItemStatus.merged: 'merged'>
  E        +  where <BatchItemStatus.migration_rebase_failed: 'migration_rebase_failed'> = <orch.db.models.BatchItem object at 0x7d85a29d71a0>.status
  E        +  and   <BatchItemStatus.merged: 'merged'> = BatchItemStatus.merged
  tests/integration/test_batch_manager.py:419: AssertionError
  ------------------------------ Captured log call -------------------------------
  ERROR    orch.daemon.migration_rebase:migration_rebase.py:539 [rebase] Unexpected error for batch B001
  Traceback (most recent call last):
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/daemon/migration_rebase.py", line 364, in run_pre_merge_rebase
      revision, down_revision = _parse_migration(str(full_path))
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/daemon/migration_rebase.py", line 112, in _parse_migration
      content = Path(path).read_text(encoding="utf-8")
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/pathlib.py", line 1029, in read_text
      with self.open(mode='r', encoding=encoding, errors=errors) as f:
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/usr/lib/python3.12/pathlib.py", line 1015, in open
      return io.open(self, mode, buffering, encoding, errors, newline)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  FileNotFoundError: [Errno 2] No such file or directory: '/wt/F-00001/squash ok'
  WARNING  orch.daemon.worktree_compose:worktree_compose.py:254 [worktree_compose] Failed to write daemon event: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  WARNING  orch.daemon.merge_queue:merge_queue.py:183 [test-proj] Pre-merge rebase failed for F-00001 (batch B001): [Errno 2] No such file or directory: '/wt/F-00001/squash ok'
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  tests/integration/test_migration_pipeline.py:89
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_migration_pipeline.py:89: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:96
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_migration_pipeline.py:96: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:119
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_migration_pipeline.py:119: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:172
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_migration_pipeline.py:172: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:210
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_migration_pipeline.py:210: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_boundary_behavior_f00060.py::TestBoundaryZeroWorkItems::test_empty_project_returns_empty_bundle_no_error
  tests/integration/test_boundary_behavior_f00060.py::TestBoundarySemanticIndexMissing::test_missing_lancedb_table_treated_as_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/qa.py:358: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in ldb.table_names():
  tests/integration/test_boundary_behavior_f00060.py: 16 warnings
  tests/integration/test_code_index_pipeline.py: 8 warnings
  tests/integration/test_doc_index_job_runner.py: 8 warnings
  tests/integration/test_doc_index_poller.py: 4 warnings
  tests/integration/test_doc_indexer.py: 25 warnings
  tests/integration/test_invariants_f00060.py: 2 warnings
    /usr/lib/python3.12/asyncio/events.py:88: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      self._context.run(self._callback, *self._args)
  tests/integration/test_boundary_behavior_f00060.py::TestBoundaryNoFileOverlap::test_no_git_log_items_when_no_file_overlap
  tests/integration/test_boundary_behavior_f00060.py::TestBoundaryQuestionTooLong::test_prompt_truncation_preserves_question_not_docs
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/integration/test_boundary_behavior_f00060.py: 7 warnings
  tests/integration/test_doc_index_job_runner.py: 5 warnings
  tests/integration/test_doc_index_poller.py: 2 warnings
  tests/integration/test_doc_indexer.py: 9 warnings
  tests/integration/test_invariants_f00060.py: 1 warning
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/doc_indexer.py:141: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      return self._table_name() in db.table_names()
  tests/integration/test_boundary_behavior_f00060.py: 6 warnings
  tests/integration/test_doc_index_job_runner.py: 3 warnings
  tests/integration/test_doc_index_poller.py: 2 warnings
  tests/integration/test_doc_indexer.py: 8 warnings
  tests/integration/test_invariants_f00060.py: 1 warning
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/doc_indexer.py:208: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in db.table_names():
  tests/integration/test_boundary_behavior_f00060.py::TestBoundaryEmbedModelChange::test_embed_model_change_drops_and_reindexes
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/doc_indexer.py:173: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if self._table_name() in db.table_names():
  tests/integration/test_code_index_job.py::TestCodeIndexJobFKConstraints::test_code_index_job_fk_invalid_project
  tests/integration/test_evidences_ingest.py::TestIngestPhaseFromDiskOversize::test_oversize_raises_evidence_too_large_error_no_rows_inserted
  tests/integration/test_models.py::test_duplicate_item_id_in_same_project_rejected
  tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_project_created_in_db
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_used_for_search_query
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/conftest.py:135: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
  tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc
  tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
  tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      page = list(self._connection.table_names(page_token))
  tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
  tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in db.table_names():
  tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
  tests/integration/test_oss_dashboard_routes.py::TestOssSseEventOrder::test_stream_emits_status_and_complete_events
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_row_update_events
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_row_update_event_data_shape
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end
  tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/integration/test_doc_index_poller.py::TestDocIndexPollerStallDetection::test_stalled_job_marked_failed
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/.venv/lib/python3.12/site-packages/_pytest/stash.py:108: RuntimeWarning: coroutine 'DocIndexJobRunner.run' was never awaited
      del self._storage[key]
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_doc_indexer.py:144: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in lancedb_uri.table_names():
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in ldb_uri.table_names():
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in db.table_names():
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      assert table_name in db.table_names()
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      assert table_name in db.table_names()
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  tests/integration/test_project_docs.py::test_project_doc_unique_constraint
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7d8555ad25d0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7d85101ae810>
      db_session.flush()
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_insert_populates_search_vector
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00065/.venv/lib/python3.12/site-packages/sqlalchemy/event/attr.py:221: RuntimeWarning: coroutine 'sleep' was never awaited
      clslevel.extend(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  make: *** [Makefile:39: test-integration] Error 1
  $ mkdir -p ai-dev/active/F-00065/reports
  (no output)
  ← Write ai-dev/active/F-00065/reports/F-00065_S12_QvGate_report.md
  Wrote file successfully.


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
