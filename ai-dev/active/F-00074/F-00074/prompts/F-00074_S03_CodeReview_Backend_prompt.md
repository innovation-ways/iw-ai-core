# F-00074_S03_CodeReview_Backend_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Steps Being Reviewed**: S01 + S02
**Review Step**: S03
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status F-00074 --json`
- `ai-dev/active/F-00074/F-00074_Feature_Design.md`
- `ai-dev/active/F-00074/reports/F-00074_S01_Database_report.md`
- `ai-dev/active/F-00074/reports/F-00074_S02_Backend_report.md`
- `orch/db/models.py` (new `KeepAlive*` models)
- `orch/db/migrations/versions/<rev>_f00074_add_keepalive_tables.py`
- `orch/keep_alive_service.py`
- `orch/daemon/keep_alive_poller.py`
- `orch/daemon/main.py` (daemon wiring diff)

## Output Files

- `ai-dev/active/F-00074/reports/F-00074_S03_CodeReview_report.md`

## Review Checklist

### Database (S01)

- [ ] Three models present: `KeepAliveConfig`, `KeepAliveSlot`, `KeepAliveRun`
- [ ] `KeepAliveConfig.id` is `Integer` (not BigInteger) — singleton semantics
- [ ] `KeepAliveSlot.time_hhmm` has unique constraint `uq_keep_alive_slots_time`
- [ ] `KeepAliveRun.slot_id` is nullable FK with `ON DELETE SET NULL` (not CASCADE)
- [ ] `_TIMESTAMPTZ` alias used for all datetime columns
- [ ] `from __future__ import annotations` in migration file
- [ ] Migration `down_revision` is `add_diagram_doc_type`
- [ ] `upgrade()` seeds the singleton config row with `ON CONFLICT (id) DO NOTHING`
- [ ] `downgrade()` drops tables in correct dependency order
- [ ] `uv run iw migrations dry-run` passed (per S01 report)

### Service (S02)

- [ ] `_MESSAGES` pool contains at least 10 distinct messages
- [ ] `pick_message()` uses `random.choice()` (not sequential)
- [ ] `get_config()` handles missing row gracefully (creates with defaults)
- [ ] `add_slot()` validates `time_hhmm` format before DB insert (raises `ValueError` on invalid)
- [ ] `get_due_slots()` uses **local** `datetime.now()` — no timezone conversion
- [ ] Due-slot check: slot fired today with `status in ('success','retried_success')` → skip
- [ ] Due-slot window is exactly 30 minutes back from now (not 31, not configurable)
- [ ] `fire_claude()` uses `subprocess.run()` (blocking), NOT `subprocess.Popen()`
- [ ] `fire_claude()` has `timeout=30` guard; `TimeoutExpired` → failure result
- [ ] `fire_claude()` does NOT retry — retry is the poller's responsibility
- [ ] Poller: each slot processed independently (one failure doesn't skip others)
- [ ] Poller: opens a fresh `SessionLocal()` per `poll()` call (not reused)
- [ ] Poller: logs via `logging.getLogger('orch.keep_alive')`
- [ ] Daemon wiring: poll-count gap is 6 ticks
- [ ] Daemon wiring: `KeepAlivePoller.poll()` exception is caught and logged (daemon continues)
- [ ] No hardcoded ports, credentials, or paths

### Code quality

- [ ] Type annotations complete (no bare `Any`)
- [ ] `make lint` passes (per S02 report)
- [ ] `make typecheck` passes (per S02 report)

## Test Verification

Run and confirm pass:

```bash
make lint
make typecheck
make test-unit
```

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | `slot_id` FK uses CASCADE instead of SET NULL; poller exception propagates to daemon (crashes loop); subprocess.Popen used without wait (zombie processes); local time violated (tz-aware used) |
| HIGH | Missing uniqueness on `time_hhmm`; singleton seeding absent from migration; `fire_claude` retries internally (violates invariant) |
| MEDIUM | Missing `timeout` on subprocess; message pool fewer than 10 entries; poller reuses session across calls |
| LOW | Minor naming inconsistency; missing log message |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "F-00074",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
