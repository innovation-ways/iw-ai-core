# CR-00068: AI Assistant — Remove Per-Tab Model Bar

**Type**: Change Request
**Priority**: Medium
**Reason**: Tech debt / UX cleanup — the per-tab model bar duplicates the model selector already available in the settings panel, adding visual clutter above the message area.
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR adds no Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** migrations — it is a frontend-only change.

## Description

The AI Assistant panel renders a per-tab model bar (`#chat-assistant-tab-model-bar`) — a clickable model badge with a drop-down model picker — directly above the message area. This CR removes that bar entirely. Model selection remains fully available through the hamburger/settings button, which opens the settings panel containing a Model `<select>`. The small model badge shown on each tab-strip button is kept.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the AI Assistant lives in `dashboard/templates/chat_assistant/` (Jinja2 includes) and `dashboard/static/chat_assistant/` (`chat.js`, `chat.css`). The model bar markup is in `chat_assistant/panel.html`; its behaviour is in `chat_assistant/chat.js`.

## Current Behavior

The AI Assistant panel exposes **three** model surfaces:

1. **The per-tab model bar** — `#chat-assistant-tab-model-bar` (`panel.html` lines ~80–103): a bar above the messages area holding `#chat-assistant-tab-model-badge` (the clickable badge showing the current model) and `#chat-assistant-tab-model-dropdown` (the model picker list). `panel.html` line ~10 also lists `#chat-assistant-tab-model-bar` in the collapsed-state `<style>` block that hides panel chrome when the panel is collapsed.
2. **The tab-strip badge** — a small `.chat-assistant-tab-model-badge` element on each tab button showing that tab's model at a glance.
3. **The settings panel** — opened by the hamburger/settings button (`#chat-assistant-settings-btn`); contains a Model `<select>` (`#chat-assistant-settings-model`) that PATCHes the tab's model.

The model bar is driven by these `chat.js` functions: `_updateTabModelBar()`, `_hideTabModelBar()`, `_populateTabModelDropdown()`, and `_selectTabModel()`. It is wired up by a model-badge click listener and a document-level outside-click handler that closes the dropdown, and is refreshed from six call sites (`_updateTabModelBar` / `_hideTabModelBar` / `_populateTabModelDropdown`).

This means the model is selectable from two interactive controls (the bar and the settings panel), which is redundant and clutters the panel.

## Desired Behavior

- The per-tab model bar (`#chat-assistant-tab-model-bar` and everything inside it — the badge and the dropdown) is removed from `panel.html`, and the `#chat-assistant-tab-model-bar` selector is removed from the collapsed-state `<style>` block.
- All `chat.js` code that exists solely to drive the model bar is removed: the functions `_updateTabModelBar`, `_hideTabModelBar`, `_populateTabModelDropdown`, `_selectTabModel`; their call sites; the model-badge click listener; and the model-dropdown branch of the outside-click handler.
- The tab-strip model badge (`.chat-assistant-tab-model-badge` rendered on each tab button) is **kept** and continues to display each tab's model.
- Model selection through the settings panel continues to work unchanged.
- No JavaScript errors and no dead references remain (no `getElementById` lookups for removed ids that are then dereferenced unsafely).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `chat_assistant/panel.html` | Contains `#chat-assistant-tab-model-bar` block + a collapsed-state selector for it | Bar block removed; selector removed from `<style>` block |
| `chat_assistant/chat.js` | Has `_updateTabModelBar` / `_hideTabModelBar` / `_populateTabModelDropdown` / `_selectTabModel`, their call sites, and two event listeners | All model-bar-only code removed; `_availableModels` (used only by the dropdown) removed |
| `chat_assistant/chat.css` | `.chat-assistant-tab-model-badge` rules style the tab-strip badges | **No change** — those rules style the kept tab-strip badge, not the bar; the bar used inline Tailwind classes only |

### Breaking Changes

- None. Model selection remains available via the settings panel. No API contract, DB schema, or behaviour outside the AI Assistant panel changes.

### Data Migration

- None. No schema or data changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Remove the bar from `panel.html`; remove dead bar JS from `chat.js`; add a `tests/dashboard/` regression test | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | code-review-fix-impl | Fix CRITICAL/HIGH/MEDIUM_FIXABLE findings | — |
| S04 | code-review-final-impl | Cross-agent final review | — |
| S05 | code-review-fix-final-impl | Fix final review findings | — |
| S06 | qv-gate | `make test-integration` | — |
| S07 | qv-browser | Browser verification — bar gone, settings model picker still works, tab badges intact | — |
| S08 | self-assess-impl | Post-execution self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None — the `PATCH /api/chat/tabs/{id}` model-update path used by the settings panel is unchanged
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `chat_assistant/panel.html`, `chat_assistant/chat.js`
- **Removed components**: `#chat-assistant-tab-model-bar` (bar, badge, dropdown) and its supporting JavaScript

