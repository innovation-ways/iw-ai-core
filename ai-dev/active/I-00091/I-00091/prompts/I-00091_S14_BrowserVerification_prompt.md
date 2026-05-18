# Browser Verification Prompt: I-00091-S14-BrowserVerification

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S14
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network management
commands. `docker compose exec app <cmd>` is the only exception, and
only when the design calls for re-running a seed script inside the
already-running stack (this item does not need that).

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic commands against any DB from this prompt.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Environment

The IW orchestrator has **already** started an isolated E2E stack
built from THIS worktree's source code. The environment is ready before
this prompt runs — do NOT attempt to start, stop, or rebuild any
services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `iw-dev-01:9900`). Always
use `$IW_BROWSER_BASE_URL`. The port is allocated per-worktree so
concurrent browser_verification steps don't collide.

Do NOT hardcode application route paths — navigate via the UI when
possible (click the "Auto-Merge" item in the project nav).

Do NOT run:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose`
  command — the stack is already up.
- `playwright install` or `npx playwright install` — the CLI is
  pre-installed.
- `agent-browser` — this environment uses `playwright-cli` exclusively.
- Any direct `chromium.launch()` snippet — always go through
  `playwright-cli`.

## Input Files

- `ai-dev/active/I-00091/I-00091_Issue_Design.md`
- `ai-dev/active/I-00091/I-00091_Functional.md`
- `dashboard/templates/fragments/auto_merge_settings.html` (modified
  in S03)
- `dashboard/templates/fragments/auto_merge_status_chip.html` (modified
  in S03)
- `dashboard/routers/auto_merge_ui.py` (modified in S03)
- `dashboard/static/styles.css` (modified in S03)
- `orch/auto_merge_aggregator.py` (modified in S01)

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S14_BrowserVerification_Report.md`
- `ai-dev/active/I-00091/evidences/post/` — screenshots captured during
  verification.

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the platform requires login at this URL, log in with the provided
credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

If the dashboard renders without a login wall (as on the dev
deployment), proceed directly to V1.

Rules:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to
   read the current accessible element refs. Do not guess selectors.
2. Wait for the htmx swap to settle (the `Loading rollups…` / `Loading
   events…` placeholders should disappear) before snapshotting again.
3. Screenshots go under `ai-dev/active/I-00091/evidences/post/` with
   descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production. The auto-merge
page exercises `auto_merge_project_config` and `agent_runtime_options`
tables — both of which exist in production and contain real rows.
You do NOT need a fixture file for this verification.

If your verification fails because, e.g., no `AgentRuntimeOption` rows
exist with `enabled=True`, that is `ENV_DATA_MISSING` — see Pass
Criteria below.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove)

Automatic check by the qv-browser agent: every page route visited in
V1..V(n) is fetched via curl, fragment references
(`hx-target`, `hx-include`, `aria-controls`, `aria-labelledby`,
`href="#…"`, `for="…"`) are extracted, every referenced `id` must
appear in the same response, console error logs are scanned, and any
dangling reference or load-time JS/HTMX error is flagged.

If V0 fails, V1..V(n) still run but `overall_status` is `fail`.

