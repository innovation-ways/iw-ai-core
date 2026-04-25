# Browser Verification Prompt: CR-00022-S27-BrowserVerification

**Work Item**: CR-00022 -- OSS Compliance — per-finding fixes, table+modal UX, no branch creation
**Step**: S27
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

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only `docker ps/inspect/logs`; invoking `./ai-core.sh` or `make`.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run live alembic upgrade/downgrade commands. The E2E stack already has the schema applied.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use `$IW_BROWSER_BASE_URL`.

Do NOT run any of: `make dev`, `make e2e-up`, `docker compose`, `playwright install`, `agent-browser`, `chromium.launch()`. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/CR-00022/CR-00022_CR_Design.md` — the design document
- `dashboard/templates/pages/project/oss.html`
- `dashboard/templates/fragments/oss_table.html`
- `dashboard/templates/fragments/oss_finding_modal.html`
- `dashboard/templates/fragments/oss_apply_all_safe_modal.html`
- `dashboard/services/oss_check_catalog.yaml`
- `dashboard/services/oss_accepted.py`
- `orch/oss/fix_recipes/`
- `dashboard/routers/oss.py`

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S27_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/CR-00022/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always call `playwright-cli snapshot` **before** `fill` / `click` to get current refs.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00022/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL with schema + migrations applied + the baseline seed in `scripts/e2e_seed.py`. It does not mirror the production database.

**This CR requires** at least one project with prior OSS scan data so the table renders findings. If the central seed does not provision OSS findings, add a fixture file:

```
ai-dev/active/CR-00022/e2e_fixtures/001_oss_scan_with_findings.py
```

The file must export `def seed(db: Session) -> None` and is auto-run after the central seed. Make seeding idempotent. The fixture should insert:
- One `OssScan(project_id=<seeded_project>, status='complete', mode='scan', pill_color='red')`
- A handful of `OssFinding` rows mixing severities (1 MUST fail, 1 SHOULD fail, 2 PASS, 1 INFO fail) and `auto_apply_safe` mix (at least one True with a real recipe like OSS-CH-01, at least one False)

If your verifications can't be satisfied with seed data alone, call `iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

## Verification Steps

### V1: New table layout renders with required columns and groups

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/<seeded_project_id>/oss`.
2. Confirm the page renders the new layout — this exercises AC3.
3. **Verify**:
   - Page heading reads "OSS Compliance".
   - The action row contains exactly two buttons: `Scan` and `Apply all safe`. **No** `Prepare` or `Publish` buttons.
   - A table is present with header row labels: `Group | Test | Type | Status | Details`.
   - At least one collapsible domain group header is visible (clickable; chevron rotates).
   - Each finding row in an expanded group has a `…` button in the Details column.
   - Default filter shows failing/human-required findings only — passing rows are hidden until `All` chip is toggled.
4. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v1_table_layout.png`.

### V2: Finding modal renders rich per-test copy

1. On the same page, click the `…` button on a `MUST` failing row (e.g., `OSS-CH-01` if seeded). This exercises AC3 and AC4.
2. **Verify** the modal opens centered with these sections in order:
   - Header: severity badge, check_id, status pill, OSPS control (if present).
   - Title: finding summary.
   - "What this test checks" — non-empty paragraph.
   - "How it tests" — non-empty paragraph.
   - "Risk if you ship anyway" — non-empty paragraph.
   - "Evidence" — present if finding has evidence.
   - "How to fix" — non-empty paragraph.
   - "Preview" — visible because `auto_apply_safe=True`.
   - "References" — list of links if any.
   - Footer: `Re-run check`, `Mark accepted`, `Close`, `Apply` (Apply visible because `auto_apply_safe=True`).
3. Press `ESC` — modal closes, focus returns to the `…` button.
4. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v2_modal_open.png` (taken before ESC).

### V3: Per-finding Apply writes to working tree only — no branch change

1. Open the modal again for the same `auto_apply_safe=True` MUST finding.
2. Note the e2e checkout's current branch via `docker compose exec` (read-only `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard git -C /repo symbolic-ref HEAD`) — record as `BRANCH_BEFORE`.
3. Click `Apply` in the modal. This exercises AC1 and AC5.
4. Wait for toast confirmation.
5. **Verify**:
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard git -C /repo symbolic-ref HEAD` again — equals `BRANCH_BEFORE` (no branch switch).
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard git -C /repo branch --list 'iw-oss-publish*'` — empty output.
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard ls /tmp/oss-* 2>/dev/null || echo NONE` — output is `NONE`.
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard git -C /repo status --short` — the target file (e.g. `README.md`) appears as a modification or untracked file.
6. Click Apply a second time (idempotency check, AC5).
7. **Verify** `git diff` for the target file is unchanged from after the first apply (no growing file).
8. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v3_apply_success.png`.

