# F-00074: Keep-Alive Scheduler

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-30
**Status**: Draft

---

## Description

A system-level Keep-Alive Scheduler that fires `claude` CLI messages at configurable daily time slots to maintain Claude Max subscription usage windows. The daemon checks due slots every ~60 seconds, fires a randomly-chosen greeting via the `claude` CLI subprocess, retries once on failure, and logs each execution. A new System page provides full configuration: model selection, window-duration setting, per-slot enable/disable toggles, a 24-hour visual timeline showing coverage blocks, and a last-10-runs table.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key rules: NEVER connect tests to live DB (port 5433) — use testcontainers only; NEVER mock the database in integration tests; NEVER use `agent-browser` for browser automation — use `playwright-cli` exclusively.

## Scope

### In Scope

- Three new DB models: `KeepAliveConfig` (singleton global settings), `KeepAliveSlot` (one row per time slot), `KeepAliveRun` (execution log)
- Alembic migration creating `keep_alive_config`, `keep_alive_slots`, `keep_alive_runs` tables
- `KeepAliveService` in `orch/keep_alive_service.py`: CRUD for config/slots, due-slot detection (±30-minute missed-fire window), subprocess fire logic, run logging, randomized message selection
- `KeepAlivePoller` in `orch/daemon/keep_alive_poller.py` wired into the daemon's `_poll_cycle()` every 6 ticks (~60 s)
- API routes in new `dashboard/routers/keep_alive.py`: GET/POST config, GET/POST/DELETE/PATCH slots, GET last-10 runs; registered in `dashboard/app.py`
- New System page `dashboard/templates/pages/system/keep_alive.html`: model dropdown, window-duration dropdown, per-slot enable toggle + add/delete, 24-hour CSS timeline with green coverage blocks + gap highlighting + midnight wrap, last-10-runs table
- Nav entry `('/system/keep-alive', 'Keep-Alive')` added to `base.html` `system_links`
- Unit tests for due-slot detection and retry logic; integration tests for service CRUD; dashboard tests for page/routes

### Out of Scope

- Per-project or per-account keep-alive schedules (one global config only)
- Window-overlap guard / "already-open" detection
- Webhook or push notifications when a window expires
- Response content inspection or duration recording
- Coverage-percentage metric on the timeline
- Any retry beyond a single retry attempt

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `KeepAliveConfig`, `KeepAliveSlot`, `KeepAliveRun` models in `orch/db/models.py` + Alembic migration | — |
| S02 | backend-impl | `orch/keep_alive_service.py` (CRUD, due-slot logic, subprocess fire, run logging, message list) + `orch/daemon/keep_alive_poller.py` + daemon wiring | after S01 |
| S03 | code-review-impl | Review S01 + S02 (models, migration, service, poller, daemon wiring) | after S02 |
| S04 | api-impl | `dashboard/routers/keep_alive.py` (all routes) + register in `dashboard/app.py` | after S03 |
| S05 | frontend-impl | `dashboard/templates/pages/system/keep_alive.html`, `base.html` nav entry, `make css` | after S03, parallel with S04 |
| S06 | tests-impl | Unit tests for due-slot logic + retry; integration tests for service CRUD; dashboard page tests | after S04 + S05 |
| S07 | code-review-final-impl | Cross-layer global review of all S01–S06 work | after S06 |
| S08 | qv-gate | `make lint` | after S07 |
| S09 | qv-gate | `make format` | after S08 |
| S10 | qv-gate | `make typecheck` | after S09 |
| S11 | qv-gate | `make test-unit` | after S10 |
| S12 | qv-gate | `make allure-integration` | after S11 |
| S13 | qv-browser | End-to-end browser verification of /system/keep-alive page | after S12 |

### Database Changes

- **New tables**: `keep_alive_config`, `keep_alive_slots`, `keep_alive_runs`
- **Modified tables**: None
- **Migration notes**: Single linear migration off current head `add_diagram_doc_type`. `keep_alive_config` is a singleton table (one row, `id=1`); seeded with defaults in the migration's `upgrade()`. No enum changes.

### API Changes

