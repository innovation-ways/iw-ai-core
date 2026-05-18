# I-00098_S01_Backend_prompt

**Work Item**: I-00098 -- Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Read-only `docker ps` / `docker inspect` / `docker logs` is allowed; testcontainer fixtures inside pytest are allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp`. This item does NOT touch the schema — `keep_alive_runs` is already correct. If you find yourself reaching for a migration, STOP and raise a blocker.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00098 --json`
- `ai-dev/active/I-00098/I-00098_Issue_Design.md` — Authoritative spec
- `orch/keep_alive_service.py` — File to modify (`get_due_slots`)
- `orch/db/models.py:2223-2249` — `KeepAliveRun` definition (`fired_at` is TIMESTAMPTZ with `server_default=func.now()`)

## Output Files

- `orch/keep_alive_service.py` (modified)
- `ai-dev/active/I-00098/reports/I-00098_S01_Backend_report.md`

## Context

You are fixing a TZ-mismatch in `orch/keep_alive_service.py:get_due_slots`. The current code computes `today_date = datetime.now().date()` (naïve local) and filters `func.date(KeepAliveRun.fired_at) == today_date`. PostgreSQL evaluates `func.date()` on a TIMESTAMPTZ column in the session's `TimeZone` setting (UTC by default for the production image). On a host whose local timezone differs from UTC, the two dates disagree by one day around local midnight, the filter never matches, and the already-fired slot is reported as due.

Read the design document first to understand the full scope. Read `orch/CLAUDE.md` for SQLAlchemy 2.0 conventions and `tests/CLAUDE.md` for the test-side rules (you are NOT writing tests in this step — that's S03).

## Requirements

### 1. Replace the date-cast filter with a TIMESTAMPTZ range filter

Inside `get_due_slots` (currently at `orch/keep_alive_service.py:128-175`), the section that reads:

```python
now = datetime.now()  # noqa: DTZ005 local time per design intent
today_date = now.date()
...
run_exists = (
    db.query(KeepAliveRun)
    .filter(
        KeepAliveRun.slot_time == slot.time_hhmm,
        func.date(KeepAliveRun.fired_at) == today_date,
        KeepAliveRun.status.in_(("success", "retried_success")),
    )
    .first()
)
```

must be changed so that the date filter is replaced with a **half-open TIMESTAMPTZ range** built from tz-aware local-midnight bounds. The exact shape:

1. Compute `local_tz = datetime.now().astimezone().tzinfo` once. (This reflects the daemon host's wall-clock TZ — including DST — and is `None` only on hosts with no local TZ configured, which is not a target environment.)
2. Compute `today_start_local = datetime.combine(today_date, time.min).replace(tzinfo=local_tz)` and `tomorrow_start_local = today_start_local + timedelta(days=1)`.
3. Replace the `func.date(...) == today_date` line in the filter chain with two lines:
   ```python
   KeepAliveRun.fired_at >= today_start_local,
   KeepAliveRun.fired_at < tomorrow_start_local,
   ```
4. **Do NOT** also keep the `func.date(...)` line. The range is the only filter.
5. Update the docstring comment that says "`No KeepAliveRun exists for today (calendar day, local time) ...`" so it accurately describes the new semantics — still "today in local time" but phrased as a tz-aware range, not a date-cast comparison.

Imports: add `time` and `timedelta` is already imported; you'll also need `time` from `datetime`. Do not add unused imports.

### 2. Preserve every other behaviour in `get_due_slots`

- The `[now - 30min, now]` slot-time window logic (currently `lines 145-158`) is correct and must not be touched.
- The malformed-`time_hhmm` `try/except` must not be touched.
- The `enabled == True` slot query at line 143 must not be touched.
- The `status.in_(("success", "retried_success"))` predicate must not be touched.
- The function signature and return type (`list[KeepAliveSlot]`) must not change.

### 3. Do NOT touch any other code

- `orch/daemon/keep_alive_poller.py` — out of scope.
- `orch/db/models.py` — out of scope. The `_TIMESTAMPTZ` column is already correct.
- `tests/**` — out of scope. S03 owns the test changes.

## Project Conventions

Read `orch/CLAUDE.md`. Notable:

- SQLAlchemy 2.0 declarative style. Filters use `Column.op(...)` operator forms or natural Python comparison (`Column >= value`).
- psycopg v3 driver — naïve `datetime` objects compared against `TIMESTAMPTZ` columns can produce ambiguous behaviour; passing **tz-aware** bounds is required for this fix.
- Imports sorted via ruff isort rules; group `datetime` imports together.

## TDD Requirement

You are a Backend step. The behavioural test for this fix is written in S03 (`tests-impl`), not here. Per the project's TDD policy in `tests/CLAUDE.md` and the implementation prompt template:

- The S03 author will write the failing test first (RED). When their report becomes available you can use it as cross-evidence.
- For this S01 step, your `tdd_red_evidence` field should be `"n/a — behavioural regression test added in S03 (tests-impl); production logic change only"`.
- This is NOT a license to skip thinking about correctness — verify the fix manually by running a one-shot reproduction in a testcontainer (e.g., a small `uv run python -c '...'` snippet) and recording the result in your report's `notes` field.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting; re-stage if it changes the file.
2. `make typecheck` — zero errors on `orch/keep_alive_service.py`.
3. `make lint` — zero errors.

Record results in the `preflight` block of your result contract.

## Test Verification (NON-NEGOTIABLE)

Run only the **targeted** existing unit tests for the service module:

```bash
uv run pytest tests/unit/test_keep_alive_service.py -v
```

Do NOT run `make test-integration` or `make test-unit` — those are owned by S11/S12. If any pre-existing unit test that exercises `get_due_slots` breaks because of your change, investigate: the mocked unit tests use `MagicMock` and may not interact with the new tz-aware filter at all — but if they do break, that's evidence your fix changed observable behaviour incorrectly.

The behavioural integration tests for the bug are written in S03 — do NOT pre-emptively write them here.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00098",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/keep_alive_service.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/unit/test_keep_alive_service.py)",
  "tdd_red_evidence": "n/a — behavioural regression test added in S03 (tests-impl); production logic change only",
  "blockers": [],
  "notes": "Manually reproduced the bug pre-fix via testcontainer one-shot at <UTC-midnight-local mock instant>; verified the fixed code returns []. Verified `grep -rn 'func\\.date' orch/ dashboard/` returns zero matches after the fix."
}
```
