# I-00093 S04 — Code Review Report

## Work Item
I-00093 — Auto-merge event detail modal hides the most useful fields

## Step
S04 (code-review-impl), reviewing S03 (tests-impl)

---

## Pre-Flight Quality Gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ All files formatted |
| `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` | ✅ 47 passed, 0 failed |

---

## Review Checklist

### 1. Test Placement (I-00067)
✅ All 5 I-00093 tests use `client` (the `TestClient` fixture) and live under `tests/dashboard/test_auto_merge_routes.py`.

### 2. Semantic Correctness (I003)
All 5 tests use factory-set strings as assertions (not generic word matches):

| Test | Key Assertions |
|------|---------------|
| `test_event_modal_renders_message_and_metadata_for_health_probe` | `"probe latency 412ms"`, `"runtime_reachable"`, `"claude-sonnet-4-6"`, `"412"` |
| `test_event_modal_renders_old_new_for_config_updated` | `"auto-merge config updated from dashboard"`, `"old"`, `"new"`, `"updated_by"`, `"dashboard"` |
| `test_event_modal_renders_verdict_info_for_resolved` | `"correct"`, `"looked fine"`, `"operator"`, `name="verdict"`, `value="correct"` |
| `test_event_modal_no_verdict_form_for_non_resolved_events` | `"Step S13 launched (PID 99)"`, `"pid"`, `"99"` |
| `test_event_modal_heading_is_humanized` | Scoped `<h3 id="auto-merge-event-title">` regex → `"auto_merge_health_probe"` in heading text |

No HIGH/CRITICAL semantic-correctness red flags.

### 3. Coverage — Named Tests Present
All 5 named tests from the design are present and collected:

- `test_event_modal_renders_message_and_metadata_for_health_probe` ✅
- `test_event_modal_renders_old_new_for_config_updated` ✅
- `test_event_modal_renders_verdict_info_for_resolved` ✅
- `test_event_modal_no_verdict_form_for_non_resolved_events` ✅
- `test_event_modal_heading_is_humanized` ✅

### 4. Heading-Scoped Regex (I-00093 §4)
`test_event_modal_heading_is_humanized` uses:
```python
re.search(r'<h3[^>]*id="auto-merge-event-title"[^>]*>(.*?)</h3>', html, re.DOTALL)
```
to scope to the specific element, then asserts `"auto_merge_health_probe"` appears in `heading_text`. This is correct — the event_type does not appear elsewhere in the heading's scoped content.

### 5. Factories Commit Real Rows
Tests construct `DaemonEvent` and `MergeAutoVerdict` rows directly via `db_session.add()` + `db_session.flush()`. No ORM mocking. This is correct for integration tests using the testcontainer-backed `db_session`.

`daemon_event_factory` and `merge_verdict_factory` were added to `tests/integration/auto_merge_fixtures.py` as plain Python helper functions (available for future use) but are not used by the current tests — the tests follow the existing `_event()` inline pattern in the same file. This is acceptable.

### 6. Attribute-Scoped CSS Class Assertions (I-00067)
The heading test uses a properly scoped regex (`<h3[^>]*id="auto-merge-event-title"[^>]*>(.*?)</h3>`). Existing I-00092 tests use `re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', ...)` for attribute-scoped class checks. ✅

### 7. Targeted-Run Discipline
`tests_passed` reflects only the `tests/dashboard/test_auto_merge_routes.py` run: **47 passed, 0 failed**. The coverage threshold warning (20% < 50%) is a pre-existing global configuration issue, not introduced by these changes.

---

## TDD Evidence

`tdd_red_evidence = "n/a — coverage step (tests-impl)"` — as noted in the S03 report, this is a coverage step.

---

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_auto_merge_routes.py` | Added 5 I-00093 regression tests |
| `tests/integration/auto_merge_fixtures.py` | Added `daemon_event_factory()` and `merge_verdict_factory()` helpers |

---

## Verdict

**PASS** — All review criteria met. No mandatory fixes. All 5 named tests pass with correct semantic assertions and scoped regex patterns.

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00093",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "47 passed in tests/dashboard/test_auto_merge_routes.py",
  "notes": "Coverage threshold warning (20% < 50%) is pre-existing and global, not introduced by these changes. All 5 named tests present, semantic assertions correct, heading regex properly scoped, DB rows committed directly (no mocks)."
}
```