# Browser Verification Prompt: I-00080-S15-BrowserVerification

**Work Item**: I-00080 -- Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Step**: S15
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`, `docker system|container|image prune`).
Allowed exceptions: testcontainers spun up by pytest fixtures; read-only `docker ps|inspect|logs`; `docker compose -p "$COMPOSE_PROJECT_NAME" exec app …` (required to re-run the e2e seed after writing a fixture); `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orchestration DB (port 5433). This item adds no migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. Do NOT start, stop, or rebuild any services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or route paths. Navigate via the UI (project home → Docs) wherever possible; only fall back to a direct URL when no UI path exists, and treat a 404 on a direct URL as a `spec_mismatch` in the prompt, not a code defect. Before asserting on page content, confirm the page itself loaded (HTTP 200, no unhandled-exception page, no load-time console errors); a 500 on the page under test is itself a `code_defect`.

Do NOT run `make dev` / `make test-e2e` / `make e2e-up` / any `docker compose up|down`; do NOT run `playwright install`; do NOT use `agent-browser`; do NOT call `chromium.launch()` — use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00080/I-00080_Issue_Design.md` -- the design document (read **Browser Verification Script**, **Acceptance Criteria AC1–AC4**).
- `ai-dev/active/I-00080/evidences/pre/` -- the pre-fix screenshots (`I-00080-darkmode-diagram-white-on-white.png`, `I-00080-html-tab.png`) — compare your post-fix screenshots against these.
- `dashboard/utils/markdown.py`, `dashboard/routers/docs.py`, `dashboard/templates/docs_detail.html`, `dashboard/templates/research_detail.html` -- the modified files.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S15_BrowserVerification_Report.md` -- the mandatory report.
- `ai-dev/active/I-00080/evidences/post/` -- screenshots.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```
Then log in: `playwright-cli snapshot` to read element refs, `playwright-cli fill <user-ref> "$IW_BROWSER_E2E_USER"`, `playwright-cli fill <pwd-ref> "$IW_BROWSER_E2E_PASSWORD"`, `playwright-cli click <submit-ref>`. Always `snapshot` before `fill`/`click`; never reuse refs across pages; wait for transitions to settle.

### Switch the dashboard to DARK MODE before the diagram checks

The dark-mode label-contrast bug only manifests in dark mode. After login, run:
```bash
playwright-cli eval "() => { document.documentElement.classList.add('dark'); localStorage.setItem('theme','dark'); }"
```
(then re-navigate so the inline theme script in `base.html` also picks it up). Confirm with `playwright-cli eval "() => document.documentElement.classList.contains('dark')"` → should return `true`.

### E2E seed data — ensure a diagram doc exists

The E2E DB is `pg_dump`'d from production, so a `diagram-architecture` doc *probably* exists for some project. To make this verification deterministic regardless of prod state, **write a fixture file** `ai-dev/active/I-00080/e2e_fixtures/001_i00080_diagram_docs.py` exporting `def seed(db: Session) -> None` that idempotently upserts, for an existing project (pick one that exists in the seed — e.g. the first project from `db.execute(select(Project)).scalars().first()`):
- a `ProjectDoc` `doc_id="i00080-fenced-diagram"`, `doc_type=DocType.diagram`, `status=DocStatus.published`, `content` = a fenced ` ```mermaid `\n`graph TD; CLI["iw CLI"] --> DB[("PostgreSQL")]; DAEMON["daemon"] --> DB`\n` ``` ` block;
- a `ProjectDoc` `doc_id="i00080-raw-dsl-diagram"`, `doc_type=DocType.diagram`, `status=DocStatus.published`, `content` = `"<!-- purpose: i00080 raw-dsl check -->\n---\nconfig:\n  layout: elk\n---\ngraph TD\n  A[Foo] --> B[Bar]\n"` (no fence).
Use `db.get(ProjectDoc, ...)` (composite PK `(project_id, doc_id)`) before insert so it's idempotent. Then re-run the seed inside the app container:
```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```
> NEVER run the seed from the host shell — the host `.env` points at the production DB on 5433.
If `docker compose exec` fails (container unreachable), `iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

## Verification Steps

### V0: Pre-flight page sanity (built-in — runs unconditionally)

The agent visits every page route referenced in V1..V4, extracts fragment references (`hx-target`, `aria-controls`, `href="#…"`, `for=`, …) from the rendered HTML, verifies each referenced `id` exists, and reads `.playwright-cli/console-*.log` after each load for unhandled JS/HTMX errors. Any dangling reference or load-time error → V0 FAIL (V1..V4 still run).

### V1: Diagram doc loads promptly and renders readably in dark mode (AC1)

