# Browser Verification Prompt: I-00120-S16-BrowserVerification

**Work Item**: I-00120 -- Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step**: S16
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart|build`, `docker volume rm|prune`,
`docker system|container|image prune`). `docker compose exec app …` is allowed (and required) only when
re-running a seed after writing a fixture file. Read-only `docker ps|inspect|logs` is allowed.
The isolated E2E stack is already up — do NOT start, stop, or rebuild services.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item. Do not run `alembic upgrade|downgrade|stamp` against any DB.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source.
Do NOT start, stop, or rebuild any services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, etc.) — always use `$IW_BROWSER_BASE_URL`. Do NOT run
`make dev`, `make e2e-up`, any `docker compose up/down/restart/build`, `playwright install`, or
`agent-browser`. Use `playwright-cli` **exclusively**.

Before asserting on page content, confirm the page loaded (HTTP 200, no unhandled-exception page, no
load-time JS/HTMX console errors). A 5xx on the page is itself a `code_defect`.

## Input Files

- `ai-dev/active/I-00120/I-00120_Issue_Design.md` -- the design document.
- `dashboard/routers/usage.py`
- `dashboard/templates/fragments/llm_usage_footer.html`
- `orch/llm_usage.py`

## Output Files

- `ai-dev/active/I-00120/reports/I-00120_S16_BrowserVerification_Report.md` -- the mandatory report.
- `ai-dev/active/I-00120/evidences/post/` -- screenshots taken during verification.

## Prerequisites

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

Rules: always `snapshot` before `fill`/`click`; wait for transitions; screenshots go under
`ai-dev/active/I-00120/evidences/post/`.

## E2E DB seed data

No DB fixtures are required for this item. The relevant state is the **Codex OAuth credential**, not DB
rows: the isolated E2E `app` container does not have a `~/.local/share/opencode/auth.json`, so
`orch/llm_usage.py:_codex_usage()` returns `status == "unauthenticated"` and the footer Codex chip
shows the "not configured — run opencode auth login" warning. This is the expected, verifiable state.

If (and only if) the container unexpectedly DOES have a valid Codex token and the chip shows live bars,
that is still a PASS for the "healthy" branch — but you must then verify the warning branch cannot be
triggered from the browser alone; in that case record it and PASS on the V1 healthy-render check plus
the V2 no-regression check, noting the environment had a live token.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

The agent automatically visits every page route referenced below, checks fragment references resolve,
and reads `.playwright-cli/console-*.log` for unhandled JS/HTMX errors. V0 failure does not skip V1..Vn.

### V1: Codex auth-state warning is visible in the footer (replaces silent 0% bars)

1. Navigate to `{{IW_BROWSER_BASE_URL}}/` (the project home; the LLM-usage footer is present on every page).
2. The footer auto-refreshes via `GET /api/usage/llm/fragment` (htmx, ~60s). To read it deterministically
   without waiting, also fetch the fragment directly and inspect it:
   ```bash
   curl -s "$IW_BROWSER_BASE_URL/api/usage/llm/fragment"
   ```
   This is the same HTML htmx swaps into the footer.
3. **Verify:** in the Codex section of the fragment/footer, a warning is shown **instead of** the two
   percentage bars. Expected (no Codex token in the container): the text
   `not configured — run opencode auth login` together with the `⚠` glyph and the `text-amber-600`
   class. The Codex section must NOT render the normal `width: 0%` bar markup while in this warning
   state. (If the container has a live Codex token, instead verify the two normal Codex bars render and
   no `⚠` warning appears — record which branch you observed.)
4. **Screenshot:** `playwright-cli screenshot` then
   `cp .playwright-cli/page-*.png ai-dev/active/I-00120/evidences/post/I-00120_v1_codex_warning.png`.

### V2: No Regressions

1. Confirm the Claude and MiniMax footer chips still render their normal bars and percentages (the
   change must not affect them). Revisit one other page (e.g. a project page) and confirm the footer
   still renders without error.
2. Verify no new console errors appeared on any page visited (read `.playwright-cli/console-*.log`).
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00120/evidences/post/I-00120_v2_no_regressions.png`.

## Pass Criteria

V1 and V2 must pass. Classify any failure as CODE_DEFECT / ENV_DATA_MISSING / SPEC_MISMATCH per the
standard rules and call the appropriate `iw step-done` / `iw step-fail` with `--report`.

- A 5xx or console exception on the footer/fragment → CODE_DEFECT.
- The Codex section rendering normal `0%` bars with NO warning while the container has no Codex token
  → CODE_DEFECT (the bug is not fixed).

## Report

Write `ai-dev/active/I-00120/reports/I-00120_S16_BrowserVerification_Report.md` with a pass/fail table
(one row per V), the exact `$IW_BROWSER_BASE_URL`, which Codex branch was observed
(unauthenticated-warning vs live-bars), any issues with `file:line`, the screenshot list, and a
**No regressions observed** subsection. Then call one of:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00120/reports/I-00120_S16_BrowserVerification_Report.md
# or, on any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00120/reports/I-00120_S16_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00120",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Codex auth-state warning visible in footer", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "No regressions", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
