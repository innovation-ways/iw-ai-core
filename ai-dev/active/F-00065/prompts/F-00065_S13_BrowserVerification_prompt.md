# Browser Verification Prompt: F-00065-S13-BrowserVerification

**Work Item**: F-00065 — Diagram display in code view
**Step**: S13
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

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs — do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, etc.). Always use the env var.

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `dashboard/routers/code.py`
- `dashboard/routers/code_ui.py`
- `dashboard/routers/code_ui.py`
- `dashboard/templates/fragments/code_module_diagram.html`
- `dashboard/templates/fragments/code_architecture_diagram.html`
- `dashboard/templates/fragments/code_module_detail.html`
- `dashboard/templates/fragments/code_architecture_view.html`

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S13_BrowserVerification_Report.md`
- `ai-dev/active/F-00065/evidences/post/` — screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in with the provided credentials:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots: use `playwright-cli screenshot` (no path argument), then `cp .playwright-cli/page-*.png ai-dev/active/F-00065/evidences/post/F-00065_v<N>_<name>.png`. Passing a path to `playwright-cli screenshot` is invalid.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL that has the project's schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py`.

**This feature requires diagram `ProjectDoc` rows in the DB.** The baseline seed does not include them. You MUST add a fixture file:

```
ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py
```

The file must export `def seed(db: Session) -> None` and insert:

1. A `ProjectDoc` row for the architecture diagram:
   - `project_id`: the seeded project's ID (check `scripts/e2e_seed.py` for the project slug, typically `"iw-ai-core"` or the first project in the seed)
   - `doc_id`: `"diagram-architecture"`
   - `doc_type`: `"diagram"`
   - `tier`: `"fully_automated"`
   - `content`: a short valid Mermaid DSL, e.g.:
     ```
     ---
     config:
       layout: elk
     ---
     graph TD
       A[Dashboard] --> B[RAG]
       A --> C[Daemon]
       B --> D[LanceDB]
     ```

2. A `ProjectDoc` row for a module diagram:
   - `doc_id`: `"diagram-module-rag"` (or any slug that matches a module visible in the code view)
   - `doc_type`: `"diagram"`
   - `tier`: `"fully_automated"`
   - `content`: a short valid Mermaid DSL, e.g.:
     ```
     ---
     config:
       layout: elk
     ---
     graph TD
       MG[MapGenerator] --> LLM[LLM Client]
       MG --> DB[(ProjectDoc)]
       ModGen[ModuleGenerator] --> LLM
     ```

Make seeding idempotent (check `db.scalar(select(...).where(ProjectDoc.doc_id == ...))` before insert). If the project row doesn't exist yet, call `iw step-fail` with `ENV_DATA_MISSING:` prefix.

> ⚠️ NEVER run the seed from your host shell. After writing the fixture file, you MUST exec into the `app` container and re-run the seed **before opening the browser**:
> ```bash
> docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
> ```
> Only if this `exec` fails should you fall back to `iw step-fail` with `ENV_DATA_MISSING:`.

## Verification Steps

### V1: Architecture diagram visible on code index page (AC2)

1. Navigate to `$IW_BROWSER_BASE_URL/projects/<project-slug>/code`.
2. Wait for the page to load fully. Scroll down to find the Architecture section — the architecture diagram panel should be rendered below or alongside the architecture map text.
3. **Verify:** An element with `id="code-arch-diagram"` (or a heading "Architecture Diagram") is visible on the page. The Mermaid DSL has been rendered into an SVG inside the diagram container — NOT shown as raw text.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00065/evidences/post/F-00065_v1_arch_diagram.png`

### V2: Module diagram visible in module detail view (AC1)

1. From the code index page, click on a module that has a seeded diagram doc (e.g., the `rag` module if `diagram-module-rag` was seeded).
2. Wait for the module detail fragment to load. The module documentation should appear first, followed by a "Component Diagram" section below it.
3. **Verify:** A `<div>` with class `code-module-diagram` (or heading "Component Diagram") is visible. The Mermaid block is rendered as an SVG — not raw DSL text, not a blank container.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00065/evidences/post/F-00065_v2_module_diagram.png`

