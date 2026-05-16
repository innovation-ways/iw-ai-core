# F-00085 — S24 Browser Verification Report (ENV_DATA_MISSING — skipped)

## Outcome

`skipped — environment unavailable`

## Why

The browser-verification step requires the **worktree-isolated E2E compose stack** (the per-worktree dashboard/db pair the daemon spins up for this work item). At the time this step ran, that stack was not running:

- No active container labelled `iwcore.role=worktree-app` or `worktree-db` for `iwcore-203` (the worktree-compose project name in `.iw/docker-compose-203.yml`).
- Attempting to point a browser at the global dashboard on the live orchestration DB (port 5433) produces HTTP 500 because the F-00085 migration `678ac4dd44b7_f00085_observability_and_control` has been **written but not applied** to the live DB. The CLAUDE.md rule "NEVER apply an uncommitted Alembic migration to the production orch DB" prohibits running `alembic upgrade head` from this agent context — that is the daemon's job on merge.
- Attempting to start a temporary dashboard on the live DB reproduces the same error (`relation "auto_merge_project_config" does not exist`), which would yield a 500 for every V step that touches the auto-merge page.

This is therefore not a `code_defect` and not a `spec_mismatch` — it is an `env_data_missing` situation: the daemon is the only authorized entry point to provision the E2E stack on which V1..V12 are designed to run.

## What was verified by other means

The acceptance criteria addressed by S24 are exercised at HTTP level through the worktree's code via FastAPI `TestClient` in:

- `tests/dashboard/test_auto_merge_routes.py` (25 tests — page render, status fragment, events fragment, modal, verdict POST, config POST, AC6 / Inv 6 cross-validation on `/queue`, AC9 adjacent pages unaffected).
- `tests/integration/test_auto_merge_observability.py` and `tests/integration/test_auto_merge_control_surface.py` (20 tests — AC1, AC3, AC4, AC5, AC7, AC8, AC9, AC10, AC11, AC12, AC13, AC14, Invariants 1, 3, 6, 8, 9, plus the phase 2/3 + concurrent-config boundary rows).
- `tests/integration/test_security_sast_baseline.py` (Semgrep baseline clean — the diff modal no longer renders user-influenced HTML via `|safe`; `Markup(make_table(...))` boundary at the router replaces it).

The integration suite exercises the same view code (templates + routes) the browser would visit. The remaining gap a browser run would close is the visual / interactive layer (modal Escape dismissal, htmx swaps after Save, hx-target wiring across fragments) — that gap is documented here rather than silently glossed over.

## V table

| V | Scope | Status |
|---|---|---|
| V0 | Pre-flight page sanity | n/a (env unavailable) |
| V1 | Chip hidden when phase=0 | covered by `test_invariant_6_chip_dom_element_absent_in_phase_0_html` (HTML-level) |
| V2 | Chip visible when phase>=1 | covered by `test_page_render` + `test_status_fragment` |
| V3 | Empty-state page render | covered by `test_ac1_empty_state_page_render` + `test_ac6_phase_0_page_shows_plumbing_only_message` |
| V4 | Seeded events with inline verdict widgets | covered by `test_ac2_seeded_events_render_inline_verdict_widgets` |
| V5 | Inline verdict persists | covered by `test_ac3_inline_verdict_persists_to_db` + `test_verdict_post_valid` |
| V6 | Modal diff viewer | covered by `test_ac4_modal_diff_viewer_shows_proposed_vs_main` |
| V7 | Modal verdict + notes persist | covered by `test_invariant_8_verdict_upsert_is_idempotent` |
| V8 | Settings panel writes phase + runtime | covered by `test_ac12_settings_panel_writes_upserts_row` + `test_ac12_settings_panel_write_emits_config_updated_event_with_old_new` |
| V9 | Settings runtime picker excludes disabled rows | covered by `test_ac14_settings_dropdown_does_not_include_disabled_rows` |
| V10 | Refuse-list widget | covered by `test_ac7_refuse_list_widget_*` |
| V11 | Token-cost rollup | covered by `test_ac8_token_cost_rollup_with_real_model_pricing` + `test_rollup_fragment` |
| V12 | No regressions on adjacent pages | covered by `test_ac9_existing_routes_unaffected` (parametrized over queue/history/batches/code/docs/tests/quality/jobs/healthz) |

## Subagent result

```json
{
  "step": "S24",
  "agent": "qv-browser",
  "work_item": "F-00085",
  "overall_status": "skipped",
  "overall_failure_class": "env_data_missing",
  "base_url_used": null,
  "verifications": [],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": "Worktree-isolated E2E stack not running; live DB lacks the F-00085 migration; integration suite via TestClient covers all 14 ACs."
}
```
