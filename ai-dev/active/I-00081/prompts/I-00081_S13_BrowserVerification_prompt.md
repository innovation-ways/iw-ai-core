# Browser Verification Prompt: I-00081-S13-BrowserVerification

**Work Item**: I-00081 -- Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
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
  4. `docker compose -p "$COMPOSE_PROJECT_NAME" exec app …` to re-run the
     E2E seed after writing an `e2e_fixtures` file (see "E2E DB seed data").

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

This item adds no migrations. If you find one in the change set, that is a
finding for the report, not something you apply.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `iw-dev-01:9900`). Always use `$IW_BROWSER_BASE_URL`. The port is allocated per-worktree so concurrent browser_verification steps don't collide; hardcoding it silently tests the wrong environment.

Do NOT hardcode application **route paths** beyond the well-known `/project/{id}/code` (which this item touches). Prefer to navigate via the UI: open the project list / project home and click into a project, then into its "Code" tab — the route the app uses is whatever those links resolve to. If a direct URL 404s, treat it as `SPEC_MISMATCH` (the prompt's URL is wrong), not a code defect, and report the corrected path.

Before asserting on page *content*, first confirm the page **loaded successfully** (HTTP 200, no unhandled-exception page, no load-time JS/HTMX console errors). A 500 on the Code page is itself a `CODE_DEFECT` finding — capture the traceback and report it; don't retry.

Do NOT run any of the following -- they will break the isolated stack or duplicate work the orchestrator already performed:

- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose up/down/restart/build` -- the stack is already up
- `playwright install` or `npx playwright install` -- the CLI is pre-installed
- `agent-browser` -- this environment uses `playwright-cli` **exclusively**
- Any `chromium.launch()` Python/Node snippet -- always go through `playwright-cli`

## Input Files

- `ai-dev/active/I-00081/I-00081_Issue_Design.md` -- the design document (read **Steps to Reproduce**, **Browser Verification Script**, **Acceptance Criteria**).
- `ai-dev/active/I-00081/evidences/pre/I-00081-bug-evidence.png` -- the pre-fix screenshot (raw Markdown as red text + three "Syntax error in text / mermaid version 11.14.0" boxes). Your post-fix screenshots should show the diagram(s) rendered instead.
- Files modified by the implementation steps:
  - `dashboard/routers/code_ui.py`
  - `dashboard/templates/fragments/code_architecture_diagram.html`
  - `dashboard/templates/fragments/code_architecture_view.html`

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S13_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/I-00081/evidences/post/` -- screenshots taken during verification

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

(If the E2E dashboard has no auth wall, skip the login — just confirm the home page loads.)

Rules for interacting with the page:

1. Always call `playwright-cli snapshot` **before** `fill` / `click` to read the current accessible element IDs. Do not guess selectors or reuse refs from a previous page.
2. Wait for navigation/transitions to settle before snapshotting again. Mermaid renders client-side after `DOMContentLoaded` — wait ~2-3s after the Code page loads before snapshotting the diagram region.
3. Screenshots go under `ai-dev/active/I-00081/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump` (run by `ai-dev/iw-config/worktree-seed.sh`). It reflects current production state — which means a `diagram-architecture` ProjectDoc in the **iw-doc-generator Markdown-with-fences form** very likely already exists (that's exactly the row that triggered this incident — `iw-ai-core:diagram-architecture`, `generated_by='skill:iw-doc-generator'`). **First, try to verify against the real seeded data**: open the Code page for a project whose `diagram-architecture` doc is that form (the `iw-ai-core` project itself is the prime candidate — but its `id` in the E2E DB is the same `iw-ai-core`).

If, and only if, no suitable `diagram-architecture` doc exists in the seeded DB (e.g. the dump predates DOC-00057), add a fixture file:

```
ai-dev/active/I-00081/e2e_fixtures/001_md_diagram_architecture.py
```

exporting `def seed(db: Session) -> None` that idempotently (`db.get(...)` before insert) creates, for some seeded project `<pid>` that also has a completed `CodeIndexJob` + an `architecture-map` doc (so the Code page enters the "has a completed job" branch):
- a `ProjectDoc` `id=f"{pid}:diagram-architecture"`, `doc_id="diagram-architecture"`, `doc_type=DocType.diagram`, `tier="fully_automated"`, `editorial_category=EditorialCategory.technical`, `status="published"`, `generated_by="skill:iw-doc-generator"`, `source_paths=["docs/"]`, and `content` = a Markdown document with a `# … — Architecture Diagram` H1, a `<!-- generated: … -->` comment, two `> **Why this diagram?** …` blockquotes, and two ` ```mermaid ` fenced blocks (one `flowchart TB`, one `erDiagram`), each prefixed with `---\nconfig:\n  layout: elk\n---`.

After writing the fixture you MUST re-run the seed inside the `app` container before opening the browser:

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

> ⚠️ **NEVER run `uv run python scripts/e2e_seed.py` from your host shell** — the host `.env` resolves to the production orch DB on port 5433. Only `docker compose exec app …`. If `docker compose exec` fails, call `iw step-fail` with `ENV_DATA_MISSING:` so the daemon re-provisions the stack.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove this step)

> Automatically prepended by the qv-browser agent. Documented here so reviewers know what runs. The agent visits every distinct route referenced in V1..Vn, checks fragment id references resolve, and reads `.playwright-cli/console-*.log` for unhandled JS/HTMX errors. A dangling reference or unhandled load-time error is a V0 FAIL (and `overall_status=fail`), but V1..Vn still run.

### V1: The "Architecture Diagram" widget renders the diagram(s) — no "Syntax error in text" box

1. Navigate to `{{IW_BROWSER_BASE_URL}}` → the project list / home → click into the project whose `diagram-architecture` doc is the iw-doc-generator Markdown form (prefer `iw-ai-core`; the resulting URL should be `{{IW_BROWSER_BASE_URL}}/project/<pid>/code`). Wait for the page to load (HTTP 200, no exception page).
2. Wait ~2-3s for client-side Mermaid to render, then scroll the "Architecture Diagram" section into view — e.g. `playwright-cli eval "document.getElementById('code-arch-diagram')?.scrollIntoView({block:'center'})"`. This is the widget the bug lived in.
3. **Verify** (all must hold):
   - The "Architecture Diagram" section contains **rendered diagram SVG(s)** — `playwright-cli snapshot` (and/or `playwright-cli eval "document.querySelectorAll('#code-arch-diagram svg').length"`) shows ≥1 `<svg>` under `#code-arch-diagram`, and the doc had 2 fenced blocks → expect ≥2 rendered diagrams (or ≥2 `pre[data-lang="mermaid"]`/`.mermaid` containers, each upgraded to an SVG).
   - There is **NO** "Syntax error in text" / "mermaid version 11.14.0" error SVG anywhere on the page (`playwright-cli eval "document.body.innerText.includes('Syntax error in text')"` → `false`).
   - There is **NO** "Mermaid error: No diagram type detected" red text inside `#code-arch-diagram` (`document.getElementById('code-arch-diagram').innerText` does not contain `No diagram type detected` and does not contain a literal triple-backtick `mermaid` fence).
   - No new console errors appeared on this page load (check `.playwright-cli/console-*.log`).
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00081/evidences/post/I-00081_v1_code_arch_diagram_rendered.png`.

### V2: The rest of the Code page still works (No Regressions)

1. On the same `/project/<pid>/code` page: confirm the "Architecture" / module list / architecture-map prose section still renders (the `content_html` block), the module chips load (htmx — `#code-component-chips-slot`), and the page chrome (nav, search box, footer) is intact.
2. Navigate to a project whose `diagram-architecture` doc is the **legacy bare-DSL form** if one exists in the seed (or, if you can't tell, just confirm the Code page of a *second* project also loads without a "Syntax error in text" box). Verify its "Architecture Diagram" widget (if present) renders a single diagram with its purpose line — no regression to the legacy path.
3. **Verify:** no new console errors on any page visited during V1..V2; no HTTP 5xx; no broken htmx target ids.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00081/evidences/post/I-00081_v2_no_regressions.png`.

## Pass Criteria

All V0..V2 must pass. Any failure -- including a partial or ambiguous result -- requires calling `iw step-fail` with a reason. There is no "mostly passed".

Classify any failure:

| Failure shape | Class | Action |
|---|---|---|
| Code page returned 5xx or threw a console exception; "Syntax error in text" box still present; raw Markdown still dumped in `#code-arch-diagram` | CODE_DEFECT | normal `--reason` |
| Code page rendered cleanly but no project in the seed has a `diagram-architecture` doc in the iw-doc-generator form AND `docker compose exec app … e2e_seed.py` couldn't be run | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: ..."` + add `e2e_fixtures/001_md_diagram_architecture.py` |
| The route path in this prompt 404s but the Code page exists at a different path | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V1 ... corrected path is ..."` |

CODE_DEFECT → normal `--reason`. ENV_DATA_MISSING → prefix `ENV_DATA_MISSING:` and add the fixture (don't just retry). SPEC_MISMATCH → prefix `SPEC_MISMATCH:` and cite the corrected path; the fix-cycle agent must NOT patch code for a SPEC_MISMATCH.

Do not write "blocked by V1 — n/a" chains — create missing preconditions yourself via the `e2e_fixtures` route + re-seed.

## Report

After verification, write `ai-dev/active/I-00081/reports/I-00081_S13_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V0..V2.
- The exact `$IW_BROWSER_BASE_URL` used and the project id(s) you tested.
- For V1: how many fenced blocks the tested `diagram-architecture` doc had vs how many rendered SVGs you observed; whether you used seeded data or added a fixture.
- Any issues found, with `file:line` references if you investigated root cause.
- The screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V2.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00081/reports/I-00081_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00081/reports/I-00081_S13_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00081",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Architecture Diagram widget renders, no syntax-error box", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "No regressions on the Code page / legacy bare-DSL diagram", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
