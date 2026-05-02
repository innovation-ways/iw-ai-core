# CR-00028_S09_CodeReview_Final_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Review Step**: S09 (Final Cross-Agent Review)
**Implementation Steps Reviewed**: S01..S08

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — design (especially AC1–AC7)
- All step reports: S01..S08
- All per-agent review reports: S02, S04, S06, S08
- All files in any implementation step's `files_changed`

## Output Files

- `ai-dev/active/CR-00028/reports/CR-00028_S09_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** for CR-00028. The change touches the database, the daemon, the actions API, the dashboard templates, and the test suite. Per-agent reviews caught local issues; your job is to catch cross-cutting issues they couldn't:

1. **The end-to-end chain**: enum (S01) → daemon transition writes new value (S03) → batch_manager exclusion sets / group computation see new value (S03) → actions endpoint accepts/rejects new value correctly (S03) → templates render new badge / buttons (S05) → tests assert all of the above (S07).
2. **The invariant**: "setup of item N+1 runs only after item N's merge is 100% complete" — verify it survives end-to-end.
3. **The cascade is preserved for legacy `failed`** — operator-explicit "give up" path via `abandon-merge` still triggers the same cascade with the same daemon event.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in any changed file = CRITICAL finding (`category: conventions`).

## Review Checklist

### 1. Completeness vs Design Document

Walk every section of `CR-00028_CR_Design.md`:

- Description ✓
- Current Behavior ✓
- Desired Behavior — verify each row of the desired-behavior table is implemented
- Affected Components table — verify each row's "Changed To" column matches the code
- Acceptance Criteria AC1–AC7 — each must have at least one test (S07) or verification (S15)

### 2. Chain Integrity

Trace one full scenario by reading code:

1. Mock a failed `worktree_commit.sh` exit
2. → `merge_queue._merge_item` writes `BatchItemStatus.merge_failed` (S03 change)
3. → next poll, `batch_manager._process_batch` calls `_current_execution_group(items)` — confirms it returns the group (not advances past)
4. → cascade gate `failed_in_prior_group` evaluates: `merge_failed not in _BLOCKING_TERMINAL_STATUSES` → no cascade
5. → dependent items stay `pending`, batch stays `executing`
6. → operator clicks "Retry merge" in dashboard → htmx POST → `actions.restart_merge` accepts `merge_failed` → flips to `completed`
7. → next merge_queue poll picks up the item, retries

Any break in this chain = CRITICAL finding.

### 3. Cross-Agent Consistency

- Are statuses referenced consistently as enum members (`BatchItemStatus.merge_failed`), not raw strings (`"merge_failed"`) — except in templates and `_merge_status()` where the API is intentionally string-typed?
- Daemon event types MUST match between emit-site (`merge_queue.py`, `actions.py`) and the SSE registry (`dashboard/routers/sse.py`). The `_WATCHED_EVENTS` set is an allow-list — events not in it are silently dropped. Verify:
  - `merge_conflict` (pre-existing) is in `_TOAST_EVENTS` and `_TOAST_SEVERITY` ✓ (no change required)
  - `merge_abandoned` (new) is in BOTH `_TOAST_EVENTS` and `_TOAST_SEVERITY` — CRITICAL if missing
  - `merge_restarted` (pre-existing) — out of scope for this CR; do not require it to be added
- Naming: `merge_failed` consistent across enum, code, badge dict, action-button macro, and `_merge_status()` return value? Confirm a single string value flows from `_merge_status` → template badge lookup → button condition.
- Confirm-modal pattern preserved: action buttons use `hx-get → /confirm-item/<action>/<id>` (NOT `hx-post` + `hx-confirm`). A direct `hx-confirm` attribute on either button = CRITICAL.
- `_ITEM_ACTION_LABELS["abandon-merge"]` registered with `danger=True` so the modal renders with the destructive-action visual treatment.

### 4. Integration Points

- Migration applies cleanly under daemon's pre-merge dry-run (verify by reading the migration file — `ALTER TYPE` syntax + IF NOT EXISTS + no-op downgrade)
- Dashboard fragment templates compile (no Jinja2 syntax errors) — try a smoke-render via TestClient if affordable
- htmx targets / response shapes — Retry-merge / Abandon return fragments compatible with the row's `hx-target`

### 5. Test Coverage (Holistic)

- All 7 ACs have test coverage (S07 + S15)
- Both happy path AND error paths covered (e.g., abandon-merge on wrong status returns 422)
- No regressed tests in the broader suite

### 6. Architecture Compliance

- Daemon stays sync (no async leaks)
- Composite PKs respected
- Append-only tables (`daemon_events`) used correctly
- DaemonEvent.metadata gotcha — `event_metadata` Python attr

### 7. Security & Robustness

- htmx `hx-confirm` on Abandon (irreversible without manual SQL)
- No hardcoded URLs, ports, credentials
- Endpoints return 422 (not 500) on bad input

### 8. SQL / DB Migration

- Re-read the migration file. Does `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'merge_failed'` run cleanly in PostgreSQL 14+?
- Is downgrade a documented no-op?
- Does `revision` chain to the current head?

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass with zero failures. Integration failure = CRITICAL.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "CR-00028",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": "AC chain trace summary"
}
```

`verdict`: `pass` if 0 CRITICAL + 0 HIGH + 0 MEDIUM (fixable). `mandatory_fix_count` = sum of those three.
