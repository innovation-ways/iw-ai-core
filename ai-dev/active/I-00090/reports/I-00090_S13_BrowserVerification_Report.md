# I-00090 S13 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9927`
- E2E user: `dev@example.local`
- Stack: E2E isolated stack via `COMPOSE_PROJECT_NAME=iw-ai-core-e2e-i00090`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | (inline) | No dangling DOM refs on /system/running or /project/iw-ai-core/running; no console errors at load |
| V1 | /system/running excludes inactive CRs | pass | null | evidences/post/I-00090_v1_system_running_failed_table.png | HTTP 200; Failed table empty; CR-00023/49/52/54 absent from rendered page |
| V2 | /project/iw-ai-core/running excludes inactive CRs | pass | null | evidences/post/I-00090_v2_project_running_failed_table.png | HTTP 200; Failed table empty; same four CRs absent |
| V3 | Active failing item still surfaces | n/a | null | (skipped) | Seed has no active failing items (Failed tables empty on both pages); AC2 covered by S03 unit tests |
| V4 | Recently Completed filtered | pass | null | (verified via curl) | No stale CRs found in Recently Completed section on /system/running |
| V5 | No regressions | pass | null | evidences/post/I-00090_v5_no_regressions.png | Running Now table header unchanged; sidebar links intact |

## Console / Network Errors
None observed on any page visited during V1..V5.

## No Regressions
- **Running Now table**: header row (`Project | Item | Step / Agent | PID | Duration | Last seen | Action`) still present with correct columnheaders. Content is "No steps running right now." — unchanged structure.
- **Per-project sidebar**: `/project/iw-ai-core/running` navigation shows all expected links (Dashboard, Batches, Queue, Jobs, Auto-Merge, History, Tests, Quality, Docs, Research, Code) alongside the System sidebar group (Running Tasks, Worktree Health, Container Health, System Status, Test Coverage, Keep-Alive, All Active Work, Configuration).
- **No new console errors** on any page visited during V1..V4.

## Screenshots captured
- `ai-dev/active/I-00090/evidences/post/I-00090_v1_system_running_failed_table.png`
- `ai-dev/active/I-00090/evidences/post/I-00090_v2_project_running_failed_table.png`
- `ai-dev/active/I-00090/evidences/post/I-00090_v5_no_regressions.png`

## Root cause (on failure only)
N/A — all verifications passed or were legitimately n/a.