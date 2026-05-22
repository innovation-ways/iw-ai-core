# I-00103 S06 Code Review Report

## Step Reviewed
S05 (tests-impl) — Reproduction + regression tests for `merge_auto_resolution_failed` per-file error strings.

## Verdict: ✅ PASS

Zero CRITICAL, HIGH, or MEDIUM_FIXABLE findings. All gates green.

---

## Checklist Summary

### 1. Test files exist with documented names
- `tests/integration/test_auto_merge_failed_event_metadata.py` ✅
- `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` ✅

### 2. TDD Approach cases match design doc
All 7 named test functions present with non-stub bodies:

| Design Doc Test | Delivered Test | Status |
|---|---|---|
| `test_i00103_failed_event_carries_per_file_error_strings` | `test_i00103_failed_event_carries_per_file_error_strings` | ✅ |
| `test_per_file_errors_truncated_at_500_chars` | `test_per_file_errors_truncated_at_500_chars` | ✅ |
| `test_per_file_errors_only_includes_errored_calls` | `test_per_file_errors_only_includes_errored_calls` | ✅ |
| `test_per_file_errors_absent_or_empty_when_no_calls_errored` | `test_per_file_errors_absent_or_empty_when_no_calls_errored` | ✅ |
| `test_event_detail_renders_per_file_errors_section_when_present` | `test_event_detail_renders_per_file_errors_section_when_present` | ✅ |
| `test_event_detail_hides_per_file_errors_section_when_absent` | `test_event_detail_hides_per_file_errors_section_when_absent` | ✅ |
| `test_event_detail_hides_per_file_errors_section_when_empty_list` | `test_event_detail_hides_per_file_errors_section_when_empty_list` | ✅ |

### 3. Semantic correctness (not shape-only)
All assertions check specific expected values:

- Integration: `entry["file_path"] == "tests/dashboard/test_auto_merge_routes.py"`, `"LLM call timed out after 120s" in entry["error"]`, `entry["cli_tool"] == default_runtime_option.cli_tool`, `entry["model"] == default_runtime_option.model`
- Dashboard: `"LLM call timed out after 120s" in html`, `"tests/dashboard/test_auto_merge_routes.py" in html`, `"opencode/minimax/MiniMax-M2.7" in html`

No bare-shape-only assertions found. ✅

### 4. CSS class assertions are attribute-scoped (I-00067 lesson)
Dashboard tests use full attribute anchors:
- `assert 'class="auto-merge-modal__per-file-errors"' in html` ✅
- `assert 'class="auto-merge-modal__per-file-error"' in html` ✅

No bare-substring `'per-file-error'` assertions. ✅

### 5. Test placement is correct
- Integration tests under `tests/integration/` (uses testcontainer `db_session`) ✅
- Dashboard tests under `tests/dashboard/` (uses `client` fixture) ✅

### 6. RED proof
`tdd_red_evidence` field in S05 report cites:
- `ai-dev/active/I-00103/evidences/pre/I-00103-bug-event-80689-missing-error.png` (pre-fix screenshot)
- DB events 80689 / 88770 (queried 2026-05-21, no `per_file_errors` key)

`tests-impl` is exempt from live RED-run (fix already landed). ✅

### 7. Fixture & isolation rules
- No direct live-DB connection (testcontainer `db_session` used throughout) ✅
- `event.event_metadata` used correctly (not `event.metadata`) ✅

### 8. Tests actually pass

```
tests/integration/test_auto_merge_failed_event_metadata.py   4 passed
tests/dashboard/test_auto_merge_event_detail_per_file_errors.py  3 passed
======================== 7 passed, 1 warning in 15.02s =========================
```

### 9. Cross-test independence
Each test creates its own `test_project`, `tmp_path`, work item with unique item IDs (`F-99920`–`F-99923`). No shared state, no `pytest.mark.order`. ✅

### 10. No test pollution of live DB
`db_session` and `client` fixtures both derive from testcontainers. No hardcoded `IW_CORE_DB_*` env reads in test files. ✅

---

## Acceptance Criteria Coverage

| AC | Covered By | Notes |
|---|---|---|
| AC1: per_file_errors contains file_path, error, cli_tool, model | `test_i00103_failed_event_carries_per_file_error_strings` | Semantic assertions on all 4 keys |
| AC2: regression test suite passes | All 7 tests + existing auto_merge tests (76 passed) | Clean regression |
| AC3: dashboard renders error string with label | `test_event_detail_renders_per_file_errors_section_when_present` | Checks HTML contains error substring, file path, runtime label |
| AC4: backward compatibility (absent key → 200, no exception) | `test_event_detail_hides_per_file_errors_section_when_absent` + `test_event_detail_hides_per_file_errors_section_when_empty_list` | Both HTTP 200, section hidden, Metadata block still renders |
| AC5: truncation at 500 chars | `test_per_file_errors_truncated_at_500_chars` | Exact `== 500` assertion |

---

## Pre-flight Gates

| Gate | Result |
|---|---|
| `make lint` | ✅ All checks passed (including `scripts/check_templates.py`) |
| `make format` | ✅ 837 files already formatted |

---

## Regression Check

```
tests/integration/test_auto_merge_phase1.py  +  tests/dashboard/test_auto_merge_routes.py
======================== 76 passed, 1 warning in 28.66s =========================
```

No regressions introduced. ✅

---

## Files Changed

| File | Change |
|---|---|
| `tests/integration/test_auto_merge_failed_event_metadata.py` | New — 4 integration tests |
| `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` | New — 3 dashboard tests |

---

## Notes

1. **Design doc vs. fixture values**: The design doc's reproduction test example specifies `cli_tool='opencode', model='minimax/MiniMax-M2.7'`. The `make_default_runtime_option` fixture hardcodes `cli_tool='claude', model='claude-sonnet-4-6-automerge-test'`. The S05 test correctly asserts against the actual fixture values (`default_runtime_option.cli_tool`, `default_runtime_option.model`), which is the right approach — it proves the propagation chain without relying on unverified hardcoded strings.

2. **`opencode`/`minimax` runtime option**: Test 1 updates the runtime option row's `cli_tool` to `'opencode'` within the test transaction to avoid `uq_agent_runtime_options_cli_model` conflicts. This is correct and contained within the transaction — safe for concurrent test runs.

3. **Truncation exactness**: `== 500` (not `>= 500`) is the correct assertion — the implementation slices `[:500]`, not `[:500] + "..."`.
