# F-00064 S12 QV Fix Cycle 1/5

Quality gate S12 for work item F-00064 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 5 approve/unapprove CLI tests fail due to missing ai-dev/active/<item_id>/ directory fixture; 1129 tests pass

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00064 --step S12
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started F-00064 step S12 (already in progress)
  $ make test-integration 2>&1
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dd61cd55100146X0kxsaHojV1t
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_run_worktree_not_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_discard_job_not_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestWorktreeSymbolsRemoved::test_prep_branch_name_not_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestRunFixWorksInRepoRoot::test_run_fix_writes_to_project_repo_root PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestNoTempfilePaths::test_no_tmp_oss_paths_in_oss_service PASSED [ 76%]
  tests/integration/test_oss_dashboard_service.py::TestRunJob::test_run_scan_job_transitions_to_complete PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRunJob::test_run_install_job_no_worktree PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRunJob::test_run_install_nonzero_exit_sets_error_with_tail PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestCancelJob::test_cancel_running_job PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestCancelJob::test_cancel_queued_job PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestRecoverOrphanedJobs::test_orphan_recovery_marks_jobs_error PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestJobEventStream::test_sse_stream_yields_status_and_progress PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestJobEventStream::test_sse_stream_replay_restreams_tail PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestProbeTier1Wrapper::test_probe_tier1_dashboard_returns_dict PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestComputeFreshness::test_freshness_matches_head_sha PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestComputeFreshness::test_freshness_no_scans_yet PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestLatestScanAndSummary::test_latest_scan_returns_none_when_empty PASSED [ 77%]
  tests/integration/test_oss_dashboard_service.py::TestLatestScanAndSummary::test_scan_summary_not_yet_scanned PASSED [ 78%]
  tests/integration/test_oss_dashboard_service.py::TestLatestScanAndSummary::test_scan_summary_with_existing_scan PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_row_update_events PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_row_update_event_data_shape PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_progress_events_for_stdout_tail PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseReconnectReplaysTail::test_stream_replay_on_reconnect_precedes_live_events PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseReconnectReplaysTail::test_reconnect_replays_before_live_stream PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_emitted_at_20s_interval PASSED [ 78%]
  tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_comment_format PASSED [ 78%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_green_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_yellow_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_red_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_gray_renders_correct_css_class PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_stale_pill_has_warning_annotation PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTabVisibilityInvariant::test_oss_tab_present_when_enabled PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTabVisibilityInvariant::test_oss_tab_absent_when_disabled PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTabVisibilityInvariant::test_oss_enabled_flag_controls_tab_visibility PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_in_dashboard_page PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_tests_page PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_quality_page PASSED [ 79%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_in_oss_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_batches_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_is_htmx_loaded PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_install_job_has_no_worktree_columns PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_worktree_columns_removed_from_schema PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoScanGrayPillInvariant::test_no_scan_renders_gray_pill_not_yet_scanned PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoScanGrayPillInvariant::test_no_scan_gray_pill_in_full_oss_page PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestDomainCardEmptyStateInvariant::test_no_findings_renders_empty_state_message PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestDomainCardEmptyStateInvariant::test_domain_card_with_findings_renders_correctly PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallModalEnableButtonInvariant::test_enable_button_disabled_when_tools_missing PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestInstallModalEnableButtonInvariant::test_enable_button_enabled_when_all_tools_installed PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssTableColumnOrder::test_table_has_correct_column_headers PASSED [ 80%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssFindingModalCatalogContent::test_modal_fragment_included_in_oss_page PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestOssFilterChips::test_filter_chips_present_with_defaults PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestCliBlockRemoved::test_no_prepare_cli_block PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestCliBlockRemoved::test_no_publish_cli_block PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_code_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_tests_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_quality_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_documentation_page_loads_without_oss_errors PASSED [ 81%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_detail_rows_created PASSED [ 81%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_evidence_json_strips_results PASSED [ 81%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_no_results_means_no_detail_rows PASSED [ 81%]
  tests/integration/test_oss_finding_details.py::TestPersistDetails::test_cascade_delete_on_finding PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_returns_paginated_results PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_default_limit PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_capped_flag_propagated PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_unknown PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_belongs_to_other_project PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_no_detail_table_returns_empty PASSED [ 82%]
  tests/integration/test_oss_finding_details.py::TestSchema::test_oss_finding_detail_table_exists PASSED [ 82%]
  tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit PASSED [ 82%]
  tests/integration/test_oss_freshness.py::TestOssFreshness::test_fresh_when_head_matches PASSED [ 82%]
  tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_preserves_last_pill_color PASSED [ 82%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_scan_table_exists PASSED [ 82%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_finding_table_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_tool_run_table_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_project_oss_enabled_column_exists PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_scan_columns PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_finding_columns PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_tool_run_columns PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_scan_indexes PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_finding_indexes PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssMigrationApply::test_oss_tool_run_indexes PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_scan_status_enum PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_project_oss_job_kind_enum PASSED [ 83%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_scan_mode_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_project_oss_job_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_finding_auto_apply_safe_column PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_project_oss_job_no_worktree_path_column PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_pill_color_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_finding_severity_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_finding_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssEnumValues::test_oss_tool_run_status_enum PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_scan_defaults PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_scan_all_fields PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_finding_defaults PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssORMModels::test_oss_tool_run_defaults PASSED [ 84%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_to_oss_scan PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_to_oss_scan PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_to_project PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_project_cascades_to_scans PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_findings PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_tool_runs PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssRelationships::test_project_oss_scans_relationship PASSED [ 85%]
  tests/integration/test_oss_migration.py::TestOssRelationships::test_oss_scan_findings_relationship PASSED [ 85%]
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
  tests/integration/test_oss_persistence.py::TestComputePillColor::test_empty_returns_green PASSED [ 86%]
  tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row PASSED [ 86%]
  tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_rejects_make_oss_mode PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_item_detail_has_mermaid PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_running_page_does_not_have_mermaid PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_running_page_does_not_have_hljs PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_project_dashboard_does_not_have_mermaid PASSED [ 87%]
  tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_base_html_comment_about_lazy_loading PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_rebase_idempotent_when_main_not_advanced PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_rebase_multi_file_chain_only_root_rewritten PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_batch_rebase_emits_daemon_event PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_parallel_batches_rebase_rewrites_stale_down_revision PASSED [ 87%]
  tests/integration/test_parallel_migrations.py::test_rebase_and_dry_run_succeed_for_stale_worktree PASSED [ 87%]
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
  tests/integration/test_project_docs.py::test_project_doc_version_defaults PASSED [ 88%]
  tests/integration/test_project_docs.py::test_project_doc_jsonb_fields PASSED [ 88%]
  tests/integration/test_project_docs.py::test_project_doc_unique_constraint PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_cascade_on_project_delete PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_version_create PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_version_cascade_on_doc_delete PASSED [ 89%]
  tests/integration/test_project_docs.py::test_project_doc_version_multiple_versions PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_create PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_status_default PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_doc_id_nullable PASSED [ 89%]
  tests/integration/test_project_docs.py::test_doc_generation_job_cascade_on_project_delete PASSED [ 89%]
  tests/integration/test_project_docs.py::test_invalid_doc_type_rejected PASSED [ 89%]
  tests/integration/test_project_docs.py::test_invalid_doc_status_rejected PASSED [ 89%]
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
  tests/integration/test_project_onboarding_api.py::TestNewProjectModalRoute::test_has_browse_button PASSED [ 90%]
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
  tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_navigates_to_subdirectory PASSED [ 91%]
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
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationApply::test_kind_enum PASSED [ 92%]
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
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobCascadeDeletes::test_delete_project_cascades_to_jobs PASSED [ 93%]
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
  tests/integration/test_register_to_item_status_roundtrip.py::test_register_stamping_preserves_unicode PASSED [ 94%]
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
  tests/integration/test_reindex_docs_endpoint.py::TestReindexDocsEndpoint::test_post_row_has_correct_config_fields PASSED [ 95%]
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
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_pre_phase PASSED [ 97%]
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
  ________________________ test_approve_draft_to_approved ________________________
  db_session = <sqlalchemy.orm.session.Session object at 0x7ad0ba63a3c0>
  test_project = <orch.db.models.Project object at 0x7ad0ba63b980>
  cli_get_session = <function cli_get_session.<locals>._get_session at 0x7ad0baf2d440>
      def test_approve_draft_to_approved(
          db_session: Any,
          test_project: Project,
          cli_get_session: Any,
      ) -> None:
          runner = CliRunner()
          invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
          result = invoke(runner, ["approve", "I-00001"], cli_get_session)
  >       assert result.exit_code == 0, result.output
  E       AssertionError: Error: Active directory not found: ai-dev/active/I-00001/. Create the design doc and prompts before approving.
  E         
  E       assert 1 == 0
  E        +  where 1 = <Result SystemExit(1)>.exit_code
  tests/integration/test_cli_core.py:384: AssertionError
  ___________________________ test_approve_json_output ___________________________
  db_session = <sqlalchemy.orm.session.Session object at 0x7ad0ba639610>
  test_project = <orch.db.models.Project object at 0x7ad0ba639e80>
  cli_get_session = <function cli_get_session.<locals>._get_session at 0x7ad0c0394220>
      def test_approve_json_output(
          db_session: Any,
          test_project: Project,
          cli_get_session: Any,
      ) -> None:
          runner = CliRunner()
          invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
          result = runner.invoke(
              cli,
              ["--project", "test-proj", "--json", "approve", "I-00001"],
              obj={"get_session": cli_get_session},
              catch_exceptions=False,
          )
  >       assert result.exit_code == 0
  E       assert 1 == 0
  E        +  where 1 = <Result SystemExit(1)>.exit_code
  tests/integration/test_cli_core.py:405: AssertionError
  _______________________ test_unapprove_approved_to_draft _______________________
  db_session = <sqlalchemy.orm.session.Session object at 0x7ad0bac507d0>
  test_project = <orch.db.models.Project object at 0x7ad0bac53620>
  cli_get_session = <function cli_get_session.<locals>._get_session at 0x7ad0c0394360>
      def test_unapprove_approved_to_draft(
          db_session: Any,
          test_project: Project,
          cli_get_session: Any,
      ) -> None:
          runner = CliRunner()
          invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
          invoke(runner, ["approve", "I-00001"], cli_get_session)
          result = invoke(runner, ["unapprove", "I-00001"], cli_get_session)
  >       assert result.exit_code == 0, result.output
  E       AssertionError: Error: Cannot unapprove: current status is 'draft'
  E         
  E       assert 1 == 0
  E        +  where 1 = <Result SystemExit(1)>.exit_code
  tests/integration/test_cli_core.py:448: AssertionError
  _____________________ test_unapprove_completed_batch_is_ok _____________________
  db_session = <sqlalchemy.orm.session.Session object at 0x7ad0bac511f0>
  test_project = <orch.db.models.Project object at 0x7ad0bac51550>
  cli_get_session = <function cli_get_session.<locals>._get_session at 0x7ad0c01a4900>
      def test_unapprove_completed_batch_is_ok(
          db_session: Any,
          test_project: Project,
          cli_get_session: Any,
      ) -> None:
          runner = CliRunner()
          invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
          invoke(runner, ["approve", "I-00001"], cli_get_session)
          batch = Batch(
              project_id="test-proj",
              id="BATCH-00001",
              status=BatchStatus.completed,
              cli_tool="opencode",
          )
          db_session.add(batch)
          db_session.flush()
          db_session.add(
              BatchItem(
                  project_id="test-proj",
                  batch_id="BATCH-00001",
                  work_item_id="I-00001",
                  status=BatchItemStatus.merged,
              )
          )
          db_session.flush()
          result = invoke(runner, ["unapprove", "I-00001"], cli_get_session)
  >       assert result.exit_code == 0
  E       assert 1 == 0
  E        +  where 1 = <Result SystemExit(1)>.exit_code
  tests/integration/test_cli_core.py:516: AssertionError
  ___________________ test_full_flow_next_id_register_approve ____________________
  db_session = <sqlalchemy.orm.session.Session object at 0x7ad0bac52420>
  test_project = <orch.db.models.Project object at 0x7ad0bac51ac0>
  cli_get_session = <function cli_get_session.<locals>._get_session at 0x7ad0c03965c0>
      def test_full_flow_next_id_register_approve(
          db_session: Any,
          test_project: Project,
          cli_get_session: Any,
      ) -> None:
          runner = CliRunner()
          result = runner.invoke(
              cli,
              ["--project", "test-proj", "--json", "next-id", "--type", "incident"],
              obj={"get_session": cli_get_session},
              catch_exceptions=False,
          )
          assert result.exit_code == 0
          item_id = json.loads(result.output)["id"]
          assert item_id.startswith("I-")
          result = runner.invoke(
              cli,
              [
                  "--project",
                  "test-proj",
                  "--json",
                  "register",
                  item_id,
                  "Full flow test",
                  "--type",
                  "incident",
              ],
              obj={"get_session": cli_get_session},
              catch_exceptions=False,
          )
          assert result.exit_code == 0
          assert json.loads(result.output)["created"] is True
          result = runner.invoke(
              cli,
              ["--project", "test-proj", "--json", "approve", item_id],
              obj={"get_session": cli_get_session},
              catch_exceptions=False,
          )
  >       assert result.exit_code == 0
  E       assert 1 == 0
  E        +  where 1 = <Result SystemExit(1)>.exit_code
  tests/integration/test_cli_core.py:565: AssertionError
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  tests/integration/test_migration_pipeline.py:89
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_migration_pipeline.py:89: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:96
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_migration_pipeline.py:96: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:119
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_migration_pipeline.py:119: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:172
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_migration_pipeline.py:172: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_migration_pipeline.py:210
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_migration_pipeline.py:210: PytestUnknownMarkWarning: Unknown pytest.mark.slow - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
      @pytest.mark.slow
  tests/integration/test_boundary_behavior_f00060.py::TestBoundaryZeroWorkItems::test_empty_project_returns_empty_bundle_no_error
  tests/integration/test_boundary_behavior_f00060.py::TestBoundarySemanticIndexMissing::test_missing_lancedb_table_treated_as_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/qa.py:358: DeprecationWarning: table_names() is deprecated, use list_tables() instead
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
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/doc_indexer.py:141: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      return self._table_name() in db.table_names()
  tests/integration/test_boundary_behavior_f00060.py: 6 warnings
  tests/integration/test_doc_index_job_runner.py: 3 warnings
  tests/integration/test_doc_index_poller.py: 2 warnings
  tests/integration/test_doc_indexer.py: 8 warnings
  tests/integration/test_invariants_f00060.py: 1 warning
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/doc_indexer.py:208: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in db.table_names():
  tests/integration/test_boundary_behavior_f00060.py::TestBoundaryEmbedModelChange::test_embed_model_change_drops_and_reindexes
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/doc_indexer.py:173: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if self._table_name() in db.table_names():
  tests/integration/test_code_index_job.py::TestCodeIndexJobFKConstraints::test_code_index_job_fk_invalid_project
  tests/integration/test_models.py::test_duplicate_item_id_in_same_project_rejected
  tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_project_created_in_db
  tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected
  tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_used_for_search_query
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/conftest.py:135: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
  tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc
  tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
  tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/.venv/lib/python3.12/site-packages/llama_index/vector_stores/lancedb/base.py:319: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      page = list(self._connection.table_names(page_token))
  tests/integration/test_code_index_pipeline.py::test_full_index_cycle
  tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
  tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in db.table_names():
  tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
  tests/integration/test_oss_dashboard_routes.py::TestOssSseEventOrder::test_stream_emits_status_and_complete_events
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_row_update_events
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_row_update_event_data_shape
  tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end
  tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/integration/test_doc_index_poller.py::TestDocIndexPollerStallDetection::test_stalled_job_marked_failed
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/.venv/lib/python3.12/site-packages/_pytest/stash.py:108: RuntimeWarning: coroutine 'DocIndexJobRunner.run' was never awaited
      del self._storage[key]
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_doc_indexer.py:144: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
  tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/doc_indexer.py:349: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in lancedb_uri.table_names():
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/orch/rag/doc_indexer.py:365: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in ldb_uri.table_names():
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_doc_indexer.py:283: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      if table_name in db.table_names():
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_doc_indexer.py:345: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      assert table_name in db.table_names()
  tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_doc_indexer.py:364: DeprecationWarning: table_names() is deprecated, use list_tables() instead
      assert table_name in db.table_names()
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
  tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_oss_migration.py:231: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  tests/integration/test_project_docs.py::test_project_doc_unique_constraint
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7ad06ae1cbc0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7ad0c0a897c0>
      db_session.flush()
  tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  tests/integration/test_step_monitor_lifecycle.py::test_full_lifecycle_emits_single_warn_then_idempotent
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00064/.venv/lib/python3.12/site-packages/psycopg/_column.py:61: RuntimeWarning: coroutine 'sleep' was never awaited
      def __getitem__(self, index: Any) -> Any:
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  make: *** [Makefile:39: test-integration] Error 1
  **FAIL** - 5 failed, 1129 passed
  Failures are all in `test_cli_core.py` - approve/unapprove commands require `ai-dev/active/<item>/` directory which doesn't exist in test environment.
  $ mkdir -p ai-dev/active/F-00064/reports
  (no output)
  ← Write ai-dev/active/F-00064/reports/F-00064_S12_QvGate_report.md
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
