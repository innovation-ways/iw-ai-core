# Browser Verification Prompt: I-00060-S11-BrowserVerification

**Work Item**: I-00060 -- Code chat — pin user message on Enter and tighten empty Assistant bubble
**Step**: S11
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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

This step makes no DB changes — any alembic activity is a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:5174`, no `localhost:3100`). Always use the env var. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding a port is a bug that will silently test the wrong environment (often the dev server serving `main` branch instead of your feature worktree).

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00060/I-00060_Issue_Design.md` -- the design document
- Files modified by S01 (expected):
  - `dashboard/static/chat/composer.js`
  - `dashboard/static/chat.css` (the `min-height: 50dvh` rule deletion at line 3)
  - `dashboard/static/chat/render.js` (only if S01 touched it)
- Files added by S03 (the new browser tests):
  - `tests/dashboard/browser/test_chat_scroll_i00060.py`

## Output Files

- `ai-dev/active/I-00060/reports/I-00060_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00060/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs (e10, e12, ...)
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00060/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB
via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects
current production state.

For I-00060 you need a project that has its **RAG code index built** so
the Code page chat is functional. If the seed already includes such a
project (most do — `iw-ai-core` itself is registered), use it. If not,
add a fixture under `ai-dev/active/I-00060/e2e_fixtures/` per the standard
`templates/design/QVBrowser_Prompt_Template.md` rules — but for this work
item that should not be necessary; if it is, prefix the failure reason
with `ENV_DATA_MISSING:` so the daemon classifies it correctly.

## Verification Steps

### V1: Submit scrolls the just-typed user bubble into view (AC1)

1. Navigate to `$IW_BROWSER_BASE_URL/projects` and pick a project that has
   the RAG code index built (snapshot, click the project tile).
2. Click the **Code** tab (or navigate directly to
   `$IW_BROWSER_BASE_URL/project/<project-id>/code`).
3. Click `#chat-collapse-btn` (the chevron) to expand the chat panel —
   this triggers the chat layout we need to test.
