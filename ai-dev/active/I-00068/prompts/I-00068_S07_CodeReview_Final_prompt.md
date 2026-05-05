# I-00068_S07_CodeReview_Final_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds NO migrations — verify the diff confirms this.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document
- All implementation step reports under `ai-dev/active/I-00068/reports/I-00068_S0{1,3,5}_*_report.md`
- All per-agent code review reports under `ai-dev/active/I-00068/reports/I-00068_S0{2,4,6}_CodeReview_report.md`
- All files listed in S01 + S03 + S05 `files_changed`

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S07_CodeReview_Final_report.md`

## Context

You are performing the final cross-agent review for I-00068. Your job is to confirm the backend fix (S01), the template hardening (S03), and the regression tests (S05) work together to make the bug impossible to reintroduce.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Report new violations as CRITICAL findings.

## Review Checklist

### 1. Completeness vs Design Document

- AC1 (archive events carry `entity_type="batch"`) — covered by S01 + S05 backend test?
- AC2 (BATCH- IDs route to `/batch/` even with `entity_type=None`) — covered by S03 + S05 dashboard test?
- AC3 (existing `entity_type` routing preserved) — covered by S05 regression test?
- AC4 (generic `/item/` fallback still works for non-BATCH IDs) — covered by S05 negative test?
- AC5 (regression tests exist and are falsifiable) — confirmed?

If any AC has no corresponding implementation or test, that is a CRITICAL finding (`missing_requirements`).

### 2. Cross-Agent Consistency

- The signature change to `_emit` in S01 does not break any caller. Run `grep -rn "batch_archiver._emit\|from orch.archive.batch_archiver import _emit" orch/ tests/` and confirm only intra-file callers exist.
- The dashboard prefix check in S03 (`'BATCH-'`) matches the same prefix the backend writes (the actual batch IDs in the system are `BATCH-NNNNN`). Verify by reading `orch/cli/id_commands.py` or wherever batch IDs are minted, then confirm the prefix matches.
- The new test file `tests/integration/test_i00068_batch_link_routing.py` is not duplicating anything in `tests/integration/test_dashboard_pages.py`.

### 3. Integration Points

- The backend fix (S01) and template fix (S03) are both required for full coverage:
  - Without S01, new archive events still carry `entity_type=None`, but S03's prefix check catches them.
  - Without S03, historical events with `entity_type=None` are still broken — but S01 fixes new ones.
  - Both together: defence-in-depth.
- Confirm by reading both diffs end-to-end.

### 4. No regressions

Run `make test-integration` AND `make test-unit`. Existing tests pass:

- `tests/integration/test_dashboard_pages.py::test_recent_activity_batch_event_links_to_batch_route`
- `tests/integration/test_dashboard_pages.py::test_recent_activity_doc_job_event_links_to_doc_job_route`
- `tests/integration/test_dashboard_pages.py::test_recent_activity_work_item_event_links_to_item_route`
- `tests/integration/test_dashboard_pages.py::test_recent_activity_unknown_entity_type_falls_back_to_item_route`
- `tests/integration/test_dashboard_pages.py::test_recent_activity_no_link_renders_when_entity_id_is_null`
- All archiver tests (e.g., any in `tests/integration/test_batch_archiver*.py` or wherever).

### 5. Architecture Compliance

- Read `orch/CLAUDE.md` and `dashboard/CLAUDE.md` for conformance.
- No UPDATE/DELETE on `daemon_events` (append-only).
- No JS or Tailwind class changes (per design).
- `event_metadata` is the Python attribute name (not `metadata`).

### 6. Security

- Template autoescape is preserved.
- No SQL injection (ORM constructor used correctly).
- No XSS (no `|safe`, no `Markup(...)`).

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass with zero failures. Integration test failures are CRITICAL.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00068",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
