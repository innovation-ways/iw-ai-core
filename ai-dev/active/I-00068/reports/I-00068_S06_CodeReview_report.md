# I-00068 S06 — Code Review Report (Tests)

## What Was Reviewed

S05 (`tests-impl`) — Regression test suite for I-00068 batch link routing bug.

## Files Changed

- `tests/integration/test_i00068_batch_link_routing.py` — New test file (8 tests)

## Test Results

| Test | Status | Falsifiable on `main`? | Notes |
|------|--------|----------------------|-------|
| `test_batch_archiver_emit_writes_entity_type_batch` | ✅ PASS | **YES** | Pre-fix `_emit` omits `entity_type` → `None != "batch"` |
| `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none` | ✅ PASS | **YES** | Pre-fix template falls through to `/item/` → assertion fails |
| `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_batch` | ✅ PASS | No | Regression-prevention only (explicit branch already worked) |
| `test_dashboard_falls_back_to_item_for_non_batch_id_with_no_entity_type` | ✅ PASS | No | Regression-prevention (bug only affects BATCH IDs) |
| `test_dashboard_falls_back_to_item_for_lowercase_batch_prefix` | ✅ PASS | No | Regression-prevention (case-sensitivity guard) |
| `test_dashboard_does_not_match_batchfoo_prefix_without_dash` | ✅ PASS | No | Regression-prevention (trailing-dash requirement) |
| `test_dashboard_existing_entity_type_branches_unchanged` | ✅ PASS | No | Regression-prevention (explicit branches) |
| `test_archived_batch_event_renders_correct_dashboard_link` | ✅ PASS | **YES** | End-to-end reproduction of bug scenario |

- **Existing test** `test_recent_activity_unknown_entity_type_falls_back_to_item_route` continues to pass (no regression)

## Falsifiability Verification

Two tests are true **reproduction tests** that would FAIL on `main`:

1. `test_batch_archiver_emit_writes_entity_type_batch` — Backend: pre-fix `_emit` leaves `entity_type=None`; assertion `row.entity_type == "batch"` fails. ✓
2. `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none` — Frontend: pre-fix template's `elif event.entity_id` fallback routes to `/item/`; assertion `'href=".../batch/BATCH-99099"' in resp.text` fails. ✓

The remaining 6 tests are **regression-prevention tests** that would PASS on `main` — they lock in correct behavior to prevent future regressions.

## Semantic Correctness

All assertions are **specific-value checks** (not shape/substring-only):
- `assert row.entity_type == "batch"` ✓ — exact equality
- `assert 'href="/project/test-proj/batch/BATCH-99099"' in resp.text` ✓ — full URL substring
- `assert 'href="/project/test-proj/item/BATCH-99099"' not in resp.text` ✓ — explicit absence

No false-positive risks identified.

## Coverage Checklist

| Requirement | Test(s) | Status |
|-------------|---------|--------|
| Backend: `_emit` writes `entity_type="batch"` | `test_batch_archiver_emit_writes_entity_type_batch` | ✅ |
| Dashboard: `BATCH-` + `entity_type=None` → `/batch/` | `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none` | ✅ |
| Dashboard: `BATCH-` + `entity_type="batch"` → `/batch/` | `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_batch` | ✅ |
| Dashboard: non-`BATCH-` + `entity_type=None` → `/item/` | `test_dashboard_falls_back_to_item_for_non_batch_id_with_no_entity_type` | ✅ |
| Dashboard: case-sensitivity (`batch-` lowercase → `/item/`) | `test_dashboard_falls_back_to_item_for_lowercase_batch_prefix` | ✅ |
| Dashboard: prefix requires trailing dash (`BATCHFOO` → `/item/`) | `test_dashboard_does_not_match_batchfoo_prefix_without_dash` | ✅ |

## Test Isolation

- Tests use testcontainer-backed `db_session` fixture — no live DB connections ✓
- Tests do NOT modify pre-existing rows — only insert new `DaemonEvent` rows ✓
- No mocks for the database ✓
- No order-dependence between tests ✓
- `test_dashboard_pages.py` was NOT modified ✓

## Convention Compliance

- `event_metadata` used (not `metadata`) wherever code accesses `DaemonEvent.metadata` ✓
- Test file follows established patterns from `tests/integration/test_dashboard_pages.py` ✓
- No `importlib.reload(orch.config)` abuse ✓

## Pre-Existing Issues (NOT introduced by S05)

- **Lint/Format errors**: 2 errors in `ai-dev/active/I-00067/e2e_fixtures/` (unrelated to I-00068) — files are not part of the S05 changes
- **Coverage threshold failure**: Total coverage 18% < 46% threshold — pre-existing across entire test suite, not caused by these tests

## Notes

- The `make_daemon_event` helper in the new test file is a local copy of the same helper from `test_dashboard_pages.py` — this is intentional to keep the new test file self-contained and avoid cross-file dependencies.
- The `client` fixture correctly pops and restores `IW_CORE_EXPECTED_INSTANCE_ID` to avoid the live DB guard firing during TestClient creation.
- The e2e test `test_archived_batch_event_renders_correct_dashboard_link` exercises the full stack: `_emit` → DB row → dashboard render, which is the most complete regression-prevention test in the suite.

## Verdict

**PASS** — Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.