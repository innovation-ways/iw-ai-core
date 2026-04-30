# F-00074_S07_CodeReview_Final_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Review Step**: S07 — Cross-Layer Global Review
**Agent**: code-review-final-impl

---

## Input Files

- `uv run iw item-status F-00074 --json`
- `ai-dev/active/F-00074/F-00074_Feature_Design.md`
- All step reports: `reports/F-00074_S01_*.md` through `reports/F-00074_S06_*.md`
- `orch/db/models.py` (KeepAlive* models)
- `orch/db/migrations/versions/<rev>_f00074_add_keepalive_tables.py`
- `orch/keep_alive_service.py`
- `orch/daemon/keep_alive_poller.py`
- `orch/daemon/main.py`
- `dashboard/routers/keep_alive.py`
- `dashboard/app.py`
- `dashboard/templates/pages/system/keep_alive.html`
- `dashboard/templates/fragments/keep_alive_*.html`
- `dashboard/templates/base.html`
- `tests/unit/test_keep_alive_service.py`
- `tests/integration/test_keep_alive_integration.py`
- `tests/dashboard/test_keep_alive_routes.py`

## Output Files

- `ai-dev/active/F-00074/reports/F-00074_S07_CodeReview_Final_report.md`

## Review Scope

Cross-layer consistency, integration correctness, completeness, and security. Check that every layer agreed on contracts, invariants were maintained end-to-end, and no layer assumed something the adjacent layer did not deliver.

## Checklist

### Cross-layer contracts

- [ ] `KeepAliveConfig` singleton (`id=1`) is referenced consistently in models, service, migration seed, and API tests.
- [ ] `keep_alive.router` has **no prefix** in `APIRouter(...)` — page route is `/system/keep-alive`, API routes are `/api/keep-alive/...`, all defined as absolute paths on the same router.
- [ ] Fragment template names match exactly what the API router calls (`TemplateResponse(...)` path == actual file path).
- [ ] Context variable names passed from router match what templates reference (e.g., `slots`, `config`, `runs`, `available_models`, `available_durations`).
- [ ] htmx `hx-target` IDs in templates match HTML element IDs (`#slot-list`, `#runs-table`, `#timeline-bar`, `#config-form`, `#slot-row-{{ slot.id }}`).
- [ ] `PATCH /api/keep-alive/slots/{id}/toggle` returns a slot row fragment (primary) + timeline OOB swap (secondary) — same OOB pattern as POST/DELETE slots.
- [ ] Slot add form uses `hx-ext="json-enc"` so `SlotPayload(BaseModel)` receives a JSON body (not URL-encoded form data).
- [ ] Config form also uses `hx-ext="json-enc"` (or equivalent) for `ConfigPayload(BaseModel)`.
- [ ] POST/DELETE/PATCH slot mutation routes return the timeline OOB fragment (`<div id="timeline-bar" hx-swap-oob="innerHTML">...`) so the timeline updates without a separate GET request.

### Security

- [ ] No subprocess shell injection: `fire_claude` uses `["claude", "-p", message]` as a list (NOT `shell=True`). If S02 used `shell=True`, flag as CRITICAL.
- [ ] `message` content is from the hardcoded pool — not from user input — so injection is moot, but verify anyway.
- [ ] No credentials or tokens passed to the subprocess beyond what the ambient environment provides.
- [ ] No file paths constructed from user-supplied `time_hhmm` values.
- [ ] `time_hhmm` validation in `add_slot()` prevents malformed strings reaching the DB.

### Completeness

- [ ] All 7 API endpoints from the design are implemented in `keep_alive.py`.
- [ ] Router is registered in `dashboard/app.py`.
- [ ] Nav entry present in `base.html` `system_links`.
- [ ] All 5 template files exist: `keep_alive.html`, `keep_alive_slots.html`, `keep_alive_slot_row.html`, `keep_alive_timeline.html`, `keep_alive_runs.html`.
- [ ] `make css` was run and `dashboard/static/styles.css` is updated (per S05 report).

### Daemon integrity

- [ ] `KeepAlivePoller.poll()` exception is caught in `daemon/main.py` — a crash cannot bring down the daemon loop.
- [ ] Poll-count gap is exactly 6 (not less — would fire too frequently; not more — would miss slots).
- [ ] Poller does not hold a DB session across poll ticks (opens/closes per call).

### Test coverage

- [ ] Unit tests cover all 7 due-slot scenarios from the Boundary Behavior table.
- [ ] Integration tests cover the FK SET NULL behaviour (delete slot → run.slot_id = NULL).
- [ ] Dashboard tests cover 409 on duplicate slot and 404 on missing slot/config.
- [ ] No test connects to port 5433.

### Invariants (from design doc)

- [ ] INV-1: Singleton config (id=1) — verified by integration test.
- [ ] INV-2: Unique `time_hhmm` — unique constraint in migration + IntegrityError test.
- [ ] INV-3: At most one successful fire per slot per calendar day — verified by unit test.
- [ ] INV-4: Status enum values — all four used in code match the four allowed strings.
- [ ] INV-5: Subprocess timeout 30 s enforced in `fire_claude`.
- [ ] INV-6: Subprocess inherits ambient environment — no custom env dict in `subprocess.run`.
- [ ] INV-7: Delete → SET NULL (not CASCADE) — verified by integration test.

## Test Verification

Run the full suite:

```bash
make lint
make format
make typecheck
make test-unit
make allure-integration
```

All must pass before issuing a `pass` verdict.

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | `shell=True` in subprocess (injection risk); daemon poll loop not guarded; missing router registration; template path mismatch (renders wrong page); router has prefix that conflicts with API paths (all API routes become unreachable) |
| HIGH | Missing htmx target ID alignment; singleton not seeded in migration; missing 409 on duplicate; FK uses CASCADE not SET NULL; slot/config form sends form-encoded not JSON (API returns 422) |
| MEDIUM | Missing nav entry; timeline midnight-wrap not implemented; missing OOB timeline swap in slot mutations (timeline never updates) |
| LOW | Minor naming inconsistency; cosmetic template issue |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00074",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "layer_coverage": {
    "database": "reviewed",
    "backend": "reviewed",
    "api": "reviewed",
    "frontend": "reviewed",
    "tests": "reviewed"
  },
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
