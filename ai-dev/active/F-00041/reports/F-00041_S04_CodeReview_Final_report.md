# F-00041 S04 CodeReview_Final Report

**Work Item**: F-00041 — Interactive Document IDE — Guide Editor & Diff Viewer UI
**Step**: S04
**Agent**: CodeReview_Final
**Date**: 2026-04-14
**Completion Status**: complete (with critical findings)
**Review Passed**: false

---

## Summary

Reviewed all F-00041 artifacts against the design document. The 9 htmx endpoints in `docs.py` (lines 821-1069) and 5 template fragments exist in the worktree. However, there are **two CRITICAL UX bugs** that make the IDE tab non-functional: (1) the IDE panel starts hidden and has no mechanism to become visible, and (2) the instance and section guide editors are completely absent from the IDE tab layout. Additionally, no integration tests exist for the IDE endpoints.

---

## Files Reviewed

| File | Status | Notes |
|------|--------|-------|
| `dashboard/routers/docs.py` | ✅ All 9 endpoints present | Lines 821-1069 |
| `dashboard/templates/fragments/docs_ide_tab.html` | ❌ CRITICAL: Missing editors | Only type guide loaded; no instance/section editors |
| `dashboard/templates/fragments/docs_guide_type_editor.html` | ✅ Present | Simple textarea + save |
| `dashboard/templates/fragments/docs_guide_instance_editor.html` | ✅ Present | Shows "Inheriting" when None |
| `dashboard/templates/fragments/docs_guide_sections_panel.html` | ✅ Present | Uses `extract_sections` |
| `dashboard/templates/fragments/docs_section_diff_panel.html` | ✅ Present | Version inputs + compare button |
| `dashboard/templates/docs_detail.html` | ❌ CRITICAL: No tab switch | IDE tab button missing `onclick`; `switchDocTab` doesn't handle 'ide' |
| `tests/integration/api/test_docs_ide_api.py` | ❌ NOT FOUND | No IDE integration tests exist |

---

## Findings

### CRITICAL-1 — IDE Panel Never Becomes Visible

**Location**: `docs_detail.html` lines 173-182 (tab button) and line 235 (`#ide-panel` div)

**Problem**: The `#ide-panel` div starts with `class="hidden px-4 py-6"`. The IDE tab button uses htmx to load content but does NOT call `switchDocTab('ide')`. The `switchDocTab()` JavaScript function (line 262) only handles 'markdown', 'html', 'pdf' modes — it has no case for 'ide'.

**Impact**: When a user clicks the IDE tab, content loads into `#ide-panel` via htmx, but the panel remains hidden. The user sees no response.

**Required Fix**: 
1. Add `onclick="switchDocTab('ide')"` to the IDE tab button
2. Add 'ide' case to `switchDocTab()` that un-hides `#ide-panel` and updates tab styling

---

### CRITICAL-2 — Instance and Section Guide Editors Missing from IDE Tab

**Location**: `fragments/docs_ide_tab.html`

**Problem**: The design spec says the IDE tab contains "two panels: a **Guide Editor** (type guide, instance guide, and per-section guides) and a **Section Diff Viewer**." The current `docs_ide_tab.html` only contains the type guide editor loaded via htmx on load. The instance guide editor and section guide panel are not included anywhere.

**Impact**: Users can only edit the type guide. Instance and section guide editing is completely inaccessible.

**Required Fix**: `docs_ide_tab.html` must include instance and section editors, each loaded via htmx on load.

---

### HIGH — No Integration Tests for IDE Endpoints

**Location**: `tests/integration/api/test_docs_ide_api.py` — does not exist

**Problem**: The S03 Tests report does not exist and no IDE-specific integration tests were found. The design doc (line 225) requires "Integration tests: test all 9 htmx endpoints with real DB via testcontainer."

**Required Fix**: Create `tests/integration/api/test_docs_ide_api.py` with tests for all 9 endpoints.

---

## Acceptance Criteria Checklist

| AC | Description | Status | Notes |
|----|-------------|--------|-------|
| AC1 | IDE tab loads on document detail page | ❌ FAIL | Tab button exists but panel never becomes visible (CRITICAL-1) |
| AC2 | Type guide editor shows and saves content | ✅ PASS | Endpoint works; template exists |
| AC3 | Instance guide shows "inheriting" message when no override | ✅ PASS | Template checks `instance_guide is none` |
| AC4 | Section guide panel lists sections from doc content | ⚠️ PARTIAL | Endpoint uses `extract_sections` correctly, but panel not in IDE tab |
| AC5 | Section diff panel shows changed sections | ⚠️ PARTIAL | Panel template exists but not reachable due to CRITICAL-1 |

---

## Correctness Checklist

| Item | Status | Notes |
|------|--------|-------|
| All 9 endpoints present | ✅ | Lines 821-1069 in docs.py |
| IDE tab is lazy-loaded | ❌ | htmx load exists but panel stays hidden |
| `extract_sections` used for section list | ✅ | Line 999: `from orch.doc_sections import extract_sections` |
| All endpoints use `DocService` methods | ✅ | No direct DB access in guide routes |
| Existing tabs unaffected | ✅ | No changes to other tabs |
| Instance DELETE returns 204 | ✅ | Line 973: `return Response(status_code=204)` |

---

## Subagent Result

```json
{
  "step": "S04",
  "agent": "CodeReview_Final",
  "work_item": "F-00041",
  "completion_status": "complete",
  "review_passed": false,
  "findings": [
    "CRITICAL-1: IDE panel starts hidden and has no mechanism to become visible — switchDocTab doesn't handle 'ide' mode",
    "CRITICAL-2: Instance and section guide editors are completely missing from docs_ide_tab.html — only type guide is present",
    "HIGH: No integration tests exist for any of the 9 IDE endpoints (test_docs_ide_api.py not found)"
  ],
  "mandatory_fixes": [
    "Add onclick='switchDocTab('ide')' to IDE tab button in docs_detail.html",
    "Add 'ide' case to switchDocTab() JS function to un-hide #ide-panel",
    "Add instance guide and section guide htmx-load divs to docs_ide_tab.html",
    "Create tests/integration/api/test_docs_ide_api.py with tests for all 9 endpoints"
  ],
  "notes": "The 9 endpoints are correctly implemented in docs.py and the individual template fragments exist. However, the UX integration is broken — the IDE panel is invisible when clicked and only the type guide editor is present in the IDE tab layout. The instance and section editors are entirely absent."
}
```