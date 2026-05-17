# CR-00057_S03_Frontend_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. This step does not touch containers.

## ⛔ Migrations: agents generate, daemon applies

This step does not touch migrations.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md` — design (AC1, AC5, AC6 are most relevant)
- `ai-dev/active/CR-00057/reports/CR-00057_S02_API_report.md` — confirms the new `?project_id` query parameter is live
- `dashboard/static/chat_assistant/chat.js` — only JS file you are modifying
- `dashboard/templates/chat_assistant/panel.html` — read-only reference for the existing IDs (you must not change them)
- `dashboard/templates/base.html` — read-only reference for how the panel is mounted on every page
- `CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S03_Frontend_report.md`
- Modified: `dashboard/static/chat_assistant/chat.js`
- Modified or extended: `tests/dashboard/test_chat_router.py` is *not* yours — S04 owns the integration coverage. If you need a thin smoke test for the JS path itself (e.g. via the dashboard `TestClient` checking the rendered page references `chat.js`), put it in a new file under `tests/dashboard/` only if strictly necessary; otherwise leave testing entirely to S04.

## Context

`chat.js` currently fetches `/api/chat/config` and creates a session via `/api/chat/sessions` without telling the server which project the operator is viewing. You need to:

1. Detect the current project_id from the URL.
2. Pass it on both the config fetch and the session creation (`directory` argument set to the project's repo_root or a project-relative identifier).
3. Make sure pages outside `/project/{id}/...` continue to work (no project_id → fail-open list).

## Requirements

### 1. `_currentProjectId()` helper

Add a private helper near the top of `chat.js`:

```js
function _currentProjectId() {
  // /project/{id}/... → id; everything else → null
  var m = /^\/project\/([^\/]+)\//.exec(window.location.pathname);
  return m ? m[1] : null;
}
```

Treat the parsed id as opaque — do not URL-decode or normalize beyond what `regex` returns.

### 2. Append `?project_id` to the config fetch

Locate the existing `fetch('/api/chat/config')` (around line 649). Build the URL with `URLSearchParams` (or string concat with `encodeURIComponent`) so a missing project_id results in the bare `/api/chat/config` URL (matches the fail-open server contract). Keep the existing periodic refresh timer (`_modelRefreshTimer`).

### 3. Pass `directory` on session creation

Locate `_createSession()` (around line 145). When `_currentProjectId()` returns a non-null id, fetch the project's `repo_root` from a small new dashboard endpoint **OR** simply pass the project id as `directory` (decide based on what the opencode client accepts — read `orch/chat/opencode_client.py::create_session` to see what `directory` is forwarded as).

If `directory` is meant to be an absolute path: add a tiny helper on the server side **in S02's scope, not here** — coordinate via your report rather than adding a server route now. The simplest path is: pass the project_id as a sentinel and let the existing opencode client resolve it server-side. **Make the choice explicit in your report.**

If implementing requires a server-side change you didn't expect, STOP and raise a blocker — do not silently expand scope into the API layer.

### 4. Re-fetch config when project changes

The chat panel is rendered once and persists across SPA-like navigation. If the user navigates between projects without a full page reload (htmx swaps), `_currentProjectId()` may change mid-session. Add a `_lastProjectId` module variable; on each refresh tick (existing 30 s interval), compare; if changed, clear the dropdown and re-fetch.

### 5. No template/HTML changes

You must not rename, remove, or add elements in `panel.html`, `composer.html`, or any other template. The `<select id="chat-assistant-model">` element and its IDs must remain identical (a downstream qv-browser step asserts the dropdown contents on the existing selector).

### 6. Linting

Run `node --check dashboard/static/chat_assistant/chat.js` (the project's lint step does this). Make sure the script still parses.

```bash
make lint
```

`make lint` also runs `scripts/check_templates.py` on Jinja2 templates — your changes shouldn't break it.

### 7. Smoke verification (manual, not automated here)

Open the chat panel on a project page and on the root `/` page in your local dashboard. Verify the network panel shows `?project_id=` on the project page and no parameter on `/`. You do not need to automate this — the qv-browser step (S15) will assert it.

## Project Conventions

- Plain JS, no build step.
- Use `URLSearchParams` for query string building.
- Module-scope variables go inside the existing IIFE.
- Don't add console.log for normal flow; only on caught errors.

## TDD Requirement

For a JS-only change like this, behavioral tests are hard to write at the unit level. Use `"n/a — frontend JS in a no-build static asset; behavior covered by S04 dashboard tests and S15 qv-browser"` in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` (CSS/JS skip — no impact); `make lint` (must pass `node --check`); `make typecheck` (Python only — no impact). Zero errors.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/static/chat_assistant/chat.js"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "n/a — covered by S04 + S15",
  "tdd_red_evidence": "n/a — frontend JS in a no-build static asset; behavior covered by S04 dashboard tests and S15 qv-browser",
  "blockers": [],
  "notes": "Document your choice on the directory wire (project_id sentinel vs repo_root resolution)."
}
```
