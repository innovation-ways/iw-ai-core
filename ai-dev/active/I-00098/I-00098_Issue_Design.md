# I-00098: Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-18
**Reported By**: sergio (diagnosed while triaging I-00090 S12 failure on 2026-05-18)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This item adds no docker-compose changes. Testcontainer fixtures used by the new integration test are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item leaves migrations unchanged** — the fix is service-layer Python only. The `keep_alive_runs` table schema (`fired_at: TIMESTAMPTZ`) is correct; the bug is in how `orch/keep_alive_service.py:get_due_slots` queries it.

## Description

The keep-alive scheduler re-fires slots that have already succeeded earlier today for roughly one hour around local midnight whenever the host's local timezone differs from UTC. The duplicate fires happen on every daemon poll cycle (~60s) during that window — visible as extra `claude` subprocess invocations and extra `keep_alive_runs` rows. The bug surfaced when I-00090's S12 integration-test gate failed intermittently at 00:35 WEST (= 23:35 UTC May 17): `test_poll_skips_slot_already_run_today` exercised exactly this code path and was mis-diagnosed as `pytest-randomly` order-dependence.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key references:
- `orch/CLAUDE.md` — service layer conventions, SQLAlchemy 2.0 style.
- `tests/CLAUDE.md` — `pytest-randomly` per-test template-clone isolation; testcontainer rules.
- `skills/iw-ai-core-testing/SKILL.md` — TDD RED evidence, semantic-strength assertions.

## Steps to Reproduce

1. Configure a Keep-Alive slot for time HH:MM (e.g., 23:00 local) and enable it.
2. Let the daemon's `KeepAlivePoller` poll once during the slot's 30-min window so a `KeepAliveRun(status='success')` row is written for today.
3. Wait until local time has crossed midnight but UTC has not (e.g., on a host in WEST/+01:00, between 00:00 and 00:59 local = 23:00–23:59 UTC the prior day).
4. Trigger another poll within the slot's window (or reduce the window logic so the same slot is still considered).

**Expected**: The slot is recognized as "already run today" via the successful run from step 2; `fire_claude` is NOT called again; no new `KeepAliveRun` row is written.

**Actual**: `get_due_slots()` returns the slot as if no run had landed today; `fire_claude` is called again (and retried on failure, so up to 2 calls per poll); a duplicate `KeepAliveRun` row is written for the same calendar day.

## Root Cause Analysis

In `orch/keep_alive_service.py:128-175` (`get_due_slots`):

```python
now = datetime.now()                            # NAÏVE LOCAL time
today_date = now.date()                         # local calendar date
...
run_exists = (
    db.query(KeepAliveRun)
    .filter(
        KeepAliveRun.slot_time == slot.time_hhmm,
        func.date(KeepAliveRun.fired_at) == today_date,   # <-- BUG
        KeepAliveRun.status.in_(("success", "retried_success")),
    )
    .first()
)
```

`KeepAliveRun.fired_at` is `_TIMESTAMPTZ` (see `orch/db/models.py:2238-2240`) and is written by the server default `func.now()`. PostgreSQL stores TIMESTAMPTZ values as UTC internally. **`func.date()` applied to a TIMESTAMPTZ value evaluates in the session's `TimeZone` setting** — which is UTC by default for the official `postgres` image (used by both testcontainers and the production orch DB).

When the host's local timezone differs from UTC (the IW AI Core dev/CI host is in Europe/Lisbon, WEST = UTC+1 in DST), the two halves of the filter use different timezones:

- `today_date` — naïve local. At 00:35 WEST May 18 → `2026-05-18`.
- `func.date(KeepAliveRun.fired_at)` — UTC (session TZ). The earlier successful run fired at, say, 23:00 WEST May 17 = 22:00 UTC May 17. `func.date()` returns `2026-05-17`.

The filter `2026-05-17 == 2026-05-18` is false → `run_exists is None` → the slot is treated as due → `fire_claude` is called.

The bug-exposing window per local TZ offset:

| Local TZ offset | Bug window (local time) |
|-----------------|-------------------------|
| UTC | none (no mismatch) |
| UTC+1 (WEST DST) | 00:00–00:59 |
| UTC+2 (CEST) | 00:00–01:59 |
| UTC-5 (EST) | 19:00–23:59 prev day in local-vs-UTC ordering — slot fires across local midnight only if the slot itself is in the prev-day-local window |

Audit: `grep -rn "func\.date" orch/ dashboard/` returns exactly this one occurrence (verified 2026-05-18). No other call sites need the same fix.

