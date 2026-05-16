# F-00085_S13_Tests_prompt

**Work Item**: F-00085
**Step**: S13
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in `tests/integration/conftest.py` are exempt.

## ⛔ Migrations: agents generate, daemon applies

No new migrations in this step.

## Input Files

- `ai-dev/active/F-00085/F-00085_Feature_Design.md` — AC1..AC14, Boundary table, Invariants 1..9
- `skills/iw-ai-core-testing/SKILL.md` — assertion strength, isolation, red-flag checklist
- S01..S11 deliverables (all merged at this step)
- Existing test patterns:
  - `tests/conftest.py` + `tests/integration/conftest.py` — testcontainer fixture
  - `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` — alembic + DB-state test pattern
  - `tests/dashboard/test_runtime_overrides_api.py` — dashboard TestClient pattern

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S13_Tests_report.md`
- All test files listed under "Test files" below

## Context

Comprehensive test coverage for F-00085. Every AC, every Boundary row, and every Invariant gets at least one mapped test.

## Test files

### Unit tests

#### `tests/unit/test_auto_merge_aggregator.py`

Covers `orch/auto_merge_aggregator.py`. ≥ 18 tests including:

- `test_status_snapshot_empty_db` — zero events → sane defaults; counts dict has every event-type key with value 0
- `test_status_snapshot_with_seeded_events`
- `test_list_recent_events_pagination`
- `test_list_recent_events_type_filter`
- `test_list_recent_events_left_joins_verdicts` — events with and without verdicts both appear
- `test_get_event_detail_returns_none_for_missing`
- `test_get_event_detail_includes_verdict_when_present`
- `test_verdict_rollup_7d_window`
- `test_verdict_rollup_30d_window`
- `test_verdict_rollup_excludes_older_events`
- `test_refuse_list_breakdown_groups_by_reason`
- `test_refuse_list_breakdown_window_filter`
- `test_health_summary_no_probes` → state="unknown"
- `test_health_summary_recent_success` → state="healthy"
- `test_health_summary_recent_failures_exceed_threshold` → state="degraded" or "down"
- `test_token_cost_rollup_per_model_breakdown`
- `test_token_cost_rollup_unknown_model_sets_flag`
- `test_token_cost_rollup_handles_missing_llm_calls_metadata`

#### `tests/unit/test_auto_merge_config_resolution.py`

Covers `resolve_project_config`. ≥ 12 tests covering every branch.

- `test_resolve_per_project_db_phase_and_runtime_both_set`
- `test_resolve_per_project_db_phase_only_runtime_from_toml`
- `test_resolve_per_project_db_runtime_only_phase_from_toml`
- `test_resolve_no_db_row_falls_back_to_toml`
- `test_resolve_no_db_no_toml_uses_hardcoded_defaults`
- `test_resolve_phase_2_in_db_rejected_with_clear_error` — Inv 5
- `test_resolve_phase_3_in_db_rejected_with_clear_error` — Inv 5
- `test_resolve_disabled_runtime_in_db_falls_back_to_toml_runtime`
- `test_resolve_disabled_runtime_emits_auto_merge_config_invalid_once`
- `test_resolve_deterministic_invariant_2` — same inputs × 10 iterations → identical ResolvedConfig
- `test_resolve_returns_source_field_per_project_db_when_db_row_exists`
- `test_resolve_returns_source_field_toml_when_no_db_row`

#### `tests/unit/test_auto_merge_health.py`

Covers `maybe_run_probe`. ≥ 8 tests.

- `test_probe_skipped_when_recent_event_exists` — `now - last < interval` → no subprocess call
- `test_probe_fires_when_no_recent_event` → records event with `runtime_reachable=True` on stub success
- `test_probe_records_failure_on_subprocess_error` → `runtime_reachable=False`, error in metadata
- `test_probe_records_failure_on_timeout`
- `test_probe_skipped_when_phase_0` — no probe when resolved phase=0
- `test_probe_uses_resolved_per_project_runtime` — picks up DB-overridden runtime
- `test_probe_subprocess_timeout_capped` — `max(15, interval // 4)`
- `test_probe_non_blocking_does_not_raise` — any exception → logged + swallowed

#### `tests/unit/test_auto_merge_pricing.py`

Covers `MODEL_PRICING` math. ≥ 6 tests.

- `test_pricing_known_model_claude_sonnet`
- `test_pricing_known_model_minimax`
- `test_pricing_unknown_model_returns_zero`
- `test_pricing_unknown_model_sets_has_unknown_models_flag`
- `test_pricing_zero_tokens_returns_zero_cost`
- `test_pricing_covers_every_enabled_agent_runtime_option` — assert each currently-enabled row's `model` is in `MODEL_PRICING`

### Integration tests (testcontainer DB)

#### `tests/integration/test_auto_merge_observability.py`

ACs 1, 2, 3, 4, 5, 7, 8.

- `test_ac1_empty_state_page_render`
- `test_ac2_seeded_events_render_inline_verdict_widgets`
- `test_ac3_inline_verdict_persists_to_db`
- `test_ac4_modal_diff_viewer_shows_proposed_vs_main` — mock `subprocess.run` for `git show`
- `test_ac4_boundary_file_no_longer_on_main` — mock subprocess returncode != 0 → placeholder rendered
- `test_ac5_health_probe_emits_event_with_metadata` — stub the executor subprocess
- `test_ac5_chip_state_transitions_healthy_to_degraded`
- `test_ac7_refuse_list_widget_hidden_when_zero`
- `test_ac7_refuse_list_widget_groups_by_reason`
- `test_ac8_token_cost_rollup_with_real_model_pricing`
- `test_boundary_event_with_no_llm_calls` — modal still renders
- `test_boundary_multiple_files_in_one_event` — multi-file diff renders
- `test_boundary_unknown_model_in_metadata` — banner shown, cost contributes $0
- `test_invariant_1_daemon_events_append_only` — no diff code path UPDATEs/DELETEs `daemon_events`

#### `tests/integration/test_auto_merge_control_surface.py`

ACs 10, 11, 12, 13, 14.

- `test_ac10_per_project_phase_override_isolates_projects` — Project A phase=1, Project B no row → A fires LLM, B does not
- `test_ac11_per_project_runtime_override_uses_picked_model`
- `test_ac12_settings_panel_writes_upserts_row`
- `test_ac12_settings_panel_write_emits_config_updated_event_with_old_new`
- `test_ac13_use_global_default_clears_row_or_nulls_fields`
- `test_ac14_post_disabled_runtime_returns_400`
- `test_ac14_settings_dropdown_does_not_include_disabled_rows` — assert by inspecting rendered HTML
- `test_boundary_phase_2_post_rejected_400`
- `test_boundary_phase_3_post_rejected_400`
- `test_boundary_oversize_verdict_notes_413`
- `test_boundary_verdict_on_attempted_event_400`
- `test_boundary_runtime_disabled_after_save_falls_back` — disable row mid-flight; next merge falls back to TOML
- `test_boundary_concurrent_config_writes_last_write_wins`
- `test_invariant_3_toml_standalone_when_db_empty` — no per-project rows → behaviour matches F-00084
- `test_invariant_9_config_updated_event_records_before_after`

#### `tests/dashboard/test_auto_merge_routes.py`

Dashboard TestClient. ≥ 14 tests.

- One per endpoint: page render, status fragment, events fragment, event detail, verdict POST (valid + invalid verdict + oversize notes + non-resolved event), config POST (valid + disabled runtime + phase=2 + oversize), rollup fragment
- `test_ac6_phase_0_hides_chip_in_header_html` — assert the chip include block is absent from rendered HTML
- `test_ac6_phase_0_page_shows_plumbing_only_message`
- `test_ac9_existing_routes_unaffected` — sweep `/<p>/queue, /history, /batches, /code, /docs, /tests, /quality, /jobs, /worktrees, /healthz`; assert all 200 + no template-render errors
- `test_invariant_6_chip_dom_element_absent_in_phase_0_html` — Inv 6 deeper check
- `test_invariant_8_verdict_upsert_is_idempotent` — POST verdict twice with different values → second call overwrites; `merge_auto_verdicts` row count stays at 1

### Browser tests (S24's prompt expands these)

This step does NOT write browser tests directly — those are S24's responsibility. But this step's integration coverage must be strong enough that S24 is verifying user experience, not finding logic bugs.

### Fixture pattern

Use a shared helper module `tests/fixtures/auto_merge_observability/fixtures.py` (if it doesn't already exist from F-00084's S06).

- `seeded_events_factory(db, project_id, *, attempts=3, resolved=3, failed=0, skipped=0, health_probes=0)` — seeds DaemonEvents with realistic `event_metadata` shapes.
- `mock_git_show(monkeypatch, file_contents: dict[str, str | None])` — stubs `subprocess.run(["git", "show", "main:<file>"])` per-file mapping; `None` → simulate file deleted.
- `fake_executor_subprocess(monkeypatch, *, response="OK", returncode=0, timeout=False)` — stubs the step_executor.sh probe call.

### Assertion strength (mandatory per `iw-ai-core-testing`)

- Assert on specific event types AND specific metadata keys, NOT just "an event fired".
- Compare exact dict/list contents where possible.
- Use `pytest.approx` only for floats; never for integers, strings, or dicts.
- Test names describe behaviour ("test_ac12_settings_panel_writes_upserts_row"), not implementation.
- Avoid `assert ... is not None` as final assertion.

### Isolation rules (CLAUDE.md hard rules)

- NEVER connect to live DB (port 5433).
- Use testcontainer fixtures.
- Replace `psycopg2://` URLs with `postgresql+psycopg://` per CLAUDE.md.
- Apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` if any test uses FTS.
- Use `monkeypatch.delenv()`, NEVER `importlib.reload(orch.config)`.

### Coverage target

- `orch.auto_merge_aggregator`: ≥ 90 % line coverage
- `orch.daemon.auto_merge_health`: ≥ 85 %
- `dashboard.routers.auto_merge_ui`: ≥ 85 %
- Run `uv run pytest tests/unit/test_auto_merge_*.py tests/integration/test_auto_merge_*.py tests/dashboard/test_auto_merge_routes.py --cov=orch.auto_merge_aggregator --cov=orch.daemon.auto_merge_health --cov=dashboard.routers.auto_merge_ui -v` and include coverage in your report.

## TDD Requirement

This is a `tests-impl` step. Per the `iw-ai-core-testing` guidance, the RED-GREEN cycle is "structural" — the tests are the deliverable. `tdd_red_evidence` should be a 1–3 line snippet showing one of your tests would have FAILED against a deliberately-broken version of the upstream code (e.g., comment out the Phase-0 short-circuit and confirm `test_ac10_per_project_phase_override_isolates_projects` fails).

## Pre-flight Quality Gates

1. `make format`.
2. `make typecheck` — zero errors on your new test files.
3. `make lint` — zero errors.
4. Targeted: `uv run pytest tests/unit/test_auto_merge_*.py tests/integration/test_auto_merge_*.py tests/dashboard/test_auto_merge_routes.py -v` — all green.

## Test Verification

- Run ONLY the test files you wrote/modified. Do NOT run `make test-unit` (full suite) or `make test-integration` (S20/S21 QV gates).

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "tests-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "tests/unit/test_auto_merge_aggregator.py",
    "tests/unit/test_auto_merge_config_resolution.py",
    "tests/unit/test_auto_merge_health.py",
    "tests/unit/test_auto_merge_pricing.py",
    "tests/integration/test_auto_merge_observability.py",
    "tests/integration/test_auto_merge_control_surface.py",
    "tests/dashboard/test_auto_merge_routes.py",
    "tests/fixtures/auto_merge_observability/fixtures.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<N> passed, 0 failed; coverage on orch.auto_merge_aggregator=<pct>% daemon.auto_merge_health=<pct>% dashboard.routers.auto_merge_ui=<pct>%",
  "tdd_red_evidence": "Confirmed test_ac10_per_project_phase_override_isolates_projects fails when resolve_project_config bypasses the DB lookup (asserted Project B never called LLM; got 1 LLM call when bypass was active)",
  "blockers": [],
  "notes": "AC1..AC14 each mapped to ≥1 test; Invariants 1..9 each mapped; every Boundary row covered. FakeLLM + mock_git_show + fake_executor_subprocess factored into shared fixtures module. No real LLM calls in CI; no live DB connections."
}
```
