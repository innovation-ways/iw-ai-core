# Browser Verification Prompt: I-00101-S15-BrowserVerification

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S15
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. `docker compose exec app …` is allowed when re-running the seed after writing a fixture; everything else (compose up/down/restart/build, image/volume/network prune, container kill/stop/rm) is forbidden. The orchestrator has already brought up the isolated e2e stack — do NOT attempt to start, stop, or rebuild any services.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var. Do NOT hardcode application route paths beyond the project home / lists; prefer to navigate via the UI (open `/system/running` or the project home and click the link/row for the seeded work item).

Do NOT run any of the following:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down` command — the stack is already up
- `playwright install` or `npx playwright install`
- `agent-browser` — use `playwright-cli` exclusively
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document
- `ai-dev/active/I-00101/I-00101_Functional.md` — functional doc (Why / What Changed / How It Behaves)
- `orch/daemon/scope_amendment.py` — helpers under test
- `dashboard/routers/actions.py` — new endpoints
- `dashboard/templates/components/scope_amend_modal.html` — modal
- `dashboard/templates/components/status_badge.html` — badge variant
- `dashboard/templates/fragments/item_steps_table.html` — button wiring

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S15_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/I-00101/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always `playwright-cli snapshot` BEFORE `fill`/`click`.
2. Wait for navigation between snapshots.
3. Screenshots go under `ai-dev/active/I-00101/evidences/post/` with descriptive names.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production via `pg_dump`. To verify the scope-blocked UI flow you need a synthetic work item with:

- A `WorkItem` row (any project, status=in_progress, worktree_path pointing at a fake tmp path that lives under the e2e container's fs).
- A `WorkflowStep` row in status `needs_fix`.
- A `FixCycle` row with `status=escalated, fix_metadata={"scope_violations": [".test-target.toml"]}`.
- A pre-existing fake worktree manifest at `<worktree>/ai-dev/active/<id>/workflow-manifest.json` with a narrow `scope.allowed_paths` (so the amend write can be observed).

Write a fixture file:

```
ai-dev/active/I-00101/e2e_fixtures/001_scope_blocked_seed.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent (`db.get(...)` before insert). It must also write the synthetic worktree manifest to a real filesystem path the e2e app container can reach (the worktree directory is mounted at `/workspace`, so write under `/workspace/.e2e-test-worktrees/I-00101-synth/ai-dev/active/I-00101-SYNTH/workflow-manifest.json`).

After writing the fixture file, re-run the seed inside the `app` container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from the host shell — the host's `.env` resolves to the production orchestration DB on port 5433 and would write test rows into the real DB. Only use `docker compose exec`. If `docker compose exec` fails (container unreachable), call `iw step-fail` with `ENV_DATA_MISSING:` so the daemon re-provisions the stack.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

The qv-browser agent prepends this automatically — page-route reachability, fragment-id integrity, console-error scan on every page visited in V1..V(n). Do NOT modify this step.

### V1: Scope-blocked badge renders on the item detail page

