# Browser Verification Prompt: I-00066-S14-BrowserVerification

**Work Item**: I-00066 -- OSS finding modal too narrow and footer buttons unclear
**Step**: S14
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp commands against
the live orchestration DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack
built from THIS worktree's source code. The environment is ready
before this prompt runs -- do NOT attempt to start, stop, or rebuild
any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` /
`$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` /
`$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no
`localhost:9900`). Always use the env var.

Do NOT run any of the following:
- `make dev`, `make test-e2e`, `make e2e-up`, or any
  `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser`
- Any direct `chromium.launch()` snippet

Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00066/I-00066_Issue_Design.md` -- Design document
- `ai-dev/active/I-00066/evidences/pre/I-00066-bug-evidence.png` --
  Pre-fix screenshot (modal narrow, buttons label-like)
- Files modified by S01:
  - `dashboard/static/tailwind.src.css`
  - `dashboard/static/styles.css`
  - `dashboard/templates/fragments/oss_finding_modal.html`

## Output Files

- `ai-dev/active/I-00066/reports/I-00066_S14_BrowserVerification_Report.md`
- `ai-dev/active/I-00066/evidences/post/` -- screenshots taken
  during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The IW AI Core dashboard does not require a login form for this
project (it surfaces all projects without authentication on the
isolated stack). If the landing page presents a login form, follow
the standard prerequisites template:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref>     "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Otherwise proceed directly.

Rules:
1. Always call `playwright-cli snapshot` BEFORE `fill`/`click` to
   read fresh accessible element refs.
2. Wait for navigation/transitions to settle.
3. Screenshots go under `ai-dev/active/I-00066/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production
orchestration DB via `pg_dump`. For this incident, the seed already
contains plenty of OSS findings on the `iw-ai-core` project (the
pre-fix screenshot was captured against the production DB and shows
many failing rows). No fixture file is needed.

If — against expectation — the OSS table on the worktree stack is
empty (no rows with a "..." details button), call:

```bash
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "ENV_DATA_MISSING: V1 expects at least one OSS finding row on /project/iw-ai-core/oss to click the View-details button" \
  --report ai-dev/active/I-00066/reports/I-00066_S14_BrowserVerification_Report.md
```

## Verification Steps

### V1: Modal opens at ~80% viewport width and footer buttons are clearly buttons

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/oss`.
2. Run `playwright-cli snapshot` to read fresh refs. Locate any
   `button` whose accessible name starts with
   `View details for OSS-` (these are the row-level "…" buttons).
3. `playwright-cli click <ref>` on the first such button — this is
   the user gesture that opens the OSS finding modal under fix.
4. **Verify** (run `playwright-cli snapshot` again):
   - A `dialog` element with title `oss-finding-modal` (or the
     accessible name "OSS finding") is visible.
   - Inside the dialog, the footer area contains three visible
     buttons: `Re-run check`, `Mark accepted`, `Close`. Each has a
     button role with `[cursor=pointer]`.
   - Run a small JS check via `playwright-cli` to verify the
     rendered modal width is at least 70% of the viewport (i.e.
     the 80vw rule is winning):

     ```bash
     playwright-cli eval "
       (() => {
         const inner = document.querySelector('.oss-modal-inner');
         if (!inner) return 'MISSING';
         const rect = inner.getBoundingClientRect();
         const ratio = rect.width / window.innerWidth;
         return ratio.toFixed(2);
       })()
     "
     ```

     The returned ratio must be >= 0.70 (allowing for the outer
     1rem flex padding). Anything below 0.65 indicates the
     `max-width: 36rem` regression is back.
5. **Screenshot:** `playwright-cli screenshot` (no path argument),
   then `cp .playwright-cli/page-*.png ai-dev/active/I-00066/evidences/post/I-00066_v1_modal_open.png`.

### V2: Footer Close button dismisses the modal

1. With the modal still open from V1, snapshot to get the fresh ref
   of the footer Close button (text content `Close`, NOT the header
   `×` close icon).
2. `playwright-cli click <footer-close-ref>` — this exercises the
   existing `.modal-close` JS click handler. The new
   `.modal-footer-close` class must NOT have removed `modal-close`
   from the button's class list.
3. **Verify** (snapshot after click):
   - The dialog is no longer visible (the modal element has
     `aria-hidden="true"` again, or the dialog node is no longer
     in the accessibility tree).
4. **Screenshot:** save as
   `ai-dev/active/I-00066/evidences/post/I-00066_v2_modal_closed.png`.

### V3: No Regressions

1. Re-open the modal by clicking another row's "…" button. Confirm
   the modal renders correctly a second time (no stale state).
2. Click the header `×` close button (top-right of the modal,
   accessible name "Close modal" — the SMALL icon, not the footer
   button). Verify the modal also closes via this path. The
   header `×` style is intentionally unchanged by this fix; this
   verifies the unchanged path still works.
3. Verify no new console errors appeared on any page visited during
   V1/V2/V3:
   ```bash
   playwright-cli console-log
   ```
4. **Screenshot:** save as
   `ai-dev/active/I-00066/evidences/post/I-00066_v3_no_regressions.png`.

## Pass Criteria

All V1..V3 must pass. Any failure — including a partial or
ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned an HTTP error, threw a
  console exception, rendered the wrong element, the modal width
  ratio was below 0.65, the footer Close button did not close the
  modal, or the header `×` no longer worked. Use a normal
  `--reason`.
- **ENV_DATA_MISSING** — the OSS table is empty (no rows with a
  "…" button to click). Prefix the reason with
  `ENV_DATA_MISSING:` and propose adding a fixture file.

## Report

After verification, write
`ai-dev/active/I-00066/reports/I-00066_S14_BrowserVerification_Report.md`
containing:

- A pass/fail table with one row per V1..V3.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the
  report is self-contained).
- The measured modal-width ratio from V1.
- Any issues found, with `file:line` references if you investigated.
- A list of the screenshots captured (relative paths under
  `evidences/post/`).
- A **No regressions observed** subsection covering the header
  `×`-close path tested in V3.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00066/reports/I-00066_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00066/reports/I-00066_S14_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "I-00066",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Modal opens at ~80vw, footer buttons visible", "status": "pass|fail", "screenshot": "ai-dev/active/I-00066/evidences/post/I-00066_v1_modal_open.png", "notes": "width ratio: <value>"},
    {"id": "V2", "name": "Footer Close button dismisses the modal", "status": "pass|fail", "screenshot": "ai-dev/active/I-00066/evidences/post/I-00066_v2_modal_closed.png", "notes": ""},
    {"id": "V3", "name": "No regressions (header × close still works, no console errors)", "status": "pass|fail", "screenshot": "ai-dev/active/I-00066/evidences/post/I-00066_v3_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/I-00066/evidences/post/I-00066_v1_modal_open.png",
    "ai-dev/active/I-00066/evidences/post/I-00066_v2_modal_closed.png",
    "ai-dev/active/I-00066/evidences/post/I-00066_v3_no_regressions.png"
  ],
  "notes": ""
}
```
