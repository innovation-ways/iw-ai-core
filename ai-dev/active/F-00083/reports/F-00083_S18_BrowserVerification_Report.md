# F-00083 S18 Browser Verification Report

## Pre-flight: OpenCode Runtime Availability

**Result: FAIL — SPEC_MISMATCH**

The `/api/chat/config` endpoint returned HTTP 503 with `{"error": "OpenCode runtime unavailable"}`. The OpenCode binary is not available in this worktree's E2E stack configuration. All V(n) verifications depend on a healthy OpenCode runtime and would provide no actionable signal if run against a missing runtime.

**Recommendation:** The worktree-compose configuration must include the OpenCode binary in the `app` service (or a dedicated sidecar) so that `opencode serve` is reachable at runtime. Without this, the Dashboard AI Assistant feature cannot function.

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight runtime check | fail | spec_mismatch | N/A | OpenCode runtime unavailable (HTTP 503) |
| V1–V10 | N/A | n/a | null | N/A | Skipped — runtime prerequisite not met |

## Root Cause

The E2E stack was provisioned without the OpenCode binary in the container image. The `/api/chat/config` endpoint at `orch/chat/config.py` calls `opencode serve` internally and returns 503 when the binary is not found.

**Relevant code:** `orch/chat/config.py` — the route that returns 503 when OpenCode is unavailable.

## Console / Network Errors

- HTTP 503 at `http://localhost:9921/api/chat/config` — "OpenCode runtime unavailable"

## Screenshots Captured

No screenshots captured — pre-flight check failed and V(n) steps were not executed per the spec.

## Report Conclusion

**Result: spec_mismatch**

The worktree's E2E stack is missing the OpenCode binary. The feature cannot be browser-verified without it. This is a configuration issue (worktree-compose is missing the binary), not a code defect in the implemented feature.

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "F-00083",
  "overall_status": "spec_mismatch",
  "overall_failure_class": "spec_mismatch",
  "base_url_used": "http://localhost:9921",
  "verifications": [
    {"id": "V0", "name": "Pre-flight OpenCode runtime", "status": "fail", "failure_class": "spec_mismatch", "screenshot": "", "notes": "HTTP 503 OpenCode runtime unavailable"},
    {"id": "V1", "name": "Ctrl+/ toggles panel", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V2", "name": "Prompt stream approval abort", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V3", "name": "Per-tab independent sessions", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V4", "name": "Model selector", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V5", "name": "Skills tray / autocomplete", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V6", "name": "Tab-refresh reconnect", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V7", "name": "Research view deep-link", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V8", "name": "Currently viewing chip", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V9", "name": "Context % indicator", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V10", "name": "Regression guard Code Q&A chat", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"},
    {"id": "V_no_regressions", "name": "No regressions", "status": "n/a", "failure_class": null, "screenshot": "", "notes": "Skipped — runtime prerequisite not met"}
  ],
  "console_errors_observed": ["HTTP 503 /api/chat/config — OpenCode runtime unavailable"],
  "screenshots": [],
  "notes": "OpenCode runtime unavailable in E2E stack. Worktree-compose needs OpenCode binary. All V(n) checks skipped — would provide no signal against missing runtime."
}
```