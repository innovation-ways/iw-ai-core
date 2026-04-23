# Browser Verification Prompt: F-00059-S12-BrowserVerification

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S12
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutation command.
See S01 banner. If a testcontainer appears stuck, rely on pytest teardown /
Ryuk — never `docker kill`.

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from
THIS worktree's source code. The environment is ready before this prompt
runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use
the env var.

Do NOT run any of:
- `make dev`, `make e2e-up`, or any `docker compose` command — the stack is up.
- `playwright install` or `npx playwright install` — the CLI is pre-installed.
- `agent-browser` — this environment uses `playwright-cli` **exclusively**.
- `chromium.launch()` snippets — always go through `playwright-cli`.

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — design doc, especially *AC3*
- Files modified by S01..S06:
  - `orch/db/models.py`, `orch/db/migrations/versions/{hash}_add_functional_doc_columns.py`
  - `orch/cli/item_commands.py`, `scripts/backfill_functional_doc.py`
  - `dashboard/routers/items.py`
  - `dashboard/templates/fragments/item_functional_doc.html`
  - `dashboard/templates/pages/project/item_detail.html`

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S12_BrowserVerification_Report.md`
- `ai-dev/active/F-00059/evidences/post/` — screenshots

## Prerequisites

Every QvBrowser run MUST start with:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then authenticate:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always call `playwright-cli snapshot` **before** `fill` / `click`. Do not
   guess selectors.
2. Wait for navigation/transitions before re-snapshotting.
3. Screenshots go under `ai-dev/active/F-00059/evidences/post/`.

## E2E DB seed data

The E2E stack starts with a fresh Postgres + schema + migrations + baseline
seed (`scripts/e2e_seed.py`). For F-00059 this verification requires:

- At least one work item with `functional_doc_content` populated (a paragraph
  or two so the tab is non-trivial).
- At least one work item with `functional_doc_content = NULL` AND
  `functional_doc_path = NULL` (to prove the empty state).

If the baseline seed does not cover both, add a fixture at:

```
ai-dev/active/F-00059/e2e_fixtures/001_functional_doc_seed.py
```

Exporting `def seed(db: Session) -> None`, idempotent.

## Verification Steps

### V1: Functional Design tab renders with content (AC3)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<seeded-project>/item/<populated-item>`.
2. **Verify:** the item detail page loads; the tab row shows "Design Document"
   and immediately after it a new "Functional Design" tab. Tab order:
   Overview → Design Document → Functional Design → Reports → ... (or the
   current ordering with Functional Design inserted right after Design
   Document).
3. Click "Functional Design".
4. **Verify:** the tab content swaps to rendered markdown containing the
   seeded prose (assert on a unique word from the seed).
5. **Verify:** the required H2 sections (Why, What Changed, How It Behaves)
   are visible as headings in the rendered HTML.
6. **Screenshot:** `ai-dev/active/F-00059/evidences/post/F-00059_v1_populated_tab.png`.

### V2: Empty state for items without content

1. Navigate to the item seeded with NULL `functional_doc_content`.
2. Click "Functional Design".
3. **Verify:** the tab renders the empty-state message referencing the
   backfill script path — no server error, no broken layout.
4. **Screenshot:** `ai-dev/active/F-00059/evidences/post/F-00059_v2_empty_state.png`.

### V3: Design Document tab still works

1. On the same item (NULL functional doc) click "Design Document".
2. **Verify:** the existing design-doc content renders exactly as before the
   feature shipped — no changes to headings, font sizes, or styling.
3. Click back to "Functional Design" and back to "Design Document" twice in
   quick succession.
4. **Verify:** no stale content bleeds between tabs; htmx swap is clean.
5. **Screenshot:** `ai-dev/active/F-00059/evidences/post/F-00059_v3_design_doc_unchanged.png`.

### V4: No Regressions

1. Open Overview, Reports, Artifacts, Evidences, Logs, Fix Cycles, Execution
   Report tabs on the populated item in sequence.
2. **Verify:** each tab renders without console errors; the tab row is
   visually unchanged except for the added "Functional Design" button;
   keyboard focus order across tabs is sensible.
3. Navigate to the project home / dashboard home.
4. **Verify:** no console errors; no visual regressions.
5. **Screenshot:** `ai-dev/active/F-00059/evidences/post/F-00059_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure — including ambiguous or partial results —
requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page errored, threw a console exception, or rendered
  wrongly. Fix-cycle can patch this. Normal `--reason`.
- **ENV_DATA_MISSING** — page rendered HTTP 200 but showed empty state because
  seed lacked the expected data. Prefix `--reason` with `ENV_DATA_MISSING:`
  so the daemon classifies the failure correctly; the fix path is to add a
  seed fixture, not to retry.

## Report

Write `ai-dev/active/F-00059/reports/F-00059_S12_BrowserVerification_Report.md` with:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references.
- A list of captured screenshots.
- A **No regressions observed** subsection covering V4.

Then call exactly one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00059/reports/F-00059_S12_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00059/reports/F-00059_S12_BrowserVerification_Report.md
```

Always include `--report` on both paths.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "F-00059",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "functional tab renders content", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "empty state for null content", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "design-doc tab unchanged", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
