# CR-00056_S10_CodeReview_Final_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Review Step**: S10 (Final Review — implementation cross-cut, pre-tests)
**Implementation Steps Reviewed**: S01..S09

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — full document
- All implementation reports: `ai-dev/work/CR-00056/reports/CR-00056_S01_*` through `_S09_*`
- All per-agent review reports
- All files in all `files_changed` arrays

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S10_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of the implementation work for CR-00056, before the dedicated tests step (S11). This review focuses on **end-to-end integration**: does the schema add (S01) → daemon snapshot (S04) → dashboard route (S06) → template + JS (S08) chain actually work as one feature?

The per-agent reviews (S02/S05/S07/S09) each look at one slice. Your job is to spot the cross-cutting issues they can't.

## Read the Design Document FIRST

- `Acceptance Criteria` — every AC1..AC9 maps to a slice spanning multiple steps. Trace each one end-to-end.
- `TDD Approach` — note every test file the design names by path. Cross-check that each is present in some implementation step's `files_changed` (or will be in S11, which is the tests step — but the design-named tests for S04 and S06 should already exist as RED-evidence).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on any S01..S09 file → CRITICAL.

## Review Checklist

### 1. End-to-end completeness — trace every AC across layers

For each AC1..AC9, identify which step(s) implement it and confirm the chain is intact:

| AC | Steps that touch it | What to verify |
|---|---|---|
| AC1 | S01 | Migration applied via `make migration-check`; both columns visible in `\d+ step_runs` |
| AC2 | S01, S04 | Daemon writes prompt content to StepRun.prompt_text at initial launch |
| AC3 | S01, S04 | Daemon writes fix prompt to fix_prompt_text + base prompt to prompt_text on retry |
| AC4 | S06, S08 | `has_prompt` flag drives View button vs "—" rendering |
| AC5 | S06, S08 | htmx GET to route → fragment with `<pre>`, role="dialog", aria-modal="true" |
| AC6 | S08 | Escape/backdrop/close all dismiss + focus restored |
| AC7 | S04, S06, S08 | Fix-cycle prompts produce stacked labelled sections |
| AC8 | S08 | Copy button → `window.iwClipboard.copy(...)` |
| AC9 | S06 | 404 on project/item mismatch (not 403, not 500) |

Any AC with a missing link → CRITICAL.

### 2. Cross-agent consistency

- The route name in S06 (`/item/{item_id}/step/{step_id}/prompt-modal`) matches the `hx-get` URL in the template from S08 — exact string match.
- The `StepDetail.has_prompt` field added in S06 is the same field the template in S08 reads.
- The CSS class names used in the template from S08 match what's defined in `styles.css` (no orphan classes).
- The `data-prompt-section-body="{{ loop.index0 }}"` attributes set by the template and read by `prompt_modal.js` use the same name.
- The agent label rendering in the modal header matches the agent label rendering in the table column.

### 3. Integration points — DB → daemon → route → template

- The daemon writes `prompt_text` at row creation (S04). Confirm by reading the changed `batch_manager.py` lines.
- The route in S06 reads `step_runs.prompt_text` / `fix_prompt_text` via SQLAlchemy. Confirm the query joins / filters use the new column names exactly.
- The template in S08 iterates `sections` — confirm the route in S06 builds `sections` with the exact key names the template uses (`label`, `text`).

### 4. Architecture compliance

- `step_runs` remains append-only — no UPDATE statements introduced anywhere.
- Fragment template does not extend `base.html`.
- Routers stay thin — the section-aggregation logic in S06 is ≤40 lines; if larger, factor into `orch/`.

### 5. Cross-cutting security

- `{{ section.text }}` rendered via Jinja autoescape — no `|safe`.
- No new endpoint without project_id scoping.
- No clipboard helper bypass anywhere.

### 6. Performance

- `has_prompt` doesn't cause N+1. If S06 does Python-side aggregation, verify it uses pre-fetched StepRuns (no extra query per step inside the `_get_steps()` loop).

### 7. Manifest scope check

- The files actually modified by S01..S09 are all listed in `workflow-manifest.json:scope.allowed_paths`. If any modified file is outside the scope, the merge-time gate will block — flag now.

### 8. CLAUDE.md hard rules sweep

- Run a final sweep for these patterns in files changed:
  ```bash
  grep -RIn 'navigator\.clipboard\.writeText' dashboard/    # MUST be zero hits in S08 files
  grep -RIn 'importlib\.reload' tests/                       # MUST be zero hits in any test added
  grep -RIn 'psycopg2' orch/ tests/                          # MUST be zero hits in any new code (psycopg v3 only)
  grep -RIn "\"{}[^\"]*\"\\.format\\(" dashboard/templates/  # Jinja format-filter — must be %-style
  ```

## Test Verification (NON-NEGOTIABLE)

Do NOT re-run `make test-unit` / `make test-integration` here — those are
duplicated work that S18 (unit) and S19 (integration) QV gates own. Running
them again in this step caused the I-00073 timeout (2702s) and is forbidden
project-wide for any `*-impl` step.

Instead, cross-check that the targeted tests added by S04
(`tests/integration/test_daemon_prompt_snapshot.py`) and S06
(`tests/dashboard/test_prompt_modal_route.py`) exist in the corresponding
step reports and that their `tests_passed` field is `true`. A missing or
failing targeted test at this point → CRITICAL.

If you need a quick smoke before merge, run only the changed-file scope:

```bash
uv run pytest tests/integration/test_daemon_prompt_snapshot.py tests/dashboard/test_prompt_modal_route.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview_Final",
  "work_item": "CR-00056",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
