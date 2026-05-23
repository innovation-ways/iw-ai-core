# CR-00078_S05_CodeReview_report.md

## Step Overview

**Step**: S05 — Code Review (daemon hook + helper)
**Work Item**: CR-00078 — Per-batch ignore overlap & force-start
**Agent**: code-review-impl

---

## Review Scope

Per-agent review of S04's daemon hook (`batch_manager._process_batch`) and the pure helper `filter_blocked_by_ignores` from `scope_overlap.py`.

---

## Findings

### ✅ CRITICAL checks — all PASS

1. **Helper purity (AC1)** — `filter_blocked_by_ignores` in `orch/daemon/scope_overlap.py` is a pure function. No DB import, no `Session` parameter, no logger calls. Importable from `tests/unit/` without SQLAlchemy instantiation. ✅

2. **Per-batch WHERE clause (AC5 critical)** — `grep -n 'BatchOverlapIgnore' orch/daemon/batch_manager.py` at line 472-475 shows:
   ```python
   select(BatchOverlapIgnore).where(
       BatchOverlapIgnore.project_id == self.project_id,
       BatchOverlapIgnore.batch_id == batch.id,
       BatchOverlapIgnore.held_item_id == item.work_item_id,
   )
   ```
   All three of `project_id`, `batch_id`, AND `held_item_id` are present. ✅

3. **No regression on existing path** — When `ignored_pairs` is empty, `filter_blocked_by_ignores(blocked_by, set())` returns `list(blocked_by)` (input unchanged). The `blocked_by = filtered_blocked_by` assignment then has no effect, so `item_held_for_scope` still fires for every blocking pair. ✅

4. **Event emission gating (AC2)** — `batch_overlap_allowed_by_ignore` is emitted only when `not filtered_blocked_by and ignored_pairs`. It is NOT emitted when:
   - There were no ignores at all (`ignored_pairs` empty → condition `ignored_pairs` is False).
   - Ignores existed but didn't fully clear the hold (`filtered_blocked_by` non-empty → condition `not filtered_blocked_by` is False). ✅

5. **Commit pattern** — `db.commit()` is called once per item, after `_emit_event`, matching the existing site convention. ✅

6. **String literal consistency** — `"batch_overlap_allowed_by_ignore"` appears exactly once in `batch_manager.py` at line 484, and is referenced (as the expected string) in:
   - `ai-dev/active/CR-00078/prompts/CR-00078_S06_API_prompt.md` (line 77 — timeline table)
   - `ai-dev/active/CR-00078/prompts/CR-00078_S10_Tests_prompt.md` (lines 38, 74-75, 88, 139)
   No typos detected. ✅

7. **Pure helper edge cases** — S04 added exactly one RED test case (`test_daemon_overlap_filter.py::TestFilterBlockedByIgnoresEmpty::test_empty_ignores_returns_input`). No over-building. The full unit test suite is owned by S10. ✅

---

### Additional checks

- **Lint** (`uv run ruff check`): All checks passed. ✅
- **Type check** (`uv run mypy`): Success — no issues found in `batch_manager.py` and `scope_overlap.py`. ✅
- **Unit test** (`tests/unit/test_daemon_overlap_filter.py`): 1 passed (the RED anchor). ✅

---

## Summary

| Check | Severity | Result |
|-------|----------|--------|
| Helper purity | CRITICAL | ✅ PASS |
| WHERE clause completeness (AC5) | CRITICAL | ✅ PASS |
| No regression on no-ignores path | CRITICAL | ✅ PASS |
| Event emission gating (AC2/AC3) | CRITICAL | ✅ PASS |
| Commit pattern | HIGH | ✅ PASS |
| String literal consistency | HIGH | ✅ PASS |
| Pure helper test scope | MEDIUM | ✅ PASS (no over-building) |
| Lint / typecheck | — | ✅ All pass |

**Total findings: 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW**

No blockers. S04 implementation is clean.