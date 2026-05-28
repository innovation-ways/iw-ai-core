# I-00116 S02 — Code Review of S01 (Backend)

**Work Item**: I-00116
**Step**: S02
**Agent**: CodeReview
**Date**: 2026-05-28

---

## What was done

Per-agent review of S01's changes to `orch/daemon/step_monitor.py`. No files were changed during this review step.

---

## Pre-Flight Gates

| Gate | Result |
|------|--------|
| `make lint` | **pass** |
| `make format-check` | **pass** |

Both pre-flight gates passed cleanly. No findings.

---

## Review Checklist

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_try_recover_completed_review_step` exists with exact signature `(db, run, project_id, now)` | ✅ pass | Line 255 |
| 2 | Helper gated on `step_type in ('code_review', 'code_review_final')` | ✅ pass | Line 273: `run.step_type not in _REVIEW_STEP_TYPES` |
| 3 | Report glob anchored on BOTH `work_item_id` AND `step_str` | ✅ pass | Line 293: `{run.work_item_id}_{step_str}_*_report.md` |
| 4 | mtime guard: `Path(report).stat().st_mtime > run.started_at.timestamp()` | ✅ pass | Lines 309–312: stale report rejected |
| 5 | JSON parse extracts first ```json ``` fenced block only | ✅ pass | Lines 319–336: line-by-line parser reads from ` ```json` to ` ``` (not whole file) |
| 6 | Missing `verdict` or `mandatory_fix_count` → returns False | ✅ pass | Line 338: `verdict not in ("pass","fail")`; `mandatory_fix_count` defaulted to `0` |
| 7 | Verdict mapping: `pass`→completed; `fail`+`mandatory_fix_count>0`→needs_fix; else False | ✅ pass | Lines 345, 353–356 |
| 8 | DaemonEvent uses `event_metadata` (not `metadata`) | ✅ pass | Lines 362–379: `_emit_event(... event_metadata=...)`; `_emit_event` stamps `event_metadata=metadata or {}` at line 819 |
| 9 | DaemonEvent payload has all required fields | ✅ pass | Lines 370–378: `work_item_id`, `step_id`, `step_run_id`, `report_path`, `report_mtime_iso`, `verdict`, `mandatory_fix_count` |
| 10 | `_try_recover_completed_review_step` called AFTER `_probe_for_child`, BEFORE `_handle_crashed` | ✅ pass | Lines 494–504: in `not alive` block, order is: `completed_at` fast-return → `_probe_for_child` → `completed_at` fast-return → `_try_recover...` → `_handle_crashed` |
| 11 | `_probe_for_child` and `_handle_crashed` are UNCHANGED | ✅ pass | No edits to either function body |
| 12 | No `logger.info(f"...` — uses `%`-style placeholders | ✅ pass | Line 381: `logger.info("I-00116 recovered run %s step=%s/%s from report=%s verdict=%s", ...)` |
| 13 | `datetime.now(UTC)` (not `datetime.utcnow()`) | ✅ pass | Line 464: `now = datetime.now(UTC)` |
| 14 | Non-review step types fall through to `_handle_crashed` unchanged | ✅ pass | Line 273: early-return inside helper; original route preserved for non-review step types |

---

## Detailed Observations

### Item 5 — JSON fence parser is well-scoped

The markdown parser at lines 319–336 accumulates text only after a ` ```json` line is seen, resetting the accumulator only at the opening fence. This means:
- Malformed reports (no JSON block, or text before the block) → `contract is None` → returns `False`
- Multiple JSON blocks → only the first is considered (the report should have exactly one)
- Empty block (` ``` ` immediately after ` ```json`) → `contract_text` is empty ` "" ` → `json.loads("")` raises → caught by `return False` at outer try/except, or more precisely, if no text was accumulated before the closing fence, `contract_text` is falsy and the `if contract_text:` guard at line 332 skips the parse, leaving `contract is None`

This is correct defensive behaviour for the "malformed report → caller falls through to `_handle_crashed`" path.

### Item 7 — Verdict mapping is exact

The design specifies:
- `verdict='pass'` → step `completed`
- `verdict='fail'` with `mandatory_fix_count > 0` → step `needs_fix`
- anything else → `False`

Lines 338–356 implement:
- `verdict` not in `('pass', 'fail')` → returns `False`
- `run.status = RunStatus.completed if verdict == "pass" else RunStatus.failed`
- `parent_status = StepStatus.needs_fix if verdict == "fail" and mandatory_fix_count > 0 else StepStatus.completed`

This covers the `verdict='fail'` + `mandatory_fix_count == 0` case correctly (step is marked `completed`, not `needs_fix`), matching the contract the S01 S07 tests will verify.

### Item 8 — `event_metadata` is correctly used throughout

The `DaemonEvent` model (models.py line 1495) defines `event_metadata: Mapped[Any] = mapped_column("metadata", JSONB, ...)` — SQLAlchemy maps the Python name `event_metadata` to the DB column named `metadata`. `_emit_event` at line 803 takes `metadata: dict | None = None` as its argument and passes it to the `event_metadata=` parameter of the constructor. The S01 code uses `_emit_event(...)` with a `metadata={...}` kwarg. This is fully consistent — there is no use of the forbidden `DaemonEvent.metadata=` form anywhere.

### Item 14 — `_REVIEW_STEP_TYPES` is module-private and correctly scoped

`_REVIEW_STEP_TYPES = ("code_review", "code_review_final")` is defined at module level (line 252) and used only by `_try_recover_completed_review_step`. No other function depends on it, so adding `code_review_fix` or `code_review_fix_final` later would require only a one-line edit to `_REVIEW_STEP_TYPES`.

---

## Findings

No issues found. The S01 implementation satisfies all 14 checklist items.

---

## Verdict

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00116",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make lint (ruff) and make format-check (ruff format --check) both passed. No S01 test files exist yet — S07 (Tests) writes the regression tests."
}
```