The `tests/integration/test_keep_alive_poller_integration.py::test_poll_skips_slot_already_run_today` test landed in I-00087 (commit `40c2e2b2`) but used `log_run()` with the DB-default `fired_at = now()` — it happens to pass at most times of day because both halves land on the same UTC date; it only flakes when the test executes during the local-midnight UTC window. I-00090's hardening pinned the test to local-noon via `freeze_time`, which **stops the flake but hides the bug**. I-00098 fixes the production code and adds a near-midnight regression test that would fail pre-fix.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/keep_alive_service.py` (`get_due_slots`) | Date-mismatch filter mis-identifies already-run slots as due during the local-midnight UTC window. |
| `orch/daemon/keep_alive_poller.py` (`KeepAlivePoller.poll`) | Consumes `get_due_slots`; spawns duplicate `claude` subprocesses and writes duplicate `KeepAliveRun` rows. |
| `keep_alive_runs` table | Accumulates duplicate rows during the bug window (no schema change needed). |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Replace the `func.date(fired_at) == today_date` filter in `get_due_slots` with a `TIMESTAMPTZ` half-open range using **tz-aware** local-midnight bounds: `fired_at >= today_start_local AND fired_at < tomorrow_start_local`. Construct the bounds from the system's local tz (via `datetime.now().astimezone().tzinfo`) so they are tz-aware and unambiguous regardless of the DB session's `TimeZone` setting. | — |
| S02 | `code-review-impl` | Review S01 — predicate correctness, tz-aware datetime construction, no scope creep, lint/format clean. | — |
| S03 | `tests-impl` | Add new integration test(s) in `tests/integration/test_keep_alive_integration.py` exercising `get_due_slots` against a real testcontainer DB. The bug-exposing test freezes Python's clock at 00:30 local (an offset that maps to the previous calendar day in UTC) and seeds a `KeepAliveRun(status='success', fired_at=<earlier-today local>)` via the **server default** `func.now()` (call `log_run()` and then re-stamp `fired_at` via raw `UPDATE` to a known earlier-today instant, OR write a small helper). Plus parametrized variants for UTC, +01:00 DST, +02:00 CEST, and a host whose local tz is behind UTC. Each variant asserts `get_due_slots(db)` returns `[]` after a `success`-status run was logged. | — |
| S04 | `code-review-impl` | Review S03 — RED evidence; assertions verify behaviour (no slot returned), not just shape; testcontainer isolation; no `importlib.reload(orch.config)`. | — |
| S05 | `code-review-final-impl` | Cross-step review: design ↔ predicate ↔ test consistency; AC1/AC2 traceability; scope adherence to `allowed_paths`. | — |
| S06..S12 | QV Gates | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests (1800s budget) | — |
| S13 | `self-assess-impl` | Self-assessment via `iw-item-analyze`. | — |

Agent slugs and gate menu follow `skills/iw-workflow/SKILL.md`. No `qv-browser` step — backend-only fix.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. The `keep_alive_runs` schema (`fired_at` TIMESTAMPTZ + `server_default=func.now()`) is correct.

### Code Changes

- **Files to modify**:
  - `orch/keep_alive_service.py` — replace the `func.date(...)` predicate in `get_due_slots`.
  - `tests/integration/test_keep_alive_integration.py` — add the bug-exposing test + tz-variant cases.
- **Nature of change**: SQLAlchemy filter expression replaced; predicate semantics preserved (still "no successful run today") but evaluated on instants instead of date-cast values.

## File Manifest

All files for this work item live under `ai-dev/active/I-00098/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00098_Issue_Design.md` | Design | This document |
| `I-00098_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00098_S01_Backend_prompt.md` | Prompt | S01 fix instructions |
| `prompts/I-00098_S02_CodeReview_Backend_prompt.md` | Prompt | S02 backend review |
| `prompts/I-00098_S03_Tests_prompt.md` | Prompt | S03 regression tests |
| `prompts/I-00098_S04_CodeReview_Tests_prompt.md` | Prompt | S04 tests review |
| `prompts/I-00098_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-step review |
| `prompts/I-00098_S13_SelfAssess_prompt.md` | Prompt | S13 self-assessment |

Reports are created during execution in `ai-dev/active/I-00098/reports/`.

## Test to Reproduce

A failing integration test that demonstrates the bug before the fix and passes after. Uses the testcontainer-backed `db_session` fixture and freezes time to the local-midnight UTC mismatch window:

```python
# tests/integration/test_keep_alive_integration.py (NEW test in this file)

from datetime import UTC, datetime, timedelta
from freezegun import freeze_time
from sqlalchemy import text

