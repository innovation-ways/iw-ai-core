# F-00065 S06 CodeReview Tests Report

## What was done

Reviewed S05 (tests-impl) output against the design doc and project conventions.

## Files Reviewed

- `tests/unit/dashboard/test_preprocess_mermaid.py`
- `tests/dashboard/test_code_diagram_endpoint.py`

## Checklist Results

| Item | Status | Notes |
|------|--------|-------|
| 3 `_preprocess_mermaid` unit tests present | PASS | All assert `<pre data-lang="mermaid">` format |
| 3 endpoint tests present | PASS | 200+fragment, 200+empty-state, 404 |
| No live DB connections in unit tests | PASS | `_preprocess_mermaid` inlined in test file |
| No live DB connections in dashboard tests | **FAIL** | Import of `dashboard.dependencies.get_db` at module load triggers live_db_guard before mock can override |
| Tests match project conventions | PASS | TestClient pattern, mock DB override, descriptive test names |
| Boundary behavior rows covered | PASS | All 5 boundary scenarios from design doc covered |

## CRITICAL Issue: Dashboard endpoint tests fail on collection

`test_code_diagram_endpoint.py` imports `dashboard.dependencies.get_db` at line 23 inside `_make_client`. This causes `orch.db.live_db_guard` to fire during pytest collection — before the session-scoped `_arm_live_db_guard` fixture sets `IW_CORE_TEST_CONTEXT`. The import chain is:

```
dashboard/dependencies.py:7 → orch.db.session → orch.db.live_db_guard → LiveDbConnectionRefusedError
```

The `TestClient` + `app.dependency_overrides` pattern correctly suppresses the real DB, but the guard blocks collection before any test runs.

**Impact**: `test_diagram_endpoint_returns_fragment_when_doc_exists`, `test_diagram_endpoint_returns_empty_state_when_no_doc`, and `test_diagram_endpoint_returns_404_for_unknown_project` all fail during collection.

**Fix required**: Either (a) move the `from dashboard.dependencies import get_db` import inside the `_make_client` method body (inside a function that is not called during collection), or (b) restructure so the `app` and `dependency_overrides` are created in a conftest fixture rather than at test construction time.

## Unit Tests: PASS

`test_preprocess_mermaid.py` correctly inlines the regex to avoid the `live_db_guard` import issue. All 3 tests pass.

## Non-F-00065 Pre-existing Failures

`tests/dashboard/test_chat_a11y.py` and `tests/dashboard/test_chat_templates.py` each have 1 failure unrelated to F-00065 (existing test suite).

## Findings

| Severity | File | Line | Message |
|----------|------|------|---------|
| CRITICAL | tests/dashboard/test_code_diagram_endpoint.py | 23 | Import of `get_db` at module level fires live_db_guard before `_arm_live_db_guard` fixture runs — tests fail during collection |
| LOW | tests/dashboard/test_code_diagram_endpoint.py | 17–28 | `_make_client` creates a new `create_app()` call per test — could be cached at class level for performance |

## Step Status

**partial** — 3/6 tests fail during collection (the 3 endpoint tests). The unit tests for `_preprocess_mermaid` all pass. S05 correctly identified the import risk and inlined the function, but missed that the `from dashboard.dependencies import get_db` at module level would also trigger the guard.

## Recommendation

S05 agent should fix the import-by-name issue and re-run. S07 (final review) should not proceed until S05 test fixes are verified passing.