### V3: Empty state for module without a diagram (AC3)

1. Click on a module that does NOT have a seeded diagram doc (any module other than the one seeded in V2).
2. Wait for the module detail to load.
3. **Verify:** The diagram section shows the empty-state message "No diagram yet" (or an element with class `code-diagram-empty`). No error toast, no 404 page, no broken fragment — just the empty state.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00065/evidences/post/F-00065_v3_empty_state.png`

### V4: Mermaid blocks in architecture text render correctly (AC4)

1. Navigate back to `$IW_BROWSER_BASE_URL/projects/<project-slug>/code` (the code index page).
2. Inspect the architecture map text area — if the architecture map content includes a ` ```mermaid ``` ` fenced block (inserted by F-00064's `generate_level1`), it should be rendered as a diagram.
3. **Verify:** No `<div class="mermaid">` is visible in the DOM (that was the old broken format). Instead, any Mermaid content in the architecture text is rendered as an SVG inside a `<pre data-lang="mermaid">` container. If the architecture map has no Mermaid block at all, skip this verification and note it in the report.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00065/evidences/post/F-00065_v4_mermaid_render.png`

### V5: No Regressions

1. Navigate to the main project page and verify it loads without errors.
2. Click on a module, confirm the existing doc section, generating states, and Q&A panel are all intact (not broken by the new diagram slot).
3. Verify no new console errors appeared on any page visited during V1–V4.
4. **Screenshot:** `playwright-cli screenshot` → `cp .playwright-cli/page-*.png ai-dev/active/F-00065/evidences/post/F-00065_v5_no_regressions.png`

## Pass Criteria

All V1–V5 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, or showed broken UI. Use a normal `--reason`.
- **ENV_DATA_MISSING** — the page rendered cleanly with HTTP 200 but showed an empty-state because the E2E DB lacks the diagram `ProjectDoc` rows. Prefix the reason with `ENV_DATA_MISSING:` and point to the fixture file:

  ```bash
  uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
    --reason "ENV_DATA_MISSING: V1/V2 require diagram ProjectDoc rows — add ai-dev/active/F-00065/e2e_fixtures/001_diagram_docs.py" \
    --report ai-dev/active/F-00065/reports/F-00065_S13_BrowserVerification_Report.md
  ```

## Report

After verification, write `ai-dev/active/F-00065/reports/F-00065_S13_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1–V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if the agent investigated root cause.
- A list of the screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering the adjacent flows tested in V5.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00065/reports/F-00065_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00065/reports/F-00065_S13_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00065",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "Architecture diagram visible", "status": "pass|fail", "screenshot": "F-00065_v1_arch_diagram.png", "notes": ""},
    {"id": "V2", "name": "Module diagram visible", "status": "pass|fail", "screenshot": "F-00065_v2_module_diagram.png", "notes": ""},
    {"id": "V3", "name": "Empty state for no diagram", "status": "pass|fail", "screenshot": "F-00065_v3_empty_state.png", "notes": ""},
    {"id": "V4", "name": "Mermaid blocks render correctly", "status": "pass|fail", "screenshot": "F-00065_v4_mermaid_render.png", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "F-00065_v5_no_regressions.png", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/F-00065/evidences/post/F-00065_v1_arch_diagram.png",
    "ai-dev/active/F-00065/evidences/post/F-00065_v2_module_diagram.png",
    "ai-dev/active/F-00065/evidences/post/F-00065_v3_empty_state.png",
    "ai-dev/active/F-00065/evidences/post/F-00065_v4_mermaid_render.png",
    "ai-dev/active/F-00065/evidences/post/F-00065_v5_no_regressions.png"
  ],
  "notes": ""
}
```
