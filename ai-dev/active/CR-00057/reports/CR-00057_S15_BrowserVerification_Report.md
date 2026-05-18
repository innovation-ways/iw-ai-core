# CR-00057 S15 Browser Verification Report

## Environment
- Base URL used: http://localhost:9936
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/CR-00057_v0_preflight_sanity.png | Curl fragment-ref/id sweep passed on `/project/iw-ai-core/`, `/system/status`, `/project/iw-ai-core/code`, `/project/iw-ai-core/docs`, `/project/iw-ai-core/jobs`; no Playwright console log files were emitted. |
| V1 | Curated 5-model allowlist on iw-ai-core | pass | null | evidences/post/CR-00057_v1_dropdown_filtered.png | Dropdown shows exactly 5 options in expected order; `anthropic/claude-opus-4-7` selected. |
| V2 | /api/chat/config returns curated list | pass | null | evidences/post/CR-00057_v2_api_response.png | JSON `models` and `default_model` match expected curated list/order; also saved raw JSON evidence file `CR-00057_v2_api_response.json`. Response includes extra key `project_directory`, non-blocking. |
| V3 | Fail-open on system page | pass | null | evidences/post/CR-00057_v3_fail_open_system_page.png | System page model selector shows unfiltered list (>5 models), confirming fail-open behavior. |
| V4 | Project switch refreshes dropdown | n/a | null | evidences/post/CR-00057_v4_project_switch.png | ENV_DATA_MISSING: only `iw-ai-core` project appears in seeded UI project switcher, so no second project target with deterministic allowlist/no-allowlist state was available for in-app switch verification. |
| V5 | Prompt round-trip with default model | pass | null | evidences/post/CR-00057_v5_prompt_roundtrip.png | Sent `hello`; assistant response rendered (`ok — running ls`) with no error event. |
| V6 | No regressions across project tabs | pass | null | evidences/post/CR-00057_v6_no_regressions.png | Code/Docs/Jobs pages loaded and snapshots succeeded; chat panel remained mounted/expandable; no console log errors observed. |

## Console / Network Errors
None observed (no `.playwright-cli/console-*.log` files emitted during this run).

## No Regressions
Visited and validated:
- `/project/iw-ai-core/code`
- `/project/iw-ai-core/docs`
- `/project/iw-ai-core/jobs`

All loaded without visible JS/HTMX failures; AI Assistant panel stayed present and functional.

## Screenshots captured
- ai-dev/active/CR-00057/evidences/post/CR-00057_v0_preflight_sanity.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v1_dropdown_filtered.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v2_api_response.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v3_fail_open_system_page.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v4_project_switch.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v5_prompt_roundtrip.png
- ai-dev/active/CR-00057/evidences/post/CR-00057_v6_no_regressions.png

## Additional evidence
- ai-dev/active/CR-00057/evidences/post/CR-00057_v2_api_response.json
