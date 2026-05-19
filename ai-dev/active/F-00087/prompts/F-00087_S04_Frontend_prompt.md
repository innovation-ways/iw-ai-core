# F-00087_S04_Frontend_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00087 --json`.
- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design (read §Scope, §Frontend Changes, AC8 in full)
- `ai-dev/active/F-00087/reports/F-00087_S01_Backend_report.md` — confirms the API shape (`/api/chat/config?runtime=pi`)
- `ai-dev/active/F-00087/reports/F-00087_S03_CodeReview_FIX_report.md` (if present) — S03 fix report
- Existing UI (created by F-00086):
  - `dashboard/templates/chat_assistant/create_tab_modal.html` — runtime dropdown is here
  - `dashboard/static/chat_assistant/chat.js` — tab lifecycle and event dispatch

## Output Files

- `dashboard/templates/chat_assistant/create_tab_modal.html` — runtime dropdown gains "Pi" option
- `dashboard/static/chat_assistant/chat.js` — re-fetch model list on runtime change; per-tab model dropdown restricted to active tab's runtime
- `dashboard/static/chat_assistant/chat.css` (or append to `dashboard/static/styles.css` per CLAUDE.md mitigation if `make css` is unavailable) — minimal styling if needed
- `ai-dev/active/F-00087/reports/F-00087_S04_Frontend_report.md`

## Context

You are extending the create-tab modal's runtime dropdown to offer "Pi" as a second selectable option, and wiring the model dropdown (both in the modal and per-tab above the composer) to re-fetch its model list when the runtime changes. The user experience for sending prompts, aborting, approving permissions, etc. is unchanged — the only visible differences are the new dropdown option and the model list it produces.

## Requirements

### 1. Runtime dropdown gains "Pi" option

In `create_tab_modal.html`, the runtime `<select>` (F-00086 wired it as single-option "OpenCode") now has TWO options:

```html
<select id="chat-tab-runtime">
  <option value="opencode" selected>OpenCode</option>
  <option value="pi">Pi</option>
</select>
```

Match the existing styling and naming conventions (id/class names, htmx attributes if any). If F-00086 used a different control (radio buttons, segmented control), match that pattern — read `create_tab_modal.html` carefully before editing.

### 2. Re-fetch model list on runtime change

When the user changes the runtime dropdown, the model dropdown MUST re-fetch from `GET /api/chat/config?project_id=X&runtime=<selected_runtime>` and replace its options with the response's `models` list. Selecting `default_model` from the response if present.

Add an event listener (likely in `chat.js`) on the runtime `<select>`'s `change` event. Use the existing fetch pattern in chat.js (don't introduce a new HTTP client library). Match the existing error-handling: on 503 or non-200, show an inline error in the modal and disable the Create button until a valid model is selected.

### 3. Per-tab model dropdown is runtime-scoped

The model dropdown above the composer (F-00086 — when the user clicks the model badge to change a tab's model) lists models from `/api/chat/config?runtime=<tab.runtime>`. For a Pi tab, this means ONLY Pi models appear; for an OpenCode tab, ONLY OpenCode models.

**No cross-runtime model switching.** A user wanting to switch from a Pi model to an OpenCode model must close the Pi tab and create a new OpenCode tab. Document this in the dropdown's `title` attribute (tooltip): "Switching runtime requires creating a new tab."

### 4. Empty model list handling

If the Pi catalogue is empty for the project (Boundary Behavior row `GET /api/chat/config?runtime=pi` with empty `agent_runtime_options`), the response is `{"models": [], "default_model": "", ...}`. Show an inline message in the modal: "No Pi models configured for this project. See docs/IW_AI_Core_AI_Assistant_Models.md." Disable the Create button.

### 5. Tab strip indicator (optional but recommended)

Each tab in the strip should visually indicate its runtime (small badge, icon, or color coding). At minimum, add a `data-runtime="<opencode|pi>"` attribute to the tab DOM element so CSS or future enhancements can style it. Don't over-engineer the visual; consistency with F-00086's tab strip styling matters more than novelty.

### 6. CSS strategy

Try `make css` first. If it fails or reports "Nothing to be done", append plain CSS rules directly to `dashboard/static/styles.css` per the CLAUDE.md mitigation rule (I-00067). Document which path you took in your report.

## Project Conventions

Read `dashboard/CLAUDE.md`. Critical:
- `window.iwClipboard.copy(text, button)` for any copy buttons (do NOT use `navigator.clipboard.writeText` directly).
- Attach event listeners via `addEventListener` in chat.js; no inline `onclick=` handlers.
- Mtime-keyed Tailwind purge — avoid dynamic class names that defeat JIT purging.
- Routers/templates are thin — business logic in the backend, not in JS.

## TDD Requirement

Frontend behaviour is exercised by:
- S05's integration tests (model dropdown population for runtime=pi via TestClient).
- S13's qv-browser verification (the actual modal/dropdown UX).

For S04 alone, `tdd_red_evidence` is `"n/a — UI template/JS changes; behavioural coverage in S05 (integration) and S13 (qv-browser)"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` (Python file changes, if any)
2. `make typecheck`
3. `make lint` — includes `lint-js` and `lint-templates`
4. **Manual smoke**: open the dashboard, expand the chat panel, click "+", open the runtime dropdown and verify both OpenCode and Pi options appear; switch runtime and verify the model list re-fetches. Don't send a real prompt (S13 owns end-to-end browser verification with a real Pi runtime).

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "F-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat_assistant/create_tab_modal.html",
    "dashboard/static/chat_assistant/chat.js",
    "dashboard/static/chat_assistant/chat.css"
  ],
  "preflight": {
    "format": "ok|skipped:no-python-changes",
    "typecheck": "ok|skipped:no-python-changes",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "manual smoke: runtime dropdown shows OpenCode + Pi, model list re-fetches on change",
  "tdd_red_evidence": "n/a — UI template/JS changes; behavioural coverage in S05 (integration) and S13 (qv-browser)",
  "blockers": [],
  "notes": "CSS strategy used: <make-css|plain-css-fallback>"
}
```
