# I-00091 S07 — Final Cross-Agent Code Review Report

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S07 (CodeReviewFinal)
**Status**: PASS

---

## What Was Done

Performed a global cross-agent review of S01 (Backend), S03 (Frontend), and S05 (Tests) to verify that:
1. Per-axis `phase_source` / `runtime_source` fields produced by S01 match what S03's templates consume
2. The literal string values `per_project_db`, `toml`, `hardcoded` are consistent across all layers
3. The combined HTML fragment response from `auto_merge_set_config` contains both `id="auto-merge-settings"` and the OOB chip marker
4. All acceptance criteria (AC1–AC5) have tests covering them

---

## Files Changed (across S01/S03/S05)

| File | Step | Change |
|------|------|--------|
| `orch/auto_merge_aggregator.py` | S01 | Added `phase_source` and `runtime_source` to `ResolvedConfig`; `source` preserved as back-compat property |
| `dashboard/templates/fragments/auto_merge_settings.html` | S03 | Per-axis `_phase_override` / `_runtime_override` booleans; `id="auto-merge-settings"` wrapper; `hx-target` updated; "Saved" indicator |
| `dashboard/templates/fragments/auto_merge_status_chip.html` | S03 | Per-axis source lines with `hx-swap-oob` on the chip element |
| `dashboard/routers/auto_merge_ui.py` | S03 | Non-JSON POST returns concatenated settings HTML + OOB chip |
| `dashboard/static/styles.css` | S03 | CSS rules for saving/saved indicators (plain CSS, appended per CLAUDE.md) |
| `tests/unit/test_auto_merge_config_resolution.py` | S05 | 5 new per-axis source tests + 3 updated assertions for new `source` property semantics |
| `tests/dashboard/test_auto_merge_routes.py` | S05 | 4 matrix tests using `_extract_select_block` helper |
| `tests/integration/test_auto_merge_control_surface.py` | S05 | 2 combined-fragment POST tests |

---

## Pre-Flight Checks

| Check | Result |
|-------|--------|
| `make lint` | PASS — all checks passed |
| `make format` | PASS — 750 files already formatted |
| No new migrations under `orch/db/migrations/versions/` | PASS — no new files |
| `make css` mitigation (plain CSS appended to styles.css) | PASS — rules at end of file, no Tailwind recompile needed |

---

## Cross-Agent Consistency Verification

### Field Names
- ✅ `ResolvedConfig.phase_source` (S01 line 29) matches template expression `status.config.phase_source` (settings.html line 3, chip.html line 32)
- ✅ `ResolvedConfig.runtime_source` (S01 line 30) matches template expression `status.config.runtime_source` (settings.html line 4, chip.html line 33)

### Literal String Values
- ✅ All `Literal["per_project_db", "toml", "hardcoded"]` values use underscore (`per_project_db`), not hyphen
- ✅ Template comparisons `== 'per_project_db'` (settings.html lines 3–4, chip.html lines 32–33) use the same underscore form
- ✅ No `"per-project-db"` or other variants anywhere

### Template IDs
- ✅ Section `id="auto-merge-settings"` (settings.html line 1) matches `hx-target="#auto-merge-settings"` (settings.html line 7)
- ✅ Chip `id="auto-merge-status-chip"` (chip.html line 20) matches `hx-swap-oob="outerHTML:#auto-merge-status-chip"` (chip.html line 20 with `{% if oob %}`)

### Router Response (Non-JSON Branch)
- ✅ `auto_merge_set_config` (auto_merge_ui.py lines 387–408) renders settings fragment + OOB chip and concatenates them as `HTMLResponse(settings_html + chip_html)`
- ✅ `hx-swap-oob="outerHTML:#auto-merge-status-chip"` is present in the chip template (line 20)

---

## Test Coverage vs. Acceptance Criteria

| AC | Description | Test(s) |
|----|-------------|---------|
| AC1 | Phase-only override renders correctly | `test_settings_form_reflects_phase_only_override` (dashboard) |
| AC2 | Runtime-only override renders correctly | `test_settings_form_reflects_runtime_only_override` (dashboard) |
| AC3 | Both-axes override + in-place refresh | `test_settings_form_reflects_both_axes_override` (dashboard) + `test_save_config_returns_combined_fragment` (integration) |
| AC4 | Clear-back-to-global | `test_settings_form_clears_back_to_global` (dashboard) + `test_ac13_use_global_default_clears_row_or_nulls_fields` (integration) |
| AC5 | Regression test exists | All 4 matrix tests + existing suite |

**TDD named tests from Issue Design document:**
- ✅ `test_resolve_project_config_records_per_axis_source_phase_only_override` (unit)
- ✅ `test_resolve_project_config_records_per_axis_source_runtime_only_override` (unit)
- ✅ `test_resolve_project_config_records_per_axis_source_both_axes_override` (unit)
- ✅ `test_resolve_project_config_records_per_axis_source_no_override` (unit)
- ✅ `test_save_config_returns_combined_fragment` (integration)

---

## Test Results (Targeted Run)

```
tests/unit/test_auto_merge_config_resolution.py:        17 passed, 0 failed
tests/dashboard/test_auto_merge_routes.py:              29 passed, 0 failed
tests/integration/test_auto_merge_control_surface.py:  15 passed, 0 failed
Total:                                                    61 passed, 0 failed
```

Coverage failure (20% vs required 50%) is pre-existing — not caused by this item. All three test files pass cleanly under the `--randomly-seed=2249059655` ordering.

---

## Integration Points

| Point | Verified |
|-------|----------|
| Non-JSON POST → combined fragment (settings + OOB chip) | ✅ `auto_merge_ui.py` lines 387–408 |
| JSON POST → unchanged JSON `{ok, project_id, phase, runtime_option_id}` | ✅ `auto_merge_ui.py` lines 368–375 + `test_save_config_json_response_unchanged` |
| `DaemonEvent` with `event_type="auto_merge_config_updated"` still emitted | ✅ `auto_merge_ui.py` lines 350–364 + `test_ac12_settings_panel_write_emits_config_updated_event_with_old_new` |
| hx-target on form matches section id | ✅ settings.html line 7: `hx-target="#auto-merge-settings"` |
| OOB chip has `id="auto-merge-status-chip"` | ✅ chip.html line 20 |

---

## Security

- No `| safe` filter added to user-controlled data
- No hardcoded credentials introduced
- No new endpoints added; existing `/auto-merge/config` retains validation (phase ∈ {None,0,1}; runtime_option_id must be enabled)

---

## Backwards Compatibility

- `ResolvedConfig.source` property is preserved (returns `per_project_db` if either axis is from DB, else `runtime_source`)
- No callers of `.source` outside S03's scope (grep confirmed all 7 matches are in template files or design docs)
- S03 migrated chip to per-axis source lines; back-compat property ensures old chip text behaviour is preserved for any callers not yet migrated

---

## Findings

No CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "I-00091",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "17 unit passed, 29 dashboard passed, 15 integration passed, 0 failed",
  "missing_requirements": [],
  "notes": "All 61 targeted tests pass under random seed 2249059655. Cross-agent field-name and literal-value consistency verified. No new migrations. make lint and make format both clean."
}
```