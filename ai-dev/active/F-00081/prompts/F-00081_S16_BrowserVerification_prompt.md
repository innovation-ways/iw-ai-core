# Browser Verification Prompt: F-00081-S16-BrowserVerification

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S16
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. You MUST NOT execute commands that change Docker container/volume/network state. Read-only `docker ps` / `docker inspect` / `docker logs` are allowed. `docker compose exec app …` is allowed and required when re-running the seed after writing a fixture file. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step. Read-only `alembic history|current|show` is allowed for diagnostics.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no other literal). Always read `$IW_BROWSER_BASE_URL`.

Do NOT run any of the following — they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make e2e-up`, or any `docker compose` start/stop/restart command — the stack is already up.
- `playwright install` or `npx playwright install` — the CLI is pre-installed.
- `agent-browser` — this environment uses `playwright-cli` exclusively.
- Any `chromium.launch()` Python/Node snippet — always go through `playwright-cli`.

## Input Files

- `ai-dev/active/F-00081/F-00081_Feature_Design.md` — the design.
- Implementation reports: `ai-dev/active/F-00081/reports/F-00081_S0[1-6]_*_report.md`.
- Files modified by S05 (frontend) — listed in `F-00081_S05_Frontend_report.md`:
  - `dashboard/templates/components/step_pipeline.html`
  - `dashboard/templates/fragments/batch_items_rows.html`
  - `dashboard/templates/fragments/item_overview.html`
  - `dashboard/static/styles.css`
- Files modified by S04 (API) — listed in `F-00081_S04_API_report.md`:
  - `dashboard/routers/runtime_overrides.py`

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S16_BrowserVerification_Report.md` — mandatory report.
- `ai-dev/active/F-00081/evidences/post/` — screenshots taken during verification.

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If a login screen appears (the iw-ai-core dashboard does not currently require auth, but if the E2E stack adds one):

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Always call `playwright-cli snapshot` before `fill`/`click` to read current accessible refs. Wait for transitions to settle before re-snapshotting.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. It reflects current production state — including this feature's migration once the daemon has applied it inside the worktree compose stack.

If your verifications require data not present in production (e.g. a batch with multiple items in mixed states with overrides set), add a fixture file:

```
ai-dev/active/F-00081/e2e_fixtures/001_runtime_override_demo.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent (`db.get(...)` before insert). After writing it, **re-run the seed inside the `app` container before opening the browser**:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from the host shell — the host's `.env` resolves to the production orchestration DB on port 5433 and you would write into the real DB. If `docker compose exec` fails, call `iw step-fail` with `ENV_DATA_MISSING:` so the daemon re-provisions the stack.

## Verification Steps

### V1: Compressed strip on batch items tab

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/batches` and click into any active or recent batch (or seed one via fixture if none exist). Then go to the items tab.
2. **Verify**: each row's step strip is visibly compact (no large coloured circles). Element class `.iw-step-strip` is present and contains one `.iw-step-seg` per workflow step. The strip's bounding box width is well under the prior ~50px-per-step layout — capture the page so reviewers can compare against `evidences/pre/F-00081-batch-items-before.png`.
3. Hover one segment and **verify** the tooltip text contains the step ID and status.
4. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v1_compressed_strip.png`.

### V2: CLI / Model columns visible on items tab

1. Stay on the items tab.
2. **Verify** two new columns labelled "CLI" and "Model" exist after the title column. Each row shows either a badge with a CLI / model label or "(default)" muted text.
3. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v2_cli_model_columns.png`.

### V3: Item detail dropdowns — editable when pending

1. Navigate to an item that has at least one `pending`, `failed`, or `paused` step (seed via fixture if necessary; the production E2E DB usually has at least one). The URL is `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/<F-or-I-id>`.
2. **Verify**: the steps table has CLI and Model columns. Editable rows render `<select>` elements; non-editable rows render plain badge text (no `<select>`).
3. Open the CLI `<select>` on a pending step and confirm both `OpenCode` and `Claude Code` options appear.
4. Open the Model `<select>` and confirm models filter to the chosen CLI (e.g. selecting Claude Code shows only Sonnet 4.6 and Opus 4.7, not MiniMax).
5. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v3_item_dropdowns.png`.

### V4: Override persistence end-to-end

1. On the same item, change the CLI dropdown for a pending step to `Claude Code` and the Model to `Opus 4.7`. Wait for the htmx swap.
2. **Verify** the row now shows the chosen pair as a badge (or stays as `<select>` with the new selection — match S05's chosen behaviour).
3. Reload the page. **Verify** the selection persists (the override hit the database).
4. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v4_override_persisted.png`.

### V5: Lock semantics on a completed step

1. On any item with a `completed` step, **verify** that step's CLI and Model cells render as read-only labels (no `<select>` element in the DOM for that row).
2. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v5_completed_locked.png`.

### V6: Bulk apply

1. On the same item, click "Apply to all remaining" (or whatever interaction S05 chose — read S05's report `notes`).
2. **Verify** every still-editable step row updates to show the same chosen pair.
3. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v6_bulk_apply.png`.

### V7: Default placeholder

1. Navigate to a freshly-registered item with no overrides set anywhere (seed if needed).
2. **Verify** the item-level CLI/Model badges on the batch items tab read `(default)` in muted text.
3. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v7_default_placeholder.png`.

### V8: No Regressions

1. Revisit the previous flows you used in V1–V7 plus adjacent ones: the queue page (`/project/iw-ai-core/queue`), the batches list, the item-fix-cycles tab, the worktrees page. Verify they still load and render correctly.
2. Verify no new console errors appeared on any page visited during V1–V7. Use the browser devtools snapshot via `playwright-cli snapshot` and inspect for error-state messaging.
3. **Screenshot**: `ai-dev/active/F-00081/evidences/post/F-00081_v8_no_regressions.png`.

## Pass Criteria

All V1..V8 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but the verification expects rows that the seed does not contain (e.g. an item with mixed step statuses). Add an `e2e_fixtures` file and prefix the reason with `ENV_DATA_MISSING:`:

```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V3 expects item with at least one pending step under batch with multiple items — add ai-dev/active/F-00081/e2e_fixtures/001_demo.py" \
  --report ai-dev/active/F-00081/reports/F-00081_S16_BrowserVerification_Report.md
```

## Report

After verification, write `ai-dev/active/F-00081/reports/F-00081_S16_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V8.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found with `file:line` references.
- The list of screenshots captured.
- A **No regressions observed** subsection covering V8.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00081/reports/F-00081_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00081/reports/F-00081_S16_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "F-00081",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Compressed strip on batch items tab", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "CLI / Model columns visible", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Item detail dropdowns editable", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Override persistence", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Lock semantics on completed step", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Bulk apply", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "Default placeholder", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "No Regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
