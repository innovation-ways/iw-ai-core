# I-00079_S01_frontend-impl_prompt

**Work Item**: I-00079 — Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00079 --json`. `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00079/I-00079_Issue_Design.md` — design document (read first; especially Root Cause Analysis, the affected-templates table, and AC1–AC3)
- `ai-dev/active/I-00079/evidences/pre/` — pre-fix evidence (`I-00079-broken-link-404.png` shows the 404; `I-00079-queue-snapshot.yml` shows the broken `<a href>`)
- `dashboard/templates/macros/empty_state.html` — the `empty_state(...)` macro; `primary_href` is dropped straight into `<a href="{{ primary_href }}">` — so the value you pass is the literal link target
- `dashboard/routers/system.py` — the doc viewer: `router = APIRouter(prefix="/system")` (line ~40) and `@router.get("/docs/{doc_path:path}")` (line ~438). Docs live at `/system/docs/<key>` where `<key>` = path under `docs/` with `.md` **stripped** (and curated `**/CLAUDE.md` paths keep their `.md`); subdirectory keys like `implementation/00_INDEX` are supported (CR-00044).
- `dashboard/routers/help.py` — `_SLUG_TO_DOC` map (lines ~32-55): the canonical, already-correct `/system/docs/...` targets per page slug. **Match your new `primary_href` values to this map.**
- The 6 files to edit (see Requirements): `dashboard/templates/pages/project/queue.html`, `dashboard/templates/pages/project/history.html`, `dashboard/templates/pages/project/batches.html`, `dashboard/templates/pages/system/all_active.html`, `dashboard/templates/docs_library.html`, `dashboard/templates/research_library.html`
- `dashboard/CLAUDE.md`, `CLAUDE.md` — conventions (Tailwind is prebuilt — an href-string edit needs no `make css`; `make lint` runs `scripts/check_templates.py` over Jinja2 templates)

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_S01_frontend-impl_report.md` — step report
- Modified: the 6 template files listed above (and optionally `tests/dashboard/test_empty_states.py` if you seed a minimal RED→GREEN assertion — see TDD Requirement)

## Context