Note: `docker compose exec` is **read-only introspection** for git state — allowed by the docker policy.

### V4: Mark accepted writes `.iw/oss-accepted.yaml`

1. Open the modal for a `MUST` failing finding. This exercises AC6.
2. Click `Mark accepted` — reason form appears inline.
3. Type "E2E verification — accept for test" into the reason textarea.
4. Click `Confirm acceptance`.
5. **Verify**:
   - Toast confirmation appears.
   - Modal closes.
   - The row moves to the "Accepted risk" group at the bottom of the table.
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard cat /repo/.iw/oss-accepted.yaml` — file contains an entry with the expected `check_id`, a 16-hex-char `finding_hash`, the reason text, and `accepted_by`.
6. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v4_accepted_yaml.png` (page with row in Accepted group).

### V5: Apply all safe — preview is deselectable, never operates on unsafe findings

1. On the OSS page, click `Apply all safe`. This exercises AC9 and AC10.
2. **Verify** preview modal opens with:
   - Heading "Apply all safe fixes — preview".
   - Copy stating "Writes to your working tree only. No branch is created."
   - A list with one `<details>` per recipe.
   - Every recipe has a top-level checkbox, checked by default.
   - **No** row corresponds to a `MUST` finding with `auto_apply_safe=False` (e.g., a secret-in-history finding) — verify by check_id.
3. Deselect one recipe (uncheck top-level checkbox).
4. Click `Apply selected`.
5. **Verify**:
   - Toast confirmation lists applied check IDs (the deselected one is absent).
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard git -C /repo symbolic-ref HEAD` — branch unchanged.
   - Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard git -C /repo status --short` — files for selected recipes appear as modifications; deselected recipe's files do NOT.
6. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v5_apply_all_safe_preview.png` (taken before clicking Apply).

### V6: SSE row updates — no full-page reload during scan

1. Click `Scan`. This exercises AC8.
2. While the scan runs, **observe** that:
   - Individual `<tr>` rows transition status pill in place.
   - The page URL does NOT change.
   - The browser's reload indicator does NOT spin (no full reload).
   - The console (open DevTools via `playwright-cli evaluate "console.log('marker')"` after scan starts) shows no `location.reload()` calls.
3. After scan completes, the summary pill at the top updates without a reload.
4. **Verify** by checking page sources via `playwright-cli evaluate "performance.getEntriesByType('navigation').length"` — the count should remain 1 (single navigation, no full reload).
5. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v6_scan_complete.png`.

### V7: Removed CLI subcommands and routes return errors

1. Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard uv run iw oss --help` and verify the output does NOT list `prepare` or `publish`. This exercises AC2.
2. Run `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/project/<seeded_project_id>/oss/prepare` — expect `404`.
3. Run the same for `/oss/publish` — expect `404`.
4. **Screenshot** is not required for V7; capture the terminal output in the report instead.

### V8: No Regressions

1. Revisit adjacent pages: `/project/<seeded_project_id>/dashboard`, `/project/<seeded_project_id>/jobs`, `/project/<seeded_project_id>/code` — confirm they still render.
2. Open browser DevTools console — confirm no new console errors appeared on any page visited during V1..V7.
3. Verify the navigation sidebar still highlights "OSS" when on the OSS page.
4. **Screenshot:** `ai-dev/active/CR-00022/evidences/post/CR-00022_v8_no_regressions.png`.

## Pass Criteria

All V1..V8 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. Use a normal `--reason`.
- **ENV_DATA_MISSING** — page rendered cleanly with HTTP 200 but showed an empty-state message because the E2E DB lacks the required OSS findings. Prefix the reason:

```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V1 needs OSS findings — add ai-dev/active/CR-00022/e2e_fixtures/001_oss_scan_with_findings.py" \
  --report ai-dev/active/CR-00022/reports/CR-00022_S27_BrowserVerification_Report.md
```

## Report

Write `ai-dev/active/CR-00022/reports/CR-00022_S27_BrowserVerification_Report.md` containing:

- Pass/fail table with one row per V1..V8.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root-caused.
- List of screenshots captured under `evidences/post/`.
- A **No regressions observed** subsection.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00022/reports/CR-00022_S27_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00022/reports/CR-00022_S27_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S27",
  "agent": "qv-browser",
  "work_item": "CR-00022",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "Table layout + filters", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Modal renders rich per-test copy", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Apply writes to working tree only — no branch change + idempotent", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Mark accepted writes .iw/oss-accepted.yaml", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Apply all safe — deselectable preview, never operates on unsafe", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "SSE row updates — no full-page reload", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "Removed CLI subcommands + routes return errors", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V8", "name": "No regressions on adjacent pages", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