- **New endpoints**:
  - `GET /system/keep-alive` — full page render
  - `GET /api/keep-alive/config` — return current config JSON
  - `POST /api/keep-alive/config` — update model + window_duration_hours; returns htmx fragment
  - `GET /api/keep-alive/slots` — list all slots JSON
  - `POST /api/keep-alive/slots` — add a new slot (time_hhmm); returns updated slot list fragment
  - `DELETE /api/keep-alive/slots/{slot_id}` — remove slot; returns updated slot list fragment
  - `PATCH /api/keep-alive/slots/{slot_id}/toggle` — flip enabled; returns updated slot row fragment
  - `GET /api/keep-alive/runs` — last 10 runs (for table)
- **Modified endpoints**: None

### Frontend Changes

- **New components**: `dashboard/templates/pages/system/keep_alive.html` (full page), htmx fragments for slot list and config form response
- **Modified components**: `dashboard/templates/base.html` (add `('/system/keep-alive', 'Keep-Alive')` to `system_links`)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00074/F-00074_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00074/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00074/prompts/F-00074_S01_Database_prompt.md` | Prompt | Database models + migration |
| `ai-dev/active/F-00074/prompts/F-00074_S02_Backend_prompt.md` | Prompt | Service + poller + daemon wiring |
| `ai-dev/active/F-00074/prompts/F-00074_S03_CodeReview_Backend_prompt.md` | Prompt | Code review of S01+S02 |
| `ai-dev/active/F-00074/prompts/F-00074_S04_API_prompt.md` | Prompt | API routes |
| `ai-dev/active/F-00074/prompts/F-00074_S05_Frontend_prompt.md` | Prompt | System page + nav |
| `ai-dev/active/F-00074/prompts/F-00074_S06_Tests_prompt.md` | Prompt | Unit + integration + dashboard tests |
| `ai-dev/active/F-00074/prompts/F-00074_S07_CodeReview_Final_prompt.md` | Prompt | Cross-layer global review |
| `ai-dev/active/F-00074/prompts/F-00074_S13_BrowserVerification_prompt.md` | Prompt | QV browser verification |
| `orch/db/models.py` | Modified | Add `KeepAliveConfig`, `KeepAliveSlot`, `KeepAliveRun` models |
| `orch/db/migrations/versions/<rev>_f00074_add_keepalive_tables.py` | New | Migration: create three tables, seed config defaults |
| `orch/keep_alive_service.py` | New | Service: CRUD, due-slot detection, subprocess fire, run logging |
| `orch/daemon/keep_alive_poller.py` | New | Poller: checks due slots every ~60s, fires claude subprocess |
| `orch/daemon/main.py` | Modified | Import and wire `KeepAlivePoller` into `_poll_cycle()` |
| `dashboard/routers/keep_alive.py` | New | FastAPI router with all keep-alive API + page routes |
| `dashboard/app.py` | Modified | Register `keep_alive` router |
| `dashboard/templates/pages/system/keep_alive.html` | New | Keep-alive system page |
| `dashboard/templates/base.html` | Modified | Add keep-alive nav entry to `system_links` |
| `tests/unit/test_keep_alive_service.py` | New | Unit tests: due-slot logic, retry, message randomization |
| `tests/integration/test_keep_alive_integration.py` | New | Integration tests: CRUD, slot CRUD, run logging |
| `tests/dashboard/test_keep_alive_routes.py` | New | Dashboard route tests |

## Acceptance Criteria

### AC1: Config persists and is reflected in the page

```
Given no keep-alive config has been saved yet
When the user opens /system/keep-alive for the first time
Then the page renders with default values: model=claude-sonnet-4-6, window_duration_hours=5, no slots
```

### AC2: Slot management

```
Given the keep-alive page is open
When the user adds a slot with time "10:02", then toggles it disabled, then deletes it
Then the slot list updates via htmx with each action (no full page reload), and the timeline refreshes accordingly
```

### AC3: Daemon fires due slots

```
Given a slot exists for "05:00" with enabled=true and no KeepAliveRun exists for today
When the daemon's KeepAlivePoller runs at 05:00 (±30 min)
Then a claude subprocess is spawned with a randomly-chosen message, and a KeepAliveRun row is written with status=success or status=retried_success
```

### AC4: Retry on failure

```
Given a slot is due and the first claude subprocess invocation fails (non-zero exit code)
When the poller catches the failure
Then it retries once; if the retry succeeds the run is logged as retried_success; if both fail the run is logged as retried_failed
```

### AC5: Missed-fire catch-up within 30 minutes

```
Given a slot for "05:00" exists and the daemon was restarted at 05:15 with no run logged for today
When the poller runs at 05:15
Then the slot is detected as missed (within 30-minute window) and fired immediately
```

### AC6: Timeline visualisation

```
Given slots at 05:00, 10:02, 15:04, 20:06 with window_duration_hours=5
When the user views /system/keep-alive
Then a 24-hour horizontal bar is visible, each slot renders a green block from its start time spanning 5 hours, uncovered gaps are highlighted in muted red, and the 20:06 block wraps correctly past midnight
```

### AC7: Last 10 runs table

```
Given more than 10 KeepAliveRun rows exist
When the page loads or the table refreshes
Then only the 10 most recent runs are shown, ordered newest-first, with fired_at timestamp and status badge
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Slot already fired today | Slot due, KeepAliveRun(status=success) exists for today | Poller skips — no second fire |
| Missed fire >30 min ago | Slot at 05:00, daemon starts at 06:00 | Skip (outside 30-min window) |
| Daemon starts exactly at slot time | Slot at 10:02, daemon polls at 10:02 | Fires immediately |
| All slots disabled | All KeepAliveSlot.enabled=false | Poller iterates but fires nothing |
| No config row | `keep_alive_config` table is empty | Poller is a no-op; page shows defaults |
| Slot time crosses midnight | Slot at 23:30, window_duration_hours=5 | Timeline block starts at 23:30, wraps to 04:30 next day (shown as two partial blocks) |
| window_duration_hours changed | User changes 5h → 3h | Timeline re-renders immediately with new block widths |
| Duplicate slot time | User adds "10:02" when it already exists | Router returns 409 Conflict; slot list unchanged |
| Claude CLI not on PATH | `claude` binary missing | Run logged as retried_failed with error message; daemon continues |
| Delete slot with existing runs | Slot deleted that has KeepAliveRun rows | Runs' `slot_id` set to NULL (nullable FK); runs remain in history |

