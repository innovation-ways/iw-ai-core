# Browser Verification Prompt: CR-00058-S14-BrowserVerification

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S14
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived infrastructure containers are outside your scope. Allowed exceptions: testcontainer fixtures via pytest; read-only `docker ps`/`inspect`/`logs`; invoking `./ai-core.sh` or `make`; `docker compose exec` for running the seed inside an already-up stack.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB. Read-only `alembic history/current/show` is fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports, hostnames, or absolute route paths. Navigate via the UI when possible (open a list page and click the item under test).

Before asserting on the content of any page, first confirm the page loaded successfully (HTTP 200, no unhandled-exception page, no load-time console errors). A 5xx is itself a `code_defect` finding.

Do NOT run: `make dev`, `make e2e-up`, any `docker compose up/down/restart/build`, `playwright install`, `agent-browser`, direct `chromium.launch()`. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md` — design doc; AC6
- `dashboard/templates/fragments/batch_items_rows.html` (modified)
- `dashboard/routers/batches.py` (modified)
- `dashboard/static/styles.css` (potentially modified)
- `dashboard/templates/_partials/help/batches.html`, `_partials/help/queue.html`, `_partials/help/batch_detail.html` (modified)

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S14_BrowserVerification_Report.md`
- `ai-dev/active/CR-00058/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in with `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` via the standard login flow (snapshot first, then fill/click using the accessible refs).

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production via `pg_dump`. For this CR's verifications, you need both event types present (`item_held_for_scope` and `item_overlap_allowed_by_policy`) for at least one batch in the test project. If the seed doesn't contain them, add a fixture file `ai-dev/active/CR-00058/e2e_fixtures/001_overlap_gate_events.py` that:

- Picks an existing `Batch` with at least one `BatchItem` (any status) — or seeds a synthetic batch with two items: one in status `pending` with a recent `item_held_for_scope` DaemonEvent, one in status `executing` with a recent `item_overlap_allowed_by_policy` DaemonEvent and metadata `{candidate_item_id, in_flight_item_ids, dropped_globs, matched_allow_patterns}` matching the design's contract.
- Exports `def seed(db: Session) -> None`; idempotent.

Then re-run the seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

**NEVER run the seed from the host shell** — it would write to the production DB on port 5433.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

The agent will visit every distinct page in V1..V(n) and check for dangling fragment refs, unhandled HTMX/JS errors, and 5xx responses. V0 failure does not skip V1..V(n).

### V1: Held-reason pill renders on a held batch item

1. Navigate from the project home to the **Batches** list page (click the project's "Batches" tab/link). Open the batch that contains the seeded held item.
2. **Verify:** the held item's row shows the existing held-reason pill (text matches the format produced by `item_held_for_scope` events — e.g. "held by scope overlap on …" or the wording used in the current pill).
3. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/CR-00058/evidences/post/CR-00058_v1_held_pill.png`.

### V2: New "policy allowed" pill renders on a released batch item

1. On the same batch detail page (or navigate to the batch that contains the seeded allowed item), locate the row for the item with an `item_overlap_allowed_by_policy` event.
2. **Verify:** the row shows a new info-tone pill whose visible text references "policy allowed" and includes at least one matched allow pattern (e.g. `dashboard/**`). Hover the pill (or inspect `title`) to confirm the tooltip lists the full set of matched allow patterns and the blocking item IDs from the event metadata.
3. **Screenshot:** `ai-dev/active/CR-00058/evidences/post/CR-00058_v2_policy_allowed_pill.png`.

### V3: Held precedence — held pill wins when both events exist

1. If the seed contains an item with BOTH event types in the window, navigate to it (otherwise add a fixture row to create the dual case).
2. **Verify:** only the **held** pill renders for that item — the policy-allowed pill is suppressed.
3. **Screenshot:** `ai-dev/active/CR-00058/evidences/post/CR-00058_v3_held_precedence.png`.

### V4: Queue page surfaces the same pills

1. Navigate to the project's **Queue** page.
2. **Verify:** items with the seeded events show the same pill tones as on Batches (held / policy_allowed). The visual treatment may differ if Queue uses a denser row, but the *presence* and *text* of the pills must match.
3. **Screenshot:** `ai-dev/active/CR-00058/evidences/post/CR-00058_v4_queue_pills.png`.

### V5: Help partial mentions the new pill

1. On Batches, Queue, and Batch Detail pages, open the help panel/popover (existing UI element — find it via snapshot).
2. **Verify:** each help panel contains a sentence describing the new "policy allowed" pill (added in S04).
3. **Screenshot:** `ai-dev/active/CR-00058/evidences/post/CR-00058_v5_help_copy.png`.

### V6: No Regressions

1. Revisit adjacent UI: batch list filters, item detail link from a batch item row, the existing "held" pill on items that don't have a policy-allowed event.
2. Verify no new console errors on any page visited during V1..V5.
3. **Screenshot:** `ai-dev/active/CR-00058/evidences/post/CR-00058_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure requires `iw step-fail` with a classified `--reason` (CODE_DEFECT, ENV_DATA_MISSING, SPEC_MISMATCH). See template guidance.

## Report

Write `ai-dev/active/CR-00058/reports/CR-00058_S14_BrowserVerification_Report.md` with a per-V pass/fail table, the `$IW_BROWSER_BASE_URL` used, any issues with `file:line` references, the screenshot list, and a "No regressions observed" subsection. Then call `iw step-done` (pass) or `iw step-fail` (fail), always with `--report`.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "CR-00058",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "...",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Held-reason pill renders", "status": "pass|fail|n/a", "failure_class": "...|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Policy-allowed pill renders", "status": "...", "failure_class": "...|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Held precedence", "status": "...", "failure_class": "...|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Queue page surfaces pills", "status": "...", "failure_class": "...|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Help partial mentions new pill", "status": "...", "failure_class": "...|null", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions", "status": "...", "failure_class": "...|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
