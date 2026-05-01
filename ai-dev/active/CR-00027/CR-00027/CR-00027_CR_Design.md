# CR-00027: Dashboard Sidebar Nav — Collapsible Section Headers

**Type**: Change Request
**Priority**: Low
**Reason**: UX / readability — section headers should be visually distinct from nav items, and collapsible sections reduce visual noise
**Created**: 2026-04-30
**Status**: Draft

---

## Description

The sidebar left-nav has two section groupings — "Projects" and "System" — whose header labels currently look identical to the nav items beneath them (same text size, same color). This change makes those headers visually distinct (bold, `text-sidebar-primary-foreground`) and wraps each section in a `<details>/<summary>` element so users can collapse/expand them. Collapsed state is persisted in `localStorage` so it survives page reloads, using a small vanilla-JS snippet already in the sidebar's `<script>` block.

---

## Project Context

See `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, Tailwind CSS conventions (prebuilt via `make css`), and htmx fragment patterns. Tailwind classes must be added to templates (not dynamic JS strings) so the JIT purge picks them up. Run `make css` after editing templates.

---

## Current Behavior

In `dashboard/templates/base.html` (lines 85–133):

- "Projects" header is a `<p>` tag with classes `text-xs text-sidebar-foreground font-medium uppercase tracking-wide` — no chevron, not clickable, not collapsible.
- The projects list below it is an htmx-loaded `<div>` that expands independently (individual project entries use `<details>/<summary>`).
- "System" header is a similar `<p>` tag inside a border-top wrapper — also not collapsible.
- System links are always visible; there is no way to hide them.
- State is never persisted; the sidebar always shows the same layout on every page load.

---

## Desired Behavior

- "Projects" and "System" labels become `<summary>` elements inside `<details open>` wrappers.
- Headers are styled with `font-semibold text-sidebar-primary-foreground` (visually heavier and brighter than the nav items) plus a rotating chevron SVG matching the pattern in `nav_projects.html`.
- Clicking a header toggles the section open/closed.
- The open/closed state of each section is saved in `localStorage` under keys `sidebar-projects-open` and `sidebar-system-open`. On page load the saved value is restored before first paint to avoid flicker.
- Both sections default to **open** when no localStorage value is found.
- The implementation is entirely frontend (HTML + a small vanilla-JS snippet in `base.html`). No backend, no DB, no API changes.

---

## Impact Analysis

### Affected Components

| Component | File | Change Type |
|-----------|------|-------------|
| Sidebar nav template | `dashboard/templates/base.html` | Modify |
| Compiled CSS | `dashboard/static/styles.css` | Regenerate (`make css`) |

### Breaking Changes

None. The sidebar is a Jinja2 template rendered server-side; no API contracts change.

### Data Migration

Not required.

---

## Implementation Plan

| Step | Agent | Description | Parallel? |
|------|-------|-------------|-----------|
| S01 | frontend-impl | Wrap Projects and System sections in `<details open>`/`<summary>`; style headers; add localStorage persistence JS | — |
| S02 | code-review-impl | Per-agent code review of S01 | after S01 |
| S03 | code-review-fix-impl | Fix CRITICAL/HIGH findings from S02 | after S02 |
| S04 | code-review-final-impl | Cross-agent final review | after S03 |
| S05 | code-review-fix-final-impl | Fix final review findings | after S04 |
| S06 | qv-gate | `make css` — CSS build gate | after S05 |
| S07 | qv-gate | `make lint` — Lint gate | after S06 |
| S08 | qv-browser | Browser verification — expand/collapse both sections; localStorage persistence | after S07 |

### Frontend Changes Summary

**`dashboard/templates/base.html`**

Projects section (lines ~88–98):
- Wrap in `<details id="sidebar-projects" open>` with `<summary>` replacing the `<p>` header.
- Apply `font-semibold text-sidebar-primary-foreground` to the summary label text.
- Add a rotating chevron SVG (same pattern as `nav_projects.html`).
- The htmx-loaded `<div>` becomes the `<details>` body.

System section (lines ~103–133):
- Wrap in `<details id="sidebar-system" open>` with `<summary>` replacing the border-top+`<p>` header.
- Same bold/color/chevron treatment.
- System links `{% for %}` block becomes the body.

localStorage persistence (add to existing `<script>` block at bottom):
```js
// Restore sidebar section collapse state
(function() {
  ['sidebar-projects', 'sidebar-system'].forEach(function(id) {
    var el = document.getElementById(id);
    var key = id + '-open';
    var saved = localStorage.getItem(key);
    if (saved === 'false') el.removeAttribute('open');
    el.addEventListener('toggle', function() {
      localStorage.setItem(key, el.open ? 'true' : 'false');
    });
  });
})();
```

---

## File Manifest

| File | Action | Notes |
|------|--------|-------|
| `ai-dev/active/CR-00027/CR-00027_CR_Design.md` | Create | This document |
| `ai-dev/active/CR-00027/workflow-manifest.json` | Create | Step definitions |
| `ai-dev/active/CR-00027/prompts/CR-00027_S01_Frontend_prompt.md` | Create | frontend-impl prompt |
| `ai-dev/active/CR-00027/prompts/CR-00027_S02_CodeReview_prompt.md` | Create | code-review-impl prompt |
| `ai-dev/active/CR-00027/prompts/CR-00027_S03_CodeReviewFix_prompt.md` | Create | code-review-fix-impl prompt |
| `ai-dev/active/CR-00027/prompts/CR-00027_S04_CodeReviewFinal_prompt.md` | Create | code-review-final-impl prompt |
| `ai-dev/active/CR-00027/prompts/CR-00027_S05_CodeReviewFixFinal_prompt.md` | Create | code-review-fix-final-impl prompt |
| `ai-dev/active/CR-00027/prompts/CR-00027_S08_BrowserVerification_prompt.md` | Create | qv-browser prompt |
| `dashboard/templates/base.html` | Modify | Collapsible headers + localStorage JS |
| `dashboard/static/styles.css` | Regenerate | `make css` after template edit |

---

## Acceptance Criteria

**AC1 — Headers are visually distinct**
- Given the dashboard is loaded
- When the sidebar is visible
- Then "PROJECTS" and "SYSTEM" labels appear with `font-semibold` weight and `text-sidebar-primary-foreground` color, clearly differing from the nav items below them, and each has a chevron indicator

**AC2 — Sections start expanded**
- Given no `localStorage` value is set for the section
- When the page loads
- Then both "Projects" and "System" sections are expanded and their contents are visible

**AC3 — Sections collapse on click**
- Given a section is expanded
- When the user clicks the section header
- Then the section contents hide and the chevron rotates to indicate collapsed state

**AC4 — Sections expand on click**
- Given a section is collapsed
- When the user clicks the section header
- Then the section contents become visible and the chevron rotates back

**AC5 — State persists across page reloads**
- Given the user has collapsed the "System" section
- When the user navigates to another page or reloads the current page
- Then the "System" section remains collapsed and "Projects" section remains in its last state

**AC6 — No regressions**
- Given the sidebar changes are applied
- When navigating across project pages and system pages
- Then active link highlighting, htmx-loaded project list, worktree badge polling, and mobile hamburger toggle all work correctly; no JS console errors appear

---

## Rollback Plan

- **Database**: N/A
- **Code**: Revert the commit that modifies `base.html` and regenerate CSS with `make css`
- **Data**: No data loss — localStorage keys are client-side only; clearing them restores default (expanded) behavior

---

## Dependencies

- **Depends on**: None
- **Blocks**: None

---

## TDD Approach

This is a pure frontend change. No new unit or integration tests are required. The existing dashboard test suite (`tests/dashboard/`) does not test sidebar rendering and does not need updating. Browser verification (S07) covers the functional acceptance criteria end-to-end.

---

## Notes

- The localStorage approach is ~8 lines of vanilla JS added to the existing inline `<script>` block at the bottom of `base.html`. No new JS files, no frameworks.
- The `<details>/<summary>` pattern is already used for per-project collapse in `nav_projects.html`, so this is consistent with existing patterns.
- `make css` must be run after editing `base.html` to pick up any new Tailwind classes. The agent prompt includes this step.
