# CR-00078_S05_CodeReview_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S05
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This step touched the daemon, not migrations.

## Scope of Review

Per-agent review of S04's daemon hook + helper.

1. **Helper purity** — `filter_blocked_by_ignores` has no DB import, no `Session` parameter, no logger calls. It is importable from `tests/unit/` without instantiating SQLAlchemy.

2. **Per-batch scope (AC5 critical)** — `grep -n 'BatchOverlapIgnore' orch/daemon/batch_manager.py` MUST show a WHERE clause that includes ALL THREE of `project_id`, `batch_id`, AND `held_item_id`. If any one is missing, that is a CRITICAL finding (AC5 violation).

3. **No regression on existing path** — when `ignored_pairs` is empty, the new code's behaviour MUST be identical to pre-CR (still emit `item_held_for_scope` for every blocking pair). Trace the diff carefully.

4. **Event emission gating** — `batch_overlap_allowed_by_ignore` is emitted ONLY when ignores cleared the hold (`not filtered_blocked_by and ignored_pairs`). It is NOT emitted when:
   - There were no ignores at all.
   - Ignores existed but didn't fully clear the hold (some pairs remain).

5. **Commit pattern** — matches the existing site (one `db.commit()` per item, not per event).

6. **String literal for event type** — `"batch_overlap_allowed_by_ignore"` is used consistently between the daemon (emitting) and any code that reads it (S06's Timeline rendering). Search for typos.

7. **Pure helper edge cases** — confirm that S04 added the single RED test case but stopped there (the full unit-test suite is owned by S10). If S04 over-built tests, that's MEDIUM (not CRITICAL) — note it for S10 to extend rather than duplicate.

## Severity Guide

- CRITICAL: missing `batch_id` or `project_id` in the ignore-table WHERE clause; regression on the no-ignores path; emission of `batch_overlap_allowed_by_ignore` when no ignores exist.
- HIGH: typo in event-type string; helper not pure.
- MEDIUM: over-emission, over-testing in S04, missing comments.
- LOW: naming, docstrings.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00078",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