4. Send 8 warm-up questions to force the messages container to overflow.
   For each one: snapshot, fill `#chat-input` with `warmup question N`,
   click `#chat-send`, and wait for the SSE stream to complete (the
   bubble's actions block becomes visible). This may take ~10–20s per
   question — that is acceptable.
5. Manually scroll the messages container to the top:

   ```bash
   playwright-cli evaluate "document.getElementById('chat-messages').scrollTop = 0"
   ```

6. Snapshot, fill `#chat-input` with `the question we care about`, click
   `#chat-send`. Do NOT wait — measure immediately.
7. **Verify** with a single evaluate that returns a JSON object:

   ```bash
   playwright-cli evaluate "(() => {
     const c = document.getElementById('chat-messages');
     const articles = c.querySelectorAll('article[data-role=\"user\"]');
     const last = articles[articles.length - 1];
     const lr = last.getBoundingClientRect();
     const cr = c.getBoundingClientRect();
     return { lastBottom: lr.bottom, lastTop: lr.top, ctop: cr.top, cbot: cr.bottom };
   })()"
   ```

   Expected: `lastBottom <= cbot` AND `lastTop >= ctop` — the user bubble
   is fully inside the container's viewport. If either inequality fails,
   V1 FAILS.
8. **Screenshot:** `playwright-cli screenshot`, then
   `cp .playwright-cli/page-*.png ai-dev/active/I-00060/evidences/post/I-00060_v1_submit_scrolls.png`.

### V2: Empty Assistant bubble is compact pre-stream (AC2)

1. From the same page (or refresh and re-expand chat if you prefer a clean
   state), snapshot and fill `#chat-input` with `explain this module`.
2. Click `#chat-send`.
3. **Immediately** (before the first SSE token arrives — within a few
   hundred ms; if your stream is fast enough that you cannot catch the
   pre-token state, retry by sending a question whose backend takes
   longer):

   ```bash
   playwright-cli evaluate "(() => {
     const articles = document.querySelectorAll('article[data-role=\"assistant\"]');
     const a = articles[articles.length - 1];
     const r = a.getBoundingClientRect();
     return { height: r.height, body_text_len: (a.querySelector('.chat-message-body')||{}).textContent?.length || 0 };
   })()"
   ```

   Expected: `height <= 48` AND `body_text_len === 0`. If `body_text_len`
   is already > 0, the stream beat you to it — retry. If `height > 48`
   with `body_text_len === 0`, V2 FAILS.
4. **Screenshot:** `playwright-cli screenshot` then `cp` to
   `ai-dev/active/I-00060/evidences/post/I-00060_v2_empty_bubble_compact.png`.

### V3: Stream follows the caret only when at the bottom (AC3)

1. Wait for the V2 stream to complete (or send a fresh long-answer
   question).
2. Mid-stream (while tokens are still arriving), scroll the messages
   container up by 300px:

   ```bash
   playwright-cli evaluate "document.getElementById('chat-messages').scrollTop -= 300"
   ```

3. Wait 3 seconds for more tokens to arrive.
4. **Verify**:

   ```bash
   playwright-cli evaluate "(() => {
     const c = document.getElementById('chat-messages');
     return { scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
   })()"
   ```

   Expected: `scrollTop` did NOT jump back to (`scrollHeight - clientHeight`).
   The user remains where they scrolled. If `scrollTop` was yanked
   forward, V3 FAILS.
5. Confirm the floating "↓ Latest" button (`#chat-scroll-to-bottom`) is
   visible (snapshot, look for it).
6. Click `#chat-scroll-to-bottom`. Verify `scrollTop` now equals
   `scrollHeight - clientHeight` (within 2px).
7. **Screenshot:** `I-00060_v3_conditional_follow_scroll.png`.

### V4: No Regressions

1. From the chat, send a question whose answer cites code (anything that
   triggers RAG citations — e.g. "what does composer.js do"). Wait for
   stream completion.
2. Verify a citation chip (`[data-cite]`) is present and clicking it
   opens the citation popover.
3. Send a question asking for a mermaid diagram (or use any
   mermaid-emitting prompt for this project). Verify a `<svg>` mermaid
   render appears in the assistant bubble.
4. Collapse the chat panel (click the collapse chevron); confirm the
   `#chat-expand-rail` shows. Re-expand; confirm messages are preserved.
5. Verify NO new console errors appeared on any page visited during V1..V4:

   ```bash
   playwright-cli console
   ```

   The list should be empty (or only contain pre-existing benign
   warnings). Any new errors → V4 FAILS.
6. **Screenshot:** `I-00060_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed".

### Distinguishing code defects from environment gaps

Before failing the step, classify the failure:

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. The fix-cycle agent can patch this. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly with HTTP 200 but the project has no RAG index built and the chat stream errors out for that reason. Prefix the reason with `ENV_DATA_MISSING:`:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: no project in the seed has a RAG code index built — chat cannot stream — add ai-dev/active/I-00060/e2e_fixtures/001_seed_indexed_project.py" \
    --report ai-dev/active/I-00060/reports/I-00060_S11_BrowserVerification_Report.md
  ```

## Report

After verification, write `ai-dev/active/I-00060/reports/I-00060_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- The numeric measurements captured in V1, V2, V3 (bubble heights, scroll positions).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V4 (citations, mermaid, collapse/expand, console).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00060/reports/I-00060_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00060/reports/I-00060_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00060",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Submit scrolls user bubble into view", "status": "pass|fail", "screenshot": "evidences/post/I-00060_v1_submit_scrolls.png", "notes": ""},
    {"id": "V2", "name": "Empty assistant bubble compact pre-stream", "status": "pass|fail", "screenshot": "evidences/post/I-00060_v2_empty_bubble_compact.png", "notes": ""},
    {"id": "V3", "name": "Conditional follow-scroll while streaming", "status": "pass|fail", "screenshot": "evidences/post/I-00060_v3_conditional_follow_scroll.png", "notes": ""},
    {"id": "V4", "name": "No regressions (citations, mermaid, collapse, console)", "status": "pass|fail", "screenshot": "evidences/post/I-00060_v4_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed.
- `base_url_used`: the concrete URL the agent actually hit.
- `console_errors_observed`: any console errors seen, even if the verification otherwise passed.
