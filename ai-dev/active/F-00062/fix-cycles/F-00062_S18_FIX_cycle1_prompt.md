# F-00062 S18 QV Fix Cycle 1/5

Quality gate S18 for work item F-00062 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 2 unit tests failed in test_worktree_compose.py::TestDiscoverPorts - test assertions expect integer but receive string port values

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00062 --step S18
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started F-00062 step S18 (already in progress)
  $ make test-unit
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dc6c76875001Jum2HT6vHb6lhp
  tests/unit/test_qa_v2_relevance_filter_eval.py::TestRelevanceFilterRegression::test_filter_drops_off_topic_items_mentions_only_color_change PASSED [ 76%]
  tests/unit/test_qa_v2_relevance_filter_eval.py::TestRelevanceFilterRegression::test_filter_removes_hallucinated_id_not_in_bundle PASSED [ 76%]
  tests/unit/test_qa_v2_relevance_filter_eval.py::TestRelevanceFilterRegression::test_llm_mentions_zero_ids_emits_no_citations PASSED [ 76%]
  tests/unit/test_qa_v2_relevance_filter_eval.py::TestRelevanceFilterRegression::test_filter_respects_allowed_ids_superset_not_subset PASSED [ 76%]
  tests/unit/test_qa_v2_relevance_filter_eval.py::TestRelevanceFilterRegression::test_functional_doc_content_used_in_snippet_not_summary PASSED [ 76%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigDefaults::test_default_provider_is_local PASSED [ 76%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigDefaults::test_default_index_tier_is_balanced PASSED [ 76%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigDefaults::test_default_llm_model_is_none PASSED [ 76%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigDefaults::test_default_embed_model_is_none PASSED [ 76%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigDefaults::test_default_ollama_url PASSED [ 76%]
  tests/unit/test_rag_config.py::TestResolvedLlmModel::test_fast_tier_default PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedLlmModel::test_balanced_tier_default PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedLlmModel::test_quality_tier_default PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedLlmModel::test_explicit_override_wins PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedEmbedModel::test_fast_tier_default PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedEmbedModel::test_balanced_tier_default PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedEmbedModel::test_quality_tier_default PASSED [ 77%]
  tests/unit/test_rag_config.py::TestResolvedEmbedModel::test_explicit_override_wins PASSED [ 77%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigValidation::test_invalid_provider_raises PASSED [ 77%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigValidation::test_invalid_index_tier_raises PASSED [ 77%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigValidation::test_valid_provider_local PASSED [ 77%]
  tests/unit/test_rag_config.py::TestCodeUnderstandingConfigValidation::test_valid_tier_values PASSED [ 77%]
  tests/unit/test_rag_config.py::TestTierDefaults::test_all_tiers_have_defaults PASSED [ 77%]
  tests/unit/test_rag_config.py::TestTierDefaults::test_no_none_in_defaults PASSED [ 77%]
  tests/unit/test_rag_config.py::TestIndexPathConfig::test_default_index_path PASSED [ 77%]
  tests/unit/test_rag_config.py::TestIndexPathConfig::test_custom_index_path PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestIndexDesignDocsFunctionExists::test_function_is_importable PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestIndexDesignDocsChunking::test_chunking_respects_chunk_size PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestIndexDesignDocsChunking::test_single_chunk_when_under_threshold PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestSkipOnNullDesignDoc::test_null_content_not_indexed PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestSummaryOnlyFallback::test_summary_only_item_emits_one_row PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestIncrementalModeFilter::test_incremental_filters_by_updated_at PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestIncrementalModeFilter::test_incremental_uses_merge_insert_not_delete_reinsert PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestMapgenOnlyBypassesDocs::test_mapgen_only_does_not_call_docs_indexer PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestDocIndexResult::test_doc_index_result_fields PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestDocIndexResult::test_doc_index_result_default_errors_empty PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestDocsTableSchema::test_table_name_hyphen_to_underscore PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestProgressEvents::test_emits_indexing_docs_phase PASSED [ 78%]
  tests/unit/test_rag_docs_indexer.py::TestEmbeddingModel::test_uses_resolved_embed_model PASSED [ 78%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocHappyPath::test_valid_doc_passes PASSED [ 78%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocHappyPath::test_valid_doc_at_word_boundary_500 PASSED [ 78%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocStructural::test_missing_file_blocks PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocStructural::test_missing_h2_why_blocks PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocStructural::test_missing_h2_what_changed_blocks PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocStructural::test_missing_h2_how_it_behaves_blocks PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocWordCount::test_499_words_passes PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocWordCount::test_500_words_passes PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocWordCount::test_501_words_blocks PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.py] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.md] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.sql] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.js] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.ts] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.tsx] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.html] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.json] PASSED [ 79%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.toml] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.yaml] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_file_extension_triggers_warning[.yml] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[orch/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[dashboard/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[scripts/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[ai-dev/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[tests/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[skills/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[templates/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_path_fragment_triggers_warning[executor/] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_sql_ddl_triggers_warning[ALTER TABLE work_items ADD COLUMN] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_sql_ddl_triggers_warning[alter table work_items add column] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_sql_ddl_triggers_warning[CREATE TABLE new_table] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_sql_ddl_triggers_warning[DROP TABLE old_table] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_sql_ddl_triggers_warning[INSERT INTO work_items] PASSED [ 80%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_sql_ddl_triggers_warning[SELECT * FROM work_items] PASSED [ 81%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocForbiddenTerms::test_code_fence_triggers_warning PASSED [ 81%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocCombined::test_structural_and_content_issues_both_reported PASSED [ 81%]
  tests/unit/test_review_design_functional_validation.py::TestValidateFunctionalDocCombined::test_structural_failure_drives_blocking_not_content PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_false PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_absent PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_raises_when_env_true PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestDryRun::test_dry_run_refuses_live_url PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestListPendingRevisions::test_multiple_heads_raises PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestIsLiveDbUrl::test_is_live_db_url_matches_config PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestBuildAlembicConfig::test_build_alembic_config_override_respected PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestBuildAlembicConfig::test_build_alembic_config_falls_back_to_default PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestWriteMigrationLog::test_write_migration_log_old_revision_persisted PASSED [ 81%]
  tests/unit/test_safe_migrate.py::TestWriteMigrationLog::test_write_migration_log_backward_compat_no_old_revision PASSED [ 82%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_when_agent_context PASSED [ 82%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set PASSED [ 82%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag PASSED [ 82%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant PASSED [ 82%]
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None] PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true PASSED [ 82%]
  tests/unit/test_safe_migrate_guards.py::TestDryRunLiveDbUrlGuard::test_raises_value_error_when_tempdb_equals_live PASSED [ 83%]
  tests/unit/test_safe_migrate_guards.py::TestListPendingRevisionsEmptyDb::test_returns_all_revisions_when_db_is_empty PASSED [ 83%]
  tests/unit/test_safe_migrate_guards.py::TestMultipleHeadsErrorArgs::test_args_contains_both_heads PASSED [ 83%]
  tests/unit/test_safe_migrate_guards.py::TestMigrationLogWrittenOnAlembicFailure::test_apply_logs_when_alembic_raises PASSED [ 83%]
  tests/unit/test_safe_migrate_guards.py::TestMigrationLogWrittenOnAlembicFailure::test_rollback_logs_when_alembic_raises PASSED [ 83%]
  tests/unit/test_skill_sync.py::test_parse_version_basic PASSED           [ 83%]
  tests/unit/test_skill_sync.py::test_parse_version_with_quotes PASSED     [ 83%]
  tests/unit/test_skill_sync.py::test_parse_version_no_frontmatter PASSED  [ 83%]
  tests/unit/test_skill_sync.py::test_parse_version_missing_version_key PASSED [ 83%]
  tests/unit/test_skill_sync.py::test_parse_version_missing_file PASSED    [ 83%]
  tests/unit/test_skill_sync.py::test_new_skill_is_copied PASSED           [ 83%]
  tests/unit/test_skill_sync.py::test_outdated_skill_is_updated PASSED     [ 83%]
  tests/unit/test_skill_sync.py::test_uptodate_skill_is_skipped PASSED     [ 83%]
  tests/unit/test_skill_sync.py::test_project_override_not_overwritten PASSED [ 83%]
  tests/unit/test_skill_sync.py::test_force_overwrites_project_override PASSED [ 83%]
  tests/unit/test_skill_sync.py::test_check_only_no_files_modified PASSED  [ 84%]
  tests/unit/test_skill_sync.py::test_lock_file_created_on_first_sync PASSED [ 84%]
  tests/unit/test_skill_sync.py::test_lock_file_updated_on_subsequent_sync PASSED [ 84%]
  tests/unit/test_skill_sync.py::test_unlocked_existing_skill_treated_as_override PASSED [ 84%]
  tests/unit/test_skill_sync.py::test_empty_skills_dir_no_changes PASSED   [ 84%]
  tests/unit/test_skill_sync.py::test_skill_missing_manifest_records_error PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.draft-WorkItemStatus.approved] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.approved-WorkItemStatus.draft] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.approved-WorkItemStatus.in_progress] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.in_progress-WorkItemStatus.completed] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.in_progress-WorkItemStatus.failed] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.in_progress-WorkItemStatus.paused] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.paused-WorkItemStatus.in_progress] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_valid[WorkItemStatus.failed-WorkItemStatus.in_progress] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.draft-WorkItemStatus.draft] PASSED [ 84%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.in_progress-WorkItemStatus.in_progress] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.completed-WorkItemStatus.completed] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.draft-WorkItemStatus.in_progress] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.draft-WorkItemStatus.completed] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.draft-WorkItemStatus.failed] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.completed-WorkItemStatus.draft] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.completed-WorkItemStatus.approved] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.completed-WorkItemStatus.in_progress] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.paused-WorkItemStatus.completed] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_status_invalid[WorkItemStatus.paused-WorkItemStatus.approved] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_valid[WorkItemPhase.active-WorkItemPhase.work] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_valid[WorkItemPhase.work-WorkItemPhase.done] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_invalid[WorkItemPhase.active-WorkItemPhase.active] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_invalid[WorkItemPhase.active-WorkItemPhase.done] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_invalid[WorkItemPhase.work-WorkItemPhase.active] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_invalid[WorkItemPhase.done-WorkItemPhase.active] PASSED [ 85%]
  tests/unit/test_state_machine.py::test_work_item_phase_invalid[WorkItemPhase.done-WorkItemPhase.work] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_work_item_phase_invalid[WorkItemPhase.done-WorkItemPhase.done] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.pending-StepStatus.in_progress] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.in_progress-StepStatus.completed] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.in_progress-StepStatus.failed] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.in_progress-StepStatus.needs_fix] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.needs_fix-StepStatus.in_progress] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.needs_fix-StepStatus.failed] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.failed-StepStatus.pending] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_valid[StepStatus.failed-StepStatus.skipped] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.pending-StepStatus.pending] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.in_progress-StepStatus.in_progress] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.completed-StepStatus.completed] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.completed-StepStatus.pending] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.completed-StepStatus.in_progress] PASSED [ 86%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.completed-StepStatus.failed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.skipped-StepStatus.pending] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.skipped-StepStatus.in_progress] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.pending-StepStatus.completed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.pending-StepStatus.failed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.pending-StepStatus.needs_fix] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.needs_fix-StepStatus.completed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_step_status_invalid[StepStatus.needs_fix-StepStatus.skipped] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_valid[RunStatus.pending-RunStatus.running] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_valid[RunStatus.running-RunStatus.completed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_valid[RunStatus.running-RunStatus.failed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_valid[RunStatus.running-RunStatus.timeout] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_valid[RunStatus.running-RunStatus.killed] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_valid[RunStatus.running-RunStatus.stalled] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.pending-RunStatus.pending] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.running-RunStatus.running] PASSED [ 87%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.completed-RunStatus.completed] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.completed-RunStatus.pending] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.completed-RunStatus.running] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.failed-RunStatus.running] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.timeout-RunStatus.running] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.killed-RunStatus.running] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.stalled-RunStatus.running] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.pending-RunStatus.completed] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.pending-RunStatus.failed] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_run_status_invalid[RunStatus.pending-RunStatus.timeout] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.planning-BatchStatus.approved] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.planning-BatchStatus.archived] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.approved-BatchStatus.executing] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.approved-BatchStatus.archived] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.executing-BatchStatus.paused] PASSED [ 88%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.executing-BatchStatus.completed] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.executing-BatchStatus.completed_with_errors] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.paused-BatchStatus.executing] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.paused-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.completed-BatchStatus.publishing] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.completed-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.completed_with_errors-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.publishing-BatchStatus.published] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.publishing-BatchStatus.publish_failed] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.published-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.publish_failed-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_valid[BatchStatus.blocked-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.planning-BatchStatus.planning] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.executing-BatchStatus.executing] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.archived-BatchStatus.archived] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.archived-BatchStatus.planning] PASSED [ 89%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.archived-BatchStatus.approved] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.planning-BatchStatus.executing] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.planning-BatchStatus.completed] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.approved-BatchStatus.completed] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.executing-BatchStatus.published] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.completed-BatchStatus.executing] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_status_invalid[BatchStatus.published-BatchStatus.publishing] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.pending-BatchItemStatus.setting_up] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.setting_up-BatchItemStatus.executing] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.setting_up-BatchItemStatus.failed] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.executing-BatchItemStatus.completed] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.executing-BatchItemStatus.failed] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.executing-BatchItemStatus.stalled] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.completed-BatchItemStatus.merged] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.failed-BatchItemStatus.pending] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_valid[BatchItemStatus.stalled-BatchItemStatus.pending] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.pending-BatchItemStatus.pending] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.executing-BatchItemStatus.executing] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.merged-BatchItemStatus.merged] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.merged-BatchItemStatus.pending] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.merged-BatchItemStatus.executing] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.skipped-BatchItemStatus.pending] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.skipped-BatchItemStatus.executing] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.pending-BatchItemStatus.executing] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.pending-BatchItemStatus.completed] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.setting_up-BatchItemStatus.completed] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.setting_up-BatchItemStatus.merged] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.executing-BatchItemStatus.merged] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.completed-BatchItemStatus.pending] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.completed-BatchItemStatus.executing] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_invalid_transition_message_includes_values PASSED [ 91%]
  tests/unit/test_state_machine.py::test_invalid_transition_message_includes_entity_type PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Research-True] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.failed-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.paused-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.completed-WorkItemStatus.draft-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.completed-WorkItemStatus.approved-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.completed-WorkItemStatus.in_progress-WorkItemType.Research-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Feature-True] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Feature-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-WorkItemType.Feature-False] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.approved-WorkItemStatus.in_progress-WorkItemType.ChangeRequest-True] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.approved-WorkItemStatus.draft-WorkItemType.Issue-True] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.in_progress-WorkItemStatus.completed-WorkItemType.Feature-True] PASSED [ 92%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-None-True] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-None-False] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-None-False] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Research-True] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Feature-True] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.approved-WorkItemStatus.in_progress-WorkItemType.ChangeRequest-True] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-None-True] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Research-False] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-WorkItemType.Research-False] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.completed-WorkItemStatus.draft-WorkItemType.Research-False] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Feature-False] PASSED [ 93%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-None-False] PASSED [ 93%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_styles_css_exists_and_non_empty PASSED [ 93%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_inter_woff2_files_exist PASSED [ 93%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_theme_css_exists PASSED [ 93%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_vendor_htmx_exists PASSED [ 93%]
  tests/unit/test_static_assets.py::TestStylesCssContent::test_styles_css_contains_tailwind_directives PASSED [ 94%]
  tests/unit/test_static_assets.py::TestStylesCssContent::test_theme_css_contains_font_face PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_valid[StepStatus.failed] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_valid[StepStatus.needs_fix] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.pending] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.in_progress] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.completed] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.skipped] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_valid PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.pending] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.in_progress] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.completed] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.needs_fix] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.skipped] PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_valid PASSED [ 94%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.pending] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.completed] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.failed] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.needs_fix] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.skipped] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.implementation] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.code_review] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.code_review_final] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.quality_validation] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.qv_fix] PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_screenshot_passes PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_missing_dir_fails PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_empty_dir_fails PASSED [ 95%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_only_subdirs_fails PASSED [ 95%]
  tests/unit/test_step_monitor.py::test_pid_alive_within_timeout_no_action PASSED [ 95%]
  tests/unit/test_step_monitor.py::test_pid_dead_marks_failed PASSED       [ 95%]
  tests/unit/test_step_monitor.py::test_pid_none_marks_failed PASSED       [ 96%]
  tests/unit/test_step_monitor.py::test_pid_permission_error_treated_as_dead PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_pid_alive_timeout_exceeded PASSED  [ 96%]
  tests/unit/test_step_monitor.py::test_timeout_skipped_when_started_at_is_none PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_timeout_skipped_when_timeout_secs_is_none PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_pid_alive_stalled PASSED           [ 96%]
  tests/unit/test_step_monitor.py::test_stall_skipped_when_heartbeat_is_none PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_stall_not_triggered_when_heartbeat_fresh PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_timeout_takes_priority_over_stall PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_get_timeout_step_config_override PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_get_timeout_project_override PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_get_timeout_platform_default PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_get_timeout_fallback_for_unknown_step_type PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_get_timeout_step_config_empty_no_key PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_get_timeout_all_platform_defaults PASSED [ 96%]
  tests/unit/test_step_monitor.py::test_kill_process_sends_sigterm_returns_true PASSED [ 97%]
  tests/unit/test_step_monitor.py::test_kill_process_dead_pid_returns_false PASSED [ 97%]
  tests/unit/test_step_monitor.py::test_kill_process_does_not_raise_on_dead_pid PASSED [ 97%]
  tests/unit/test_step_monitor.py::test_no_running_steps_commits_and_returns PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveExecutionDir::test_uses_test_config_for_test_run_type PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveExecutionDir::test_uses_quality_config_for_quality_run_type PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveExecutionDir::test_returns_none_when_project_not_found PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveExecutionDir::test_returns_none_when_execution_dir_missing_in_config PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveExecutionDir::test_quality_returns_none_when_quality_config_missing PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveAllureDirs::test_uses_test_config_for_test_run_type PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveAllureDirs::test_uses_quality_config_for_quality_run_type PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveAllureDirs::test_falls_back_to_defaults_for_test_run_type PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveAllureDirs::test_falls_back_to_defaults_for_quality_run_type PASSED [ 97%]
  tests/unit/test_test_runner.py::TestResolveAllureDirs::test_returns_none_when_project_not_found PASSED [ 97%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_emits_test_started_on_begin PASSED [ 97%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_emits_test_completed_on_success PASSED [ 97%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_emits_test_failed_on_failure PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_does_not_emit_quality_events PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_started_on_begin PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_completed_on_success PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_failed_on_failure PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_does_not_emit_test_events PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_test_run_cleans_allure_results PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_test_run_generates_allure_report PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_quality_run_skips_allure_cleanup PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_quality_run_skips_allure_report_generation PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestQueryCountCtx::test_default_zero PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestQueryCountCtx::test_increment_and_get PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestQueryCountCtx::test_reset PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_instantiation_with_engine PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_default_threshold_is_500 PASSED [ 98%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_emits_warn_above_threshold PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_warn_log_contains_required_fields PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_debug_log_below_threshold PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_pool_status_in_log PASSED [ 99%]
  tests/unit/test_timing_middleware.py::TestTimingMiddleware::test_does_not_swallow_upstream_exceptions PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_hit_returns_cached_value PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_miss_returns_none_for_missing_key PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_expired_key_returns_none PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_delete_removes_key PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_clear_removes_all_keys PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_concurrent_access_does_not_crash PASSED [ 99%]
  tests/unit/test_ttl_cache.py::TestTTLCache::test_stats_hit_miss PASSED   [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_badge_returns_from_cache_on_second_call_within_ttl PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_badge_returns_cached_value_after_expiry PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_cached_fn_provides_hit_miss_stats PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestWorktreePageCaching::test_collect_worktrees_returns_same_value_from_cache PASSED [100%]
  ___________ TestDiscoverPorts.test_parses_docker_compose_port_output ___________
  self = <test_worktree_compose.TestDiscoverPorts object at 0x7dc3d74c7140>
  tmp_path = PosixPath('/tmp/pytest-of-sergiog/pytest-2527/test_parses_docker_compose_por0')
      def test_parses_docker_compose_port_output(self, tmp_path: Path) -> None:
          worktree = tmp_path / "worktree"
          worktree.mkdir()
          iw_dir = worktree / ".iw"
          iw_dir.mkdir()
          iw_config = worktree / "ai-dev" / "iw-config"
          iw_config.mkdir(parents=True)
          template = iw_config / "worktree-compose.template.yml"
          template.write_text("services:\n  db:\n    image: postgres")
          env_toml = iw_config / "worktree-env.toml"
          env_toml.write_text(
              '[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"\n"app:9900" = "IW_CORE_DASHBOARD_PORT"'
          )
          compose_file = iw_dir / "docker-compose-F-00062.yml"
          compose_file.write_text("services:\n  db:\n    image: postgres")
          cfg = load_config("F-00062", "iw-ai-core", worktree)
          with patch("subprocess.run") as mock_run:
              mock_run.return_value = MagicMock(
                  returncode=0,
                  stdout="0.0.0.0:34567\n",
                  stderr="",
              )
              ports = discover_ports(cfg)
          assert "IW_CORE_DB_PORT" in ports
  >       assert ports["IW_CORE_DB_PORT"] == 34567
  E       AssertionError: assert '34567' == 34567
  tests/unit/daemon/test_worktree_compose.py:234: AssertionError
  __________________ TestDiscoverPorts.test_handles_ipv6_output __________________
  self = <test_worktree_compose.TestDiscoverPorts object at 0x7dc3d74c7800>
  tmp_path = PosixPath('/tmp/pytest-of-sergiog/pytest-2527/test_handles_ipv6_output0')
      def test_handles_ipv6_output(self, tmp_path: Path) -> None:
          worktree = tmp_path / "worktree"
          worktree.mkdir()
          iw_dir = worktree / ".iw"
          iw_dir.mkdir()
          iw_config = worktree / "ai-dev" / "iw-config"
          iw_config.mkdir(parents=True)
          template = iw_config / "worktree-compose.template.yml"
          template.write_text("services:\n  db:\n    image: postgres")
          env_toml = iw_config / "worktree-env.toml"
          env_toml.write_text('[port_to_env]\n"db:5432" = "IW_CORE_DB_PORT"')
          compose_file = iw_dir / "docker-compose-F-00062.yml"
          compose_file.write_text("services:\n  db:\n    image: postgres")
          cfg = load_config("F-00062", "iw-ai-core", worktree)
          with patch("subprocess.run") as mock_run:
              mock_run.return_value = MagicMock(
                  returncode=0,
                  stdout="[::]:54321\n",
                  stderr="",
              )
              ports = discover_ports(cfg)
  >       assert ports["IW_CORE_DB_PORT"] == 54321
  E       AssertionError: assert '54321' == 54321
  tests/unit/daemon/test_worktree_compose.py:262: AssertionError
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  orch/db/models.py:175
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/orch/db/models.py:175: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/test_code_qa_router_rerender.py: 1 warning
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_v2_prompt_layout.py: 8 warnings
  tests/unit/test_qa_v2_relevance_filter_eval.py: 5 warnings
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/unit/test_code_ui_routes.py::TestCodeIndexStream::test_sse_stream_returns_idle_when_no_runner_in_registry
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_falls_back_when_module_filter_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/tests/unit/test_qa_engine.py:625: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/tests/unit/test_qa_engine.py:723: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/tests/unit/test_qa_engine.py:819: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00062/tests/unit/test_qa_engine.py:905: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  make: *** [Makefile:36: test-unit] Error 1
  $ mkdir -p ai-dev/active/F-00062/reports
  (no output)
  ← Write ai-dev/active/F-00062/reports/F-00062_S18_QvGate_report.md
  Wrote file successfully.


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
