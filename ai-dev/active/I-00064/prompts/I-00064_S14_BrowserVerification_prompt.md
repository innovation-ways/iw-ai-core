# Browser Verification Prompt: I-00064-S14-BrowserVerification

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
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

Allowed exceptions: testcontainer fixtures, read-only introspection
(`docker ps`, `docker inspect`, `docker logs`), and `./ai-core.sh` /
`make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

`docker compose -p "$COMPOSE_PROJECT_NAME" exec app …` is allowed and
required when (and only when) you need to re-run the seed after writing
an `e2e_fixtures/*.py` file.

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step does NOT touch migrations.)

## Environment

The IW orchestrator has **already** started an isolated E2E stack built
from THIS worktree's source code. The environment is ready before this
prompt runs — do NOT attempt to start, stop, or rebuild any services
yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always
use the env var. The port is allocated per-worktree so concurrent
browser_verification steps don't collide.

Do NOT run any of the following — they will break the isolated stack
or duplicate work the orchestrator already performed:

- `make dev`, `make e2e-up`, or any `docker compose up/down/restart/build` — the stack is already up
- `playwright install` or `npx playwright install` — the CLI is pre-installed
- `agent-browser` — this environment uses `playwright-cli` **exclusively**
- Any direct `chromium.launch()` snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00064/I-00064_Issue_Design.md` — design document
- `orch/jobs/aggregator.py` — file modified by S01
- `tests/integration/test_i00064_doc_generation_view_document_url.py` — file added by S03
- `ai-dev/active/I-00064/evidences/pre/` — pre-fix screenshots and snapshots (use as a baseline for comparison)

## Output Files

- `ai-dev/active/I-00064/reports/I-00064_S14_BrowserVerification_Report.md` — mandatory report
- `ai-dev/active/I-00064/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

This dashboard is unauthenticated (`/healthz/identity` is the only auth-
bypass endpoint, but the rest of the dashboard does not gate behind
login in iw-ai-core's local dev/E2E topology). If a login form appears
in your environment, log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

If no login form is shown, proceed directly to the navigation steps
below.

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to
   read the current accessible element IDs. Do not guess selectors or
   reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00064/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration
DB via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It
reflects current production state.

For this verification, you need at least one **doc_generation job** in
the database whose `doc_id` FK points at an existing **ProjectDoc**.
Production already has `DOC-00001` linked to `iw-ai-core:code-index` —
so the seed should include this row. If the seed does not include any
doc_generation row (i.e., V1 below shows the empty Jobs view or an
"Unknown" page when navigating to the job), classify as
`ENV_DATA_MISSING` and add a fixture file under
`ai-dev/active/I-00064/e2e_fixtures/001_doc_generation_job.py` that
seeds a project, a ProjectDoc with inner id `code-index`, and a
DocGenerationJob with `public_id="DOC-00001"`. After writing the
fixture, run inside the container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell** — it would write into
> the production DB on port 5433.

## Verification Steps

### V1: "View document" link resolves end-to-end (the bug fix)

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/jobs/doc_generation/DOC-00001`.
2. Take a `playwright-cli snapshot`. **Verify:** the snapshot contains a link with role `link` and accessible name `→ View document`. The `/url:` field for that link MUST be of the form `/project/iw-ai-core/docs/<inner_id>` where `<inner_id>` does NOT contain a colon — concretely, it should read `/url: /project/iw-ai-core/docs/code-index` (or whatever the seeded doc's inner id is). It MUST NOT be `/project/iw-ai-core/docs/iw-ai-core:code-index`.
3. **Capture an evidence screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00064/evidences/post/I-00064_v1_job_detail_link_correct.png`.
4. Click the link via its ref id from the snapshot: `playwright-cli click <ref>`.
5. **Verify:** the new page URL is `…/project/iw-ai-core/docs/code-index` (or the inner id), the page title contains the doc title (e.g. "Code Index" or whatever is seeded), the response is HTTP 200, and the rendered page contains a non-empty document body or "No content yet" placeholder — but NOT a JSON 404 body. Specifically the snapshot MUST NOT contain the literal text `"detail":"Document` (which would indicate a 404 JSON response).
6. **Capture an evidence screenshot:** `playwright-cli screenshot`, then `cp .playwright-cli/page-*.png ai-dev/active/I-00064/evidences/post/I-00064_v1_doc_detail_renders.png`.

### V2: Orphan job hides the link (no 500, no broken link)

1. From the Jobs view (`{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/jobs?type=doc_generation`), pick a doc_generation row with status `completed` whose linked doc has been deleted, OR navigate to a known-orphan job public_id if one is present in the seed. If the seed has no orphan, you may skip V2 and note "no orphan present in seed; orphan path covered by integration test `test_i00064_orphan_doc_id_is_none`" in the report — this is acceptable and does NOT count as failure.
2. **Verify:** if an orphan job page renders, the "→ View document" link is absent (the `{% if raw.get('doc_id') %}` guard hides it). The rest of the page renders cleanly. No 500.
3. **Capture an evidence screenshot:** `ai-dev/active/I-00064/evidences/post/I-00064_v2_orphan_no_link.png` (or omit if V2 skipped per V2.1).

### V3: No regressions on adjacent flows

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/docs` — the doc catalog must still load and list `code-index` (clickable, opens the same doc detail). No console errors.
2. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/jobs` — the unified Jobs list must still render. No console errors.
3. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/jobs/code_mapping/<any code_mapping public_id from the seed>` — the page renders, and the "→ View code map" link points at `/project/iw-ai-core/code` (no doc_id in URL). No 500. (This protects the comment-only edit S01 made in `_fetch_code_mapping`.)
4. **Verify:** every page visited during V1..V3 has zero new console errors.
5. **Capture an evidence screenshot:** `ai-dev/active/I-00064/evidences/post/I-00064_v3_no_regressions.png`.

## Pass Criteria

V1 and V3 must pass. V2 may be skipped if no orphan exists in the seed
(noted in the report as documented above) — that is an acceptable
condition because the orphan path is exhaustively covered by the
integration test in `tests/integration/test_i00064_doc_generation_view_document_url.py`.

Any failure of V1 or V3 — including a partial or ambiguous result —
requires calling `iw step-fail` with a reason. There is no "mostly
passed".

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** — the page returned an HTTP error, threw a console
  exception, rendered the wrong element, or showed broken UI. Use a
  normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but
  showed an empty-state ("No jobs yet") because the E2E DB lacks the
  expected `DOC-00001` row. Add an `e2e_fixtures` file (see "E2E DB
  seed data" above) and prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1 expects DOC-00001 doc_generation job — added ai-dev/active/I-00064/e2e_fixtures/001_doc_generation_job.py" \
    --report ai-dev/active/I-00064/reports/I-00064_S14_BrowserVerification_Report.md
  ```

  The reason is for the human reviewer; the fix path is to add a
  fixture, not to retry.

## Report

After verification, write
`ai-dev/active/I-00064/reports/I-00064_S14_BrowserVerification_Report.md`
containing:

- A pass/fail table with one row per V1..V3.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is
  self-contained).
- Any issues found, with `file:line` references if you investigated
  root cause.
- A list of the screenshots captured (relative paths under
  `evidences/post/`).
- A **No regressions observed** subsection covering V3.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00064/reports/I-00064_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00064/reports/I-00064_S14_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the
orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "I-00064",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "View document link resolves", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Orphan job hides link", "status": "pass|fail|skipped", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "No regressions on adjacent flows", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if V1 and V3 passed (V2 may be `skipped`).
- `base_url_used`: the concrete URL the agent actually hit.
- `console_errors_observed`: any console errors seen during any V(n).
