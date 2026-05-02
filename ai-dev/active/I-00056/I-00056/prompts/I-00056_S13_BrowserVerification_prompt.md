# Browser Verification Prompt: I-00056-S13-BrowserVerification

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Testcontainers via pytest fixtures allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials:** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers:** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT run `make dev`, `docker compose`, `playwright install`, `agent-browser`, or any `chromium.launch()` snippet. Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- `dashboard/utils/markdown.py`
- `dashboard/routers/code_ui.py`
- `dashboard/routers/code.py`
- `dashboard/templates/fragments/code_architecture_view.html`
- `dashboard/templates/fragments/code_module_chips.html`
- `orch/rag/mapgen.py`

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S13_BrowserVerification_Report.md`
- `ai-dev/active/I-00056/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Always `playwright-cli snapshot` before `fill`/`click`. Screenshots: `playwright-cli screenshot` (no path arg), then `cp .playwright-cli/page-*.png ai-dev/active/I-00056/evidences/post/<name>.png`.

## E2E DB seed data

If the E2E DB lacks an architecture-map for any project, add a fixture file `ai-dev/active/I-00056/e2e_fixtures/001_seed_arch_map.py` exporting `def seed(db: Session) -> None`. Seed:

- A `Project` row.
- A `ProjectDoc` with `id={project_id}:architecture-map`, `doc_type='architecture'`, content with at least 3 H2 sections (Purpose, Components — with 2+ component bullets, Entry Points).
- A completed `CodeIndexJob` referencing the architecture-map doc id.

Run inside the container:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from the host shell — `.env` resolves to the production DB on port 5433.

## Verification Steps

### V1: Chip strip is the first interactive surface

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code`.
2. Wait for chip strip htmx load to settle.
3. **Verify** the chip strip element exists and precedes the prose body in document order:
   ```bash
   playwright-cli evaluate "(()=>{
     const chipsSlot = document.querySelector('#code-component-chips-slot');
     const chips = document.querySelector('#code-component-chips');
     const prose = document.querySelector('.prose-doc');
     if (!chipsSlot || !prose) return 'missing-elements';
     const slotIdx = chipsSlot.compareDocumentPosition(prose) & Node.DOCUMENT_POSITION_FOLLOWING;
     const chipCount = chips ? chips.querySelectorAll('a').length : 0;
     return { slotBeforeProse: !!slotIdx, chipCount };
   })()"
   ```
   Expect `slotBeforeProse === true` and `chipCount >= 1`.
4. **Screenshot:** `ai-dev/active/I-00056/evidences/post/I-00056_v1_chip_strip_top.png`.

### V2: Click a chip → module detail loads in #code-detail-panel

1. Snapshot, then click the first chip.
2. Wait for htmx swap to complete.
3. **Verify** the `#code-detail-panel` is non-empty AND contains an `<h2>` or similar heading naming the module:
   ```bash
   playwright-cli evaluate "(()=>{
     const panel = document.querySelector('#code-detail-panel');
     if (!panel) return 'no-panel';
     return { hasContent: panel.textContent.trim().length > 0, html: panel.innerHTML.length };
   })()"
   ```
   Expect `hasContent === true` and `html > 100`.
4. **Screenshot:** `ai-dev/active/I-00056/evidences/post/I-00056_v2_module_detail_loaded.png`.

### V3: Non-Purpose H2 sections are collapsed by default

1. Reload the page (or open in a new tab) so client-side state is fresh.
2. **Verify** the FIRST `<details>` inside `.prose-doc` is `open`, the rest are not:
   ```bash
   playwright-cli evaluate "(()=>{
     const ds = document.querySelectorAll('.prose-doc details');
     const states = Array.from(ds).map(d => ({summary: d.querySelector('summary')?.textContent.trim(), open: d.open}));
     return { count: ds.length, states };
   })()"
   ```
   Expect `states[0].open === true` and `states.slice(1).every(s => s.open === false)`.
3. **Screenshot:** `ai-dev/active/I-00056/evidences/post/I-00056_v3_collapsed_h2.png`.

### V4: User can expand a collapsed section

1. Click the second `<details>`'s `<summary>`.
2. **Verify** the section is now open:
   ```bash
   playwright-cli evaluate "document.querySelectorAll('.prose-doc details')[1].open"
   ```
   Expect `true`.
3. **Screenshot:** `ai-dev/active/I-00056/evidences/post/I-00056_v4_expanded.png`.

### V5: No Regressions

1. Confirm the cards section (`#code-components-section`) still renders below the prose with the same module count as the chip strip.
   ```bash
   playwright-cli evaluate "(()=>{
     const chipCount = document.querySelectorAll('#code-component-chips a').length;
     const cardCount = document.querySelectorAll('#code-components-section a[href*=\"/code/modules/\"]').length;
     return { chipCount, cardCount, match: chipCount === cardCount };
   })()"
   ```
   Expect `match === true`.
2. Confirm no new console errors appeared during V1..V4.
3. **Screenshot:** `ai-dev/active/I-00056/evidences/post/I-00056_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure requires `iw step-fail`.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — Chip slot missing, wrong DOM order, all H2s open, click does nothing → fix-cycle agent patches code.
- **ENV_DATA_MISSING** — Page returned 200 but no architecture-map seeded → add an `e2e_fixtures/` file. Prefix the reason with `ENV_DATA_MISSING:`.

## Report

Write `ai-dev/active/I-00056/reports/I-00056_S13_BrowserVerification_Report.md`:

- Pass/fail table for V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Numeric/JSON output from each `evaluate` call.
- Screenshot list.
- "No regressions observed" subsection.

Then call **one** of:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00056/reports/I-00056_S13_BrowserVerification_Report.md

uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00056/reports/I-00056_S13_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00056",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "chip strip precedes prose", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "chip click loads detail", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Purpose open, rest closed", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "expand works", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
