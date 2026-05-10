# Browser Verification Prompt: CR-00043-S15-BrowserVerification

**Work Item**: CR-00043 -- Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers
**Step**: S15
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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

This CR has no migrations. Allowed for agents: `alembic history / current / show` (read-only).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code (including the updated `Dockerfile.e2e`, which now ships Chromium). The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or route paths. Navigate via the UI (click links/rows) wherever possible; only fall back to a direct URL when no UI path exists, and treat a 404 on a hand-typed URL as a `spec_mismatch`, not a code defect. Before asserting on a page's content, confirm the page itself loaded (HTTP 200, no unhandled-exception page, no load-time console errors).

Do NOT run: `make dev` / `make e2e-up` / any `docker compose` lifecycle command (the stack is up); `playwright install` / `npx playwright install`; `agent-browser`; any `chromium.launch()` snippet. Use `playwright-cli` exclusively. `docker compose -p "$COMPOSE_PROJECT_NAME" exec app ...` is allowed for read-only introspection (e.g. confirming `which chromium` inside the container) and for re-running the seed after writing a fixture.

## Input Files

- `ai-dev/active/CR-00043/CR-00043_CR_Design.md` -- the design document (authoritative)
- `dashboard/utils/markdown.py` -- the Chromium resolver
- `Dockerfile.e2e` -- now installs `chromium` (this is the image the E2E stack builds)

## Output Files

- `ai-dev/active/CR-00043/reports/CR-00043_S15_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00043/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in if a login form is presented:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Always `playwright-cli snapshot` before `fill`/`click` to read current element refs. Screenshots: `playwright-cli screenshot` (no path arg) then `cp .playwright-cli/page-*.png ai-dev/active/CR-00043/evidences/post/<name>.png`.

## E2E DB seed data

The E2E PostgreSQL is seeded from production via `pg_dump`; it already contains
the iw-ai-core project's documents (including architecture docs with Mermaid
diagrams), so no fixture file is needed for this verification. If you somehow
find no document with Mermaid diagram code blocks, add
`ai-dev/active/CR-00043/e2e_fixtures/001_<name>.py` exporting
`def seed(db: Session) -> None` and re-run the seed inside the app container —
do NOT run the seed from your host shell (it writes to the production DB).

## Verification Steps

### V0: Pre-flight page sanity (built-in — runs unconditionally; documented here for reviewers)

The agent visits each page route used below and checks for dangling fragment
references and load-time console errors; any failure is a V0 FAIL (but V1..Vn
still run).

### V1: PDF download returns a real PDF (HTTP 200 + %PDF) in the E2E stack

1. From the dashboard, navigate via the UI to a project with architecture
   documentation (e.g. iw-ai-core) and open a document that contains Mermaid
   diagram code blocks (e.g. an "architecture" / "architecture-map" doc). Confirm
   the doc detail page is HTTP 200 with no load-time console exception.
   - Screenshot: `cp .playwright-cli/page-*.png ai-dev/active/CR-00043/evidences/post/CR-00043_v1_doc_page.png`
2. Determine the doc's `/pdf` URL (it's the target of the "Download PDF" link/tab
   on this page — read it from the snapshot; don't hand-construct it). Request it
   and inspect the response:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" "<the /pdf URL>"
   curl -s "<the /pdf URL>" | head -c 8 | xxd
   ```
   You may also confirm the binary is present in the container:
   `docker compose -p "$COMPOSE_PROJECT_NAME" exec app sh -c 'command -v chromium && chromium --version'`.
3. **Verify:** the `/pdf` request returns **HTTP 200** and the body begins with the
   `%PDF` magic bytes (`25 50 44 46`). This is AC5 — the real Chromium path now
   works inside the E2E stack.
4. **Screenshot:** the doc page after clicking "Download PDF" (or the inline PDF
   viewer if one opens): `cp .playwright-cli/page-*.png ai-dev/active/CR-00043/evidences/post/CR-00043_v1_pdf.png`.

> If — and only if — the request returns the old `503 {"error":"PDF generation
> unavailable", ...}`, that means the Chromium provisioning in `Dockerfile.e2e`
> (S03) didn't take. That is a **CODE_DEFECT** for this CR (the whole point was to
> make the happy path reachable here): fail with a normal `--reason` citing the
> 503 and what `which chromium` returns inside the container. Do NOT classify it
> `ENV_DATA_MISSING`.

### V2: Mermaid diagrams render in the HTML view (no regression)

1. Back on the doc detail page, switch to the HTML view/tab. Confirm HTTP 200.
2. **Verify:** Mermaid diagrams render as inline SVG (diagram shapes visible) — OR
   degrade to a code block — and there is **no error banner** and no 500. Either
   rendered-SVG or code-block-fallback is acceptable; an error/blank is not.
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/CR-00043/evidences/post/CR-00043_v2_html_view.png`.

### V3: No Regressions

1. Revisit adjacent flows: the docs catalog page lists documents and is HTTP 200;
   opening another doc works; the project home page renders.
2. Verify no new console errors appeared on any page visited during V1..V2.
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/CR-00043/evidences/post/CR-00043_v3_no_regressions.png`.

## Pass Criteria

All of V1..V3 must pass. Classify any failure: a 5xx/console-exception/missing-element-that-should-be-present is a CODE_DEFECT (normal `--reason`); a cleanly-rendered page missing data only because the seed lacks it is ENV_DATA_MISSING (`--reason "ENV_DATA_MISSING: ..."` + add a fixture) — but note the iw-ai-core docs are seeded from prod, so a missing diagram doc would be surprising; a V step asking for something the design doc says is correctly absent is SPEC_MISMATCH. Specifically: a `503` on `/pdf` here is a CODE_DEFECT (S03 provisioning gap), NOT ENV_DATA_MISSING.

## Report

Write `ai-dev/active/CR-00043/reports/CR-00043_S15_BrowserVerification_Report.md` with: a pass/fail table for V1..V3; the exact `$IW_BROWSER_BASE_URL` used; the `/pdf` HTTP status and first bytes observed; `which chromium` / `chromium --version` from inside the app container; any issues with `file:line` refs; the screenshot list; and a "No regressions observed" subsection.

Then call **one** of:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00043/reports/CR-00043_S15_BrowserVerification_Report.md

uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00043/reports/CR-00043_S15_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "CR-00043",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "PDF download returns HTTP 200 + %PDF", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Mermaid HTML view renders (no regression)", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "No regressions", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
