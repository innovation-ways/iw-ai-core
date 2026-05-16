# Browser Verification Prompt: CR-00056-S22-BrowserVerification

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S22
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

`docker compose exec app ...` against the per-worktree compose stack is allowed when re-running the seed after writing a fixture file.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against any DB. The CR-00056 migration has already been applied to the per-worktree DB by the stack's seed phase.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or URLs.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart` command -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` -- the design document
- `dashboard/templates/fragments/item_steps_table.html`
- `dashboard/templates/fragments/prompt_text_modal.html`
- `dashboard/static/styles.css`
- `dashboard/static/prompt_modal.js`
- `dashboard/routers/items.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/fix_cycle.py`
- `orch/db/models.py`

## Output Files

- `ai-dev/active/CR-00056/reports/CR-00056_S22_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00056/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click`.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00056/evidences/post/`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production via `pg_dump`. To verify the Prompt column you need an item with at least one StepRun whose `prompt_text` column is non-NULL — i.e., a step that was launched **after** S04 of this CR was deployed.

Two paths to satisfy that precondition:

**Path A — pick a recent item** that has a step launched by the daemon after this CR landed. Navigate the project home → History tab, look for an item whose latest step ran today, and click into it. If found, use that item for V1–V4 and skip the fixture.

**Path B — add a fixture** at `ai-dev/active/CR-00056/e2e_fixtures/001_prompt_seed.py` that inserts a WorkItem + WorkflowStep + two StepRuns:
- StepRun #1: `prompt_text = "INITIAL PROMPT BODY — operator should see this in the modal."`
- StepRun #2: `fix_prompt_text = "FIX-CYCLE PROMPT BODY — for cycle 1."`, `prompt_text = "INITIAL PROMPT BODY — operator should see this in the modal."`

`def seed(db: Session) -> None` must be idempotent (use `db.get(...)` then update-or-insert). After writing the file, re-seed inside the app container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run the seed from your host shell.**

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

Auto-run by the qv-browser agent.

### V1: Prompt column visible in steps table

1. Navigate to the project home: `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/`.
2. Click into an item that has at least one StepRun with prompt_text (use the item from Path A or the fixture-seeded item from Path B).
3. **Verify:** the steps table renders a column titled "Prompt" positioned **immediately to the right of "Model" and immediately to the left of "Status"**. The column header text is exactly `Prompt`.
4. **Verify:** at least one row in the table renders a `View` button in the Prompt cell. Rows for synthetic steps (S00, MERGE) or steps without runs render `—` instead.
5. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v1_prompt_column.png`.

### V2: Modal opens on View click and shows prompt text

1. From V1, click the `View` button in a row whose StepRun has `prompt_text` set.
2. **Verify:** a modal appears with:
   - `role="dialog"`, `aria-modal="true"`.
   - A header showing the step ID (e.g., "Step S04") and the agent label.
   - A scrollable `<pre>` body containing the prompt text. For Path B's seeded item, the body contains the literal string `INITIAL PROMPT BODY — operator should see this in the modal.`.
   - A `Copy` button in the section header.
3. **Verify:** the prompt-file path string is visible in the modal header subtitle (when set on the WorkflowStep).
4. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v2_modal_open.png`.

### V3: Modal dismissal honours Escape, backdrop, and close button

1. From V2 (modal open), press the **Escape** key. **Verify** the modal disappears and focus returns to the `View` button.
2. Re-open the modal. Click the **close button** (`×`) in the header. **Verify** the modal closes.
3. Re-open the modal. Click the **backdrop area** (outside the modal but inside the viewport). **Verify** the modal closes.
4. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v3_modal_dismissed.png` (snapshot taken after final dismissal showing the table again).

### V4: Stacked Initial + Fix Prompt sections (requires Path B fixture or a real fix-cycle item)

1. Open the modal for an item whose step has both an initial run and a fix-cycle retry (Path B seeds this).
2. **Verify:** the modal body contains **two labelled sections**:
   - `Initial Prompt` containing the base prompt text.
   - `Fix Prompt (cycle 1)` containing the fix-cycle prompt text.
3. **Verify:** the sections are stacked vertically (Initial above Fix).
4. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v4_fix_cycle_stacked.png`.

### V5: Copy-to-clipboard works

1. From V2 or V4 (modal open), click the `Copy` button on a section.
2. **Verify:** the button briefly shows `Copied` (or equivalent success text from `window.iwClipboard.copy`).
3. **Verify (best-effort):** read the clipboard via playwright-cli if supported, OR re-open the modal and visually confirm the button reverted to `Copy` after the success window. If clipboard read is not supported in headless mode, document this and rely on the button-state assertion as proxy.
4. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v5_copy_feedback.png`.

### V6: XSS safety on prompt content

1. If Path B's fixture inserts a StepRun whose `prompt_text` contains a literal `<script>alert("xss")</script>` string, open that step's modal.
2. **Verify:** the modal body **renders the text as escaped HTML** — i.e., the literal `<script>` characters are visible as text inside the `<pre>`, NOT executed. No `alert` dialog appears.
3. **Verify:** browser console has no JS errors during the open.
4. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v6_xss_escaped.png`.

(If the fixture doesn't include an XSS payload, document V6 as `n/a — fixture does not include XSS payload` and rely on the unit-test coverage of escaping. But adding the payload to the fixture is the better option.)

### V7: No Regressions

1. Revisit adjacent tabs on the item-detail page (Reports, Files, Logs) and verify they still load without errors.
2. Revisit other project pages (Queue, History, Batches) and verify no console errors.
3. Verify the existing CLI/Model `<select>` and bulk-apply form in the steps table still work (click the bulk dropdown, change a row's CLI override) — the new Prompt column must not have broken htmx wiring for sibling cells.
4. **Screenshot:** `ai-dev/active/CR-00056/evidences/post/CR-00056_v7_no_regressions.png`.

## Pass Criteria

All V1..V7 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail`.

### Distinguishing code defects from environment gaps and spec mismatches

Standard policy. Use `ENV_DATA_MISSING:` prefix if V1's precondition cannot be met without a fixture and Path B fixture has not been added. Use `SPEC_MISMATCH:` only if the design doc explicitly contradicts what the V step asks.

## Report

After verification, write `ai-dev/active/CR-00056/reports/CR-00056_S22_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V7.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if the agent investigated root cause.
- The list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V7.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00056/reports/CR-00056_S22_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00056/reports/CR-00056_S22_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S22",
  "agent": "qv-browser",
  "work_item": "CR-00056",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Prompt column visible", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Modal opens with prompt text", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Modal dismissal a11y", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Stacked Initial + Fix sections", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Copy-to-clipboard", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "XSS escape on prompt content", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions on adjacent tabs/pages", "status": "pass|fail|n/a", "failure_class": "null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