## File Manifest

All files for this work item live under `ai-dev/active/CR-00068/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00068_CR_Design.md` | Design | This document |
| `CR-00068_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00068_S01_Frontend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00068_S02_CodeReview_prompt.md` | Prompt | S02 code review instructions |
| `prompts/CR-00068_S03_CodeReviewFix_prompt.md` | Prompt | S03 review-fix instructions |
| `prompts/CR-00068_S04_CodeReviewFinal_prompt.md` | Prompt | S04 final review instructions |
| `prompts/CR-00068_S05_CodeReviewFixFinal_prompt.md` | Prompt | S05 final review-fix instructions |
| `prompts/CR-00068_S07_BrowserVerification_prompt.md` | Prompt | S07 browser verification instructions |
| `prompts/CR-00068_S08_SelfAssess_prompt.md` | Prompt | S08 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00068/reports/`.

## Acceptance Criteria

### AC1: Model bar is gone

```
Given the AI Assistant panel is open with an active chat tab
When the panel renders
Then no model bar (#chat-assistant-tab-model-bar), model badge (#chat-assistant-tab-model-badge in the bar), or model dropdown (#chat-assistant-tab-model-dropdown) appears above the messages area
```

### AC2: Model is still changeable via the settings panel

```
Given the AI Assistant panel is open with an active chat tab
When the user clicks the hamburger/settings button and changes the Model select, then saves
Then the tab's model is updated and the new model is reflected on the tab-strip badge
```

### AC3: Tab-strip model badge is kept

```
Given the AI Assistant panel is open with one or more chat tabs
When the tab strip renders
Then each tab button still shows its small model badge
```

### AC4: No JavaScript errors or dead references

```
Given the AI Assistant panel is opened, tabs are switched, and the settings panel is used
When these interactions occur
Then the browser console reports no errors and no removed-element references break behaviour
```

## Rollback Plan

- **Database**: Not applicable — no schema changes.
- **Code**: Revert the squash-merge commit for CR-00068. `panel.html` and `chat.js` return to their prior state, restoring the model bar.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/chat_assistant/panel.html`
- `dashboard/static/chat_assistant/chat.js`
- `dashboard/static/chat_assistant/chat.css`
- `tests/dashboard/**`

## TDD Approach

- Unit tests: None required — pure presentation removal with no Python logic.
- Integration tests: None required — no API or backend change.
- Dashboard tests: S01 adds `tests/dashboard/test_cr00068_model_bar_removed.py` — a fast, no-database test asserting `chat_assistant/panel.html` and `chat.js` no longer reference `#chat-assistant-tab-model-bar` (and that the kept tab-strip `.chat-assistant-tab-model-badge` class is untouched). A design-time grep found no existing dashboard test asserting on the bar's presence; if S01 finds one, it updates it. The new test runs in the S06 `make test-integration` QV gate.
- Browser verification (S07): confirms the bar is gone, the settings-panel model picker still updates the model, and tab-strip badges remain.

## Notes

- `chat.css` is expected to be **untouched**: the model bar used inline Tailwind utility classes, and the `.chat-assistant-tab-model-badge` rules style the *tab-strip* badges that are being kept. The implementer must NOT remove `.chat-assistant-tab-model-badge` or `.chat-assistant-tab-btn-active .chat-assistant-tab-model-badge`.
- `_defaultModel` and `_refreshModels` / `_scheduleModelRefresh` must be **kept** — `_instantCreateTab` uses `_defaultModel` to pick a new tab's default model. Only `_availableModels` (used solely by the removed dropdown) becomes dead and should be removed, along with the `_availableModels` assignment/reset inside `_refreshModels` and `_scheduleModelRefresh`.
- The implementer must grep the final `chat.js` for every removed id (`chat-assistant-tab-model-bar`, `chat-assistant-tab-model-badge` *as used by the bar*, `chat-assistant-tab-model-dropdown`, `chat-assistant-tab-model-label`) and every removed function name to confirm zero dangling references. Note `chat-assistant-tab-model-badge` as a **CSS class** is still used by the tab strip — only the bar's element id usage is removed.
- The **create-tab modal** has its own, separate model picker driven by `_populateCreateTabModelDropdown` / `_fetchModelsForModal` / `_modalModels` / `_modalDefaultModel`. This subsystem is unrelated to the per-tab model *bar* and must NOT be touched. Beware the near-identical name: `_populateCreateTabModelDropdown` (kept) vs `_populateTabModelDropdown` (removed) — only the latter is deleted.
