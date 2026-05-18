# I-00097 S04 — Code Review Report (S03: tests-impl)

## What was reviewed

S03 (`tests-impl`) added 5 regression tests to `tests/dashboard/test_auto_merge_routes.py` covering the two I-00097 polish behaviours.

## Files changed

| File | Change |
|------|--------|
| `tests/dashboard/test_auto_merge_routes.py` | +140 lines: 5 new tests + imports |

(S01-front-end changes to `auto_merge_rollup.html` and `auto_merge_event_row.html` are also in the worktree but are not the subject of S03 review.)

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 750 files already formatted |

## Tests

```
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
==================== 30 passed in 44.79s ====================
```

All 30 tests pass (25 pre-existing + 5 new I-00097 tests).

## Review checklist

### 1. Test placement (I-00067) ✅
All 5 I-00097 tests use `client`, live under `tests/dashboard/`, and are driven by the `TestClient` pattern. No live DB usage.

### 2. Semantic correctness ✅
- **`test_token_cost_zero_renders_as_dollar_zero`**: Asserts `$0.000000` absent AND uses a scoped regex `<p\b[^>]*>...\s*\$(\S+)\s*</p>` to extract the exact cost value, asserting it equals the string `"0"`. This is stronger than a raw `"$0" in html` check.
- **`test_entity_id_renders_as_link_for_work_item_ids`**: The regex `<a\b[^>]*\bhref="/project/iw-ai-core/item/CR-00057"[^>]*>\s*CR-00057\s*</a>` covers the full `<a>` with `href`, `>CR-00057<` — not just the bare string. Route uses singular `item`. ✅
- **`test_entity_id_renders_plain_when_not_work_item_id`**: Asserts `"iw-ai-core" in html` (must appear) AND `not re.search(r'href="/project/[^"]+/item/iw-ai-core"', html)` (must NOT be linkified). ✅
- **`test_entity_id_renders_dash_when_null`**: Uses scoped regex `<td[^>]*\bfont-mono\b[^>]*>\s*—\s*</td>` to avoid matching other cells. ✅

### 3. Coverage — all 5 named tests present ✅

| Test | Covers |
|------|--------|
| `test_token_cost_zero_renders_as_dollar_zero` | AC1 |
| `test_token_cost_nonzero_keeps_precision` | AC2 |
| `test_entity_id_renders_as_link_for_work_item_ids` | AC3 |
| `test_entity_id_renders_plain_when_not_work_item_id` | AC4 |
| `test_entity_id_renders_dash_when_null` | AC5 |

### 4. Linkification — all three IW prefixes ⚠️ MEDIUM

The linkification test (`test_entity_id_renders_as_link_for_work_item_ids`) only covers `CR-00057`. The design doc requires all three IW prefixes (`F-NNNNN`, `I-NNNNN`, `CR-NNNNN`) to prevent regressions on the other two. The underlying filter (`_is_work_item_id` in `dashboard/app.py:353`) correctly matches all three prefixes, and the template implementation in `auto_merge_event_row.html:7-8` uses the filter directly — so the implementation is correct. The test gap is in coverage only.

**Suggested fix**: Either add `pytest.mark.parametrize("entity_id", ["CR-00057", "F-00057", "I-00057"])` to `test_entity_id_renders_as_link_for_work_item_ids`, or add two more tests for `F-` and `I-` cases.

### 5. Targeted-run discipline ✅
Tests are scoped to the targeted subset. The 30-test run was only for verification; the S03 report correctly shows a targeted 5-test run.

### 6. CSS class assertions ✅ N/A
I-00097 is a template fix; no new CSS classes were introduced.

## Findings

| Severity | File | Lines | Description | Suggested fix |
|----------|------|-------|-------------|---------------|
| MEDIUM | `tests/dashboard/test_auto_merge_routes.py` | 338–368 | `test_entity_id_renders_as_link_for_work_item_ids` only tests `CR-00057`; `F-` and `I-` prefixes are not covered. Regression risk if the filter logic is changed. | Add `pytest.mark.parametrize("entity_id", ["CR-00057", "F-00057", "I-00057"])` to cover all three IW prefixes, or add two more explicit tests. |

## Verdict

**PASS** — all mandatory items (test placement, semantic correctness, 5 named tests, targeted discipline, lint/format gates, all 30 tests passing) are satisfied. The only finding is MEDIUM severity: parametrize the entity_id test to cover F- and I- prefixes.

## JSON result

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00097",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "MEDIUM",
      "file": "tests/dashboard/test_auto_merge_routes.py",
      "lines": "338-368",
      "description": "test_entity_id_renders_as_link_for_work_item_ids only covers CR-00057. F-NNNNN and I-NNNNN are not tested, leaving a regression gap if the work_item_id filter logic changes.",
      "suggested_fix": "Add pytest.mark.parametrize('entity_id', ['CR-00057', 'F-00057', 'I-00057']) to cover all three IW ID prefixes."
    }
  ],
  "tests_passed": true,
  "test_summary": "30 passed in 44.79s (5 new I-00097 tests + 25 pre-existing)",
  "notes": "Implementation (S01) is correct: auto_merge_rollup.html uses conditional $0 formatting and auto_merge_event_row.html uses the work_item_id filter. Tests are semantically correct. The single MEDIUM finding is a coverage gap (CR-only in linkification test) that is fixable via parametrize."
}
```