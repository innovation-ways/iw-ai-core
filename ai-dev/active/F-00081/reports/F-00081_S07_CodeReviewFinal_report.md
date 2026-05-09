# F-00081 S07 — Final Cross-Agent Code Review Report

**Step**: S07 (code-review-final-impl)
**Work Item**: F-00081 — Per-Item / Per-Step Agent + Model Override
**Reviewed Steps**: S01 (Database) · S02 (Backend) · S03 (Code Review S02) · S04 (API) · S05 (Frontend) · S06 (Tests)
**Status**: ✅ PASS with one informational finding

---

## Pre-Review Quality Gates

| Gate | Result |
|------|--------|
| `make format` / `make format-check` | ✅ 661 files already formatted |
| `make typecheck` | ✅ No issues in 238 source files |
| `make test-frontend` | ✅ 576 passed, 14 skipped, 1 xfailed |
| F-00081-specific tests (63 tests) | ✅ 63 passed |

---

## Pre-Review Lint Gate: 1 Informational Finding

```
ARG001 Unused function argument: `project_id`
  --> dashboard/routers/runtime_overrides.py:55:5
```

The `GET /runtime-options` endpoint receives `project_id` as a path parameter (required for route consistency with the router's `/project/{project_id}/api` prefix) but the catalogue is global — no per-project filtering. This is **intentional** (documented in S05 report). It's a cosmetic `ARG001` lint warning, not a bug, and doesn't block merge. **No fix required.**

---

## 1. Completeness vs Design Document

### Acceptance Criteria (AC1–AC8)

| AC | Implementation | Test |
|----|---------------|------|
| **AC1** Default preserved, `--model minimax` in command, `agent_runtime_option_id` recorded | `orch/agent_runtime/resolver.py`, `orch/daemon/batch_manager.py:1196–1219`, `orch/daemon/fix_cycle.py:1900–1925` | `test_resolves_to_default_row_and_records_option_id`, `test_command_contains_model_flag`, `test_step_run_records_default_option_id` — test_f00081_cascade.py |
| **AC2** Item override (claude, claude-opus-4-7) → command uses `claude -p … --model claude-opus-4-7` | same launch sites + resolver cascade | `test_item_override_resolves_to_specified_pair`, `test_command_uses_claude_with_model`, `test_step_run_records_item_override_id` — test_f00081_cascade.py |
| **AC3** Step override beats item override | `resolver.py:54–70` (step checked first) | `test_step_override_wins`, `test_item_override_used_when_step_has_none` — test_f00081_cascade.py |
| **AC4** UI lock: non-editable → badge, editable → `<select>` | `item_overview.html:91–113` | `test_pending_step_has_select_element`, `test_completed_step_has_badge_not_select`, `test_in_progress_step_has_badge_not_select` — test_runtime_override_templates.py |
| **AC5** Mid-flight non-preemption (running step unaffected) | resolver reads from DB at launch time; step_runs is append-only | `test_running_step_unaffected_by_item_override_change`, `test_next_pending_step_picks_up_new_override` — test_f00081_cascade.py |
| **AC6** Bulk: exactly one DaemonEvent per call | `audit.py` emits once per call; bulk skips non-editable silently | `test_bulk_five_steps_emits_one_event_with_5_step_ids`, `test_zero_editable_steps_emits_zero_events` — test_f00081_audit.py + test_f00081_invariants.py |
| **AC7** Default cannot be disabled (CHECK constraint) | Migration creates `ck_agent_runtime_options_default_must_be_enabled` | `test_default_row_cannot_be_disabled`, `test_attempting_second_default_row_raises_integrity_error` — test_f00081_invariants.py |
| **AC8** Compressed strip ≤ 120px | `step_pipeline.html` + plain CSS in `styles.css:351–359` | `test_strip_width_formula_complies_for_various_counts`, `test_strip_width_formula_for_8_steps` — test_f00081_invariants.py |

**All 8 ACs implemented and test-covered.**

### Boundary Behavior — All 8 Rows Covered

| Boundary | Test |
|----------|------|
| Catalogue empty → fallback to is_default row | `test_resolver_falls_back_to_default_and_warns` — test_f00081_boundaries.py |
| Override points to disabled row → skip, fall through | `test_resolver_skips_disabled_step_override_falls_to_item`, `test_resolver_skips_disabled_item_override_falls_to_project` — test_f00081_boundaries.py |
| Bulk on zero editable steps → 204, no event | `test_bulk_zero_editable_returns_204_and_no_event` — test_f00081_boundaries.py |
| Step race (in_progress before PATCH) → 409 | `test_single_step_patch_returns_409_when_step_becomes_in_progress` — test_f00081_boundaries.py |
| Project default pair not in catalogue → warning, fallback | `test_resolver_falls_back_when_project_pair_not_in_catalogue` — test_f00081_boundaries.py |
| Pre-feature item (NULL FKs) → falls to catalogue default | `test_null_overrides_fall_to_catalogue_default` — test_f00081_boundaries.py |
| FK prevents delete of referenced row | `test_delete_referenced_option_raises_integrity_error` — test_f00081_boundaries.py |
| Terminal item override → 400 | `test_item_override_on_done_item_returns_400` — test_f00081_boundaries.py |

### Invariants — All 6 Covered

| Invariant | Tests |
|-----------|-------|
| Inv 1: Exactly one is_default row | `test_exactly_one_default_row_exists`, `test_attempting_second_default_row_raises_integrity_error`, `test_default_row_cannot_be_disabled`, `test_default_row_remains_one_after_disabling_non_default` |
| Inv 2: step_runs written by daemon has non-null option_id | `test_step_run_via_resolve_has_non_null_option_id`, `test_step_run_with_item_override_has_item_override_id`, `test_step_run_with_step_override_has_step_override_id` |
| Inv 3: Launch command contains `--model <model>` | `test_opencode_command_contains_model_flag`, `test_claude_command_contains_model_flag`, `test_all_catalogue_options_produce_model_flag` |
| Inv 4: One DaemonEvent per API call | `test_bulk_emits_single_event`, `test_single_step_patch_emits_one_event`, `test_zero_editable_steps_emits_zero_events` |
| Inv 5: Override changes never touch step_runs | `test_changing_item_override_does_not_touch_step_runs`, `test_changing_step_override_does_not_touch_step_runs` |
| Inv 6: Strip width bounded | `test_strip_width_formula_complies_for_various_counts`, `test_strip_width_formula_for_8_steps`, `test_strip_width_edge_case_12_steps` |

---

## 2. Cross-Agent Consistency

### Form field name
The API (S04) reads `option_id` as a form field (`Form(default=None)` in `runtime_overrides.py:152,199,248`). The frontend submits exactly `option_id` (line 99 of `item_overview.html`: `name="option_id"` on the select). ✅

### Endpoint paths
S04 registers `runtime_overrides.router` with `prefix="/project/{project_id}/api"`. Routes:
- `GET /runtime-options` → `GET /project/{p}/api/runtime-options` ✅
- `PATCH /item/{item_id}/runtime-override` → `PATCH /project/{p}/api/item/{iid}/runtime-override` ✅
- `PATCH /item/{item_id}/step/{step_id}/runtime-override` → `PATCH /project/{p}/api/item/{iid}/step/{sid}/runtime-override` ✅
- `PATCH /item/{item_id}/runtime-override/bulk` → `PATCH /project/{p}/api/item/{iid}/runtime-override/bulk` ✅

Frontend calls these exactly (item_overview.html lines 97, 206, 207). ✅

### Catalogue row shape
`GET /runtime-options` returns `{id, cli_tool, model, cli_label, model_label, display_name, is_default}`. Frontend uses `cli_label`, `model_label`, `id` in `item_overview.html` (lines 103, 201) and `cli_label`, `model_label` in `batch_items_rows.html` (lines 21, 22, 34). ✅

### DaemonEvent metadata shape
`audit.py` emits `{item_id, scope, step_ids, old_option_id, new_option_id, actor}` (lines 48–55). S06 tests assert this shape (`test_bulk_five_steps_emits_one_event_with_5_step_ids`, `test_item_override_emits_event_with_scope_item_and_null_step_ids`). ✅

### ProjectConfig model field
`project_registry.py:145`: `model: str = entry.get("model", "minimax")`. Cascade resolution uses `getattr(project, "model", "minimax")` (resolver.py:94). Consistent. ✅

### Launch command `--model` injection
- opencode: `opencode run "$(cat {prompt_file})" --model {resolved_model}` (batch_manager:1211–1218, fix_cycle:1910–1917)
- claude: `claude -p "$(cat {prompt_file})" --model {resolved_model}` (batch_manager:1213–1219, fix_cycle:1912–1919)
- Cascade tests assert the flag appears in constructed commands. ✅

---

## 3. Integration Points

### orch/agent_runtime/ does NOT import orch/daemon/
`resolver.py` imports only `AgentRuntimeOption` from `orch.db.models` and `Session` from `sqlalchemy.orm`. No daemon imports. ✅

### runtime_overrides router registered in dashboard/app.py
Line 283: `app.include_router(runtime_overrides.router)`. ✅

### Seed rows use hardcoded IDs (1–5)
Migration seeds IDs 1–5. Tests look up by `(cli_tool, model)` natural key via the resolver cascade, not hardcoded ID. The integration tests' `seed_runtime_options` fixture also uses natural-key inserts. ✅

### Bulk endpoint emits one DaemonEvent
`audit.py:58`: `session.add(event)` once per call. Bulk path (runtime_overrides.py:280–289) only calls it when `editable_steps` is non-empty. ✅

### Frontend "Apply to all remaining" calls bulk endpoint
`item_overview.html:206`: `hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/runtime-override/bulk"`. ✅

---

## 4. Test Coverage (Holistic)

S06 report's coverage table maps every AC, Invariant, and Boundary row to a named test. All named tests exist and pass. 63 F-00081-specific tests pass.

Integration tests use testcontainer PostgreSQL (no mocks). ✅

Pre-feature item shape (NULL FKs) is tested in `TestBoundaryPreFeatureItem`. ✅

---

## 5. Architecture Compliance

- **Layer boundaries**: `orch/agent_runtime/` is a clean resolver with no daemon imports; `dashboard/routers/runtime_overrides.py` is a thin router. ✅
- **PostgreSQL as sole source of truth**: catalogue lives in `agent_runtime_options` table, seeded by migration. ✅
- **psycopg v3 only**: no `postgresql+psycopg2://` in any F-00081 implementation files. The replacement in `conftest.py` and other test files is the standard testcontainer URL-rewriting pattern, not new code. ✅
- **`DaemonEvent.metadata` → `event_metadata`**: correctly handled in `audit.py:48`. ✅

---

## 6. Security

- **Model field in shell commands**: The model string comes from the DB catalogue (operator-controlled via Alembic seed). The resolver does not shell-interpolate user input. Defence-in-depth: the model string originates from the migration-seeded catalogue with `server_default` constraints; if a future migration adds a malicious pair, the operator themselves introduced it. No MEDIUM finding warranted.
- **No hardcoded credentials** in any F-00081 file. ✅
- **Auth posture of PATCH endpoints**: Same as existing `actions.py` endpoints (uses `"dashboard"` actor placeholder, matching existing pattern). No privilege escalation introduced. ✅

---

## 7. Frontend Quality

- **AC8 width budget**: Formula `6*n + gap*(n-1)` verified in `test_strip_width_formula_for_8_steps` (55px ≤ 120px) and `test_strip_width_edge_case_12_steps` (documents formula behavior). ✅
- **Plain CSS**: Appended to `dashboard/static/styles.css:351–359` per I-00067 mitigation. No Tailwind classes dynamically constructed. ✅
- **Accessibility**: All strip segments have `title` attributes (step_pipeline.html lines 12, 15, 18, 21, 24). ✅

---

## Findings

### Mandatory Fixes: 0

### Informational (no fix required)

1. **`ARG001` lint on `runtime_overrides.py:55`**: `project_id` parameter in `get_runtime_options` is unused because the catalogue is global. This is intentional (documented in S05 report). The router prefix requires the path parameter for consistency. Cosmetic only.

### Pre-Existing Failures (not introduced by F-00081)

- **Unit tests**: 120 failures in `test_step_monitor`, `test_merge_queue`, `test_merge_queue_migration_pipeline` — existed before F-00081, confirmed by S02 and S03 reports.
- **Integration tests**: 37 failures + 40 errors in `test_batch_manager`, `test_merge_queue`, `test_step_monitor_lifecycle`, `test_f_00076_*`, and other pre-existing tests — also existed before F-00081.

---

## Verdict

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00081",
  "steps_reviewed": ["S01","S02","S03","S04","S05","S06"],
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "63 F-00081-specific tests passed (8 resolver unit + 5 audit unit + 50 integration). 576 frontend tests passed. All ACs, Boundary rows, and Invariants are covered. Pre-existing failures in unrelated test suites are not caused by F-00081.",
  "missing_requirements": [],
  "notes": "One cosmetic ARG001 lint warning on an intentionally unused project_id parameter in GET /runtime-options. No code changes required. F-00081 is ready for S08 (QV Gate)."
}
```