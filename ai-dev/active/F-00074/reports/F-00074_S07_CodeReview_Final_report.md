# F-00074 S07 — Cross-Layer Final Code Review Report

## What Was Done

Reviewed all implementation layers (database, backend, API, frontend, tests) for F-00074 Keep-Alive Scheduler against the design document, cross-layer contracts, security invariants, and completeness checklist.

## Files Reviewed

| Layer | Files |
|-------|-------|
| Database | `orch/db/models.py` (KeepAliveConfig/Slot/Run), `orch/db/migrations/versions/4d9ec0083240_f00074_add_keepalive_tables.py` |
| Backend | `orch/keep_alive_service.py`, `orch/daemon/keep_alive_poller.py`, `orch/daemon/main.py` (keep-alive wiring) |
| API | `dashboard/routers/keep_alive.py`, `dashboard/app.py` (router registration) |
| Frontend | `dashboard/templates/pages/system/keep_alive.html`, `dashboard/templates/fragments/keep_alive_*.html`, `dashboard/templates/base.html` (nav), `dashboard/static/styles.css` |
| Tests | `tests/unit/test_keep_alive_service.py`, `tests/integration/test_keep_alive_integration.py`, `tests/dashboard/test_keep_alive_routes.py` |

## Cross-Layer Contract Verification

### KeepAliveConfig Singleton (INV-1)
- `KeepAliveConfig.id` is `Integer` PK (not BigInteger) — line 1840 of models.py
- Service `get_config()` fetches `id=1` directly (`db.get(KeepAliveConfig, 1)`) — line 58 of service.py
- Migration seeds `id=1` with defaults via `ON CONFLICT (id) DO NOTHING` — lines 75-79 of migration
- All slots created with `config_id=1` as default — line 97 of service.py

### API Router Design
- `keep_alive.router = APIRouter(tags=["keep-alive"])` — **no prefix** (line 19 of router)
- All paths are absolute: `/system/keep-alive`, `/api/keep-alive/config`, `/api/keep-alive/slots`, etc.
- Fragment paths match actual template files:
  - `fragments/keep_alive_config.html` → `ConfigPayload` Pydantic model
  - `fragments/keep_alive_slots.html` → context: `slots`, `config`
  - `fragments/keep_alive_timeline.html` → context: `slots`, `config`
  - `fragments/keep_alive_slot_row.html` → context: `slot`
  - `fragments/keep_alive_runs.html` → context: `runs`

### htmx Target ID Alignment
| Template element | ID | Used by |
|---|---|---|
| Slots list container div | `#slot-list` | Slot add form `hx-target`, delete button `hx-target` |
| Individual slot row | `#slot-row-{slot.id}` | Toggle button `hx-target`, delete button (inside row) |
| Timeline bar div | `#timeline-bar` | OOB swap from all slot mutations |
| Runs table container | `#runs-table` | Auto-refresh `hx-get` |
| Config form | (inline, no target) | Returns fragment + HX-Trigger toast |

### JSON Encoding
- Slot add form: `hx-ext="json-enc"` on `<form>` (keep_alive.html line 42) → `SlotPayload(BaseModel)` receives JSON body
- Config form: `hx-post="/api/keep-alive/config"` with `json-enc` → `ConfigPayload(BaseModel)` receives JSON body

### OOB Swap Pattern
All slot mutation routes (POST/DELETE/PATCH) return `_slots_and_timeline_response()` which appends:
```html
<div id="timeline-bar" hx-swap-oob="innerHTML">{timeline_html}</div>
```
The page template has `<div id="timeline-bar" class="relative h-8 rounded ...">` as the timeline container, so the OOB swap correctly updates the timeline bar in-place.

### PATCH /toggle Response
Returns slot row fragment (primary swap) + timeline OOB swap (secondary) — matching the POST/DELETE pattern.

## Security Verification

### Subprocess Injection Risk — CLEAN
- `fire_claude()` uses `subprocess.run(["claude", "-p", message], ...)` — **list form, NOT `shell=True`** (line 226 of service.py)
- `message` is from `_MESSAGES` hardcoded pool (15 strings, lines 25-41) — not user-supplied
- No credentials or tokens passed beyond ambient environment — no `env=` argument to `subprocess.run()`
- `time_hhmm` validation in `add_slot()` (via `_validate_time_hhmm()`) prevents malformed strings reaching DB

## Daemon Integrity

