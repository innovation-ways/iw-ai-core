# Browser Verification Prompt: {{ID}}-{{STEP}}-BrowserVerification

**Work Item**: {{ID}} -- {{TITLE}}
**Step**: {{STEP}}
**Agent**: qv-browser

---

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

- `ai-dev/active/{{ID}}/{{ID}}_{{TYPE}}_Design.md` -- the design document
- {{LIST_OF_FILES_MODIFIED_BY_IMPLEMENTATION_STEPS}}
  - e.g. `frontend/src/components/foo/Bar.tsx`
  - e.g. `frontend/src/pages/Baz.tsx`

## Output Files

- `ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/{{ID}}/evidences/post/` -- screenshots taken during verification

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
3. Screenshots go under `ai-dev/active/{{ID}}/evidences/post/` with descriptive filenames.

## Verification Steps

Replace the V1..V(n) below with concrete, per-acceptance-criterion verifications derived from the feature design. Each verification must state:

1. **What to navigate to** -- a route under `{{IW_BROWSER_BASE_URL}}` (the platform substitutes this placeholder with the concrete base URL at launch time, so the LLM sees a real URL).
2. **What to click or type** -- with a one-sentence rationale explaining why that interaction triggers the feature.
3. **What to verify** -- exact text, element visibility, URL change, or the absence of console errors.
4. **Capture an evidence screenshot** via `playwright-cli screenshot --filename ai-dev/active/{{ID}}/evidences/post/{{ID}}_v{N}_{{short_name}}.png`.

### V1: {{one-line description of the primary user-visible feature}}

1. Navigate to `{{IW_BROWSER_BASE_URL}}/{{specific_route}}`.
2. {{interaction -- e.g. "click the 'New Batch' button in the top-right toolbar"}} -- this {{rationale}}.
3. **Verify:** {{observable outcome -- e.g. "a modal titled 'Create Batch' is visible and contains a 'Name' input and a 'Create' button"}}.
4. **Screenshot:** `ai-dev/active/{{ID}}/evidences/post/{{ID}}_v1_{{short_name}}.png`.

### V2: {{secondary check}}

1. {{Navigate}}.
2. {{Interact}}.
3. **Verify:** {{outcome}}.
4. **Screenshot:** `ai-dev/active/{{ID}}/evidences/post/{{ID}}_v2_{{short_name}}.png`.

{{Add V3, V4, ... as needed -- one per acceptance criterion in the design doc.}}

### V(n): No Regressions

1. Revisit the buttons/flows adjacent to the changed code and verify they still behave correctly.
2. Verify no new console errors appeared on any page visited during V1..V(n-1).
3. **Screenshot:** `ai-dev/active/{{ID}}/evidences/post/{{ID}}_v{{n}}_no_regressions.png`.

## Pass Criteria

All V1..V(n) must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed"; if an expected element cannot be found, snapshot the page, attach the screenshot, and fail the step.

## Report

After verification, write `ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V(n).
- The exact `$IW_BROWSER_BASE_URL` used (copy from env so the report is self-contained).
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V(n).

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/{{ID}}/reports/{{ID}}_{{STEP}}_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure so the orchestrator can archive the evidence.

## Subagent Result Contract

```json
{
  "step": "{{STEP}}",
  "agent": "qv-browser",
  "work_item": "{{ID}}",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V(n) passed. `fail` on any failure.
- `base_url_used`: The concrete URL the agent actually hit -- used by reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n), even if the verification otherwise passed. A non-empty list on a passing run should be flagged in the report.
