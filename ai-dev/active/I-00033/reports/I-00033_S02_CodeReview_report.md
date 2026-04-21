# I-00033 S02 Code Review Report

## Summary

Reviewed S01 frontend changes for I-00033 (Code view layout bugs). All three bugs (banner dismissal, scroll container relocation, CSS variable toggle) are correctly implemented. Zero critical or high findings.

---

## Bug 1 — Last run banner dismissal

**Files**: `dashboard/templates/fragments/code_job_report.html`, `dashboard/static/code/last_run_banner.js`

| Check | Result |
|-------|--------|
| Close button has `data-dismiss-job-id="{{ last_completed_job.id }}"` | PASS — line 22 |
| Close button has `data-project-id="{{ current_project.id }}"` | PASS — line 23 |
| `aria-label="Dismiss last-run banner"` present | PASS — line 21 |
| localStorage key is project-scoped: `iw_code_lastrun_dismissed:` + projectId | PASS — `last_run_banner.js:7` |
| Dismissal is per job id (new job ≠ stored id → banner reappears) | PASS — `last_run_banner.js:8-12` |
| Script re-runs after htmx swap via `htmx:afterSettle` targeting `#code-status-panel` | PASS — `last_run_banner.js:14-19` |
| No dynamic Tailwind classes | PASS — all class values are literal strings |
| Script deferred in `project_code.html:113` | PASS |

**Extracted script** (`last_run_banner.js`, 24 lines) correctly handles the full lifecycle: initial check on DOMContentLoaded, htmx-afterSettle re-check, and click handler persisting the dismissed job id.

---

## Bug 2 — Scroll container relocation

**Files**: `dashboard/templates/project_code.html`, `dashboard/templates/fragments/code_architecture_view.html`

| Check | Result |
|-------|--------|
| `#code-content-root` no longer has `lg:overflow-y-auto` | PASS — confirmed absent |
| `#code-content-root` no longer has `lg:pr-4` | PASS — confirmed absent |
| Architecture card root has `h-full` | PASS — `code_architecture_view.html:1` |
| Architecture card root has `overflow-y-auto` | PASS — `code_architecture_view.html:1` |
| `overflow-hidden` removed from card root | PASS — confirmed absent |
| `#page-body` has `lg:gap-4` | PASS — `project_code.html:88` |
| `#code-components-section` and `#code-detail-panel` remain inside scroll container | PASS — both elements remain in `code_architecture_view.html` |

The Architecture card root now has exactly one overflow declaration (`overflow-y-auto`) with `h-full` providing the definite height needed for the scrollbar to appear.

---

## Bug 3 — CSS variable toggle

**Files**: `dashboard/static/chat/panel.js`, `dashboard/templates/chat/panel.html`

| Check | Result |
|-------|--------|
| `applyCollapsedState(true)` sets `--chat-width` to `48px` on `document.documentElement` | PASS — `panel.js:21` |
| `applyCollapsedState(false)` restores `--chat-width` from module-scoped `chatWidth` | PASS — `panel.js:25` |
| Resize handler continues to write `--chat-width` directly | PASS — `panel.js:101` |
| `mouseup` persists `chatWidth` to `localStorage.iw_chat_width` | PASS — `panel.js:110` |
| Boot sequence: line 11 sets initial value, line 114 `applyCollapsedState(false)` re-asserts it | PASS — correct sequence |

### Bug 3 companion — collapsed-rail CSS

**File**: `dashboard/templates/chat/panel.html`

| Check | Result |
|-------|--------|
| Inline `<style>` hides `#chat-context-label` when `data-collapsed="true"` | PASS — line 2 |
| Inline `<style>` hides `#chat-messages` when `data-collapsed="true"` | PASS — line 3 |
| Inline `<style>` hides `#chat-scroll-to-bottom-wrap` when `data-collapsed="true"` | PASS — line 4 |
| Inline `<style>` hides `#chat-composer` when `data-collapsed="true"` | PASS — line 5 |
| `#chat-collapse-btn` remains visible when collapsed | PASS — selector not in hide list |
| Composer selector `#chat-composer` matches rendered DOM | PASS — `composer.html:1` has `id="chat-composer"` |
| Arrow rotates 180° via `transform: rotate(180deg)` | PASS — line 6 |
| Mobile drawer behavior unchanged (`lg:` guards prevent regression) | PASS — all new selectors gated by desktop breakpoint |

---

## Cross-cutting checks

| Check | Result |
|-------|--------|
| No dynamic Tailwind class construction (`{{`, `${`, `+` in class attributes) in S01 files | PASS |
| No `chromium.launch()`, `agent-browser`, or `playwright install` calls | PASS |
| `dashboard/routers/code_ui.py` unchanged | PASS — server-side logic intact |
| No arbitrary-value Tailwind classes (e.g., `w-[123.456px]`) | PASS |
| JS syntax valid (`node --check` on `panel.js` and `last_run_banner.js`) | PASS — no errors |
| `chat/panel.html` inline style for collapsed rail is CSS-only | PASS |

---

## Acceptance Criteria coverage

- **AC1** (banner dismissible + per-job-id persistence): supported by `data-dismiss-job-id`, `data-project-id`, project-scoped localStorage key, and htmx-afterSettle re-check.
- **AC2** (scrollbar inside card): supported by `h-full overflow-y-auto` on Architecture card root; `overflow-hidden` removed.
- **AC3** (chat collapse reclaims space): supported by `--chat-width` toggle in `applyCollapsedState`; resize handler unchanged.
- **AC4** (tests exist): N/A at this step (S03 adds tests).
- **AC5** (mobile unchanged): all new CSS gated behind `lg:` breakpoints; mobile drawer layout unaffected.

---

## Verdict

**pass** — zero critical, zero high findings.

---

## Notes

The dismissal script was extracted to `last_run_banner.js` (24 lines, exceeding the ~20-line inline threshold). The `defer` attribute on the script tag in `project_code.html:113` ensures it does not block page render while still executing before `htmx:afterSettle` events fire on initial load.

The Architecture card scroll approach (removing `overflow-hidden` rather than stacking both overflow declarations) is correct and avoids CSS ordering-dependent behavior.