- `KeepAlivePoller.poll()` exception caught in `daemon/main.py` lines 590-593 — crash cannot propagate to daemon loop
- Poll-count gap is **exactly 6** (line 587: `>= 6`) — correct per design (6 ticks ≈ 60 s)
- Poller opens fresh `SessionLocal()` per `poll()` call (line 46 of poller.py) — no session reuse across ticks
- `_fire_slot()` and `_log_run()` each open their own sessions — correct isolation

## Invariants Verification

| Invariant | Status | Evidence |
|---|---|---|
| INV-1: Singleton config (id=1) | ✅ | `db.get(KeepAliveConfig, 1)`, migration seed `ON CONFLICT DO NOTHING` |
| INV-2: Unique `time_hhmm` | ✅ | `UniqueConstraint("time_hhmm")` in model line 1860 + migration line 54; `IntegrityError` → 409 in router |
| INV-3: At most one fire per slot per day | ✅ | `get_due_slots()` checks `status.in_(("success", "retried_success"))` for today's date |
| INV-4: Status enum values | ✅ | `VALID_RUN_STATUSES = ("success", "failed", "retried_success", "retried_failed")` line 182 |
| INV-5: Subprocess timeout 30s | ✅ | `subprocess.run(..., timeout=30)` line 230 |
| INV-6: Ambient env, no custom env | ✅ | No `env=` argument to `subprocess.run()` |
| INV-7: Delete → SET NULL | ✅ | `KeepAliveRun.slot_id` FK `ondelete="SET NULL"` model line 1892; integration test `test_delete_slot_nullifies_run_slot_id` passes |

## Completeness Verification

| Item | Status |
|---|---|
| All 7 API endpoints implemented | ✅ |
| Router registered in `dashboard/app.py` line 189 | ✅ |
| Nav entry `('/system/keep-alive', 'Keep-Alive')` in `base.html` line 112 | ✅ |
| All 5 template files exist | ✅ (confirmed via glob) |
| `make css` ran successfully | ✅ (S05 report; styles.css is 55,312 bytes) |
| `dashboard/static/styles.css` up to date | ✅ |

## Test Results

| Suite | Command | Result |
|---|---|---|
| Lint | `make lint` | ⚠️ 2 pre-existing ARG001 errors in `dashboard/routers/code_qa.py:67,70` (unrelated to F-00074) |
| Format | `make format` | ✅ 499 files already formatted |
| Typecheck | `make typecheck` | ✅ Success: no issues in 206 source files |
| Unit tests | `make test-unit` | ⚠️ 4 pre-existing failures (`test_qv_baseline`, `test_i00049_gate_command`, `test_make_targets×2`); **2188 passed including all 9 keep-alive unit tests** |
| Keep-alive unit tests | `uv run pytest tests/unit/test_keep_alive_service.py` | ✅ **9 passed** |
| Integration tests | `uv run pytest tests/integration/test_keep_alive_integration.py` | ✅ **10 passed** |
| Dashboard tests | `uv run pytest tests/dashboard/test_keep_alive_routes.py` | ✅ **10 passed** |

**All F-00074-specific tests pass. Pre-existing failures are confirmed unrelated to this work item (verified in S02/S03 via git stash).**

## Pre-Existing Issues (Not Introduced by F-00074)

1. **Lint**: 2× ARG001 (unused `dsl` parameter) in `dashboard/routers/code_qa.py:67,70` — pre-existing since at least S03
2. **Unit test failures** (4): `test_qv_baseline`, `test_i00049_gate_command`, `test_make_targets×2` — pre-existing baseline failures unrelated to F-00074

## Findings

No CRITICAL or HIGH severity issues found.

**LOW severity observations:**
- The `keep_alive_config.html` fragment is returned as a plain `HTMLResponse` (not `TemplateResponse`) with `HX-Trigger` header on success — this is correct behavior per design, but the toast notification depends on the client handling the `HX-Trigger` header. No issues detected.

## Verdict

**PASS** — All cross-layer contracts verified, all invariants satisfied, all F-00074 tests passing, no security issues, no CRITICAL/HIGH findings.

---

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00074",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "layer_coverage": {
    "database": "reviewed",
    "backend": "reviewed",
    "api": "reviewed",
    "frontend": "reviewed",
    "tests": "reviewed"
  },
  "tests_passed": true,
  "test_summary": "make lint: 2 pre-existing ARG001 errors (unrelated); make typecheck: success; make test-unit: 4 pre-existing failures, 2188 passed (9 keep-alive unit tests pass); integration: 10 passed; dashboard: 10 passed"
}
```
