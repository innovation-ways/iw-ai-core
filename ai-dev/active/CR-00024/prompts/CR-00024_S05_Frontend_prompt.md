# CR-00024_S05_Frontend_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Same Docker rules. The dashboard runs on port 9900 — read-only inspection is fine, but do NOT restart containers.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (AC6)
- `ai-dev/active/CR-00024/evidences/pre/CR-00024-running-before.png` — pre-state of /system/running
- `ai-dev/active/CR-00024/evidences/pre/CR-00024-worktrees-before.png` — pre-state of /system/worktrees
- `ai-dev/active/CR-00024/reports/CR-00024_S03_Backend_report.md` — to confirm the daemon side is wired
- `dashboard/routers/running.py` — `RunningRow` dataclass (line ~38) and `_query_running_now` (line ~81)
- `dashboard/routers/worktrees.py` — worktree HTML route
- `dashboard/routers/jobs_ui.py` — aggregated jobs view
- `dashboard/templates/fragments/running_table.html`
- `dashboard/templates/fragments/step_row.html`
- `dashboard/templates/fragments/jobs_table.html`

## Output Files

- `dashboard/routers/running.py` — modified
- `dashboard/routers/worktrees.py` — modified
- `dashboard/routers/jobs_ui.py` — modified
- `dashboard/templates/fragments/running_table.html` — modified
- `dashboard/templates/fragments/step_row.html` — modified
- `dashboard/templates/fragments/jobs_table.html` — modified
- `ai-dev/active/CR-00024/reports/CR-00024_S05_Frontend_report.md`

## Context

The daemon stamps `last_heartbeat` and `pid_alive` on every `StepRun` row each
poll cycle. Currently, neither field is rendered in the dashboard, so operators
have no way to tell "the daemon polled this step 30s ago, alive then" vs "the
daemon stopped polling". This step adds two new visual elements per running
step row:

1. **A "Last seen" column** showing `(now - last_heartbeat).total_seconds()` rendered as `Xs ago` / `Xm ago` / `unknown`.
2. **A pid-alive pip** — a small coloured dot (green = alive, red = dead, grey = unknown). Use the existing pip styling from the dashboard if one exists; otherwise use a small inline SVG / span with bg-color.

## Requirements

### 1. Update `RunningRow` and `_query_running_now`

In `dashboard/routers/running.py`:

```python
@dataclass
class RunningRow:
    # ... existing fields ...
    last_heartbeat_age_secs: int | None  # None when last_heartbeat is NULL
    pid_alive: bool | None               # None when pid_alive is NULL
```

In `_query_running_now`, populate the two new fields per row:

```python
last_heartbeat_age_secs=(
    int((now - run.last_heartbeat).total_seconds())
    if run.last_heartbeat is not None
    else None
),
pid_alive=run.pid_alive,
```

Where `now = datetime.now(UTC)` is captured ONCE per request (not per row) for consistency.

### 2. Render in `running_table.html`

Add a new column "Last seen" between the existing "Status" and "Duration" columns. The cell renders:

```jinja
{% if row.last_heartbeat_age_secs is none %}
  <span class="text-muted">unknown</span>
{% elif row.last_heartbeat_age_secs < 60 %}
  <span>{{ row.last_heartbeat_age_secs }}s ago</span>
{% elif row.last_heartbeat_age_secs < 3600 %}
  <span>{{ (row.last_heartbeat_age_secs // 60) }}m ago</span>
{% else %}
  <span>{{ (row.last_heartbeat_age_secs // 3600) }}h ago</span>
{% endif %}
```

Add a pid-alive pip inline next to the step_id or status (whichever feels less crowded):

```jinja
{% if row.pid_alive is true %}
  <span class="pip pip-alive" title="PID alive at last poll">●</span>
{% elif row.pid_alive is false %}
  <span class="pip pip-dead" title="PID dead at last poll">●</span>
{% else %}
  <span class="pip pip-unknown" title="PID status unknown">●</span>
{% endif %}
```

If the dashboard has no `.pip-*` CSS class, add a minimal inline `style="color: green/red/grey"` attribute. Match the existing dashboard's CSS style (Bootstrap, Tailwind, custom — read existing template files to determine).

### 3. Mirror the change in `step_row.html`

The `step_row.html` fragment is reused in multiple places. Add the same two columns / pip in the same visual position. Verify by `grep -rn "step_row.html" dashboard/templates/` which other templates include it; the change should appear consistently everywhere `step_row.html` renders.

### 4. Mirror in `jobs_table.html`

The aggregated jobs view at `/system/jobs` includes step-run rows alongside other job types. For step-run rows only, add the heartbeat column and pip. Other job types (CodeIndexJob, DocGenerationJob) don't have `last_heartbeat` — render `—` (em-dash) for those.

### 5. Worktrees page

In `dashboard/routers/worktrees.py`, the per-worktree row currently shows git status. Add the heartbeat-age + pip for the active step on each worktree (look up the running `StepRun` for that worktree, similar to how `_query_running_now` does it).

### 6. Hard Constraints

- Do NOT remove any existing column from any table.
- Do NOT change the existing column ORDER for status/started_at/duration — add the new "Last seen" column in a logical position (between Status and Duration is the design's request).
- Do NOT modify the SSE refresh logic — the existing htmx-driven fragment refresh continues to work because the template re-render produces the new column automatically.
- Do NOT add a new HTTP endpoint. Reuse existing routes.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — must report zero errors
3. `make lint` — must report zero errors (this includes the dashboard JS check via `node --check`)

## Manual smoke before reporting done

The dashboard is running locally on port 9900. After implementation:

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/system/running
playwright-cli snapshot
playwright-cli screenshot --filename ai-dev/active/CR-00024/evidences/post/CR-00024-running-after-S05.png --full-page
```

Compare the post screenshot to `evidences/pre/CR-00024-running-before.png` — the post should have the new column and pip; the existing columns should be unchanged.

(The formal browser verification is S15. This S05 smoke is for your own confidence before reporting done.)

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00024",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/running.py",
    "dashboard/routers/worktrees.py",
    "dashboard/routers/jobs_ui.py",
    "dashboard/templates/fragments/running_table.html",
    "dashboard/templates/fragments/step_row.html",
    "dashboard/templates/fragments/jobs_table.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "Manual smoke OK — see evidences/post/CR-00024-running-after-S05.png",
  "blockers": [],
  "notes": ""
}
```
