# CR-00030: Show remaining time (not end time) on Claude 5h usage slot

**Type**: Change Request
**Priority**: Low
**Reason**: UX polish — make the Claude 5h slot label match the MiniMax 5h slot's "remaining time" format already shown beside it in the same footer, so users can read time-left at a glance instead of mentally subtracting from a wall-clock end time.
**Created**: 2026-05-04
**Status**: Draft

---

## Description

Today the Claude 5h slot in the dashboard footer shows the slot's wall-clock end time (e.g. `15:00`) next to the usage percentage (e.g. `8%`). This CR changes the 5h label to render the remaining time until reset (e.g. `4h 32m`) using the same format MiniMax already uses in the adjacent bar. The Claude 7d slot label and all percentage values are unchanged.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The change is confined to the orchestration package's LLM-usage helper and its unit tests — the FastAPI footer fragment renders whichever string the backend supplies and needs no template edit.

## Current Behavior

`orch/llm_usage.py::_format_resets_at(resets_at: float)` renders the `five_hour.resets_at` Unix timestamp as a wall-clock label:

- `<24h` away → `"HH:MM"` (e.g. `"15:00"`)
- `>=24h` away → `"%a HH:MM"` (e.g. `"Tue 09:00"`)
- past / zero → `None`

`_claude_usage()` calls `_format_resets_at` for both the `five_hour` and `seven_day` windows and stores the result under `block_reset` (5h) and `week_reset` (7d). The dashboard fragment `dashboard/templates/fragments/llm_usage_footer.html` prints `block_reset` to the left of the 5h progress bar (lines 7, 11) and `week_reset` to the left of the 7d bar (lines 15, 19), with `'5h'` / `'7d'` placeholders when either is `None`.

A separate helper `_format_reset(remains_ms: int)` already renders milliseconds as `"<H>h <M>m"` (or `"<M>m"` under one hour) and is used for the MiniMax bar.

## Desired Behavior

The Claude 5h slot label shows time remaining until the slot resets, in the MiniMax-style format:

- `>=1h`  → `"<H>h <M>m"` (e.g. `"4h 32m"`, `"1h 0m"`)
- `<1h`   → `"<M>m"`       (e.g. `"25m"`, `"0m"` for less than one minute remaining but not yet expired)
- past / zero → `None` (template falls back to the existing `'5h'` placeholder)

The Claude 7d slot label is **unchanged**: it continues to render as `"HH:MM"` / `"%a HH:MM"` via the existing `_format_resets_at`.

