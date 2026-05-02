# Browser Verification Prompt: I-00055-S11-BrowserVerification

**Work Item**: I-00055 -- Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.
Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.
Testcontainers spun up by pytest fixtures are an explicit allowed exception.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD` (the dashboard runs unauthenticated in dev; if a login screen appears, use these — otherwise ignore)
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5174`). Always use `$IW_BROWSER_BASE_URL`. The port is allocated per-worktree.

Do NOT run any of the following — they will break the isolated stack:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser`
- Any `chromium.launch()` snippet

Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00055/I-00055_Issue_Design.md`
- `orch/rag/mapgen.py`
- `dashboard/routers/code_ui.py`
- `dashboard/templates/fragments/code_architecture_view.html`
- `dashboard/templates/fragments/code_architecture_diagram.html`

## Output Files

- `ai-dev/active/I-00055/reports/I-00055_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00055/evidences/post/` — screenshots

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read current accessible element refs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots: call `playwright-cli screenshot` (no path argument), then `cp .playwright-cli/page-*.png ai-dev/active/I-00055/evidences/post/<name>.png`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded at stack bring-up by the daemon: `scripts/e2e_seed.py` runs the base seed and auto-discovers every `ai-dev/{active,archive}/<item>/e2e_fixtures/*.py` file. It will already contain managed projects from `projects.toml` (e.g. `iw-ai-core`).

If a test project does not yet have the data this verification needs (no `architecture-map` doc, no `diagram-architecture` doc, or no completed `CodeIndexJob` pointing at the architecture-map), add a fixture file:

```
ai-dev/active/I-00055/e2e_fixtures/001_seed_arch_docs.py
```

The file must export `def seed(db: Session) -> None`. Make it idempotent (`db.get(...)` before insert). Seed:

- A `Project` row (or pick an existing one).
- A `ProjectDoc` with `id={project_id}:architecture-map`, `doc_type='architecture'`, content that **embeds the legacy trailing `## Architecture Diagram` mermaid block** (proves the strip helper is engaged).
- A `ProjectDoc` with `id={project_id}:diagram-architecture`, `doc_type='diagram'`, a clean ELK-frontmatter+graph DSL.
- A completed `CodeIndexJob` for that project pointing at the architecture-map doc id.

> Do NOT re-run `scripts/e2e_seed.py` yourself, and do NOT issue `docker compose exec` to seed from inside the container. The daemon reseeds on the next stack bring-up; your job is just to write the fixture file and then call `iw step-fail --reason ENV_DATA_MISSING: …` (see Pass Criteria below). The relaunched verification will see the fixture data.
>
> ⚠️ NEVER run the seed from the host shell either — `.env` resolves to the production orchestration DB on port 5433 and writes there would corrupt live state (see the 2026-04-22 incident in `docs/IW_AI_Core_DB_Setup.md`).

## Verification Steps

### V1: Code page renders the architecture diagram exactly once (light theme)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/code` (or whichever project the fixture seeded).
2. Wait for the architecture panel to render. Run `playwright-cli snapshot`.
3. **Verify** the page contains exactly one mermaid container by counting both possible markup forms:
   ```bash
   playwright-cli evaluate "(()=>{ const a=document.querySelectorAll('div.mermaid').length; const b=document.querySelectorAll('pre[data-lang=\"mermaid\"]').length; return {inline:b, bottom:a, total:a+b} })()"
   ```
   Expect `total === 1`.
4. **Screenshot:** `ai-dev/active/I-00055/evidences/post/I-00055_v1_one_diagram_light.png`.

### V2: Same page in dark theme; diagram is readable

1. Toggle theme via the theme button in the sidebar (snapshot first, then click). Wait for dark mode CSS to apply.
2. Re-run the same evaluate snippet — `total` must still be `1`.
3. **Verify** all node text inside the diagram is legible. The simplest programmatic proxy: assert that no `<text>` SVG element inside the mermaid container has a fill close to the page background. Pseudocode:
   ```bash
   playwright-cli evaluate "(()=>{
     const bg = getComputedStyle(document.body).backgroundColor;
     const texts = document.querySelectorAll('div.mermaid text, pre[data-lang=\"mermaid\"] text');
     const bad = Array.from(texts).filter(t => getComputedStyle(t).fill === bg);
     return { count: texts.length, lowContrast: bad.length };
   })()"
   ```
   Expect `lowContrast === 0` and `count > 0`.
4. **Screenshot:** `ai-dev/active/I-00055/evidences/post/I-00055_v2_one_diagram_dark.png`.

### V3: Architecture-map content does not contain inline mermaid markup

1. Still on the Code page, in either theme:
   ```bash
   playwright-cli evaluate "document.querySelector('.prose-doc')?.innerHTML.includes('mermaid') ?? false"
   ```
   Expect `false` — the architecture prose body does not mention the word "mermaid" (no inline pre-block, no class) — confirming the strip helper kicked in for legacy content and the new mapgen content has no inline diagram.
2. **Screenshot:** `ai-dev/active/I-00055/evidences/post/I-00055_v3_prose_clean.png`.

### V4: No Regressions

1. Confirm the Components cards still render (count cards under `#code-components-section`):
   ```bash
   playwright-cli evaluate "document.querySelectorAll('#code-components-section a[href*=\"/code/modules/\"]').length"
   ```
   Expect `>= 1` (any positive number is fine — exact count depends on seed).
2. Click into one component card. Verify the module detail panel loads (no HTTP error, content renders).
3. Open the browser devtools console; assert there are no new red-level errors during V1..V3 navigation. (`playwright-cli` already captures console diagnostics — review them.)
4. **Screenshot:** `ai-dev/active/I-00055/evidences/post/I-00055_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason. There is no "mostly passed".

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — Two diagrams still render, dark-mode text is invisible, or the strip helper failed → fix-cycle agent patches code. Use a normal `--reason`.
- **ENV_DATA_MISSING** — Page rendered cleanly but the seeded fixture is absent (no `architecture-map` doc, no `diagram-architecture` doc) → add an `e2e_fixtures/` file. Prefix the reason with `ENV_DATA_MISSING:`.

## Report

Write `ai-dev/active/I-00055/reports/I-00055_S11_BrowserVerification_Report.md`:

- Pass/fail table for V1..V4.
- The exact `$IW_BROWSER_BASE_URL` used.
- Numeric results from each evaluate call (`total`, `lowContrast`, etc.).
- List of screenshots captured.
- "No regressions observed" subsection.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00055/reports/I-00055_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00055/reports/I-00055_S11_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00055",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "one diagram (light)", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "one diagram + readable (dark)", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "prose has no inline mermaid", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "no regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