A user reported that the "How to design an item →" button on the empty Queue page leads to `…/docs/IW_AI_Core_CLI_Spec.md`, which returns `{"detail":"Not Found"}` (HTTP 404). The dashboard serves docs at `/system/docs/<name>` (no `.md` suffix) — `/docs/<name>.md` matches no route. Six other empty-state CTAs across the dashboard have the same broken pattern (one of them is the Queue page's second panel — the drafts list). CR-00042 fixed the equivalent links in the *help popovers* (`help.py`) but never touched the `empty_state` macro call sites in the page templates — this item finishes that job. This is a pure template change: only `primary_href` string values change. No Python, no routes, no DB, no `make css`.

## Requirements

Change **only** the `primary_href` argument in each `empty_state(...)` call below. Leave `slug`, `heading`, `body`, `primary_label`, `secondary_label`, `secondary_href`, and everything else exactly as-is. Use the verbatim target strings shown (they mirror `help.py`'s `_SLUG_TO_DOC` map):

1. **`dashboard/templates/pages/project/queue.html`** — there are **two** `empty_state(...)` calls (one for the approved-items list ~line 92-100, one for the drafts list ~line 192-200). In **both**:
   - `primary_href="/docs/IW_AI_Core_CLI_Spec.md"` → `primary_href="/system/docs/IW_AI_Core_CLI_Spec#iw-approve"`

2. **`dashboard/templates/pages/project/history.html`** (~line 139):
   - `primary_href="/docs/IW_AI_Core_Architecture.md"` → `primary_href="/system/docs/IW_AI_Core_Architecture"`

3. **`dashboard/templates/pages/project/batches.html`** (~line 137):
   - `primary_href="/docs/IW_AI_Core_Daemon_Design.md#batches"` → `primary_href="/system/docs/IW_AI_Core_Daemon_Design#batches"`

4. **`dashboard/templates/pages/system/all_active.html`** (~line 72):
   - `primary_href="/docs/IW_AI_Core_Daemon_Design.md"` → `primary_href="/system/docs/IW_AI_Core_Daemon_Design"`

5. **`dashboard/templates/docs_library.html`** (~line 129):
   - `primary_href="/docs/implementation/00_INDEX.md"` → `primary_href="/system/docs/implementation/00_INDEX"`

6. **`dashboard/templates/research_library.html`** (~line 149):
   - `primary_href="/docs/implementation/00_INDEX.md"` → `primary_href="/system/docs/implementation/00_INDEX"`

Notes:
- The line numbers above are from `main` at design time — locate the actual `empty_state(...)` call in each file (search for `primary_href="/docs/`) rather than trusting the number blindly.
- Do a final sweep: `grep -rn 'primary_href="/docs/' dashboard/` must return **nothing** after your edits. Also `grep -rn '"/docs/[A-Za-z0-9_./-]*\.md' dashboard/templates/` — there should be no remaining `/docs/*.md` link targets in templates (the `/system/docs/...` form has no `.md` and is what we want).
- Do NOT change any other links in these files. Do NOT touch `help.py` (its links are already correct). Do NOT refactor the `empty_state` macro or restyle the panels.
- `/system/docs/IW_AI_Core_CLI_Spec` resolves (the file is `docs/IW_AI_Core_CLI_Spec.md`); `#iw-approve` is the anchor the Markdown `toc` extension generates for the `#### \`iw approve\`` heading — the same anchor `help.py` uses for the `queue` slug. `/system/docs/implementation/00_INDEX` resolves because CR-00044 added subdirectory doc serving.

## Project Conventions

Read `dashboard/CLAUDE.md` and `CLAUDE.md`: Tailwind CSS is prebuilt — an href-string change does not require `make css`; fragment templates under `templates/fragments/` must NOT extend `base.html` (not relevant here — these are `pages/` templates); `make lint` runs `node --check` on dashboard JS and `scripts/check_templates.py` on Jinja2 templates. Keep the Jinja2 `format` filter `%`-style if you happen to touch any (you shouldn't need to).

## TDD Requirement

The behavioural surface is "the rendered `<a class="empty-state__cta-primary">` href resolves to HTTP 200, and is not the broken `/docs/<name>.md` form". S03 (tests-impl) will write the full regression test. Before you finish, you SHOULD add at least one minimal RED→GREEN assertion to `tests/dashboard/test_empty_states.py` — e.g. render `/project/{test_project.id}/queue`, extract the `empty-state__cta-primary` href, assert it does not start with `/docs/` and that `client.get(href.split("#")[0]).status_code == 200`. Keep it small; S03 fills in the rest. If you can't run the dashboard tests in your worktree, still add the assertion and note it in the report — don't ship the fix with zero tests.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues in files you touched:

1. `make format` — auto-fixes formatting drift; re-stage if it changes files.
2. `make typecheck` — zero errors involving your files (template-only change — likely a no-op; note any pre-existing errors).
3. `make lint` — **includes `scripts/check_templates.py` (Jinja2) and `node --check` on dashboard JS** — must pass with zero new violations.

Record results in the `preflight` object. If a tool is unavailable in your worktree, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted test file — do NOT run the full suite (`make test-unit` / `make test-integration` are downstream QV gates S09/S10):

```bash
uv run pytest tests/dashboard/test_empty_states.py -v
```

Do not report `tests_passed: true` unless this passes with zero failures. If you can't run the dashboard tests in your worktree, note it in the report — don't run the full suite "to be safe".

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/project/queue.html",
    "dashboard/templates/pages/project/history.html",
    "dashboard/templates/pages/project/batches.html",
    "dashboard/templates/pages/system/all_active.html",
    "dashboard/templates/docs_library.html",
    "dashboard/templates/research_library.html"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

- `completion_status`: `complete` when all 7 `primary_href` values are fixed (the 6 numbered call sites above, with the Queue page contributing two), the `grep` sweeps come back clean, and the targeted tests pass; `partial` if some remain; `blocked` if an external dependency prevents progress.
- `notes`: anything S02/S03 should know — e.g. exact line numbers you edited, whether you seeded a minimal test in `test_empty_states.py`.