## Invariants

1. At most one `keep_alive_config` row ever exists (`id=1` fixed; upsert pattern).
2. Each `KeepAliveSlot.time_hhmm` is unique — no two slots for the same time of day.
3. A slot is fired at most once per calendar day per `time_hhmm` (checked by poller before firing).
4. `KeepAliveRun.status` is one of: `success`, `failed`, `retried_success`, `retried_failed`.
5. The poller never blocks the daemon's main poll loop for more than 30 seconds (subprocess timeout enforced).
6. The `claude` subprocess inherits the full environment — no credential injection needed.
7. Deleting a `KeepAliveSlot` sets `KeepAliveRun.slot_id` to NULL, not cascades deletes.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/test_keep_alive_service.py`):
  - Due-slot detection: slot in window → fires; slot outside window → skips; slot fired today → skips
  - Retry logic: first call fails → retry; both fail → retried_failed
  - Message randomization: calling `pick_message()` 100 times returns at least 3 distinct messages
  - `time_hhmm` parsing: valid "HH:MM" → correct datetime; invalid → ValueError

- **Integration tests** (`tests/integration/test_keep_alive_integration.py`):
  - Config upsert: first call creates row; second call updates without creating duplicate
  - Slot CRUD: add, toggle enabled, delete; assert FK nullification on delete
  - Run logging: `log_run()` writes row; `get_recent_runs(limit=10)` returns ≤10 rows newest-first
  - Duplicate slot time rejected at DB level (unique constraint)

- **Dashboard tests** (`tests/dashboard/test_keep_alive_routes.py`):
  - `GET /system/keep-alive` returns 200 with expected page structure
  - `POST /api/keep-alive/config` with valid payload → 200; invalid payload → 422
  - `POST /api/keep-alive/slots` with duplicate time → 409
  - `DELETE /api/keep-alive/slots/{id}` non-existent → 404

## Notes

- The `claude` CLI invocation uses `-p "<message>"` (non-interactive single-prompt mode), matching the pattern already used in `orch/daemon/batch_manager.py:972`.
- Times are local system timezone (no tz conversion). The poller compares `datetime.now()` (no tz) against slot `time_hhmm` parsed as today's local datetime.
- The 15-message pool is hardcoded in `orch/keep_alive_service.py`; no DB storage or UI configuration for messages.
- The singleton config row (`id=1`) is seeded in the migration's `upgrade()` with defaults so the poller never encounters an empty config table on a live system.
- `make css` must be run after the Frontend step adds the new page, so the Tailwind classes are picked up in the built stylesheet.
