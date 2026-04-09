# CR001 — Add Favicon to IW AI Core Dashboard

## Metadata

| Field | Value |
|-------|-------|
| **ID** | CR001 |
| **Type** | ChangeRequest |
| **Priority** | Low |
| **Status** | Draft |
| **Created** | 2026-04-08 |
| **Author** | Claude Code |

## Description

### Current Behavior

The IW AI Core dashboard (FastAPI + Jinja2 on port 9900) does not include a favicon. Browsers display a generic blank icon in tabs and bookmarks, and the browser makes a fruitless `GET /favicon.ico` request on every page load.

### Desired Behavior

Add an SVG favicon featuring a circuit/brain motif styled with the dashboard's primary brand color (`#5865f2` indigo). The icon should:

- Be an inline SVG file at `dashboard/static/favicon.svg`
- Depict a stylized brain with circuit-board traces/nodes — representing AI orchestration
- Use the primary color `#5865f2` as the dominant color
- Work well at small sizes (16x16, 32x32) and in both light and dark browser chrome
- Be referenced via `<link rel="icon">` in `dashboard/templates/base.html`

## Reason for Change

Branding polish. The dashboard is the primary human interface for the platform; a recognizable favicon improves the user experience when multiple tabs are open and in bookmarks.

## Impact Assessment

- **Breaking changes**: None
- **Data migration**: Not required
- **API changes**: None
- **Database changes**: None
- **Affected layers**: Frontend (dashboard static assets + base template)

### Files Changed

| File | Change |
|------|--------|
| `dashboard/static/favicon.svg` | **New** — SVG favicon asset |
| `dashboard/templates/base.html` | **Modified** — Add `<link rel="icon">` in `<head>` |

### Files NOT Changed

- No backend, CLI, daemon, or database changes
- No Python code changes beyond possibly a test

## Change Plan

| Step | Agent | Description |
|------|-------|-------------|
| S01 | Frontend | Create `dashboard/static/favicon.svg` with circuit/brain motif in brand colors; add `<link rel="icon">` to `base.html` `<head>` |
| S02 | Tests | Add test verifying `/static/favicon.svg` returns 200 and `base.html` contains favicon link |
| S03 | CodeReview | Per-agent code review of S01-S02 |
| S04 | CodeReview_Final | Final cross-agent review |
| S05 | QualityValidation | Lint, type check, and test gates |

## Design Details

### Favicon SVG Requirements

The SVG should be a compact, single-file icon (no external dependencies):

- **Viewbox**: `0 0 32 32` (standard favicon size)
- **Motif**: Abstract brain outline with circuit traces — nodes (small circles) connected by straight/angled lines, forming a brain-like silhouette
- **Colors**: Primary `#5865f2` for the main paths/nodes; lighter tint for fills or secondary elements
- **Style**: Clean, geometric, modern — matches the dashboard's minimal aesthetic
- **Dark mode**: The icon should be visible against both light and dark tab bars (use the indigo color which has good contrast on both)

### Template Integration

In `dashboard/templates/base.html`, add inside `<head>` (after the `<meta>` tags, before font links):

```html
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
```

SVG favicons are supported in all modern browsers and allow crisp rendering at any size.

## Rollback Plan

1. Remove `dashboard/static/favicon.svg`
2. Remove the `<link rel="icon">` line from `base.html`
3. No data or schema changes to revert

## Acceptance Criteria

### AC1: Favicon file exists and is served

```
Given the dashboard is running
When a browser requests GET /static/favicon.svg
Then the response status is 200 with content type image/svg+xml
And the body contains valid SVG markup using brand color #5865f2
```

### AC2: Base template references the favicon

```
Given the base template is rendered
When any dashboard page is loaded
Then the HTML <head> contains <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
```

## Test Strategy

- **Integration test**: HTTP GET `/static/favicon.svg` returns 200 with `image/svg+xml` content type
- **Template test**: Render `base.html` and assert it contains `<link rel="icon"` pointing to the favicon
- **Quality gates**: `ruff check`, `ruff format --check`, `mypy` must all pass

## TDD Approach

- Unit tests: Verify favicon static file is served correctly (200, correct content type, valid SVG)
- Integration tests: Verify base template includes favicon `<link>` tag
- Updated tests: None — no existing tests affected

## Dependencies

- **Depends on**: None
- **Blocks**: None

## File Manifest

All files for this work item live under `ai-dev/design/active/CR001/`:

| File | Type | Purpose |
|------|------|---------|
| `CR001_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR001_S01_Frontend_prompt.md` | Prompt | S01 — create favicon and wire into template |
| `prompts/CR001_S02_Tests_prompt.md` | Prompt | S02 — add test coverage |
| `prompts/CR001_S03_CodeReview_prompt.md` | Prompt | S03 — per-agent code review |
| `prompts/CR001_S04_CodeReview_Final_prompt.md` | Prompt | S04 — final cross-agent review |

Reports are created during execution in `ai-dev/work/CR001/reports/`.

## Notes

- SVG favicons are supported by all modern browsers (Chrome 80+, Firefox 41+, Safari 12+, Edge 80+)
- No PNG/ICO fallback is needed for this internal dashboard