The percentage values (`block_pct`, `week_pct`) are unchanged in source, format, and meaning.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/llm_usage.py::_claude_usage` | `block_reset` derived from `_format_resets_at(five_hour.resets_at)` → `"15:00"` | `block_reset` derived from a new helper that converts remaining seconds to `"4h 32m"` |
| `orch/llm_usage.py::_format_resets_at` | Used by both 5h and 7d | Used by 7d only — no signature change |
| `orch/llm_usage.py` (new helper) | n/a | New private function `_format_remaining_from_ts(resets_at: float)` returning `"<H>h <M>m"` / `"<M>m"` / `None` |
| `dashboard/templates/fragments/llm_usage_footer.html` | Renders `claude_reset` and `claude_7d_reset` verbatim | Unchanged — backend provides the new string under the same key |
| `tests/unit/test_llm_usage.py` | Asserts `block_reset is not None` (string shape unverified) and exercises `_format_resets_at` for both windows | Updated assertions for the 5h shape; new tests for `_format_remaining_from_ts`; existing `_format_resets_at` tests untouched |

### Breaking Changes

- None. `_claude_usage()` continues to return the same dict keys (`block_pct`, `week_pct`, `block_reset`, `week_reset`) with the same types (`int`, `int`, `str | None`, `str | None`). Only the **content** of `block_reset` changes from a wall-clock string to a remaining-time string.

### Data Migration

- None.
- Reversibility: trivial — revert the commit. No on-disk state, no DB schema change. The 60-second in-process cache (`_cache`) self-flushes at TTL.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `_format_remaining_from_ts`; switch `_claude_usage`'s 5h branch to use it; leave 7d on `_format_resets_at` | — |
| S02 | code-review-impl | Review S01 (correctness, naming, dead-code, no template/percent regressions) | — |
| S03 | tests-impl | Update `test_claude_usage_uses_seven_day_from_cache` 5h shape assertion; add unit tests for `_format_remaining_from_ts` covering all branches | — |
| S04 | code-review-impl | Review S03 (coverage of edge cases, isolation, no use of `importlib.reload(orch.config)`) | — |
| S05 | code-review-final-impl | Global review of S01 + S03 against this design + acceptance criteria | — |
| S06..S10 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |
| S11 | qv-browser | Open the dashboard, force-refresh the footer fragment, verify the 5h slot label matches `^\d+h \d+m$` or `^\d+m$`, screenshot before/after | — |

Agent slugs match `executor/step_executor_lib.sh`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no schema or migration touched

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None — `GET /api/usage/llm/fragment` returns the same template with the same template-context keys; only the string content of `claude_reset` changes
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None — `dashboard/templates/fragments/llm_usage_footer.html` is unchanged
- **Removed components**: None

The browser verification step (S11) is required because the user-visible string in the footer is what the change targets, even though the template file itself is not edited.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00030/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00030_CR_Design.md` | Design | This document |
| `CR-00030_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00030_S01_Backend_prompt.md` | Prompt | S01 backend implementation |
| `prompts/CR-00030_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/CR-00030_S03_Tests_prompt.md` | Prompt | S03 unit tests |
| `prompts/CR-00030_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/CR-00030_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-step global review |
| `prompts/CR-00030_S11_BrowserVerification_prompt.md` | Prompt | S11 qv-browser verification |
| `evidences/pre/CR-00030-before-footer.png` | Evidence | Pre-change screenshot of the footer captured at design time |

QV gate steps S06..S10 use the canonical `qv-gate` agent and inline `command`, no per-step prompt file.

Reports are created during execution under `ai-dev/active/CR-00030/reports/`.

## Acceptance Criteria

### AC1: Claude 5h label is a remaining-time string

```
Given the rate-limits cache file contains a five_hour bucket whose resets_at is 4h 32m in the future
When the dashboard fetches /api/usage/llm/fragment
Then the rendered HTML contains the literal text "4h 32m" in the Claude 5h column
And does not contain a wall-clock string like "15:00" in that column
```

### AC2: Claude 7d label is unchanged

```
Given the rate-limits cache file contains a seven_day bucket whose resets_at is 3 days in the future
When the dashboard fetches /api/usage/llm/fragment
Then the rendered HTML contains a "%a HH:MM" wall-clock string in the Claude 7d column
And the format matches the existing _format_resets_at output exactly
```

### AC3: Sub-hour 5h label uses minutes only

```
Given the five_hour bucket's resets_at is 25 minutes in the future
When _claude_usage() runs
Then block_reset == "25m"
```

### AC4: Sub-minute 5h label is "0m"

```
Given the five_hour bucket's resets_at is 30 seconds in the future
When _claude_usage() runs
Then block_reset == "0m"
```

### AC5: Expired or missing 5h cache → None

```
Given the rate-limits cache is missing OR five_hour.resets_at is in the past
When _claude_usage() runs
Then block_reset is None
And the footer template renders the existing "5h" placeholder
```

### AC6: Percentage values are untouched

```
Given the five_hour bucket has used_percentage = 56.0
When _claude_usage() runs
Then block_pct == 56
And the rendered HTML contains "56%" in the 5h column
```

### AC7: Quality gates pass

```
Given the implementation lands on the work branch
When the orchestrator runs S06..S10
Then make lint, make format, make typecheck, make test-unit, and make allure-integration all exit 0
```

## Rollback Plan

- **Database**: Not applicable — no schema change.
- **Code**: Revert the merge commit. The change touches a single helper and its tests; reverting restores the wall-clock label.
- **Data**: No data loss possible — the 60s in-process `_cache` self-flushes; rate-limits-cache.json on disk is untouched by this code path (only read).

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/llm_usage.py`
- `tests/unit/test_llm_usage.py`

## TDD Approach

- **Unit tests** (S03):
  - `_format_remaining_from_ts(future_ts)` → `"4h 32m"` for a timestamp ~4h 32m ahead (use `monkeypatch` on `datetime.now`).
  - `_format_remaining_from_ts(future_ts_under_1h)` → `"25m"`.
  - `_format_remaining_from_ts(future_ts_under_1m)` → `"0m"`.
  - `_format_remaining_from_ts(now_ts)` → `None`.
  - `_format_remaining_from_ts(past_ts)` → `None`.
  - `_format_remaining_from_ts(0)` → `None`.
  - End-to-end via `_claude_usage()`: with `five_hour.resets_at` set to a known offset, assert `block_reset` matches `^\d+h \d+m$` or `^\d+m$`, never `^\d{1,2}:\d{2}$`.
- **Integration tests**: None required — no DB, daemon, or HTTP path is changed. Existing `make allure-integration` must still pass as a regression net.
- **Updated tests**:
  - `tests/unit/test_llm_usage.py::TestClaudeRateLimitsCache::test_claude_usage_uses_seven_day_from_cache` — strengthen the `block_reset` assertion to require the new 5h shape (still allow `week_reset` to be a wall-clock string).
- **Untouched tests**:
  - `TestFormatResetsAt` — still validates `_format_resets_at` because the 7d branch keeps using it.
  - `TestFormatReset` — unrelated MiniMax helper.

## Notes

- `_format_resets_at` stays in the module — the 7d slot still uses it. Do not remove the function; do not remove its tests.
- The new helper takes a Unix timestamp (not milliseconds) for symmetry with `_format_resets_at` and the existing `five_hour.resets_at` shape. It can be implemented in one line by computing `int(resets_at - now())` seconds and reusing the same `Hh Mm` / `Mm` formatting that `_format_reset` uses for milliseconds — extract a shared inner helper if it reduces duplication, but keep the public API surface identical.
- Risk: the in-process 60s cache (`_cache` in `get_llm_usage`) caches a *value* (`"4h 32m"`), not a *deadline*. After the deadline passes, the cached value is stale until the next 60s refresh. This was already true for the wall-clock label and is not a regression — call it out in the implementation prompt so reviewers don't try to "fix" it.
