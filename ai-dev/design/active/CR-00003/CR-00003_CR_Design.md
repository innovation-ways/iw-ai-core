# CR-00003: Replace Sidebar "IW" Text Logo with Favicon SVG Image

**Type**: Change Request
**Priority**: Low
**Reason**: Visual inconsistency — the sidebar shows a generic "IW" text badge while the browser favicon displays a distinctive circuit-brain SVG mark. This change aligns both to the same brand asset.
**Created**: 2026-04-09
**Status**: Draft

---

## Description

The dashboard sidebar currently shows a blue rounded box with the text "IW" as the brand logo. The browser tab uses a circuit-brain SVG (`dashboard/static/favicon.svg`). This CR replaces the text badge with a PNG export of the favicon SVG, displayed at the same size with a transparent background.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Current Behavior

`dashboard/templates/base.html` line 95 renders:

```html
<div class="w-7 h-7 rounded bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm">IW</div>
```

This produces a 28×28px blue rounded square with white "IW" text — completely unrelated to the favicon artwork.

## Desired Behavior

The same line is replaced with:

```html
<img src="/static/logo.png" alt="IW AI Core" class="w-7 h-7">
```

A new `dashboard/static/logo.png` (56×56px, transparent background, 2× retina) is generated from the existing `favicon.svg` using ImageMagick. The blue container `<div>` is removed entirely.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/templates/base.html:95` | `<div>` with blue bg + "IW" text | `<img>` pointing to `logo.png` |
| `dashboard/static/logo.png` | Does not exist | New PNG generated from `favicon.svg` |

### Breaking Changes

- None

### Data Migration

- None

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Generate `logo.png`; update `base.html` sidebar logo | — |
| S02 | frontend-review | Visual correctness, HTML validity, accessibility | — |
| S03 | code-review-final-impl | Global cross-layer review | — |
| S04 | code-review-fix-final-impl | Apply final fixes | — |
| S05 | quality-validation-impl | QV gates (lint, format, typecheck, unit-tests, integration-tests) | — |

### Database Changes

- None

### API Changes

- None

### Frontend Changes

- **New static asset**: `dashboard/static/logo.png`
- **Modified template**: `dashboard/templates/base.html` — sidebar logo element (line 95)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00003_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00003_S01_Frontend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00003_S02_FrontendReview_prompt.md` | Prompt | S02 review instructions |
| `prompts/CR-00003_S03_CodeReview_Final_prompt.md` | Prompt | S03 global review |
| `prompts/CR-00003_S04_CodeReview_Fix_Final_prompt.md` | Prompt | S04 fix instructions |
| `prompts/CR-00003_S05_QualityValidation_prompt.md` | Prompt | S05 QV gates |

## Acceptance Criteria

### AC1: Logo PNG exists and is transparent

```
Given the implementation is complete
When inspecting dashboard/static/logo.png
Then it is a 56×56px PNG with an alpha channel (TrueColorAlpha)
And the background is fully transparent
```

### AC2: Sidebar shows circuit-brain logo

```
Given the dashboard is running
When navigating to http://localhost:9900
Then the top-left corner of the sidebar shows the circuit-brain SVG artwork
And no blue background box is visible
And the logo is the same size as the previous "IW" box (≈28px)
```

### AC3: No regressions

```
Given the change is applied
When running make test-unit && make test-integration
Then all tests pass
```

## Rollback Plan

- **Code**: Revert `base.html` line 95 to the original `<div>IW</div>` element; delete `dashboard/static/logo.png`
- **Database**: Not applicable
- **Data**: Not applicable

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- No new unit/integration tests needed — this is a purely cosmetic template change
- Existing tests must continue to pass (QV gate confirms this)
- Browser verification (screenshot) confirms visual correctness

## Notes

- `favicon.svg` already has a transparent background (no `<rect>` fill) — the PNG export inherits this
- ImageMagick `convert` is available at `/usr/bin/convert` and supports SVG→PNG with transparency
- Command: `convert -background transparent -size 56x56 dashboard/static/favicon.svg dashboard/static/logo.png`
- The `<img>` tag uses `class="w-7 h-7"` (28×28px display) matching the removed `<div>` size
- The surrounding `<a>` tag and `<span>IW AI Core</span>` remain unchanged
