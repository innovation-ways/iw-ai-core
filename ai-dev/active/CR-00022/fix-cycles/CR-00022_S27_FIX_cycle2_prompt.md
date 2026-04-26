# CR-00022 S27 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S27 of work item CR-00022 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# Browser Verification Report — CR-00022-S27

**Step**: S27  
**Agent**: qv-browser  
**Work Item**: CR-00022  
**Overall Status**: FAIL  
**Base URL Used**: `http://localhost:9919`

---

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Table layout + filters | **pass** | `CR-00022_v1_table_layout.png` | Table renders with Group/Test/Type/Status/Details columns, domain group headers, `…` buttons. Filter chips visible. |
| V2 | Modal renders rich per-test copy | **fail** | `CR-00022_v2_modal_open.png` | Modal opens (aria-hidden removed) but all content sections show placeholder text because `window.OSS_CATALOG` is never populated — catalog not injected into page context. |
| V3 | Apply writes to working tree only — no branch change + idempotent | **fail** | — | Cannot verify — git unavailable in e2e-dashboard container (no git binary). Modal cannot be interacted with to test Apply (V2 blocks V3). |
| V4 | Mark accepted writes .iw/oss-accepted.yaml | **fail** | — | Same modal catalog issue blocks testing. |
| V5 | Apply all safe — deselectable preview, never operates on unsafe | **fail** | — | Preview modal was auto-opened on page load (intercepted clicks); cannot confirm unsafe findings excluded. |
| V6 | SSE row updates — no full-page reload | **fail** | — | Scan button interaction requires working modal first. |
| V7 | Removed CLI subcommands + routes return errors | **fail** | — | Cannot exec into container to run `uv run iw oss --help` and curl commands. |
| V8 | No regressions on adjacent pages | **fail** | — | Browser DevTools console inaccessible via playwright-cli; adjacent pages not tested due to prior failures. |

---

## Issues Found

### 1. `window.OSS_CATALOG` never populated — modal sections show placeholder text
**Severity**: High  
**Root Cause**: `dashboard/routers/oss.py` passes `catalog` dict to template context (line 179), but the template never renders `window.OSS_CATALOG = {{ catalog_json }}`. The modal JS (line 265) looks for `window.OSS_CATALOG[catalogKey]` which is always falsy.  
**Affected File**: `dashboard/templates/pages/project/oss.html`  
**Fix Needed**: After iterating findings in oss_table.html or in a script block before including oss_finding_modal.html, render: `window.OSS_CATALOG = {{ catalog | tojson }};`

### 2. Git binary not installed in e2e-dashboard container  
**Severity**: High  
**Root Cause**: `iw-ai-core-e2e-cr00022-e2e-dashboard-1` is based on `python:3.12-slim` and lacks git. V3, V4, V7 require reading git state via `docker exec ... git -C /repo`.  
**Affected**: e2e docker-compose service definition  
**Fix Needed**: Install git in the dashboard container: `apt-get install -y git` in Dockerfile.e2e

### 3. Apply-all-safe preview modal opens on page load (V5 blocked)
**Severity**: Medium  
**Root Cause**: The preview modal appears in initial HTML with `aria-hidden=true` but `display:none` / `visibility` stacking may intercept clicks. When `Apply all safe` button (e57) is clicked, the preview is already partially visible and click events on detail buttons (e144) are intercepted.  
**Affected**: The modal's `position:fixed` overlay intercepts pointer events before the target button.

### 4. `docker compose` not directly usable — only read-only introspection allowed
**Severity**: Low  
**Note**: `docker ps` / `docker inspect` are allowed; `docker exec` to run arbitrary commands is used for read-only git queries but fails because git isn't in the container.

---

## Screenshots Captured

- `ai-dev/active/CR-00022/evidences/post/CR-00022_v1_table_layout.png` — V1 pass
- `ai-dev/active/CR-00022/evidences/post/CR-00022_v2_modal_open.png` — V2 fail (catalog empty)

---

## No Regressions Observed

N/A — adjacent pages were not tested due to prior failures blocking progress. Dashboard page `/project/iw-ai-core/` rendered correctly during session start.

---

## Environment Data Status

OSS findings fixture `ai-dev/active/CR-00022/e2e_fixtures/001_oss_scan_with_findings.py` is correctly loaded — 5 findings (2 MUST fail, 1 SHOULD fail, 2 PASS) are visible in the table. No `ENV_DATA_MISSING` issue.

---

## Subagent Result Contract

```json
{
  "step": "S27",
  "agent": "qv-browser",
  "work_item": "CR-00022",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9919",
  "verifications": [
    {"id": "V1", "name": "Table layout + filters", "status": "pass", "screenshot": "CR-00022_v1_table_layout.png", "notes": "All required columns render, domain groups expand, filter chips work"},
    {"id": "V2", "name": "Modal renders rich per-test copy", "status": "fail", "screenshot": "CR-00022_v2_modal_open.png", "notes": "window.OSS_CATALOG not populated - all content sections show placeholder text"},
    {"id": "V3", "name": "Apply writes to working tree only — no branch change + idempotent", "status": "fail", "screenshot": "", "notes": "git binary missing in e2e-dashboard container; modal not functional due to V2"},
    {"id": "V4", "name": "Mark accepted writes .iw/oss-accepted.yaml", "status": "fail", "screenshot": "", "notes": "Same V2 modal issue blocks interaction; git also unavailable for verification"},
    {"id": "V5", "name": "Apply all safe — deselectable preview, never operates on unsafe", "status": "fail", "screenshot": "", "notes": "Preview modal intercepts pointer events blocking detail button clicks; cannot verify unsafe exclusion"},
    {"id": "V6", "name": "SSE row updates — no full-page reload", "status": "fail", "screenshot": "", "notes": "Cannot proceed to V6 due to V2 failure"},
    {"id": "V7", "name": "Removed CLI subcommands + routes return errors", "status": "fail", "screenshot": "", "notes": "docker exec exec unavailable - git not in container; curl not available in container"},
    {"id": "V8", "name": "No regressions on adjacent pages", "status": "fail", "screenshot": "", "notes": "DevTools console inaccessible via playwright-cli; no regressions observed on initial page loads before failures"}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "CR-00022_v1_table_layout.png",
    "CR-00022_v2_modal_open.png"
  ],
  "notes": "Critical: window.OSS_CATALOG never set — template needs to render catalog as window var. Secondary: git not installed in e2e-dashboard container preventing git state verification."
}
```


## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/CR-00022/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00022/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
