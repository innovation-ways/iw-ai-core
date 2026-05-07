# Browser Verification Prompt: F-00079-S19-BrowserVerification

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S19
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: read-only introspection (`docker ps`, `docker inspect`, `docker logs`); `./ai-core.sh` and `make` targets; `docker compose exec app ...` for re-running the seed if you write a fixture file.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Read-only inspection only. The migration was already applied to the E2E stack at provisioning time.

## Environment

The IW orchestrator has already started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports, hostnames, or credentials. Always use the env vars.

Do NOT run any of the following:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build` — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` exclusively
- Any direct `chromium.launch()` Python/Node snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- Files modified by S01 / S03 / S05 / S06 / S07 / S09 (see those reports)

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_S19_BrowserVerification_Report.md`
- `ai-dev/active/F-00079/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard requires login, follow the standard login flow per the IW conventions:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always call `playwright-cli snapshot` BEFORE `fill` / `click` to read current accessible refs. Do not reuse refs across pages.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/F-00079/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E PostgreSQL is seeded from the production orchestration DB via `pg_dump`. It reflects current production state. If your verifications require a specific work item with diff data:

- Pick an existing item known to have committed work in the production data dump (e.g., a recently completed F or I).
- If no suitable item exists in the seed, add a fixture under `ai-dev/active/F-00079/e2e_fixtures/001_files_view_seed.py` with a `def seed(db: Session) -> None` function (idempotent: `db.get(...)` before insert) that creates a `WorkItem` with non-null `diff_text` and `diff_summary`, plus a couple of completed `step_runs` with their own `diff_text`. Then re-run the seed:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from your host shell — it would write into the production DB on port 5433.

## Verification Steps

### V1: Files tab is reachable and renders the file tree

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/<chosen_item_id>` (use a project + item with diff data).
2. Click the "Files" tab button — this loads the new tab fragment.
3. **Verify**: the tab content area shows a left-side nested file tree with at least one file row carrying a status badge (A/M/D/R) and a `+N −M` count; aggregate counters in the toolbar match the sum of per-file counts.
4. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v1_files_tab_initial.png`.

### V2: Per-file diff renders with syntax highlighting

1. Click any file row in the tree — this scrolls the corresponding diff card into view and (if collapsed) expands it.
2. **Verify**: the diff card shows the unified diff with `+`/`−` line prefixes, syntax highlighting, and a sticky filename header.
3. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v2_file_diff_expanded.png`.

### V3: Step toggle filters diff content

1. Open the step selector dropdown in the toolbar.
2. Select a specific step (e.g., the `backend-impl` step) — this re-renders the diff content scoped to that step.
3. **Verify**: the visible file list shrinks (or stays the same if that step touched all files); aggregate counters update to reflect the step-scoped diff.
4. Switch back to "All steps (aggregate)" — counters and file list return to the aggregate view.
5. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v3_step_toggle.png`.

### V4: Filter input narrows visible files

1. Type a partial path substring into the filter input (e.g., `tests`).
2. **Verify**: tree rows and diff cards not matching the substring are hidden; aggregate counters update to reflect filtered scope.
3. Clear the input — full list returns.
4. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v4_filter.png`.

### V5: Untracked sub-panel works on a live worktree item

1. Pick an item that is in-progress (worktree alive).
2. Navigate to its Files tab.
3. Expand the "Other worktree files" sub-panel.
4. **Verify**: the sub-panel lists at least one untracked file; clicking a file loads its preview via the preserved `/artifact-raw` endpoint (markdown rendered, image inline, or text shown).
5. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v5_untracked_panel.png`.

### V6: Untracked sub-panel hidden on archived item

1. Navigate to an archived item's Files tab.
2. **Verify**: the "Other worktree files" sub-panel is NOT visible (item is archived → `worktree_alive=false` → panel suppressed).
3. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v6_archived_no_untracked.png`.

### V7: Export PDF downloads a non-empty PDF

1. Click "Export PDF" in the toolbar (with "All steps" selected).
2. **Verify**: the browser triggers a download of a `.pdf` file. Open it (or call `curl` against the same URL) to confirm the body is non-empty and starts with `%PDF-`.
3. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v7_pdf_export.png`.

### V8: Legacy `/tab/artifacts` returns 404

1. Navigate directly to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/<id>/tab/artifacts` (or the equivalent direct route).
2. **Verify**: the page returns HTTP 404 (or the tab content area shows the expected 404 fragment). The Artifacts button is gone from the tab bar.
3. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v8_artifacts_removed.png`.

### V9: Dark mode color scheme syncs with diff2html

1. Toggle the dashboard theme (the `☾ Toggle theme` button at the top right).
2. **Verify**: the diff cards re-render with dark-mode colors (dark backgrounds for added/removed lines; readable text contrast).
3. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v9_dark_mode.png`.

### V10: No Regressions

1. Revisit the Overview, Reports, Evidences, Logs tabs — confirm they all still render correctly with no console errors.
2. Confirm the `/artifact-raw` endpoint still works (used by the new untracked sub-panel) — the V5 step exercises this.
3. Verify no console errors appeared on any page visited during V1..V9.
4. **Screenshot**: `ai-dev/active/F-00079/evidences/post/F-00079_v10_no_regressions.png`.

## Pass Criteria

All V1..V10 must pass. Any failure (including partial / ambiguous result) → call `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but showed an empty-state message because the E2E DB lacks the historical rows the verification expects. Add a fixture file and prefix the reason with `ENV_DATA_MISSING:`:

```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V1 expects an item with diff_text populated — add ai-dev/active/F-00079/e2e_fixtures/001_files_view_seed.py" \
  --report ai-dev/active/F-00079/reports/F-00079_S19_BrowserVerification_Report.md
```

## Report

Write `ai-dev/active/F-00079/reports/F-00079_S19_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V10.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if you investigated root cause.
- A list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V10.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00079/reports/F-00079_S19_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00079/reports/F-00079_S19_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "F-00079",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Files tab reachable", "status": "pass|fail", "screenshot": "evidences/post/F-00079_v1_files_tab_initial.png", "notes": ""},
    {"id": "V2", "name": "Per-file diff renders", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V3", "name": "Step toggle filters diff", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V4", "name": "Filter narrows files", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V5", "name": "Untracked sub-panel works", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V6", "name": "Untracked hidden on archived", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V7", "name": "PDF export downloads", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V8", "name": "/tab/artifacts is 404", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V9", "name": "Dark mode sync", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V10", "name": "No regressions", "status": "pass|fail", "screenshot": "...", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
