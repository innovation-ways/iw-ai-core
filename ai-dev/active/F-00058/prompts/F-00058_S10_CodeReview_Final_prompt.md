# F-00058_S10_CodeReview_Final_prompt

**Work Item**: F-00058 — OSS compliance dashboard view + status pill
**Step**: S10
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md`
- All prior step reports (S01…S09) in `ai-dev/active/F-00058/reports/`
- Merged source under `orch/db/`, `dashboard/services/`, `dashboard/routers/`, `dashboard/templates/`

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S10_CodeReview_Final_report.md`

## Context

Global cross-layer review. Each layer was reviewed in isolation; your job is to verify they compose into a working user experience and meet every acceptance criterion.

## Review Checklist

### 1. Cross-layer consistency

- Pill color emitted by `status --json` (F-00057) matches the pill color rendered in `oss_status_pill.html` for the same scan — they MUST derive from the same function, not two parallel implementations.
- API `--json` shape (counts + stale + head_sha + scan_id) matches both:
  - The F-00057 CLI `status --json` contract.
  - The template's expected inputs.
- SSE event schema is consistent between service → router → template's `hx-sse` bindings.
- `project_oss_job.scan_id` FK is actually populated on successful scans (cross-check service code).
- The F-00057 dependency is honored — no re-implementations of `orch/oss/*` in the dashboard layer; dashboard uses the existing services.

### 2. Acceptance-criteria walkthrough

For each AC1–AC7, point to the test(s) that cover it:

- AC1 (frame on every page): `test_oss_dashboard_templates_extras.py` frame-presence iteration.
- AC2 (Install OSS flow): `test_oss_dashboard_boundary.py` disabled state + enable POST.
- AC3 (Scan + SSE): `test_oss_dashboard_sse.py` + `test_oss_dashboard_routes.py`.
- AC4 (Prepare/Publish + CLI block): `test_oss_dashboard_templates.py` CLI block + boundary test on throwaway worktree.
- AC5 (stale banner): `test_oss_dashboard_boundary.py::test_head_advanced`.
- AC6 (results tree understandable): template renders for domain + tool_run cards.
- AC7 (no regressions): frame-on-every-project-page test + manual qv-browser in S16.

Any AC without a test = CRITICAL.

### 3. No regressions elsewhere

- `make test-unit` + `make test-integration` clean.
- Grep for accidental references to `iw-oss-publish` in unrelated modules.
- Verify sibling project pages (Code, Tests, Quality, Documentation) render without console errors — manual check or deferred to S16 qv-browser.

### 4. Security

- Authorization guard on every OSS route (match existing guard from `quality.py`).
- Project slug validated; no directory traversal via crafted project_id.
- Throwaway worktree paths never user-controlled.

### 5. Design-doc manifest alignment

Every file in the design doc's *File Manifest* exists (created or modified) and no unplanned files were added.

### 6. CLAUDE.md compliance

- Testcontainer-only tests ✓.
- No `importlib.reload(orch.config)` ✓.
- `DaemonEvent.metadata` awareness ✓ (even if not directly touched).
- Dashboard's playwright-cli usage (if any in tests) uses `playwright-cli`, never `agent-browser` ✓.

### 7. Code hygiene

- No debug prints in dashboard / orch.
- No commented-out code.
- `make lint` + `uv run ruff format --check .` + `uv run mypy orch/ dashboard/` all clean.

## Test Verification (NON-NEGOTIABLE)

All QV gates (S11–S15) expected to pass. Run them locally before finalizing:

1. `make lint`
2. `uv run ruff format --check .`
3. `uv run mypy orch/ dashboard/`
4. `make test-unit`
5. `make test-integration`

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-final-impl",
  "work_item": "F-00058",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "acceptance_criteria_coverage": {
    "AC1": "covered by test_...",
    "AC2": "covered by test_...",
    "AC3": "covered by test_...",
    "AC4": "covered by test_...",
    "AC5": "covered by test_...",
    "AC6": "covered by test_...",
    "AC7": "covered by test_... + S16 qv-browser"
  },
  "notes": ""
}
```

Only `verdict: pass` when: zero CRITICAL + HIGH + MEDIUM_FIXABLE findings AND every AC has a corresponding test or deferred to S16 browser verification.
