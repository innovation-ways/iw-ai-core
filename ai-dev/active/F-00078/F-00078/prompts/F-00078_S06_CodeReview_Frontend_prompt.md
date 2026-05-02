# F-00078_S06_CodeReview_Frontend_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt. Same rules apply.

## Input Files

- `uv run iw item-status F-00078 --json`
- `ai-dev/active/F-00078/F-00078_Feature_Design.md`
- `ai-dev/work/F-00078/reports/F-00078_S05_Frontend_report.md`
- All files listed in S05's `files_changed`

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S06_CodeReview_report.md`

## Context

Review the Execution Report extension for F-00078. The S05 step:
1. Added `self_assessment: SelfAssessmentData | None` to `ExecutionReportData` and populated it in `assemble_execution_report` from disk.
2. Extended the Jinja2 fragment with a "Self-Assessment" section grouped by `target`.
3. Added clipboard-copy buttons for the per-finding paste prompts.
4. Added a parallel section to the markdown export.

Critical things to catch:
- A bug that makes the section render even when no findings exist (AC5 violation).
- File IO that raises from the assembler (AC4 / Invariant: dashboard must never 500 on missing/malformed findings).
- XSS from un-escaped `paste_prompt` in the clipboard data attribute.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

`make lint` also runs `node --check` on `dashboard/static/**/*.js` — if the agent added a JS file, that check matters.

NEW violations in the changed files → CRITICAL `category: conventions`.

## Review Checklist

### 1. Visibility rule (AC5)

- Confirm: when the project has no `self_assess` step (flag off), `self_assessment` is `None` and the section is invisible. Test by reading the assembler's lookup logic — does it correctly return None when no step matches?
- Confirm: a `pending` or `skipped` self_assess step does NOT populate `self_assessment`.
- Confirm: the template's `{% if execution_report.self_assessment %}` is the SOLE gate. No "no analysis available" placeholder text anywhere.

### 2. Defensive IO

- Does the assembler swallow `FileNotFoundError`? Does it swallow `json.JSONDecodeError`?
- Does it raise on truly unexpected errors, or does it silently log and return None? Either is acceptable, but the assembler must NEVER raise from a malformed/missing findings file. If it does, that's CRITICAL (will 500 the Execution Report tab).
- Inspect: does the file read pass `encoding="utf-8"`? If not, MEDIUM_FIXABLE.

### 3. XSS / template safety

- The `paste_prompt` string contains arbitrary text (the agent might generate prose with `<` or `&`). When embedded in `data-paste-prompt="{{ finding.paste_prompt }}"`, Jinja2's autoescape MUST be active. If the template uses `{{ finding.paste_prompt | safe }}` anywhere, that's CRITICAL.
- The `onclick="..."` inline handler reads `this.dataset.pastePrompt`, which is the escaped attribute value. That's safe IFF Jinja2 escaping is on. Verify by inspecting the rendered HTML against a finding with quotes/special chars in the paste_prompt.
- Confirm `data.bottom_line`, `data.coverage_notes`, `finding.title`, `finding.recommendation` are also rendered without `| safe`.

### 4. Markdown render parity

- Does `render_execution_report_markdown` also include the Self-Assessment block?
- Are paste prompts wrapped in fenced code blocks (so they're copy-paste-friendly from a markdown viewer)?

### 5. Grouping logic

- "Suggestions for iw-ai-core" subsection only when there's ≥1 finding with `target == "iw-ai-core"`. Same for "Suggestions for {project_id}".
- The project_id substitution should use `execution_report.project_id`, not a hardcoded string.
- If both subsections are empty (findings list non-empty but malformed), the "no findings captured" italic line should appear instead.

### 6. Severity ordering

- Findings within each subsection should render HIGH first, then MED, then LOW.
- If the agent sorted alphabetically or randomly, MEDIUM_FIXABLE.

### 7. Clipboard button accessibility

- Button has `type="button"` (so it doesn't submit a form by accident).
- Button has visible text and a sane fallback if the clipboard API rejects (older browsers / non-HTTPS pages — for localhost this is fine, but check that the failure path doesn't crash the page).
- LOW finding if missing aria-label, MEDIUM_FIXABLE if missing `type="button"`.

### 8. CSS / Tailwind

- If new utility classes were added, was `make css` re-run? Inspect the diff on `dashboard/static/styles.css` — should be a small additive change.
- Are there any dynamically constructed class names? (`class="bg-{{ severity_color }}"`) — if yes, the JIT purger won't include them. Flag MEDIUM_FIXABLE.

### 9. Out-of-scope changes

- Any change outside `orch/daemon/execution_report.py`, the fragment template, the markdown render, the styles file, and the new test files is out of scope. Skill / template / backend logic changes belong to S03 or S07. HIGH.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass. The new dashboard render test should explicitly assert presence-when-findings and absence-when-empty.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | XSS via `\| safe`; assembler raises on missing/malformed file (500s the tab); section renders when not applicable | Must fix |
| **HIGH** | Out-of-scope changes; broken file IO; AC5 violation | Must fix |
| **MEDIUM (fixable)** | Severity ordering wrong, missing escaping on a non-attribute, missing `type="button"`, new Tailwind class without rebuilding CSS | Should fix |
| **MEDIUM (suggestion)** | Optional UX improvement | Optional |
| **LOW** | Nitpick (missing aria-label, copy-button text length) | Informational |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "...",
  "notes": ""
}
```
