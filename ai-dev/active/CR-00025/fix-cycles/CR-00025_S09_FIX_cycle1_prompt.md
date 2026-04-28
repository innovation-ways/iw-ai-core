# CR-00025 S09 QV Fix Cycle 1/5

Quality gate S09 for work item CR-00025 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 12 unit tests in test_db_identity.py have fixture errors (db_session depends on _db_test_connection which is integration-only)

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start CR-00025 --step S09
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started CR-00025 step S09 (already in progress)
  $ make test-unit
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dd63d94b40015mKK7aR6yao2CP
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.executing-BatchItemStatus.merged] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.completed-BatchItemStatus.pending] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_batch_item_status_invalid[BatchItemStatus.completed-BatchItemStatus.executing] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_invalid_transition_message_includes_values PASSED [ 90%]
  tests/unit/test_state_machine.py::test_invalid_transition_message_includes_entity_type PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Research-True] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.failed-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.paused-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.completed-WorkItemStatus.draft-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.completed-WorkItemStatus.approved-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.completed-WorkItemStatus.in_progress-WorkItemType.Research-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Feature-True] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Feature-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-WorkItemType.Feature-False] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.approved-WorkItemStatus.in_progress-WorkItemType.ChangeRequest-True] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.approved-WorkItemStatus.draft-WorkItemType.Issue-True] PASSED [ 90%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.in_progress-WorkItemStatus.completed-WorkItemType.Feature-True] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-None-True] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-None-False] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_work_item_status_transitions_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-None-False] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Research-True] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Feature-True] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.approved-WorkItemStatus.in_progress-WorkItemType.ChangeRequest-True] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-None-True] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.approved-WorkItemType.Research-False] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-WorkItemType.Research-False] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.completed-WorkItemStatus.draft-WorkItemType.Research-False] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.completed-WorkItemType.Feature-False] PASSED [ 91%]
  tests/unit/test_state_machine.py::test_validate_work_item_status_type_aware[WorkItemStatus.draft-WorkItemStatus.in_progress-None-False] PASSED [ 91%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_styles_css_exists_and_non_empty PASSED [ 91%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_inter_woff2_files_exist PASSED [ 91%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_theme_css_exists PASSED [ 91%]
  tests/unit/test_static_assets.py::TestStaticAssets::test_vendor_htmx_exists PASSED [ 91%]
  tests/unit/test_static_assets.py::TestStylesCssContent::test_styles_css_contains_tailwind_directives PASSED [ 91%]
  tests/unit/test_static_assets.py::TestStylesCssContent::test_theme_css_contains_font_face PASSED [ 91%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_valid[StepStatus.failed] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_valid[StepStatus.needs_fix] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.pending] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.in_progress] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.completed] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepRestartTransition::test_invalid[StepStatus.skipped] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_valid PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.pending] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.in_progress] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.completed] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.needs_fix] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepSkipTransition::test_invalid[StepStatus.skipped] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_valid PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.pending] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.completed] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.failed] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.needs_fix] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateStepKillTransition::test_invalid[StepStatus.skipped] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.implementation] PASSED [ 92%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.code_review] PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.code_review_final] PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.quality_validation] PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_non_browser_step_types_short_circuit_to_none[StepType.qv_fix] PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_screenshot_passes PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_missing_dir_fails PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_empty_dir_fails PASSED [ 93%]
  tests/unit/test_step_commands.py::TestValidateBrowserEvidencePresent::test_browser_step_with_only_subdirs_fails PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_pid_alive_within_timeout_no_action PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_pid_dead_marks_failed PASSED       [ 93%]
  tests/unit/test_step_monitor.py::test_pid_none_marks_failed PASSED       [ 93%]
  tests/unit/test_step_monitor.py::test_pid_permission_error_treated_as_dead PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_pid_alive_timeout_exceeded PASSED  [ 93%]
  tests/unit/test_step_monitor.py::test_timeout_skipped_when_started_at_is_none PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_timeout_skipped_when_timeout_secs_is_none PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_pid_alive_stalled PASSED           [ 93%]
  tests/unit/test_step_monitor.py::test_stall_skipped_when_heartbeat_is_none PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_stall_not_triggered_when_heartbeat_fresh PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_timeout_takes_priority_over_stall PASSED [ 93%]
  tests/unit/test_step_monitor.py::test_get_timeout_step_config_override PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_get_timeout_project_override PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_get_timeout_platform_default PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_get_timeout_fallback_for_unknown_step_type PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_get_timeout_step_config_empty_no_key PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_get_timeout_all_platform_defaults PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_group_uses_killpg_when_getpgid_succeeds PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_group_falls_back_to_os_kill_when_getpgid_raises PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_group_returns_false_when_process_already_dead PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_group_does_not_raise PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_delegates_to_kill_process_group PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_dead_pid_returns_false PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_kill_process_does_not_raise_on_dead_pid PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_hard_stall_kills_and_fails_step PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_soft_stall_does_not_kill_or_fail PASSED [ 94%]
  tests/unit/test_step_monitor.py::test_no_running_steps_commits_and_returns PASSED [ 94%]
  tests/unit/test_step_monitor_get_timeout.py::test_integration_tests_gate_returns_900_not_600 PASSED [ 94%]
  tests/unit/test_step_monitor_get_timeout.py::test_lint_gate_returns_120 PASSED [ 94%]
  tests/unit/test_step_monitor_get_timeout.py::test_format_gate_returns_120 PASSED [ 94%]
  tests/unit/test_step_monitor_get_timeout.py::test_typecheck_gate_returns_240 PASSED [ 94%]
  tests/unit/test_step_monitor_get_timeout.py::test_unit_tests_gate_returns_300 PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_browser_gate_returns_1800 PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_all_qv_gate_defaults_are_consulted PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_legacy_null_gate_falls_through_to_quality_validation_default PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_no_step_argument_falls_through_to_quality_validation_default PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_unknown_gate_falls_through_to_per_type_bucket PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_step_config_override_beats_gate_default PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_project_override_beats_gate_default PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_step_config_beats_project_and_gate PASSED [ 95%]
  tests/unit/test_step_monitor_get_timeout.py::test_non_qv_step_with_gate_value_uses_step_type_bucket PASSED [ 95%]
  tests/unit/test_step_monitor_warn_50pct.py::test_warn_fires_when_past_50pct_and_marker_is_null PASSED [ 95%]
  tests/unit/test_step_monitor_warn_50pct.py::test_warn_does_not_fire_when_marker_already_set PASSED [ 95%]
  tests/unit/test_step_monitor_warn_50pct.py::test_warn_does_not_fire_below_50pct PASSED [ 95%]
  tests/unit/test_step_monitor_warn_50pct.py::test_warn_fires_only_once_across_two_poll_cycles PASSED [ 95%]
  tests/unit/test_step_monitor_warn_50pct.py::test_timeout_branch_shadows_warn_in_same_cycle PASSED [ 95%]
  tests/unit/test_step_monitor_warn_50pct.py::test_no_warn_when_timeout_secs_is_none PASSED [ 95%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[templates/design/Implementation_Prompt_Template.md] PASSED [ 95%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[templates/design/CodeReview_Prompt_Template.md] PASSED [ 95%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[templates/design/CodeReview_Final_Prompt_Template.md] PASSED [ 95%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[templates/design/QualityValidation_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[ai-dev/templates/Implementation_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[ai-dev/templates/CodeReview_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[ai-dev/templates/CodeReview_Final_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_in_scope_template_mentions_iw_item_status[ai-dev/templates/QualityValidation_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[templates/design/QualityValidation_FIX_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[templates/design/CodeReview_FIX_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[templates/design/CodeReview_FIX_Final_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[templates/design/QVBrowser_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[ai-dev/templates/QualityValidation_FIX_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[ai-dev/templates/CodeReview_FIX_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_out_of_scope_template_unchanged[ai-dev/templates/QVBrowser_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_implementation_template_has_preflight_section[templates/design/Implementation_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_implementation_template_has_preflight_section[ai-dev/templates/Implementation_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_implementation_template_contract_has_preflight_object[templates/design/Implementation_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_implementation_template_contract_has_preflight_object[ai-dev/templates/Implementation_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_non_implementation_template_lacks_preflight[templates/design/CodeReview_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_non_implementation_template_lacks_preflight[templates/design/CodeReview_Final_Prompt_Template.md] PASSED [ 96%]
  tests/unit/test_template_hints.py::test_non_implementation_template_lacks_preflight[templates/design/QualityValidation_Template.md] PASSED [ 97%]
  tests/unit/test_template_hints.py::test_non_implementation_template_lacks_preflight[ai-dev/templates/CodeReview_Prompt_Template.md] PASSED [ 97%]
  tests/unit/test_template_hints.py::test_non_implementation_template_lacks_preflight[ai-dev/templates/CodeReview_Final_Prompt_Template.md] PASSED [ 97%]
  tests/unit/test_template_hints.py::test_non_implementation_template_lacks_preflight[ai-dev/templates/QualityValidation_Template.md] PASSED [ 97%]
  tests/unit/test_template_hints.py::test_implementation_pair_pre_flight_blocks_match PASSED [ 97%]
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
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_emits_test_failed_on_failure PASSED [ 97%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_test_run_does_not_emit_quality_events PASSED [ 97%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_started_on_begin PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_completed_on_success PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_emits_quality_failed_on_failure PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunEventTypes::test_quality_run_does_not_emit_test_events PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_test_run_cleans_allure_results PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_test_run_generates_allure_report PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_quality_run_skips_allure_cleanup PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunAllureSkip::test_quality_run_skips_allure_report_generation PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_equals_is_rewritten_to_per_run_dir PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_space_separated_is_rewritten PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_with_custom_base_dir_is_rewritten PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_make_command_gets_allure_results_env_prefix PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_command_without_allure_flag_or_make_is_unchanged PASSED [ 98%]
  tests/unit/test_test_runner.py::TestLaunchTestRunCommandRewrite::test_pytest_alluredir_takes_precedence_over_make_branch PASSED [ 98%]
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
  tests/unit/test_worktree_setup_context_copy.py::test_context_files_exist_in_worktree_after_copy PASSED [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_copied_context_files_respect_exclude_patterns PASSED [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_worktree_exclude_file_contains_correct_patterns PASSED [ 99%]
  tests/unit/test_worktree_setup_context_copy.py::test_copy_step_is_silent_when_active_dir_missing PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_badge_returns_from_cache_on_second_call_within_ttl PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_badge_returns_cached_value_after_expiry PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestNavWorktreeBadgeCaching::test_cached_fn_provides_hit_miss_stats PASSED [ 99%]
  tests/unit/test_worktrees_caching.py::TestWorktreePageCaching::test_collect_worktrees_returns_same_value_from_cache PASSED [100%]
  ___________ ERROR at setup of TestGetLiveInstanceId.test_row_missing ___________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 55
        def test_row_missing(self, db_session: MagicMock) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ___________ ERROR at setup of TestGetLiveInstanceId.test_row_present ___________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 59
        def test_row_present(self, db_session: MagicMock) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ________________ ERROR at setup of TestCheckIdentity.test_match ________________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 69
        def test_match(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ______________ ERROR at setup of TestCheckIdentity.test_mismatch _______________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 82
        def test_mismatch(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ______________ ERROR at setup of TestCheckIdentity.test_bootstrap ______________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 96
        def test_bootstrap(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ___________ ERROR at setup of TestCheckIdentity.test_missing_env_set ___________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 109
        def test_missing_env_set(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  __________ ERROR at setup of TestCheckIdentity.test_missing_env_unset __________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 119
        def test_missing_env_unset(
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ___________ ERROR at setup of TestVerifyInstanceIdentity.test_match ____________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 133
        def test_match(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  _________ ERROR at setup of TestVerifyInstanceIdentity.test_bootstrap __________
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 145
        def test_bootstrap(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  ______ ERROR at setup of TestVerifyInstanceIdentity.test_mismatch_raises _______
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 156
        def test_mismatch_raises(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  _ ERROR at setup of TestVerifyInstanceIdentity.test_missing_row_with_env_set_raises _
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 171
        def test_missing_row_with_env_set_raises(
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  _ ERROR at setup of TestVerifyInstanceIdentity.test_missing_row_env_unset_does_not_raise _
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_db_identity.py, line 180
        def test_missing_row_env_unset_does_not_raise(
  file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py, line 139
    @pytest.fixture
    def db_session(_db_test_connection) -> Generator[Session, None, None]:
  E       fixture '_db_test_connection' not found
  >       available fixtures: _arm_live_db_guard, _class_scoped_runner, _function_scoped_runner, _module_scoped_runner, _package_scoped_runner, _session_faker, _session_scoped_runner, anyio_backend, anyio_backend_name, anyio_backend_options, cache, capfd, capfdbinary, caplog, capsys, capsysbinary, capteesys, cov, db_engine, db_session, doctest_namespace, event_loop_policy, faker, free_tcp_port, free_tcp_port_factory, free_udp_port, free_udp_port_factory, monkeypatch, no_cover, pg_container, pytestconfig, record_property, record_testsuite_property, record_xml_attribute, recwarn, subtests, test_project, tmp_path, tmp_path_factory, tmpdir, tmpdir_factory, unused_tcp_port, unused_tcp_port_factory, unused_udp_port, unused_udp_port_factory
  >       use 'pytest --fixtures [testpath]' for help on them.
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/integration/conftest.py:139
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  orch/db/models.py:175
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/orch/db/models.py:175: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/daemon/test_batch_manager_worktree_hooks.py::TestTerminalTransitionComposeDown::test_terminal_transition_calls_compose_down
  tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/orch/db/safe_migrate.py:516: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context(live_db_url)
  tests/unit/test_code_qa_router_rerender.py: 1 warning
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_v2_prompt_layout.py: 8 warnings
  tests/unit/test_qa_v2_relevance_filter_eval.py: 5 warnings
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/unit/test_code_ui_routes.py::TestCodeIndexStream::test_sse_stream_returns_idle_when_no_runner_in_registry
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_falls_back_when_module_filter_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_qa_engine.py:625: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_qa_engine.py:723: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_qa_engine.py:819: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_qa_engine.py:905: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_false
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:24: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_absent
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:28: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_raises_when_env_true
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:33: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/orch/db/safe_migrate.py:578: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context(live_db_url)
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_when_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:190: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:200: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:213: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:225: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate.py:235: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true]
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate_guards.py:47: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate_guards.py:59: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00025/tests/unit/test_safe_migrate_guards.py:64: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ERROR tests/unit/test_db_identity.py::TestGetLiveInstanceId::test_row_missing
  ERROR tests/unit/test_db_identity.py::TestGetLiveInstanceId::test_row_present
  ERROR tests/unit/test_db_identity.py::TestCheckIdentity::test_match
  ERROR tests/unit/test_db_identity.py::TestCheckIdentity::test_mismatch
  ERROR tests/unit/test_db_identity.py::TestCheckIdentity::test_bootstrap
  ERROR tests/unit/test_db_identity.py::TestCheckIdentity::test_missing_env_set
  ERROR tests/unit/test_db_identity.py::TestCheckIdentity::test_missing_env_unset
  ERROR tests/unit/test_db_identity.py::TestVerifyInstanceIdentity::test_match
  ERROR tests/unit/test_db_identity.py::TestVerifyInstanceIdentity::test_bootstrap
  ERROR tests/unit/test_db_identity.py::TestVerifyInstanceIdentity::test_mismatch_raises
  ERROR tests/unit/test_db_identity.py::TestVerifyInstanceIdentity::test_missing_row_with_env_set_raises
  ERROR tests/unit/test_db_identity.py::TestVerifyInstanceIdentity::test_missing_row_env_unset_does_not_raise
  make: *** [Makefile:36: test-unit] Error 1
  $ mkdir -p ai-dev/active/CR-00025/reports
  (no output)
  ← Write ai-dev/active/CR-00025/reports/CR-00025_S09_QvGate_report.md
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