def test_get_due_slots_skips_already_run_slot_across_utc_midnight(
    db_session,
) -> None:
    """Reproduces I-00098: at 00:30 local (= 23:30 UTC prev day on a +01:00 host),
    a slot with an earlier-today successful run was incorrectly returned as 'due'
    because the previous filter compared a UTC-evaluated DATE against a local DATE."""
    from orch.db.models import KeepAliveRun
    from orch.keep_alive_service import (
        add_slot, get_config, get_due_slots, log_run,
    )

    # Pin Python's clock to 00:30 local on 2026-05-18 (UTC sees 2026-05-17 23:30
    # on a +01:00 host — different calendar date).
    frozen_local = datetime(2026, 5, 18, 0, 30, 0)
    with freeze_time(frozen_local):
        # Configure slot fired at 00:15 today (in window for 00:30).
        get_config(db_session)
        db_session.flush()
        slot = add_slot(db_session, "00:15")
        run = log_run(db_session, slot.id, "00:15", "success")
        db_session.flush()

        # Re-stamp fired_at to a deterministic earlier-today-local / yesterday-UTC
        # instant. `func.now()` is server-side and `freezegun` cannot freeze it,
        # so without this re-stamp the test would be wall-clock-dependent and
        # would pass against pre-fix code (hiding the bug).
        db_session.execute(
            text("UPDATE keep_alive_runs SET fired_at = :ts WHERE id = :id"),
            {"ts": datetime(2026, 5, 17, 23, 30, tzinfo=UTC), "id": run.id},
        )
        db_session.commit()

        # Pre-fix: get_due_slots returns [slot] because
        #   func.date(fired_at)   == 2026-05-17 (UTC)
        #   today_date            == 2026-05-18 (local)
        # Post-fix: get_due_slots returns [] because the range filter is on
        # instants — `2026-05-17 23:30 UTC` falls inside
        # `[2026-05-18 00:00 +01:00, 2026-05-19 00:00 +01:00)`
        # = `[2026-05-17 23:00 UTC, 2026-05-18 23:00 UTC)`.
        assert get_due_slots(db_session) == []
```

The test relies on the testcontainer Postgres defaulting to session-TZ UTC (current behaviour). The RED expectation is that the pre-fix code returns the slot, the post-fix code returns `[]`. The re-stamp via raw `UPDATE` is required because `func.now()` is server-side and `freezegun` cannot freeze it — leaving `fired_at` as `func.now()` makes the test wall-clock-dependent and would mask the bug (the test would pass against pre-fix code on most CI clocks).

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a KeepAliveSlot configured for time HH:MM
  AND a KeepAliveRun(status='success') already exists for that slot for the
      current local calendar day
  AND the host's local time is in the local-midnight UTC mismatch window
      (local date != UTC date)
When the daemon calls get_due_slots(db) again
Then get_due_slots returns an empty list
  AND fire_claude is NOT invoked
  AND no additional KeepAliveRun row is written
```

### AC2: Regression test exists

```
Given the fix is applied
When the integration test suite runs
Then test_get_due_slots_skips_already_run_slot_across_utc_midnight passes
  AND the same test would have failed against the pre-fix code (RED captured
      in S03's tdd_red_evidence)
```

### AC3: No behavioural regression in non-bug timezones

```
Given a host whose local timezone equals UTC (no mismatch window)
When a successful run is logged and get_due_slots is called the same day
Then the slot is correctly skipped
  AND the existing tests in test_keep_alive_integration.py and
      test_keep_alive_poller_integration.py all remain green
```

## Regression Prevention

- **TZ-aware bounds throughout `get_due_slots`** — the fix removes the only `func.date(...)` call site in `orch/` and `dashboard/` (audit: `grep -rn 'func\.date' orch/ dashboard/` returns one match before this fix, zero after).
- **Parametrized tz coverage in S03** — bug-exposing test + UTC, +01:00, +02:00, and behind-UTC variants reduce the chance of a future "I'm in UTC, looks fine" regression.
- **Lesson captured in `tests/CLAUDE.md`** — out of scope for this incident, but flagged in the design notes: a follow-up doc PR should add a "TIMESTAMPTZ + naïve `datetime.now()` is a foot-gun" entry under the Gotchas section.

## Dependencies

- **Depends on**: None. (I-00090 is unrelated structurally and is already in flight; whether it merges before or after I-00098 is irrelevant — both edits live in different files.)
- **Blocks**: None.

## Impacted Paths

- `orch/keep_alive_service.py`
- `tests/integration/test_keep_alive_integration.py`

## TDD Approach

- **Reproducing test**: `test_get_due_slots_skips_already_run_slot_across_utc_midnight` in `tests/integration/test_keep_alive_integration.py` — fails pre-fix, passes post-fix.
- **Unit tests**: Not added. The bug lives in SQL semantics that mocks cannot reproduce; the existing mocked unit tests in `tests/unit/test_keep_alive_service.py` remain unchanged.
- **Integration tests**: Bug-exposing test plus tz-offset parametrized variants (UTC, +01:00 DST WEST, +02:00 CEST, and one offset behind UTC), each freezing Python's clock and asserting `get_due_slots(db) == []` after a successful run is logged.

## Notes

- The same bug pattern (naïve-local `datetime.now()` + `func.date()` over TIMESTAMPTZ) could recur in any future scheduler-style query. Worth flagging in `tests/CLAUDE.md` Gotchas as a follow-up.
- The I-00090 hardened test (`test_poll_skips_slot_already_run_today` pinned to noon-local) remains valid under the fix and is left untouched by this item.
- The new tests are integration-only because the bug is fundamentally about SQL evaluation semantics; a pure-Python unit test with a mocked DB cannot demonstrate it.
