# I-00098_S02_CodeReview_Backend_prompt

**Work Item**: I-00098 -- Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` / `docker logs` is allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item touches no migrations; flag any migration file in `files_changed` as a CRITICAL scope-violation finding.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00098 --json`
- `ai-dev/active/I-00098/I-00098_Issue_Design.md`
- `ai-dev/active/I-00098/reports/I-00098_S01_Backend_report.md`
- All files listed in S01's `files_changed` (should be exactly `orch/keep_alive_service.py`)

## Output Files

- `ai-dev/active/I-00098/reports/I-00098_S02_CodeReview_report.md`

## Context

You are reviewing the Backend fix to `orch/keep_alive_service.py:get_due_slots`. The design replaces a `func.date(KeepAliveRun.fired_at) == today_date` filter (which evaluates in session TZ on a TIMESTAMPTZ column) with a tz-aware `TIMESTAMPTZ` half-open range filter.

## Read the Design Document FIRST

Read `I-00098_Issue_Design.md` end-to-end before opening any code. Key anchors:

- **Acceptance Criteria AC1, AC2, AC3** — bug fixed in mismatch window, regression test exists, no behavioural regression in UTC.
- **Root Cause Analysis** — the predicate semantics that must be preserved.
- **Affected Components** — only `orch/keep_alive_service.py` should appear in `files_changed`; everything else is scope creep.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the changed files only:

```bash
uv run ruff check orch/keep_alive_service.py
uv run ruff format --check orch/keep_alive_service.py
```

If either reports NEW violations relative to `main`, file each as a CRITICAL finding (`category: "conventions"`).

## Review Checklist

### 1. Predicate Correctness (HIGHEST PRIORITY)

- **Half-open range**: filter must be `fired_at >= today_start_local AND fired_at < tomorrow_start_local`. A closed `<= tomorrow_start_local` would let a run from 00:00:00 of the next day count as "today" — flag as HIGH.
- **TZ awareness**: `today_start_local` MUST carry a `tzinfo` (e.g., `replace(tzinfo=local_tz)` where `local_tz = datetime.now().astimezone().tzinfo`). A naïve datetime here re-introduces ambiguity vs the TIMESTAMPTZ column — flag as CRITICAL.
- **Local-tz source**: the implementation should derive the local TZ from `datetime.now().astimezone().tzinfo`. A hardcoded `timezone(timedelta(hours=1))` or `ZoneInfo("Europe/Lisbon")` would not survive DST or relocation — flag as HIGH.
- **No remaining `func.date(...)` calls** anywhere in `orch/keep_alive_service.py`. Verify with `grep -n 'func\.date' orch/keep_alive_service.py` — output must be empty. If present, flag CRITICAL.
- **Other predicates intact**: `slot_time`, `status.in_(...)`, the enabled-slots query, and the `[now - 30min, now]` window logic must all be byte-for-byte unchanged. Any drift is at least MEDIUM (suggestion) — possibly HIGH if the semantics shift.

### 2. Scope Adherence

- `files_changed` must be `["orch/keep_alive_service.py"]` and nothing else. Any other path = CRITICAL scope-violation.
- No test files. S03 owns tests. If the agent wrote tests here, flag HIGH and note the duplication risk.

### 3. SQLAlchemy 2.0 Idiom

- Filter uses natural-Python comparison (`Column >= value`) — the project's house style.
- No bare `text("...")` SQL strings unless absolutely required.

### 4. Code Quality

- Imports: `time` from `datetime` added cleanly; no unused imports (`func` may now be unused — if so, removing it is correct; if it remains used elsewhere in the file, fine).
- Docstring updated to reflect the new semantics (still "today in local time", phrased as an instant-range, not a date-cast).

### 5a. TDD RED Evidence (behaviour-implementing step)

This is a behavioural change in a Backend step, but the behavioural test lives in S03 by design. Expectations:

- The report's `tdd_red_evidence` should be the literal `"n/a — behavioural regression test added in S03 (tests-impl); production logic change only"`.
- The report's `notes` field should describe a **manual** reproduction proving the fix works (the design spec calls this out explicitly — a small `uv run python -c '...'` snippet). If `notes` is empty or hand-waves the verification, flag MEDIUM (fixable).
- Do NOT mark this step as missing RED evidence — the design says S03 owns it.

## Test Verification

```bash
uv run pytest tests/unit/test_keep_alive_service.py -v
```

Report pass/fail in `test_summary`. If pre-existing tests break under the new predicate, that's evidence either (a) the unit tests were testing the buggy semantics — flag MEDIUM (suggestion) for follow-up — or (b) the fix is wrong, in which case raise HIGH.

## Severity Levels

Standard table: CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00098",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/unit/test_keep_alive_service.py)",
  "notes": ""
}
```