### V1: Settings form reflects a phase-only override after reload

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge` —
   prefer clicking the "Auto-Merge" item in the project nav.
2. Reset to clean state via the API so the test is hermetic:

   ```bash
   curl -s -X POST "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/config" \
     -H "Content-Type: application/json" -H "Accept: application/json" \
     -d '{"phase": null, "runtime_option_id": null}'
   ```

3. Capture refs (`playwright-cli snapshot`) and use the Phase
   `<select>` to choose `1 — dry-run`. Leave Runtime on
   `Use global default`. Click **Save** — this exercises the in-place
   form swap.
4. **Verify** (immediate, without reloading): the Phase dropdown's
   visible label reads `1 — dry-run` (not `Use global default`). A
   transient "Saved" indicator is visible briefly next to the button.
5. **Reload** the page (`playwright-cli reload`).
6. **Verify** post-reload:
   - The Phase dropdown still shows `1 — dry-run` selected.
   - The Runtime dropdown still shows `Use global default` selected.
   - The status chip (top of page) shows `Phase 1` and an indication
     that phase comes from `per_project_db` (e.g., the new "Phase
     source: per_project_db (Per-project override)" text).
   - The footer below Save reads `Last changed: …` (not `Using global
     default`).
7. **Screenshot:** `ai-dev/active/I-00091/evidences/post/I-00091_v1_phase_only.png`.

### V2: Settings form reflects a runtime-only override

1. From V1's state, reset via API to clear:

   ```bash
   curl -s -X POST "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/config" \
     -H "Content-Type: application/json" -H "Accept: application/json" \
     -d '{"phase": null, "runtime_option_id": null}'
   ```

2. Reload the page. Capture refs.
3. In the Runtime dropdown, pick any specific runtime (not "Use global
   default"). Leave Phase on global. Click **Save**.
4. **Verify** without reloading: Runtime shows the chosen model.
5. **Reload** and verify:
   - Phase dropdown: `Use global default` selected.
   - Runtime dropdown: the chosen runtime selected.
   - Footer reads `Last changed: …`.
   - Status chip shows the chosen runtime AND indicates runtime source
     is `per_project_db`.
6. **Screenshot:** `ai-dev/active/I-00091/evidences/post/I-00091_v2_runtime_only.png`.

### V3: Both-axis override

1. Reset via API.
2. Reload. Pick `1 — dry-run` AND a specific runtime. Click **Save**.
3. **Verify** without reloading: both dropdowns show their chosen
   values.
4. **Reload** and verify both still hold their chosen values; footer
   reads `Last changed: …`; chip shows phase=1 + chosen runtime, both
   marked `per_project_db`.
5. **Screenshot:** `ai-dev/active/I-00091/evidences/post/I-00091_v3_both_axes.png`.

### V4: Clear back to global

1. Starting from V3's both-axes state, pick `Use global default` in
   both dropdowns. Click **Save**.
2. **Verify** without reloading: both dropdowns show `Use global
   default`; the footer now reads `Using global default` (NOT `Last
   changed: …`).
3. **Reload** and verify both dropdowns still on global and footer
   still on `Using global default`.
4. Verify via API that the underlying DB row is gone:

   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/status" \
     -H "Accept: text/html" | grep -E "Phase|Runtime|source"
   ```

   The chip should show `Phase source: toml` (or `hardcoded`) — never
   `per_project_db`.
5. **Screenshot:** `ai-dev/active/I-00091/evidences/post/I-00091_v4_clear_to_global.png`.

### V5: In-place swap, no full-page reload

This V verifies AC3's "no full-page navigation occurs (htmx in-place
swap)" claim.

1. From V4's clean state, install a small page-load counter by
   recording the document's load time via JS — actually, simpler: open
   browser devtools is not available; instead, use a sentinel — before
   clicking Save, take a snapshot and record a stable element ref
   (e.g., the chip's `e<NNN>`). After Save, immediately snapshot again
   — if the page had reloaded, the element refs would have been
   renumbered from `e1` upward. If they continue from where they were,
   only fragments were swapped.
2. **Verify:** the post-Save snapshot's refs do NOT start from `e1`
   (which would indicate a full-page reload).
3. **Screenshot:** `ai-dev/active/I-00091/evidences/post/I-00091_v5_inplace_swap.png`.

### V6: No regressions on adjacent flows

1. Revisit the verdict rollup card — click `7d` then `30d` and confirm
   each refreshes its content (this exercises the rollup htmx-get path
   that is **not** modified by I-00091 — must remain functional).
2. Visit `/project/iw-ai-core/queue` and `/project/iw-ai-core/batches`
   — both should still render normally.
3. Verify no new console errors appeared on any page visited in
   V1..V5.
4. **Screenshot:** `ai-dev/active/I-00091/evidences/post/I-00091_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. Any failure — including a partial or ambiguous
result — requires calling `iw step-fail` with a reason. There is no
"mostly passed".

### Failure classification

- **CODE_DEFECT** — page returned a 5xx, threw a console exception,
  rendered the wrong selected option, or the post-Save swap did not
  happen. Normal `--reason`.
- **ENV_DATA_MISSING** — e.g., `AgentRuntimeOption` table has no
  enabled rows so V2/V3 cannot pick a runtime. Prefix
  `--reason "ENV_DATA_MISSING: ..."` and add a fixture file under
  `ai-dev/active/I-00091/e2e_fixtures/` if appropriate.
- **SPEC_MISMATCH** — the design doc disagrees with the V step. Prefix
  `SPEC_MISMATCH:` with a citation of the design doc location.

## Report

After verification, write
`ai-dev/active/I-00091/reports/I-00091_S14_BrowserVerification_Report.md`
containing:

- A pass/fail table with one row per V1..V6.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if root cause was
  investigated.
- A list of screenshots captured under `evidences/post/`.
- A **No regressions observed** subsection covering V6.

Then call ONE of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00091/reports/I-00091_S14_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00091/reports/I-00091_S14_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "I-00091",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Phase-only override survives reload", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Runtime-only override survives reload", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Both-axes override survives reload", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Clear back to global removes the override", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "In-place swap, no full-page reload", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions on adjacent flows", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
