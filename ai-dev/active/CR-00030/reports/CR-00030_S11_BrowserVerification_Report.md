# CR-00030 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9951`
- **E2E user:** `dev@example.local` (no auth required for the visited routes)
- **Dashboard container:** `iw-ai-core-e2e-cr00030-e2e-dashboard-1`
- **Cache injection method:** `docker exec ... > /app/.claude/rate-limits-cache.json` (host `~/.claude/` is off-limits)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Claude 5h label in 'Xh Ym' form | **pass** | `evidences/post/CR-00030_v1_5h_remaining.png` | Label rendered as `4h 31m` (matches `^\d+h \d+m$`, no colon). Bar at `8%`. |
| V2 | Claude 7d label unchanged (wall-clock) | **pass** | `evidences/post/CR-00030_v2_7d_unchanged.png` | Label rendered as `Thu 21:14` (matches `^[A-Z][a-z]{2} \d{2}:\d{2}$`, contains a colon). Bar at `15%`. |
| V3 | Sub-hour 5h label uses minutes only | **pass** | `evidences/post/CR-00030_v3_5h_minutes_only.png` | Label rendered as `24m` (matches `^\d+m$`, no `h ` component). Bar at `42%`. Cache written with `resets_at = now + 25m`; the 1m drift is the elapsed time between write and render. |
| V4 | Missing cache → '5h' placeholder | **pass** | `evidences/post/CR-00030_v4_5h_placeholder.png` | After `docker exec ... rm -f /app/.claude/rate-limits-cache.json` the label reverts to `5h` / `0%`. |
| V5 | No regressions (console, MiniMax, adjacent pages) | **pass** | `evidences/post/CR-00030_v5_no_regressions.png` | `playwright-cli console` reported `0 errors / 0 warnings` on `/`, `/system/status`, and `/project/iw-ai-core/`. MiniMax row continues to render (`5h` / `0%` placeholder — no API key configured in container). |

## Console / Network Errors
- `/` — 0 messages (verified via `playwright-cli console`).
- `/system/status` — 0 messages.
- `/project/iw-ai-core/` — 0 messages.
- `GET /api/usage/llm/fragment` — `200 OK`, valid HTML, no `TypeError` / `TemplateSyntaxError` / 5xx observed across V1..V4.

## No Regressions
- **MiniMax row**: continues to display `5h` / `0%` (placeholder, expected — container has no MiniMax API key).
- **Adjacent pages**: `/system/status` and `/project/iw-ai-core/` both load cleanly with no console errors.
- **API endpoint**: `/api/usage/llm/fragment` returns 200 with the expected fragment shape on every transition (V1 → V2 → V3 → V4).

## Screenshots captured
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v1_5h_remaining.png` — V1: `4h 31m` / 8% / `Thu 21:14` / 15%
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v2_7d_unchanged.png` — V2: same shot (V1 + V2 share the same render)
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v3_5h_minutes_only.png` — V3: `24m` / 42%
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v4_5h_placeholder.png` — V4: `5h` / 0% fallback
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v5_no_regressions.png` — V5: project page, no console errors

## Environment changes that unblocked V1/V2/V3

The previous three runs failed because the e2e compose was attempting to bind-mount the developer's host `~/.claude/` into the dashboard container. Two distinct problems followed from that:

1. The mount was `:ro`, so the qv-browser agent could never inject the controlled cache content V1/V2/V3 require.
2. To make `Path.home()` resolve through that mount, the compose forced `HOME=/home/sergiog` inside the container, which then made `uv` try to create its cache at `/home/sergiog/.cache/uv` — a path with no writable parent inside the container — and the dashboard exited before the healthcheck.

The host's `/home/sergiog/.claude/` is owned by the developer's running Claude Code session and is **off-limits** to test infrastructure. Fix:

- `docker-compose.e2e.yml`: removed the `/home/sergiog/.claude:/home/sergiog/.claude:ro` bind-mount and the `HOME` / `CLAUDE_CACHE_DIR` / `UV_CACHE_DIR` overrides; restored the container's default `HOME=/app`. Added a comment forbidding host `~/.claude/` mounts so this regression doesn't reappear in another item.
- `scripts/e2e_dashboard_entrypoint.sh`: `mkdir -p /app/.claude` so the cache directory always exists in the container's writable layer.
- `ai-dev/active/CR-00030/prompts/CR-00030_S11_BrowserVerification_prompt.md`: rewrote V1/V2/V3 to inject the cache via `docker exec` against the dashboard container, never touching host `~/.claude/`.

The S11 step was killed and `step-restart`ed before this clean run.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00030",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9951",
  "verifications": [
    {"id": "V1", "name": "Claude 5h label in 'Xh Ym' form", "status": "pass", "screenshot": "evidences/post/CR-00030_v1_5h_remaining.png", "notes": "Rendered as '4h 31m' / 8%."},
    {"id": "V2", "name": "Claude 7d label unchanged (wall-clock)", "status": "pass", "screenshot": "evidences/post/CR-00030_v2_7d_unchanged.png", "notes": "Rendered as 'Thu 21:14' / 15%."},
    {"id": "V3", "name": "Sub-hour 5h label minutes-only", "status": "pass", "screenshot": "evidences/post/CR-00030_v3_5h_minutes_only.png", "notes": "Rendered as '24m' / 42%, no 'h ' component."},
    {"id": "V4", "name": "Missing cache -> '5h' placeholder", "status": "pass", "screenshot": "evidences/post/CR-00030_v4_5h_placeholder.png", "notes": "Removed cache file via docker exec; label reverted to '5h' / 0%."},
    {"id": "V5", "name": "No regressions (console, MiniMax, adjacent pages)", "status": "pass", "screenshot": "evidences/post/CR-00030_v5_no_regressions.png", "notes": "Zero console errors on home / system status / project page; MiniMax row unaffected."}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v1_5h_remaining.png",
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v2_7d_unchanged.png",
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v3_5h_minutes_only.png",
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v4_5h_placeholder.png",
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v5_no_regressions.png"
  ],
  "notes": "All five verifications pass after fixing the e2e compose to no longer touch host ~/.claude/ and updating the prompt to inject cache via docker exec."
}
```