1. With the dashboard in **dark mode**, navigate via the UI: project home → **Docs** → click the row/View link for the fenced-diagram doc (`i00080-fenced-diagram`), or the project's "Architecture Diagram" doc if you prefer a real one. (URL resolves to something like `$IW_BROWSER_BASE_URL/project/<pid>/docs/i00080-fenced-diagram`.)
2. Observe the page **loads within a few seconds** — not the ~30 s pre-fix wait. (Note the wall-clock; it should be well under 10 s. If it still takes 30 s, that's a `code_defect` — the route is still server-rendering Mermaid.)
3. **Verify:** the page is HTTP 200, no exception page, no load-time console errors; the **Markdown** tab shows the diagram **rendered as a diagram** (an `<svg>` with visible nodes/edges), and its node/edge **labels are legible against the page** — dark text (or light text on dark, per the dark theme), **not white-on-white**. Confirm programmatically:
   ```bash
   playwright-cli eval "() => { var l = document.querySelector('.prose-doc svg foreignObject div, .prose-doc svg .nodeLabel, .prose-doc svg text'); return l ? getComputedStyle(l).color : 'no label found'; }"
   ```
   The returned colour must **not** be `rgb(255, 255, 255)` (the pre-fix value). It should be a dark colour, or — if the diagram is rendered client-side with the dark Mermaid theme — a light colour on a dark diagram surface (in which case also screenshot to confirm the diagram surface is dark, not white). Either way: **readable**.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00080/evidences/post/I-00080_v1_diagram_darkmode_readable.png`.

### V2: Raw-DSL diagram doc renders as a diagram, not garbled text (AC3)

1. Navigate via the UI to the raw-DSL diagram doc (`i00080-raw-dsl-diagram`).
2. **Verify:** HTTP 200; the Markdown tab shows it **as a diagram** (an `<svg>` / a `div.mermaid` that got upgraded), **not** as a stack of horizontal rules, a heading reading `config:`, and paragraphs of `graph TD … A[Foo] --> B[Bar]` text. Spot-check:
   ```bash
   playwright-cli eval "() => ({ hasSvgOrMermaidDiv: !!document.querySelector('.prose-doc svg, .prose-doc div.mermaid svg'), hasConfigHeading: !!Array.from(document.querySelectorAll('.prose-doc h1,.prose-doc h2,.prose-doc h3')).find(h => h.textContent.trim() === 'config:') })"
   ```
   Expect `hasSvgOrMermaidDiv: true`, `hasConfigHeading: false`.
3. **Screenshot:** `ai-dev/active/I-00080/evidences/post/I-00080_v2_raw_dsl_diagram.png`.

### V3: HTML tab renders (and is cached on re-open) (AC2)

1. On the fenced-diagram doc page, click the **HTML** tab.
2. **Verify:** within a reasonable time the iframe shows the rendered document (the diagram title text and the diagram). It is acceptable for the *first* open to take up to ~30 s (one-time `mmdc` render of a self-contained HTML file) — but it must not stay permanently blank, and it must not show a stack trace. After it renders, switch to another tab and back to **HTML** again — it should now appear **quickly** (served from cache). If the second open still takes ~30 s, that's a `code_defect` (caching not wired).
3. **Screenshot:** `ai-dev/active/I-00080/evidences/post/I-00080_v3_html_tab.png`.

### V4: PDF tab shows content or a clear "unavailable" message — never a blank iframe / bare 503 (AC2)

1. On the fenced-diagram doc page, click the **PDF** tab.
2. **Verify** one of:
   - the iframe shows the rendered PDF, **or**
   - the iframe shows a clear "PDF unavailable" message (HTTP 200) — readable text explaining the PDF engine isn't available on this server.
   It must **not** show a permanently blank iframe with no content and no message, and the response must not be a bare 503 error page. (Check the iframe's response: `playwright-cli eval "() => { var f=document.getElementById('pdf-frame'); return f ? f.getAttribute('src') : 'no frame'; }"` then fetch that path and confirm status 200.)
3. **Screenshot:** `ai-dev/active/I-00080/evidences/post/I-00080_v4_pdf_tab.png`.

### V5: No Regressions

1. Revisit adjacent Docs flows: the Docs catalog page (search/filter still works, doc rows still link out); a **non-diagram** doc (e.g. an architecture or module doc) still renders its Markdown / HTML / PDF tabs correctly; the **Download PDF** button on a doc detail page still downloads a PDF (or behaves as before). Visit the **Research** page detail for any research doc — it still renders.
2. **Verify:** no new console errors on any page visited during V1..V5; the Code page architecture diagram (the I-00055 path) still renders client-side and readably in dark mode (it must be unaffected by this change).
3. **Screenshot:** `ai-dev/active/I-00080/evidences/post/I-00080_v5_no_regressions.png`.

## Pass Criteria

All V0..V5 must pass. Classify any failure:
- Page 5xx / console exception / wrong element / broken UI the design says should be present → **CODE_DEFECT** (normal `--reason`).
- Page 200 but missing data the seed lacks → **ENV_DATA_MISSING** (`--reason "ENV_DATA_MISSING: …"`, add/extend `ai-dev/active/I-00080/e2e_fixtures/…`).
- Page 200, element correctly absent per the design, V step asks for it anyway → **SPEC_MISMATCH** (`--reason "SPEC_MISMATCH: V{N} … cite design"`; fix-cycle MUST NOT patch code for this).

Do not write `n/a` chains — create missing preconditions yourself (CLI/route → e2e_fixtures → direct DB write).

## Report

Write `ai-dev/active/I-00080/reports/I-00080_S15_BrowserVerification_Report.md` with: a pass/fail table (one row per V0..V5); the exact `$IW_BROWSER_BASE_URL` used; observed page-load times for V1 and V3 (first vs second open); the colour value returned by the V1 `getComputedStyle` check; any issues with `file:line` if root cause was investigated; the list of screenshots under `evidences/post/`; a **No regressions observed** subsection. Then call exactly one of:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" --report ai-dev/active/I-00080/reports/I-00080_S15_BrowserVerification_Report.md
# or
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" --reason "<short specific reason>" --report ai-dev/active/I-00080/reports/I-00080_S15_BrowserVerification_Report.md
```
Always pass `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "qv-browser",
  "work_item": "I-00080",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<concrete $IW_BROWSER_BASE_URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Diagram doc loads promptly + readable in dark mode", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": "load time; computed label colour"},
    {"id": "V2", "name": "Raw-DSL diagram renders as a diagram", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "HTML tab renders + cached on re-open", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": "first vs second open time"},
    {"id": "V4", "name": "PDF tab: content or clear message, never blank/503", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions (Docs catalog, non-diagram docs, Download PDF, Research, Code-page diagram)", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