1. Navigate to `$IW_BROWSER_BASE_URL/system/running`.
2. Snapshot the page and find the row for the seeded synthetic work item (`I-00101-SYNTH` or whatever ID the fixture used). Click the item link.
3. **Verify:** the synthetic step's row in the steps table shows a badge labelled `Scope blocked` (NOT the generic `Needs Fix` amber pill). Hover the badge and confirm the title/aria-label lists `.test-target.toml`.
4. **Verify:** the existing `Restart` button is NOT visible on this row; the `Skip` button IS visible; a new `Amend scope & restart` button is visible; a new `Revert & restart` button is visible.
5. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00101/evidences/post/I-00101_v1_badge_visible.png`.

### V2: Amend modal opens with the offending path pre-checked

1. From V1's state, snapshot and click the `Amend scope & restart` button.
2. **Verify:** a modal appears titled `Amend scope for …`. It contains a checkbox labelled `.test-target.toml` and the checkbox is checked. Below, a read-only list of current `allowed_paths` is rendered.
3. **Screenshot:** save as `I-00101_v2_modal_open.png`.

### V3: Submitting the modal writes the manifest, emits the event, restarts the step

1. From V2's state, snapshot and click the modal's `Amend & restart` button.
2. **Verify:** the page refreshes (or shows a toast / hx-swap result). The step row no longer shows the `Scope blocked` badge — it shows `Pending` (or whatever pending-state badge the project uses). Wait up to 90 seconds; the daemon's next poll should also flip it to `In progress` if it picks the synthetic up — but if the synthetic step has no real launcher target the step will sit in `Pending`, which is acceptable. The acceptance criterion is "step is queued for restart"; pending is sufficient evidence.
3. **Verify:** in the same UI session, navigate to a Daemon Events view (if dashboard exposes one; otherwise read `/system/all-active` or any view that renders recent daemon events). Confirm the latest event for `I-00101-SYNTH` is `scope_amended_by_operator` with `added_paths` listing `.test-target.toml`. If the dashboard does not surface daemon events on any page, this sub-verification is skipped and noted in the report.
4. **Verify (filesystem, optional check via UI not available):** read the synthetic worktree's manifest by GET-ing whatever view exposes it (item detail tab, or the parent design-time copy via `/system/all-active`). Confirm `.test-target.toml` is now in `scope.allowed_paths`.
5. **Screenshot:** save as `I-00101_v3_after_amend.png`.

### V4: Revert flow on an adjacent flow (No Regressions setup)

If time and a second synthetic seed allow, re-seed a second scope-blocked item and exercise the **Revert & restart** path: click the button, confirm the `hx-confirm` prompt, verify the step transitions to pending without manifest amendment, and that a `scope_reverted_by_operator` event was emitted. If a second synthetic seed is not feasible in this run, skip V4 and note "covered by integration tests at S05" in the report.

**Screenshot (if performed):** `I-00101_v4_after_revert.png`.

### V(n): No Regressions

1. Visit `/system/running`, the project home, and one project's history page. Confirm no new console errors, no 500 pages, no broken layouts.
2. Confirm an existing `failed`/`needs_fix` step that is NOT scope-blocked still renders the generic `needs_fix` badge and the existing `Restart` + `Skip` buttons (find one via the seeded e2e database; if none exists, seed a second synthetic that has `status=needs_fix` but NO FixCycle).
3. **Screenshot:** `I-00101_v_n_no_regressions.png`.

## Pass Criteria

All V1..V(n) must pass. Classify any failure as CODE_DEFECT / ENV_DATA_MISSING / SPEC_MISMATCH per the QVBrowser_Prompt_Template guidance:

- **CODE_DEFECT** — page 5xx, console exception, wrong element. Use a normal `--reason`. Fix-cycle agent can patch.
- **ENV_DATA_MISSING** — page rendered cleanly but the synthetic seed is missing. Prefix with `ENV_DATA_MISSING:` and add/extend the fixture file. Re-run the seed via `docker compose exec`.
- **SPEC_MISMATCH** — verification asks for something the design explicitly excludes. Prefix with `SPEC_MISMATCH:` and cite the design doc line.

## Report

Write `ai-dev/active/I-00101/reports/I-00101_S15_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env).
- Any issues found, with `file:line` references if root cause was investigated.
- List of all screenshots captured.
- A "No regressions observed" subsection.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00101/reports/I-00101_S15_BrowserVerification_Report.md

# On failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00101/reports/I-00101_S15_BrowserVerification_Report.md
```

Always include `--report` on both paths.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "I-00101",
  "overall_status": "pass|fail",
  "v_results": [
    {"id": "V0", "status": "pass|fail", "notes": ""},
    {"id": "V1", "status": "pass|fail", "notes": ""},
    {"id": "V2", "status": "pass|fail", "notes": ""},
    {"id": "V3", "status": "pass|fail", "notes": ""},
    {"id": "V4", "status": "pass|skip|fail", "notes": "skip if second seed not feasible"},
    {"id": "Vn", "status": "pass|fail", "notes": ""}
  ],
  "screenshots": [
    "ai-dev/active/I-00101/evidences/post/I-00101_v1_badge_visible.png",
    "ai-dev/active/I-00101/evidences/post/I-00101_v2_modal_open.png",
    "ai-dev/active/I-00101/evidences/post/I-00101_v3_after_amend.png",
    "ai-dev/active/I-00101/evidences/post/I-00101_v_n_no_regressions.png"
  ],
  "notes": ""
}
```
