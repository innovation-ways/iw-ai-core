# I-00091 S06 Code Review — S05 (tests-impl)

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step Reviewed**: S05 (tests-impl)
**Review Step**: S06 (code-review-impl)

---

## What Was Reviewed

The regression test suite added in S05 for I-00091, covering the four-cell
per-axis override matrix for the auto-merge settings form.

## Pre-Review Gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 750 files already formatted |

## Files Changed (by S05)

| File | Change |
|------|--------|
| `tests/unit/test_auto_merge_config_resolution.py` | Extended: 4 new per-axis source unit tests + updated 3 existing tests for back-compat `source` property |
| `tests/dashboard/test_auto_merge_routes.py` | Extended: `_extract_select_block` helper + 4 matrix dashboard tests |
| `tests/integration/test_auto_merge_control_surface.py` | Extended: `_extract_select_block` helper + 2 POST/response tests |

## Test Results (Targeted Run)

```
tests/unit/test_auto_merge_config_resolution.py:        17 passed, 0 failed
tests/dashboard/test_auto_merge_routes.py:             29 passed, 0 failed
tests/integration/test_auto_merge_control_surface.py:  15 passed, 0 failed
Total: 61 passed, 0 failed
```

## Review Checklist

### 1. Test Placement ✅

All tests using the `client` fixture live under `tests/dashboard/`
(`test_auto_merge_routes.py`), correctly using the FastAPI TestClient pattern
with `app.dependency_overrides[get_db]`. Unit tests for the pure
`resolve_project_config` function live under `tests/unit/`. Integration tests
that need real PostgreSQL (via testcontainers) live under `tests/integration/`.

### 2. Semantic Correctness ✅ (No red flags found)

The assertions use specific value checks, not bare shape checks:

- `assert 'value="1" selected' in phase_block` — specific value present ✅
- `assert 'value="global" selected' not in phase_block` — specific value absent ✅
- `_extract_select_block(html, name="phase")` scopes assertions to a single
  `<select>` block, preventing cross-matching between Phase and Runtime dropdowns ✅
- Integration test asserts `id="auto-merge-settings"` AND `hx-swap-oob` together ✅
- No bare `assert response.status_code == 200` as the only assertion ✅

### 3. Coverage Matrix ✅

**Dashboard layer** (4 matrix cells):
- `test_settings_form_reflects_phase_only_override` ✅
- `test_settings_form_reflects_runtime_only_override` ✅
- `test_settings_form_reflects_both_axes_override` ✅
- `test_settings_form_clears_back_to_global` ✅

**Unit layer** (4 matrix cells at `resolve_project_config`):
- `test_resolve_project_config_records_per_axis_source_phase_only_override` ✅
- `test_resolve_project_config_records_per_axis_source_runtime_only_override` ✅
- `test_resolve_project_config_records_per_axis_source_both_axes_override` ✅
- `test_resolve_project_config_records_per_axis_source_no_override` ✅

**Integration layer** (combined fragment response):
- `test_save_config_returns_combined_fragment` ✅
- `test_save_config_json_response_unchanged` ✅

### 4. Named Tests — All 9 Exist Verbatim ✅

| Design Name | Found |
|-------------|-------|
| `test_settings_form_reflects_phase_only_override` | ✅ |
| `test_settings_form_reflects_runtime_only_override` | ✅ |
| `test_settings_form_reflects_both_axes_override` | ✅ |
| `test_settings_form_clears_back_to_global` | ✅ |
| `test_resolve_project_config_records_per_axis_source_phase_only_override` | ✅ |
| `test_resolve_project_config_records_per_axis_source_runtime_only_override` | ✅ |
| `test_resolve_project_config_records_per_axis_source_both_axes_override` | ✅ |
| `test_resolve_project_config_records_per_axis_source_no_override` | ✅ |
| `test_save_config_returns_combined_fragment` | ✅ |

### 5. Isolation & Determinism ✅

- No hardcoded project IDs — uses `test_project` fixture with factory-generated IDs ✅
- No `importlib.reload(orch.config)` ✅
- No live DB connection (port 5433) — all DB tests use testcontainers ✅
- No `agent-browser` usage ✅
- No DB mocking in integration tests ✅

### 6. CSS Class Assertions

No CSS class assertions were found in the new tests. The `auto-merge-settings`
ID and `hx-swap-oob` string are asserted via substring inclusion, which is
appropriate since these are HTML attribute/id values, not CSS classes. ✅

### 7. TDD RED Evidence ✅

S05 report correctly states `n/a — coverage step` with the explanation that
the tests target the exact assertion gap that pre-fix code would fail on, and
provides two specific RED examples. This is correct per the design template's
standard for coverage steps.

### 8. Targeted-Run Discipline ✅

The test summary (61 passed) reflects only the 3 targeted test files, not
`make test-unit` / `make test-integration` (which are S12/S13 QV gates). The
step ran only the 3 targeted files.

---

## Verdict

**PASS** — All review items pass. The test suite correctly implements the
four-cell matrix at dashboard and unit layers, with appropriate semantic
assertions that would fail against the pre-fix bug (single-axis `source`
boolean causing both dropdowns to fall back to "global" even when only one
axis was overridden).

## Mandatory Fix Count

**0**

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00091",
  "step_reviewed": "S05",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "61 passed, 0 failed (targeted run: 3 files)",
  "notes": "All 9 named matrix tests present. Semantic assertions correctly scoped via _extract_select_block. TDD RED evidence correctly n/a for coverage step. No live DB, no improper mocking, no wrong-layer placement. Pre-review lint/format gates passed."
}
```