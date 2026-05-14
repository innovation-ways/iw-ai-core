# F-00082_S02_CodeReview_prompt

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Step Being Reviewed**: S01 (API)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` are allowed.

## ⛔ Migrations: agents generate, daemon applies

S01 must not have added migrations. If it did, that's a CRITICAL finding — flag it and stop.

## Input Files

- **Authoritative state**: `uv run iw item-status F-00082 --json`.
- `ai-dev/active/F-00082/F-00082_Feature_Design.md`.
- `ai-dev/active/F-00082/reports/F-00082_S01_API_report.md` (the implementer's report).
- Every file listed in the S01 report's `files_changed`.
- Service-layer contract: `orch/cancel.py` (read but do not modify).

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S02_CodeReview_report.md`.

## Read the Design Document FIRST

Before opening any source: read §Acceptance Criteria and §Invariants in `F-00082_Feature_Design.md`. Write down every test file the design names (`tests/dashboard/test_actions_cancel_batch.py`, `tests/dashboard/test_actions_cancel_item.py`); cross-check against the S01 `files_changed` list. The dedicated test-coverage step is S05, so S01 is only required to have anchor RED tests — but missing anchors entirely is CRITICAL.

## Pre-Review Lint & Format Gate

Run `make lint` and `make format-check`. New errors → CRITICAL.

## Review Checklist

Score each item as `pass | medium | high | critical`.

### Contract correctness
1. `cancel_item` POST handler calls `orch.cancel.cancel_work_item(db, project_id, item_id, reason=…, to_draft=…)` — exact kwarg names, no positional drift.
2. `cancel_batch` POST handler calls `orch.cancel.cancel_batch(db, project_id, batch_id, reason=…, reset_items=…)` — exact kwargs.
3. `LookupError` → HTTP 404 (not 400, not 500).
4. `ValueError` → HTTP 422 by default; HTTP 409 only when the message contains `"active batch"` (the only Conflict-class error per the design).
5. No direct manipulation of `BatchStatus.*` / `WorkItemStatus.*` / `BatchItemStatus.*` enums in the rewritten handlers. (Invariant 1, Invariant 5.) `grep` is the right tool.
6. Form params declared with `Form(...)`, with sensible defaults (`reason="cancelled by operator"`, `to_draft=False`, `reset_items=False`).
7. The toast text on success surfaces `teardown_errors` as **separate warning lines** — they do not change the HTTP status code (Invariant 4).

### Confirm-dialog GET handler
8. The handler branches on `action == "cancel"` and returns the form-bearing template name. Other actions (approve/pause/resume/kill) still return `fragments/confirm_action.html` byte-identically — no regression.
9. Template context for cancel includes `default_reason`, `reset_field_name`, `reset_field_label`. Names match what S03 expects.

### `_ACTION_LABELS` copy
10. Item cancel and batch cancel entries have destructive copy mentioning worktree teardown and the optional draft reset.

### Anchor tests
11. ≥3 anchor tests are present in `tests/dashboard/test_actions_cancel_*.py`. Each test names a `tdd_red_evidence` line in the S01 report.
12. Tests monkey-patch `orch.cancel.cancel_*` rather than mocking the DB (Rule R3 of `tests/CLAUDE.md`).

### Hygiene
13. No `from orch.daemon.…` imports in the dashboard handler (would be a layer violation).
14. No `print()` / `logging.debug(...)` left for debugging.
15. Type annotations on every new parameter; `mypy` clean.
16. ruff clean on the touched files.

## Finding Severities

- **CRITICAL**: invariant or AC violation; would cause incorrect cancellation, data corruption, or status-code mismatch with the design.
- **HIGH**: layer-violation, dead code, missing TDD evidence on a behavioural change.
- **MEDIUM**: incomplete copy, missing docstring, weak test.
- **LOW**: nit / preference.

## Report Format

Write `F-00082_S02_CodeReview_report.md` with a top summary table:

```
| # | Severity | Finding | File:line | Suggested fix |
```

End with a one-line verdict: `OVERALL: PASS | NEEDS_FIX`. If any CRITICAL or HIGH remains, verdict is NEEDS_FIX (orchestrator runs a fix cycle).

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00082",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/F-00082/reports/F-00082_S02_CodeReview_report.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "n/a — review step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "OVERALL: PASS | NEEDS_FIX (echo here)"
}
```
