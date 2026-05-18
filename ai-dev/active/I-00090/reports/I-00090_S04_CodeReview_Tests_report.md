# I-00090 S04 — Code Review: Tests (S03)

## What Was Reviewed

Step S03 (`tests-impl`) produced `tests/dashboard/test_running_router_active_filter.py` — a new 592-line test file with 16 test cases covering the active-item filter on `_query_failed_steps()` and `_query_recent_completions()`.

## Files Changed

- `tests/dashboard/test_running_router_active_filter.py` — new file (592 lines, 16 tests)

## Pre-Review Gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ All files formatted |
| `uv run pytest … -v` | ✅ 16 passed, 0 failed |
| `make test-unit` | ✅ 3065 passed, 4 skipped |

## Review Findings

### 1. Coverage Completeness — ✅ PASS

All 16 mandatory tests from design § "TDD Approach" are present:

**`_query_failed_steps` (tests 1–8):**
| # | Design name | Actual test | Status |
|---|-------------|-------------|--------|
| 1 | `test_query_failed_steps_includes_in_progress_item` | `TestQueryFailedStepsActiveItemsIncluded::test_query_failed_steps_includes_in_progress_item` | ✅ |
| 2 | `test_query_failed_steps_excludes_completed_item` | `TestQueryFailedStepsExcludesCompleted::test_query_failed_steps_excludes_completed_item` | ✅ |
| 3 | `test_query_failed_steps_excludes_cancelled_item` | `TestQueryFailedStepsInactiveItemsExcluded::test_query_failed_steps_excludes_cancelled_item` | ✅ |
| 4 | `test_query_failed_steps_excludes_archived_item` | `TestQueryFailedStepsInactiveItemsExcluded::test_query_failed_steps_excludes_archived_item` | ✅ |
| 5 | `test_query_failed_steps_includes_failed_item` | `TestQueryFailedStepsActiveItemsIncluded::test_query_failed_steps_includes_failed_item` | ✅ |
| 6 | `test_query_failed_steps_includes_paused_item` | `TestQueryFailedStepsActiveItemsIncluded::test_query_failed_steps_includes_paused_item` | ✅ |
| 7 | `test_query_failed_steps_includes_needs_fix_status` | `TestQueryFailedStepsActiveItemsIncluded::test_query_failed_steps_includes_needs_fix_status` | ✅ |
| 8 | `test_query_failed_steps_respects_project_filter` | `TestQueryFailedStepsProjectFilter::test_query_failed_steps_respects_project_filter` | ✅ |

**`_query_recent_completions` (tests 9–14):**
| # | Design name | Actual test | Status |
|---|-------------|-------------|--------|
| 9 | `test_query_recent_completions_includes_in_progress_item` | `TestQueryRecentCompletionsActiveItemsIncluded::test_query_recent_completions_includes_in_progress_item` | ✅ |
| 10 | `test_query_recent_completions_excludes_completed_item` | `TestQueryRecentCompletionsInactiveItemsExcluded::test_query_recent_completions_excludes_completed_item` | ✅ |
| 11 | `test_query_recent_completions_excludes_cancelled_item` | `TestQueryRecentCompletionsInactiveItemsExcluded::test_query_recent_completions_excludes_cancelled_item` | ✅ |
| 12 | `test_query_recent_completions_excludes_archived_item` | `TestQueryRecentCompletionsInactiveItemsExcluded::test_query_recent_completions_excludes_archived_item` | ✅ |
| 13 | `test_query_recent_completions_includes_failed_item` | `TestQueryRecentCompletionsActiveItemsIncluded::test_query_recent_completions_includes_failed_item` | ✅ |
| 14 | `test_query_recent_completions_includes_paused_item` | `TestQueryRecentCompletionsActiveItemsIncluded::test_query_recent_completions_includes_paused_item` | ✅ |

**Route-level smoke tests (tests 15–16):**
| # | Design name | Actual test | Status |
|---|-------------|-------------|--------|
| 15 | `test_system_running_route_renders_active_item_only` | `TestSystemRunningRouteActiveFilter::test_system_running_route_renders_active_item_only` | ✅ |
| 16 | `test_project_running_route_renders_active_item_only` | `TestProjectRunningRouteActiveFilter::test_project_running_route_renders_active_item_only` | ✅ |

