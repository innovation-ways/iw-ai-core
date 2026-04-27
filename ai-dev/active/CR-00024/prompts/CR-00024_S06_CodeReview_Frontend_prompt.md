# CR-00024_S06_CodeReview_Frontend_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S06
**Agent**: code-review-impl

---

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (AC6)
- `ai-dev/active/CR-00024/reports/CR-00024_S05_Frontend_report.md`
- `ai-dev/active/CR-00024/evidences/pre/CR-00024-running-before.png`, `CR-00024-worktrees-before.png`
- `ai-dev/active/CR-00024/evidences/post/CR-00024-running-after-S05.png` (if S05 captured one)
- All 6 modified dashboard files

## Output Files

- `ai-dev/active/CR-00024/reports/CR-00024_S06_CodeReview_Frontend_report.md`

## Review Checklist

### Data plumbing
- [ ] `RunningRow` dataclass gained `last_heartbeat_age_secs: int | None` and `pid_alive: bool | None`
- [ ] `_query_running_now` populates both fields per row from the joined `StepRun`
- [ ] `now` is captured once per request (consistent across all rows in the same render)
- [ ] `worktrees.py` and `jobs_ui.py` follow the same pattern

### Rendering
- [ ] "Last seen" column appears between Status and Duration in `running_table.html`
- [ ] The age formatting handles all 3 buckets: `< 60s` ("Xs ago"), `< 3600s` ("Xm ago"), `>= 3600s` ("Xh ago")
- [ ] NULL `last_heartbeat` renders as "unknown" (text-muted), not blank or "0s ago"
- [ ] pid-alive pip renders 3 states: True (positive colour), False (negative), None (neutral/grey) — title attribute is set for accessibility
- [ ] No existing column was removed; existing column ORDER for status/started_at/duration is preserved
- [ ] No template syntax errors (Jinja braces balanced, `{% if %}` blocks closed)

### Cross-template consistency
- [ ] `step_row.html` reflects the same change everywhere it's included (grep `step_row.html` in templates to verify it's used in fragments + pages)
- [ ] `jobs_table.html` shows the heartbeat column for step-run rows AND renders `—` for non-step-run job types (no JS error / KeyError)
- [ ] Worktree rows include the pip alongside their git status

### htmx / SSE refresh
- [ ] No SSE event handler regressed — the htmx fragment refresh path still triggers on `step_run_updated` / equivalent event
- [ ] No new HTTP endpoint was added (the design forbids this)

### Style + lint
- [ ] `make lint` clean (includes `node --check dashboard/static/**/*.js`)
- [ ] mypy clean on the 3 dashboard `.py` files

### Smoke evidence
- [ ] S05's report links a post-state screenshot showing the new column + pip
- [ ] Comparing pre/post visually, only the new column and pip differ — no other layout shift

## Findings Severity

- **CRITICAL**: existing column removed/renamed; rendering crashes when `last_heartbeat` is NULL; SSE refresh broken
- **HIGH**: missing column on one of the 3 tables; pip colors swapped; consistent state breakage in `jobs_table.html`
- **MEDIUM**: accessibility (no title attr, low contrast); inconsistent age formatting across templates
- **LOW**: spacing, alignment, semantic HTML choice

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00024",
  "completion_status": "complete",
  "files_reviewed": [
    "dashboard/routers/running.py",
    "dashboard/routers/worktrees.py",
    "dashboard/routers/jobs_ui.py",
    "dashboard/templates/fragments/running_table.html",
    "dashboard/templates/fragments/step_row.html",
    "dashboard/templates/fragments/jobs_table.html"
  ],
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
