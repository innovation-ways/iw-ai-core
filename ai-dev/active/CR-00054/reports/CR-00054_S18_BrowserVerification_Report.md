# CR-00054 S18 Browser Verification Report

## Environment
- Base URL used: http://localhost:9955
- E2E user: dev@example.local
- Auth wall: Not present (dashboard loaded directly)

## Pre-flight result (OpenCode stub reachability)
- `/api/chat/config` returned HTTP 200 JSON with non-empty `models` array.
- Stub reachability check: **PASS**.

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/CR-00054_v1_config_endpoint.png | Checked dangling DOM refs on `/` and `/api/chat/config`: none. Load-time console errors: none. |
| V1 | /api/chat/config returns populated models | pass | null | evidences/post/CR-00054_v1_config_endpoint.png | HTTP 200, `application/json`, keys `models` + `default_model`, first model has `id` + `name`, `default_model` matched `models[*].id`. |
| V2 | Ctrl+/ opens chat panel | pass | null | evidences/post/CR-00054_v2_panel_open.png | Panel expanded and composer present after shortcut; no console errors observed. |
| V3 | Prompt → stream → permission.asked → allow | pass | null | evidences/post/CR-00054_v3_permission_modal.png; evidences/post/CR-00054_v3_after_allow.png | Streaming text appeared, permission modal rendered, Allow closed modal, follow-up update + `Session idle.` appeared. |
| V4 | Deny path | pass | null | evidences/post/CR-00054_v4_deny.png | Permission modal rendered and Deny closed modal; run returned to `Session idle.` state. |
| V5 | Healthcheck reports healthy | pass | null |  | `docker inspect iw-ai-core-e2e-cr00054-e2e-dashboard-1 --format '{{.State.Health.Status}}'` => `healthy`. |
| V_no_regressions | Adjacent flows unchanged | pass | null | evidences/post/CR-00054_vN_no_regressions.png | Verified pages (Projects, Queue, History, Batches, Tests, Quality, Jobs, Worktrees, Docs, Research) loaded without console errors; Code chat panel behavior and theme toggle remained functional. |

## Console / Network Errors
None observed (all collected console logs reported `Errors: 0`).

## No Regressions
- Navigated and loaded:
  - `/`
  - `/project/iw-ai-core/queue`
  - `/project/iw-ai-core/history`
  - `/project/iw-ai-core/batches`
  - `/project/iw-ai-core/tests`
  - `/project/iw-ai-core/quality`
  - `/project/iw-ai-core/jobs`
  - `/system/worktrees`
  - `/docs`
  - `/project/iw-ai-core/research`
- On `/project/iw-ai-core/code`, shortcut behavior remained functional and did not break chat panels.
- Theme toggle remained operational.

## Screenshots captured
- ai-dev/active/CR-00054/evidences/post/CR-00054_v1_config_endpoint.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v2_panel_open.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v3_permission_modal.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v3_after_allow.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v4_deny.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_vN_no_regressions.png