No missing test names. All 16 present.

### 2. RED-First Reproduction Evidence — ✅ PASS

`test_query_failed_steps_excludes_completed_item` (Test 2) is the designated RED reproduction test. S03's report contains this reasoning:

> *"Pre-S01 reasoning: `_query_failed_steps()` returned rows for ALL failed/needs_fix steps regardless of parent item status. With a completed parent item, the assertion `'CR-DEAD' not in [r.item_id for r in rows]` would FAIL because CR-DEAD appears in the unfiltered result set."*

This reasoning is correct: pre-S01 `_query_failed_steps()` had no filter on `WorkItem.status`, so a `WorkflowStep` with `status=failed` on a `WorkItem` with `status=completed` would be returned. The assertion `"CR-DEAD" not in [r.item_id for r in rows]` would therefore fail — confirming the bug existed before the fix. No stash-revert or source-revert was needed; textual reasoning suffices per the design.

### 3. Assertion Strength — ✅ PASS

All assertions are semantically strong. Examples:

- `assert "CR-DEAD" not in [r.item_id for r in rows]` — specific item ID absence
- `assert "CR-ALIVE" in item_ids` — specific item ID presence
- `assert "I-ALIVE" in body and "I-DEAD" not in body` — item IDs are unique tokens, so this is semantically strong (not a CSS-class-name false-positive)

No shape-only assertions like `assert "failed" in body` or bare `assert len(rows) > 0` found.

### 4. Test Isolation & Determinism — ✅ PASS

- Every test seeds its own `Project` with a unique project ID (e.g., `"p1"`, `"proj-a"`, `"proj-b"`, `"sys-proj"`, `"proj-b-run"`)
- Item IDs are unique per test (e.g., `"CR-DEAD"`, `"CR-ALIVE"`, `"CR-PAUSED"`, `"I-ALIVE"`, `"I-DEAD"`, `"I-B-ALIVE"`, `"I-B-DEAD"`, `"I-A-DEAD"`)
- No `time.sleep`, no real network calls
- `db_session` fixture is testcontainer-backed (not live DB)
- Tests use `pytest-randomly`-safe seeds; `db_session` is cloned per-test via pgtestdbpy

### 5. Project-Filter Regression — ✅ PASS

**Test 8** (`test_query_failed_steps_respects_project_filter`): Seeds two distinct projects (`proj-a`, `proj-b`) and verifies that querying with `project_id=proj_a.id` returns only `CR-A-ACTIVE` and excludes `CR-B-ACTIVE`, and vice versa. ✅

**Test 16** (`test_project_running_route_renders_active_item_only`): Seeds two distinct projects (`test_project` / project A, `proj-b-run` / project B) and asserts:
- `I-ALIVE` appears (active, correct project)
- `I-A-DEAD` does NOT appear (completed)
- `I-B-ALIVE` does NOT appear (wrong project)
- `I-B-DEAD` does NOT appear (completed AND wrong project)

Both regression guards are present and correct.

### 6. Helper-vs-Route Coherence — ✅ PASS

- Helper-level tests (tests 1–14) call `_query_failed_steps()` / `_query_recent_completions()` directly with `db_session` — no route overhead. ✅
- Route-level tests (tests 15–16) use `client.get(...)` via the `client` fixture — correct pattern. ✅

### 7. Cleanup & Style — ✅ PASS

- Module docstring identifies `I-00090` and links to the design document. ✅
- Private seed helpers (`_make_project`, `_make_item`, `_make_step`, `_make_run`) are at module top. ✅
- Imports organized: stdlib → third-party → local. ✅

### 8. TDD RED Evidence — Exempt for tests-impl

Per §5a of the per-agent review template, `tests-impl` is exempt from producing RED-first behavioural tests. The S03 report correctly identifies Test 2 as the RED reproduction test and provides textual reasoning. No finding warranted.

## Verdict

**PASS** — Zero CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

## Test Results

```
tests/dashboard/test_running_router_active_filter.py: 16 passed, 0 failed
make test-unit: 3065 passed, 4 skipped, 5 xfailed, 2 xpassed
make lint: All checks passed
make format-check: All files formatted
```