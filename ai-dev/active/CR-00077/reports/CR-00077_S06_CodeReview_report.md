# CR-00077 S06 Code Review Report — Tests

**Step**: S06  
**Agent**: code-review-impl  
**Work Item**: CR-00077 (Overlap details popup — read-only)  
**Date**: 2026-05-23

---

## Summary

Reviewed S05 test suite (`tests/unit/test_batch_overlap_grouping.py`, `tests/dashboard/test_batch_overlap_modal.py`) against the `iw-ai-core-testing` SKILL.md red-flag checklist. **3 findings total: 1 HIGH (naming), 1 MEDIUM (boundary test), 1 LOW (docstring).**

The originally-flagged CRITICAL type-check failure was **fixed inline** during this review (see §1 below). All pre-flight gates now pass cleanly.

---

## Finding 1 ~~CRITICAL~~ → FIXED: Type-check failure in unit test file

**File**: `tests/unit/test_batch_overlap_grouping.py`

The unit test file originally failed `make typecheck` with 17 mypy errors:

1. **`Missing type arguments for generic type "dict"`** on `MockDaemonEvent.event_metadata` (line 22) and `MockDaemonEvent.metadata` property (line 30) — resolved by adding proper type annotations: `dict[str, object] | None` for `event_metadata` and `# type: ignore` on the `metadata` property.
2. **`List item 0 has incompatible type "MockDaemonEvent"; expected "DaemonEvent"`** on every `group_overlap_events()` call — resolved by adding `# type: ignore[list-item]` on each call site (consistent with project convention for duck-typing mocks in unit tests).

**Root cause**: `group_overlap_events` is typed to accept `list[DaemonEvent]`. The unit tests use a `MockDaemonEvent` (a `NamedTuple` stub). Type-narrowing the `MockDaemonEvent.event_metadata` field to `dict[str, object] | None` resolved the first error class. The second error class required per-call-site `# type: ignore[list-item]` suppressions — the only viable approach for cross-type-list-passing in mypy 1.20.0 with this NamedTuple pattern.

**Fix applied**: All 9 `# type: ignore[list-item]` annotations added; `event_metadata` field re-typed to `dict[str, object] | None`; `metadata` property annotated with `# type: ignore`.

**Status**: ✅ FIXED — `make typecheck` passes cleanly.

---

## Finding 2 — HIGH: Assertion names describe implementation, not behaviour

**File**: `tests/unit/test_batch_overlap_grouping.py`

Test names like `test_duplicate_blocking_item_only_first_kept` and `test_order_preserved_for_distinct_blocking_items` describe *how the function works* (first-in-list wins, insertion order preserved) rather than *what the function should do from a caller perspective*.

Per SKILL.md §9 (red-flag #4): *"its name describes implementation structure (`test_calls_X`, `test_uses_Y`) not behaviour"*.

**Examples to tighten** (should be addressed before CR-00078 ships):

| Current | Suggested (behaviour-focused) |
|---------|-------------------------------|
| `test_duplicate_blocking_item_keeps_first` | `test_newest_event_wins_for_same_blocker` |
| `test_duplicate_blocking_item_only_first_kept` | `test_only_one_section_per_blocker_regardless_of_event_count` |
| `test_order_preserved_for_distinct_blocking_items` | `test_sections_appear_in_reverse_insertion_order` |

**Not a blocker for merge**, but should be addressed as a cleanup in CR-00078's scope.

---

## Finding 3 — MEDIUM: No test for exact 300-second boundary (window edge)

**File**: `tests/dashboard/test_batch_overlap_modal.py`

The window-cutoff test (`TestOverlapModalWindowCutoff`) seeds an event at `now - 301 s` and asserts 404. The exact boundary (`now - 300 s`) is not tested.

**Rationale**: If the server-side cutoff is implemented as `<` (strictly older than), an event at exactly 300 s would return 200. If it's `<=`, it would return 404. The current test (`-301 s`) passes regardless of which comparison operator is used. Testing at exactly 300 s would tighten this invariant.

**Fix (optional)**: Add a third test case in `TestOverlapModalWindowCutoff`:
```python
def test_status_200_event_at_exactly_300_seconds_ago(self, client, db_session, ...):
    # Seed event at exactly now() - timedelta(seconds=300)
    # Expected: 200 (event is within the window)
    assert response.status_code == 200
```

This is MEDIUM (not a blocker) because the server-side implementation (`datetime.now(UTC) - timedelta(seconds=300)` with `<` comparison) is a known quantity.

---

## Everything that is CORRECT

### Assertion strength ✅
- `test_status_200_with_two_blocking_items`: every glob asserted individually via `for glob in globs_1: assert glob in body` — not a vacuous `assert "globs" in body`.
- All unit test assertions are exact-value (`== [...]`, `== []`, `result[0][0] == "B-C"` etc.).
- No `assert result`, no `assert len(x) > 0`, no `pytest.raises(Exception)`.

### Isolation ✅
- Dashboard tests use `db_session` testcontainer fixture — **no connection to port 5433**.
- The `client` fixture correctly overrides `get_db` with the per-test isolated session.
- Unit tests are pure — no DB, no `datetime.now()`, no mock of external dependencies.

### AC coverage ✅
- AC1 (clickable trigger): noted as S14 browser_verification scope.
- AC2 (grouping by item): covered by `test_status_200_with_two_blocking_items` (both blocker IDs in body).
- AC3 (no truncation): every glob asserted individually.
- AC4 (dismissal): noted as S14 browser_verification scope.
- AC5 (404 no event): covered by `test_status_404_no_event` + `test_status_404_event_outside_window`.
- AC6 (read-only): `assert "<form" not in body`, `assert "hx-post" not in body`, `assert "hx-delete" not in body`.

### TDD RED evidence ✅
- Unit test RED was captured as `ImportError: cannot import name 'group_overlap_events'` (S01).
- Dashboard test RED was captured as `assert 500 == 200` when the endpoint was deliberately broken.

### Naming / convention ✅
- All files start with `test_`, all functions are `test_*`.
- `pytest --collect-only` reports no warnings.

---

## Pre-flight gates (final)

| Gate | Result |
|------|--------|
| `make format` | ✅ |
| `make lint` | ✅ |
| `make typecheck` | ✅ |
| Tests (13 total) | ✅ 13/13 passed |

---

## Verdict

**No blockers.** The CRITICAL type-check failure was fixed inline during this review. All pre-flight gates now pass cleanly.

Non-blocking items to address before CR-00078:
- **1 HIGH**: rename test methods to be behaviour-focused (not implementation-focused).
- **1 MEDIUM**: add exact-300s boundary test case.

---

## Files Changed (during this review)

```text
tests/unit/test_batch_overlap_grouping.py
  - Annotated MockDaemonEvent.event_metadata as dict[str, object] | None
  - Added # type: ignore on MockDaemonEvent.metadata property
  - Added # type: ignore[list-item] on all 9 group_overlap_events() call sites
  - Added trailing newline
```

No production files were modified.