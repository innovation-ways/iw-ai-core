# F-00078_S05_Frontend_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt for full text. Same rules apply.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00078 --json`.
- `ai-dev/active/F-00078/F-00078_Feature_Design.md` -- Design document
- `ai-dev/work/F-00078/reports/F-00078_S03_Backend_report.md` -- S03 report (for the data shape from `orch/self_assess.py`)
- `orch/daemon/execution_report.py` -- The assembler you'll extend
- `dashboard/templates/fragments/item_execution_report.html` -- The fragment you'll extend
- `dashboard/CLAUDE.md` -- Stack notes (Tailwind prebuilt; htmx; server-rendered Jinja2; no React)
- `orch/self_assess.py` -- New module from S03 (dataclasses, parser, helpers)
- `dashboard/routers/items.py` -- Where the execution-report tab is served (you should NOT need to edit this — confirm)

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S05_Frontend_report.md` -- Step report
- Modified: `orch/daemon/execution_report.py`, `dashboard/templates/fragments/item_execution_report.html`
- Modified (only if you added new Tailwind classes): `dashboard/static/styles.css` (regenerated via `make css`)
- Possibly modified: `dashboard/static/` (a tiny inline JS for the clipboard button is preferred over a new file, but if you add a small JS helper, keep it under `dashboard/static/`)

## Context

You are extending the Execution Report tab to surface the new `self_assess` findings, without introducing a new tab. The user's explicit choice (F-00078 design): append a "Self-Assessment" section to the existing tab, render only when the project has the flag on AND the step ran AND a findings file exists.

Read the design document first (especially "Frontend Changes", AC4, AC5, and the "Boundary Behavior" rows about findings file states).

The data shape comes from `orch/self_assess.py` (`SelfAssessmentData` and `SelfAssessFinding` dataclasses, defined by S03). Do NOT redefine them in the dashboard layer.

## Requirements

### 1. Extend `ExecutionReportData`

In `orch/daemon/execution_report.py`:

- Import `SelfAssessmentData` from `orch.self_assess` (the top-level module created in S03 — NOT from `orch.daemon.*`). Cross-module imports inside `orch/` are fine; the dashboard router (`dashboard/routers/items.py`) MUST also reuse this same import path if it ever needs to reference the dataclass directly. Do not redefine the dataclass anywhere else and do not import it through `orch.daemon.execution_report`.
- Add a new field to `ExecutionReportData`:
  ```python
  self_assessment: SelfAssessmentData | None = None
  ```
  Use `field(default=None)` if the dataclass is frozen and requires keyword-only with default.
- In `assemble_execution_report(...)`, after building the step rows, look for a step with `step_type == StepType.self_assess`. If one exists AND its final status is in `{completed, failed}` (the step ran):
  1. Find the latest StepRun for that step.
  2. **Guard for missing `report_file`**: if `step_run is None` OR `step_run.report_file is None` (i.e., the agent called `step-done` without `--report`), set `self_assessment = None` and return — do NOT call `findings_path_for(None)`.
  3. Use `findings_path_for(step_run.report_file)` (from `orch/self_assess.py`) to derive the JSON sidecar path.
  4. Read the report MD via `step_run.report_file` for the narrative (or skip if missing).
  5. Try to parse the findings JSON via `orch.self_assess.parse_findings_json`.
  6. On success, populate `self_assessment` with the parsed data.
  7. On parser failure, populate `self_assessment` with `narrative_md` filled but `findings=[]` and a sentinel — the template handles graceful degradation.
  8. On any IO error (file not found), set `self_assessment = None`.

  All file IO must be defensive — never raise from the assembler. Wrap each read/parse in `try/except (OSError, json.JSONDecodeError, SelfAssessParseError)` and log via the module's existing logger.

- Also extend the markdown renderer `render_execution_report_markdown` with a new "## Self-Assessment" section if `data.self_assessment` is populated. Mirror the dashboard fragment's logic so the markdown export also shows findings. Include the narrative + the findings list with severity tags. (No clipboard buttons in markdown — just print the `paste_prompt` strings inside fenced code blocks.)

### 2. Extend the Jinja2 fragment

In `dashboard/templates/fragments/item_execution_report.html`, after the existing "Retry Timeline" block, add a new block:

```jinja
{% if execution_report.self_assessment %}
  {# ── Self-Assessment ──────────────────────────────────────────────────── #}
  <div class="bg-card border border-border rounded-lg p-4 mt-4">
    <h3 class="text-sm font-semibold text-foreground mb-3">Self-Assessment</h3>
    ...
  </div>
{% endif %}
```

Required UI elements (all server-rendered Jinja2, no client-side data fetching):

- **Header**: "Self-Assessment" + small "(self_assess failed)" badge if the step's final status is `failed` (so the human knows the section may be partial).
- **Bottom line** (if `self_assessment.bottom_line` is present): a single-sentence callout at the top.
- **Coverage notes** (if `self_assessment.coverage_notes` is present): small italic line, "Coverage: <text>".
- **Findings, grouped by `target`**:
  - "Suggestions for iw-ai-core" subsection (only if there's at least one finding with `target == "iw-ai-core"`).
  - "Suggestions for {project_id}" subsection (only if there's at least one with `target == "project"` — substitute the actual project id from `execution_report.project_id`).
  - Within each subsection, render findings ordered by severity (HIGH → MED → LOW), each as a card with: severity badge (color-coded, mirror the existing badge styles), title, recommendation, and a "Copy paste prompt" button.
- **Narrative** (if `self_assessment.narrative_md` is present): render below the findings, in a `<details>` collapsible block (closed by default) titled "Full narrative" so it doesn't dominate the tab.

If `self_assessment` is set but `findings == []`, render a single italic line: "Self-assessment ran but no findings were captured." Do NOT render empty subsections.

### 3. Clipboard button

Each finding's "Copy paste prompt" button copies that finding's `paste_prompt` to the clipboard. Use the standard Web Clipboard API:

```html
<button type="button"
        class="text-xs px-2 py-1 rounded bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30"
        data-paste-prompt="{{ finding.paste_prompt }}"
        onclick="navigator.clipboard.writeText(this.dataset.pastePrompt).then(() => { this.textContent = 'Copied'; setTimeout(() => this.textContent = 'Copy paste prompt', 1500); })">
  Copy paste prompt
</button>
```

Inline `onclick` is acceptable here for parity with how this fragment already attaches behavior. If `dashboard/CLAUDE.md` (or existing patterns in the file) prefer a tiny JS helper file, follow that convention instead. If you add a JS file, run `node --check` on it (per `make lint` for `dashboard/static/**/*.js`).

### 4. Visibility rules (AC5 — invisible when not applicable)

The `{% if execution_report.self_assessment %}` guard is the SOLE rendering gate. The assembler guarantees `self_assessment` is `None` when:
- The project has the flag off (no self_assess step in the manifest, so the step lookup misses).
- The step exists but is `pending` or `skipped`.
- The findings JSON file does not exist (and no narrative either).

So the template needs no extra conditionals beyond the `if` guard.

### 5. Tailwind / CSS

- If you only use existing Tailwind utility classes (matching the existing fragment's vocabulary), no rebuild needed.
- If you introduce new classes, run `make css` and commit the regenerated `dashboard/static/styles.css`.
- Do NOT use dynamic class construction (the JIT purger won't see them).

### 6. Markdown render parity

The `render_execution_report_markdown` function (same file) writes the markdown export. Add a "Self-Assessment" section to that output too — same data, just formatted as markdown. The user might export the report; consistency between UI and export matters.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:

- Tailwind prebuilt — `make css` regenerates `styles.css`.
- Fragment templates do NOT extend `base.html`.
- Use existing badge styles (look at the existing verdict badge and severity colors in this same fragment).
- htmx is the JS layer — minimal vanilla JS additions.

## TDD Requirement

For the Python side (`execution_report.py` extension):

1. **RED**: Write a unit test in `tests/unit/test_execution_report_self_assess.py` that asserts `assemble_execution_report` populates `self_assessment` when given a step with `step_type=self_assess` and a findings JSON file on disk. Use `tmp_path` and a real ProjectConfig (or stub the path resolution).
2. **GREEN**: implement.
3. **REFACTOR**: handle the missing-file case and the parse-error case in the same test file.

For the template side, write a dashboard test in `tests/dashboard/test_execution_report_self_assess.py` that uses FastAPI's `TestClient` to fetch `/project/<id>/item/<id>/tab/execution-report` and asserts the rendered HTML contains "Self-Assessment" when findings are present, and does NOT contain it when they're absent. Use a fixture that seeds a completed work item with a sidecar JSON file. The S09 step will expand on this — write at least the smoke test now.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` (also covers `dashboard/static/**/*.js` via the `node --check` step)

If you regenerate `dashboard/static/styles.css`, run `make css` and commit the file.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "F-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/execution_report.py",
    "dashboard/templates/fragments/item_execution_report.html",
    "tests/unit/test_execution_report_self_assess.py",
    "tests/dashboard/test_execution_report_self_assess.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Note whether you regenerated styles.css and whether you added a JS helper file or used inline onclick."
}
```
