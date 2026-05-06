# CR-00035_S10_CodeReview_Frontend_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Being Reviewed**: S09 (frontend-impl)
**Review Step**: S10

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt. No lifecycle commands.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. AC1, AC5).
- `ai-dev/active/CR-00035/reports/CR-00035_S09_Frontend_report.md`.
- All files in S09's `files_changed`.

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S10_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in S09's changed files = **CRITICAL**. The lint gate includes `node --check` on dashboard JS files — if any new JS was added, it must parse.

## Review Checklist

### Conditional rendering correctness

- Live Log card renders ONLY when `job.job_type.value == 'doc_generation' AND job.status == 'running'`.
- Execution Report card renders ONLY when `job.job_type.value == 'doc_generation' AND raw.report` is truthy.
- Captured log `<details>` renders ONLY when terminal state AND `raw.agent_output`.
- Download raw log link only shows when `log_file_exists` is True (passed from S07's modification of the detail handler).
- Original Parameters card and Error card still render unchanged.
- A `queued` job shows neither Live Log nor Captured log nor Execution Report.

### htmx / SSE

- The SSE wiring (htmx-sse OR vanilla EventSource) connects to the URL declared in S07 (`/project/{pid}/jobs/doc_generation/{raw.id}/log/stream`).
- Use of `raw.id` (UUID), NOT `raw.public_id`, in the URL. This is the file-naming convention.
- If using vanilla EventSource: the script closes the connection on `event:status data:terminal`. No leaked connections on tab close.
- If a JS file was added, it's <30 lines, no new dependencies, and `node --check` passes.
- htmx SSE extension is loaded in `base.html` if htmx-sse was chosen.

### Accessibility

- Log region has `aria-live="polite"` and `aria-label`.
- Status pill is a `<span>` with semantic class, not an icon-only signal.

### Tailwind

- All classes are static string literals (no `class="text-{{ color }}-500"` patterns that break JIT purge).
- `make css` was run after the edit; `dashboard/static/styles.css` reflects new classes if any.

### Visual sanity

- Card spacing matches existing cards (`mb-6` between, `p-4` inside, same border / background).
- Font sizes consistent with neighbouring text (`text-sm` for headings, `text-xs` for labels, `font-mono text-xs` for log text).

### Regression

- The original Error block at lines 244–250 of the pre-edit file STILL appears for failed jobs.
- Original Parameters card still shows the `skill_used`, `trigger_reason`, `duration_seconds`, `lint_warnings` fields.

## Test Verification

```bash
make test-unit
make test-integration
```

Open a browser and visually verify the failed DOC-00004 page (expected: Parameters + Captured log + Execution Report + Error card all visible).

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
