# Browser Verification Prompt: I-00070-S12-BrowserVerification

**Work Item**: I-00070 -- Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Step**: S12
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. The orchestrator has already brought up the isolated E2E stack — do NOT start, stop, or rebuild any services. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`). Always use the env var.

Do NOT run any of the following:
- `make dev`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser` — use `playwright-cli` exclusively
- Any `chromium.launch()` snippet — always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00070/I-00070_Issue_Design.md` — design document
- `ai-dev/active/I-00070/I-00070_Functional.md` — functional design (user-visible behaviour)
- `dashboard/static/clipboard.js` — the new shared helper
- `dashboard/templates/fragments/item_execution_report.html` — migrated fragment containing the reported button
- `dashboard/templates/base.html` — loads `clipboard.js`

## Output Files

- `ai-dev/active/I-00070/reports/I-00070_S12_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/I-00070/evidences/post/` — screenshots taken during verification

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The dashboard runs without authentication in this environment. If a login screen appears, follow the existing login pattern (snapshot → fill → click).

## E2E DB seed data

The reproduction needs a work item that has a completed `self_assess` step with at least one finding rendered, so the "Copy paste prompt" button is visible. The production-seeded DB contains I-00067 with 5 findings (or any later item that completed with findings) — those are the natural target.

If the seeded DB does NOT contain such an item (the page renders an empty Self-Assessment section or "no findings were captured"), add a fixture file at `ai-dev/active/I-00070/e2e_fixtures/001_seed_self_assess_finding.py` that inserts a minimal `self_assess` step and findings JSON (see `tests/dashboard/test_execution_report_self_assess.py::_create_item_with_self_assess` for the shape), then re-run the seed inside the `app` container before opening the browser:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

Do NOT run the seed from the host shell.

## Verification Steps

### V1: Helper helper is present and reachable

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/`.
2. Open a work item known to have Self-Assessment findings (e.g. I-00067, or whichever item the seed exposed).
3. Click the **Execution Report** tab.
4. Run `playwright-cli eval "() => typeof window.iwClipboard?.copy"` — this asserts the helper loaded.
5. **Verify:** the eval returns `"function"`. Anything else (`"undefined"`, missing) means `clipboard.js` is not loaded — STOP and call `iw step-fail`.
6. **Screenshot:** `ai-dev/active/I-00070/evidences/post/I-00070_v1_helper_loaded.png`.

### V2: Button works on a simulated non-secure context (the actual reported bug)

1. While still on the Execution Report tab with the Self-Assessment section visible, simulate the `iw-dev-01` plain-HTTP access mode by stripping the secure-context clipboard API from THIS browser session:
   ```bash
   playwright-cli eval "() => { Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true }); delete navigator.clipboard; return { isSecureContext: window.isSecureContext, hasClipboard: typeof navigator.clipboard !== 'undefined' }; }"
   ```
2. **Verify (sanity):** the eval returns `{"isSecureContext": false, "hasClipboard": false}`.
3. Take a fresh `playwright-cli snapshot` to find the ref of any **Copy paste prompt** button.
4. Capture the console log path BEFORE clicking (look at the `### Events` block from a recent snapshot or eval result).
5. Click the button.
6. **Verify:** the button label changes to `"Copied"` (snapshot it). Wait ~2 seconds; verify it reverts to `"Copy paste prompt"`.
7. **Verify (no error):** read the captured console log file. It MUST NOT contain `TypeError: Cannot read properties of undefined (reading 'writeText')`. Any such entry is a hard fail.
8. **Verify (clipboard actually wrote):** there is no portable way to read the clipboard back inside Chromium without granting permissions in this headless environment, so SKIP a clipboard-read assertion. Instead, assert that `iwClipboard.copy` resolved by inspecting console for any rejected-promise warnings; rely on the "Copied" UI feedback as the success signal (the helper only sets that label after `execCommand('copy')` returns true).
9. **Screenshot:** `ai-dev/active/I-00070/evidences/post/I-00070_v2_copied_label.png`.

### V3: Button still works on the secure-context happy path

1. Reload the page (`playwright-cli reload`) so `window.isSecureContext` is back to `true` and `navigator.clipboard` is restored.
2. Run `playwright-cli eval "() => ({ isSecureContext: window.isSecureContext, hasClipboard: typeof navigator.clipboard !== 'undefined' })"` — assert `{"isSecureContext": true, "hasClipboard": true}`.
3. Click the **Copy paste prompt** button again.
4. **Verify:** label changes to `"Copied"` then reverts. No console errors.
5. **Screenshot:** `ai-dev/active/I-00070/evidences/post/I-00070_v3_secure_context.png`.

### V4: No Regressions

1. Visit `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/oss` (the OSS view, which has the most other clipboard buttons). Click any **Copy** button on the OSS install modal or CLI block. Assert the button gives "Copied" feedback and no console error.
2. Snapshot the page to confirm no other UI regressions (no missing elements, no console errors).
3. **Screenshot:** `ai-dev/active/I-00070/evidences/post/I-00070_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — page returned an HTTP error, threw a console exception, or "Copied" label did not appear after a click. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly but the Self-Assessment section did not have a finding to click on (because the seeded DB doesn't contain a completed item with findings). Prefix the reason with `ENV_DATA_MISSING:` and reference the e2e_fixtures path.

## Report

Write `ai-dev/active/I-00070/reports/I-00070_S12_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- Console log excerpts proving NO `TypeError` was emitted in V2.
- The list of screenshots captured under `evidences/post/`.
- A **No regressions observed** subsection covering V4.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00070/reports/I-00070_S12_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00070/reports/I-00070_S12_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "I-00070",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "Helper present", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V2", "name": "Button works on simulated non-secure context", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V3", "name": "Button works on secure-context happy path", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V4", "name": "No regressions on OSS clipboard buttons", "status": "pass|fail", "screenshot": "...", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
