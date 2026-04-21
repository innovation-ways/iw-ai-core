# I-00033_S02_CodeReview_prompt

**Work Item**: I-00033 — Code view layout bugs
**Step**: S02
**Agent**: code-review-impl
**Reviews**: S01 (frontend-impl)

---

## Input Files

- `ai-dev/active/I-00033/I-00033_Issue_Design.md` — Design document
- `ai-dev/active/I-00033/reports/I-00033_S01_Frontend_report.md` — S01 report
- All files S01 modified (listed in the S01 report's `files_changed`):
  - `dashboard/templates/fragments/code_job_report.html`
  - `dashboard/templates/project_code.html`
  - `dashboard/templates/fragments/code_architecture_view.html`
  - `dashboard/static/chat/panel.js`
  - `dashboard/templates/chat/panel.html`
  - Optionally: `dashboard/static/code/last_run_banner.js` (if S01 extracted)
- `dashboard/CLAUDE.md` — conventions to enforce

## Output Files

- Report: `ai-dev/active/I-00033/reports/I-00033_S02_CodeReview_report.md`

## Review Checklist

Inspect each S01 change and record findings with severities (`critical`, `high`, `medium`, `low`, `info`). A `critical` or `high` finding is a blocking fail.

### Bug 1 — Last run banner dismissal

- [ ] The close button carries `data-dismiss-job-id="{{ last_completed_job.id }}"` (with the actual Jinja expression — not a hardcoded number).
- [ ] The close button carries `data-project-id="{{ current_project.id }}"` so the script scope is per-project.
- [ ] `aria-label="Dismiss last-run banner"` is present.
- [ ] The dismissal script reads `localStorage.getItem('iw_code_lastrun_dismissed:' + projectId)` (or equivalent — the key MUST be scoped by project id; `iw_code_lastrun_dismissed` without scope is a high-severity finding because dismissal leaks across projects).
- [ ] Dismissal is per job id — when the stored id does not match the current `data-dismiss-job-id`, the banner shows. When a new job completes (new id), the banner reappears automatically.
- [ ] The script re-runs after htmx swaps the banner. Either it listens on `document.body.addEventListener('htmx:afterSettle', ...)` with a target filter, or it uses a MutationObserver, or the script is inline and re-executes when the fragment is re-inserted. **Verify this explicitly** — a script that runs only on `DOMContentLoaded` is broken for htmx swaps.
- [ ] No dynamic Tailwind classes in the close button (no `class="w-{{ ... }}"` etc.).

### Bug 2 — Scroll container relocation

- [ ] `#code-content-root` no longer has `lg:overflow-y-auto` or `lg:pr-4`.
- [ ] The Architecture card root (first div in `code_architecture_view.html`) has BOTH `overflow-y-auto` AND `h-full` (or equivalent definite-height class).
- [ ] Without `h-full` (or similar definite height), the card grows to fit content and no scrollbar appears — this is a **high-severity** finding if `h-full` is missing.
- [ ] `#page-body` in `project_code.html` has `lg:gap-4` for the visible gutter between text and chat columns.
- [ ] The `overflow-hidden` on the card root is **removed** — the card class list must NOT contain both `overflow-hidden` and `overflow-y-auto` (S01 prescribes removal). If `overflow-hidden` is still present, flag as medium severity.
- [ ] `#code-components-section` and `#code-detail-panel` are unchanged (they stay inside the scroll container).

### Bug 3 — CSS variable toggle

- [ ] `applyCollapsedState(true)` sets `--chat-width` to `48px` on `document.documentElement`.
- [ ] `applyCollapsedState(false)` restores `--chat-width` from the module-scoped `chatWidth` variable (the already-loaded, clamped value from localStorage).
- [ ] The resize handler (`mousemove`) still writes `--chat-width` directly — no change needed there.
- [ ] The mouseup persists `chatWidth` to `localStorage.iw_chat_width` — unchanged.
- [ ] Boot sequence: initial `--chat-width` is set at line 11; the subsequent `applyCollapsedState(false)` at line 112 re-asserts it. This is fine.

### Bug 3 companion — collapsed-rail CSS

- [ ] Inline `<style>` in `chat/panel.html` hides `#chat-context-label`, `#chat-messages`, `#chat-scroll-to-bottom-wrap`, and the composer when `#chat-panel[data-collapsed="true"]`.
- [ ] `#chat-collapse-btn` remains visible when collapsed.
- [ ] The composer's selector matches whatever class/id wraps it in `chat/composer.html` — if the composer partial doesn't have a stable hook, S01 must have added one (e.g., a wrapping `class="chat-composer"` in `panel.html`). Verify the selector actually matches the rendered DOM.
- [ ] Mobile drawer behavior is unchanged — no new `lg:` selectors broke the mobile off-canvas layout.

### Cross-cutting

- [ ] No dynamic Tailwind class construction anywhere — grep the diff for `class="` strings that contain `{{`, `${`, or `+`. Report any hit as critical.
- [ ] No imports or calls to `chromium.launch()` / `agent-browser` / `npx playwright install` (none should appear; this is a template/JS change).
- [ ] `dashboard/routers/code_ui.py` is unchanged — server-side logic should not have moved (the `last_completed_recent` 1-hour window is the server's concern, dismissal is client-only).
- [ ] No new Tailwind classes depend on arbitrary values that the CDN doesn't ship (e.g., `w-[123.456px]` with decimals — use round numbers or inline style).
- [ ] JS syntax is valid — `node --check dashboard/static/chat/panel.js` and (if created) `node --check dashboard/static/code/last_run_banner.js`.

### Acceptance Criteria coverage

- [ ] AC1 (banner dismissible + per-job-id persistence) is supported by the markup and script.
- [ ] AC2 (scrollbar inside card) is supported by the class changes.
- [ ] AC3 (chat collapse reclaims space) is supported by the `--chat-width` toggle.
- [ ] AC4 (tests exist) — N/A at this step (S03 adds tests).
- [ ] AC5 (mobile unchanged) — verify no changes affect `< 1024 px` viewports. The three `lg:` breakpoints are the guard; make sure they are all present and correct.

## Verdict

Emit one of:

- `pass` — zero critical, zero high findings.
- `fail` — one or more critical or high findings. List each with `file:line` and a concrete remediation.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00033",
  "reviews_step": "S01",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "critical|high|medium|low|info", "file": "path:line", "issue": "...", "remediation": "..."}
  ],
  "notes": "Summary of review. If pass, state the key checks that passed (not a rubber-stamp)."
}
```
