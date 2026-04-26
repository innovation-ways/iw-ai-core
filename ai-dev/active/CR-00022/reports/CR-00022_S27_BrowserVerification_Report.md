# Browser Verification Report — CR-00022 S27

## Summary

| Verification | Status | Notes |
|---|---|---|
| V1: Table layout + filters | PASS | New layout renders with Group/Test/Type/Status/Details columns; Scan + Apply all safe buttons only; collapsible domain groups with `…` detail buttons; failing-only filter active by default |
| V2: Modal renders rich copy | PASS | Modal opens centered with all required sections: header (severity badge, check_id, status pill, OSPS), title, What this test checks, How it tests, Risk if you ship anyway, How to fix, Preview/Apply buttons; ESC closes modal |
| V3: Apply writes to working tree only | PASS | Branch unchanged (refs/heads/main); no iw-oss-publish branch created; no /tmp/oss-* files; git status shows only worktree artifacts (CR-00022 dirs); README.md not modified (existing stub passes the check idempotently) |
| V4: Mark accepted writes .iw/oss-accepted.yaml | PASS | Toast "✓ Risk accepted" appears; row moves to Accepted status; oss-accepted.yaml contains OSS-CH-01 entry with 16-hex finding_hash, reason text, accepted_by |
| V5: Apply all safe deselectable preview | PASS | Preview modal shows "Writes to your working tree only. No branch is created."; OSS-CH-01 (1 file) and OSS-CH-03 (0 files) listed with top-level checkboxes; OSS-CH-02 (auto_apply_safe=False) not listed; deselecting OSS-CH-03 and applying shows toast with OSS-CH-01 only; branch unchanged |
| V6: SSE row updates — no full-page reload | PASS | Scan button becomes "Scanning…" disabled; progress indicator appears; after scan completes, buttons re-enable without page reload; URL unchanged throughout |
| V7: Removed CLI/routes return errors | PASS | `iw oss --help` shows only: disable, enable, fix, install, scan, status (no prepare/publish); both POST /oss/prepare and POST /oss/publish return HTTP 404 |
| V8: No regressions | PASS | /project/iw-ai-core/, /project/iw-ai-core/jobs, /project/iw-ai-core/code all render; OSS nav sidebar item visible |

## Base URL Used

`http://localhost:9919`

## Screenshots Captured

| File | Verification |
|---|---|
| `evidences/post/CR-00022_v1_table_layout.png` | V1 – Table layout with domain groups expanded |
| `evidences/post/CR-00022_v2_modal_open.png` | V2 – OSS-CH-01 modal open with rich copy |
| `evidences/post/CR-00022_v3_apply_success.png` | V3 – After Apply (branch unchanged, no branch created) |
| `evidences/post/CR-00022_v4_accepted_yaml.png` | V4 – OSS-CH-01 moved to Accepted status |
| `evidences/post/CR-00022_v5_apply_all_safe_preview.png` | V5 – Preview modal with OSS-CH-03 unchecked |
| `evidences/post/CR-00022_v6_scan_complete.png` | V6 – After scan completes, no reload |
| `evidences/post/CR-00022_v8_no_regressions.png` | V8 – OSS page with nav highlighting |

## Issues Found

None. All 8 verifications passed.

## Notes

- OSS-CH-01 (auto_apply_safe=True) was applied twice — second apply showed same toast "Wrote README.md stub" and git diff was unchanged, confirming idempotency.
- OSS-CH-02 (auto_apply_safe=False) was NOT shown in Apply all safe preview, confirming AC10 enforcement.
- E2E fixtures at `ai-dev/active/CR-00022/e2e_fixtures/001_oss_scan_with_findings.py` correctly seeded 5 findings covering MUST/SHOULD/INFO severities and auto_apply_safe=True/False mix.
- Container bridge: dashboard at port 9900 inside container, exposed at 9919 on host; git repo at `/app` inside container (not `/repo`).

## Verifications Detail

```json
{
  "step": "S27",
  "agent": "qv-browser",
  "work_item": "CR-00022",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9919",
  "verifications": [
    {"id": "V1", "name": "Table layout + filters", "status": "pass", "screenshot": "evidences/post/CR-00022_v1_table_layout.png", "notes": "New table with Group/Test/Type/Status/Details; Scan+Apply all safe buttons only; domain group headers collapsible"},
    {"id": "V2", "name": "Modal renders rich per-test copy", "status": "pass", "screenshot": "evidences/post/CR-00022_v2_modal_open.png", "notes": "All sections present: What this test checks, How it tests, Risk if you ship anyway, How to fix, Preview, Apply"},
    {"id": "V3", "name": "Apply writes to working tree only — no branch change + idempotent", "status": "pass", "screenshot": "evidences/post/CR-00022_v3_apply_success.png", "notes": "Branch refs/heads/main unchanged; no iw-oss-publish branch; no /tmp/oss-* files; second apply idempotent"},
    {"id": "V4", "name": "Mark accepted writes .iw/oss-accepted.yaml", "status": "pass", "screenshot": "evidences/post/CR-00022_v4_accepted_yaml.png", "notes": "OSS-CH-01 entry in oss-accepted.yaml with correct fields"},
    {"id": "V5", "name": "Apply all safe — deselectable preview, never operates on unsafe", "status": "pass", "screenshot": "evidences/post/CR-00022_v5_apply_all_safe_preview.png", "notes": "OSS-CH-02 (auto_apply_safe=False) not in preview; deselecting OSS-CH-03 excluded it from apply"},
    {"id": "V6", "name": "SSE row updates — no full-page reload", "status": "pass", "screenshot": "evidences/post/CR-00022_v6_scan_complete.png", "notes": "Scan button disabled during scan; progress indicator; URL unchanged; no reload on completion"},
    {"id": "V7", "name": "Removed CLI subcommands + routes return errors", "status": "pass", "screenshot": "", "notes": "iw oss shows no prepare/publish; POST /oss/prepare 404; POST /oss/publish 404"},
    {"id": "V8", "name": "No regressions on adjacent pages", "status": "pass", "screenshot": "evidences/post/CR-00022_v8_no_regressions.png", "notes": "Dashboard, Jobs, Code pages render; OSS nav highlighted"}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "evidences/post/CR-00022_v1_table_layout.png",
    "evidences/post/CR-00022_v2_modal_open.png",
    "evidences/post/CR-00022_v3_apply_success.png",
    "evidences/post/CR-00022_v4_accepted_yaml.png",
    "evidences/post/CR-00022_v5_apply_all_safe_preview.png",
    "evidences/post/CR-00022_v6_scan_complete.png",
    "evidences/post/CR-00022_v8_no_regressions.png"
  ],
  "notes": ""
}
```