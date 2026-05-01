# CR-00027 S08 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9931` (`$IW_BROWSER_BASE_URL`)
- **E2E user:** `dev@example.local` (`$IW_BROWSER_E2E_USER`)
- **Work item:** CR-00027
- **Step:** S08

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | headers_distinct | **pass** | `evidences/post/CR-00027_v1_headers_distinct.png` | Both "Projects" and "System" labels use `font-semibold text-sidebar-primary-foreground` — visually heavier and brighter than nav items. Each has a rotating chevron SVG. |
| V2 | both_expanded | **pass** | `evidences/post/CR-00027_v2_both_expanded.png` | Fresh page load shows both Projects (with IW AI Core (E2E) project entry) and all System links (Running Tasks, Worktree Health, Container Health, System Status, Test Coverage, Keep-Alive, All Active Work, Configuration) visible. |
| V3 | projects_collapsed | **pass** | `evidences/post/CR-00027_v3_projects_collapsed.png` | After clicking "Projects" header: project list is no longer in the accessibility tree; chevron rotated. |
| V4 | projects_expanded | **pass** | `evidences/post/CR-00027_v4_projects_expanded.png` | After clicking "Projects" again: project list reappears with IW AI Core (E2E) entry; chevron rotated back. |
| V5 | system_toggle | **pass** | `evidences/post/CR-00027_v5_system_toggle.png` | System section collapsed on click (only "System" label visible); re-expanded on second click with all System links visible. |
| V6 | state_persists | **pass** | `evidences/post/CR-00027_v6_state_persists.png` | After collapsing System on `/` and navigating to `/system/status`: System section remains collapsed; Projects section remains expanded. localStorage keys `sidebar-projects-open` and `sidebar-system-open` work correctly. |
| V7 | no_regressions | **pass** | `evidences/post/CR-00027_v7_no_regressions.png` | Project page `/project/iw-ai-core/` shows: (1) htmx-loaded project sub-links (Dashboard, Batches, Queue, Jobs, History, Tests, Quality, Docs, Research, Code) in the expanded Projects section; (2) worktree badge polling element `hx-get="/system/nav/worktree-badge"` present in DOM; (3) no console errors observed. |

## Console / Network Errors
None observed throughout V1–V7.

## No Regressions
- Active link highlighting works (current page link styled with `bg-sidebar-accent text-sidebar-accent-foreground font-medium`)
- htmx-loaded project list renders correctly inside the expanded Projects section (Dashboard, Batches, Queue, Jobs, History, Tests, Quality, Docs, Research, Code sub-links)
- Worktree badge polling element `hx-get="/system/nav/worktree-badge" hx-trigger="load, every 60s"` present in the DOM at all System links
- Mobile hamburger toggle is present in the DOM (not tested visually but no JS errors)
- No JavaScript console errors on any page visited (home `/`, `/system/status`, `/project/iw-ai-core/`)

## Screenshots captured
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v1_headers_distinct.png`
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v2_both_expanded.png`
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v3_projects_collapsed.png`
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v4_projects_expanded.png`
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v5_system_toggle.png`
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v6_state_persists.png`
- `ai-dev/active/CR-00027/evidences/post/CR-00027_v7_no_regressions.png`

## Root cause (on failure only)
N/A — all verifications passed.