# I00103_S03_Frontend_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Allowed: testcontainer fixtures, read-only docker introspection, `./ai-core.sh` / `make`. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00103 --json`.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00103/I-00103_Functional.md` -- Functional summary.
- `ai-dev/active/I-00103/reports/I-00103_S01_Backend_report.md` -- Backend report (read to confirm the field name and schema landed exactly as `per_file_errors` with the documented dict shape).
- `dashboard/templates/fragments/auto_merge_event_detail.html` -- File you'll modify.
- `dashboard/static/styles.css` -- For optional class-name additions (plain CSS — see CLAUDE.md "MUST append plain CSS rules directly..." rule).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S03_Frontend_report.md` -- Step report.

## Context

S01 added a new `per_file_errors` field to the `merge_auto_resolution_failed` event metadata. Your job is to render that field as a labelled section in the dashboard event-detail modal — above the existing raw JSON dump — so the operator sees the failure reason at a glance.

Read the design document first, especially:

- `## Browser Evidence` — `evidences/pre/I-00103-bug-event-80689-missing-error.png` shows the current modal. The new section goes above the "Metadata" `<details>` block currently at the bottom of the template.
- `## Acceptance Criteria` — AC3 (render when present), AC4 (hide when absent or empty).
- `## TDD Approach` — note the test file `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` and the CSS-assertion lesson from I-00067 (use `class="..."` attribute-scoped assertions, not bare substring).

## Requirements

### 1. Add a "Per-file errors" section to `auto_merge_event_detail.html`

Insert the new section into `dashboard/templates/fragments/auto_merge_event_detail.html`, positioned **above** the existing `<details>` block that renders the raw JSON metadata. Suggested placement: after the "Message" paragraph at `<div>...<h4>Message</h4>...</div>` and before the `<div>...<h4>Metadata</h4>...</div>` block.

Render the section ONLY when `event.metadata.per_file_errors` is present **and** non-empty. Use a Jinja2 guard like:

```jinja2
{% set per_file_errors = event.metadata.get('per_file_errors') if event.metadata else None %}
{% if per_file_errors %}
  <div class="auto-merge-modal__per-file-errors">
    <h4>Per-file errors</h4>
    {% for entry in per_file_errors %}
      <div class="auto-merge-modal__per-file-error">
        <dl>
          <div><dt>file</dt><dd class="font-mono">{{ entry.file_path }}</dd></div>
          <div><dt>runtime</dt><dd class="font-mono">{{ entry.cli_tool }}/{{ entry.model }}</dd></div>
          <div><dt>error</dt><dd><pre class="auto-merge-modal__error-text">{{ entry.error }}</pre></dd></div>
        </dl>
      </div>
    {% endfor %}
  </div>
{% endif %}
```

Adapt the exact class names and DL/DT/DD pattern to match the existing template's style. Keep the markup minimal — the existing fragment uses a `<dl>` with `<dt>`/`<dd>` and Tailwind-utility classes; mirror that.

### 2. Render the error text faithfully

The `error` value is a free-form string returned by the LLM runtime (timeouts, exit codes, exception messages). It can contain newlines, JSON, or angle brackets. Wrap it in a `<pre>` (or set CSS `white-space: pre-wrap`) so multi-line errors are readable. Do NOT escape past what Jinja2 autoescape already provides — `{{ entry.error }}` is sufficient; do NOT use `| safe`.

### 3. Hide gracefully when the field is absent or empty

If `event.metadata` is None, OR `event.metadata.per_file_errors` is missing, OR it is an empty list, the section MUST NOT render. No empty "Per-file errors" header, no empty card. Verify with the second test in `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py::test_event_detail_hides_per_file_errors_section_when_absent`.

### 4. CSS — append plain rules to styles.css if needed

Per `CLAUDE.md`, when `make css` reports "Nothing to be done" or the Tailwind CLI fails (e.g., missing `postcss-selector-parser`), **append plain CSS rules directly to `dashboard/static/styles.css`** — plain CSS is served as-is.

For this fix, minimal styling is required: the new section should visually fit the existing modal. If you reuse existing Tailwind utility classes already used elsewhere in the fragment (e.g. `text-muted-foreground`, `font-mono`), no new CSS is needed. If you introduce new class names (e.g. `auto-merge-modal__per-file-errors`), add a few plain CSS rules at the bottom of `dashboard/static/styles.css` to give them minimal visual weight (1-line margin / padding rules are enough). Keep this additive — do NOT modify existing CSS rules.

### 5. Preserve existing fragment behaviour

The existing "Message" paragraph, the existing "Metadata" `<details>` block with its "Copy as JSON" button, and the existing top-of-modal `<dl>` with timestamp / type / entity_type / entity_id / project_id MUST render exactly as before. Your new section is additive only.

## Project Conventions

- Read `CLAUDE.md` and `dashboard/CLAUDE.md` for Jinja2 / htmx patterns.
- The fragment is server-rendered Jinja2 — no JS framework. Match existing template style.
- **Format string lesson from I-00075**: keep Jinja2 `format`-filter calls `%`-style: `"%dm%02ds"|format(m, s)`, never `str.format`-style. The fragment runs through `scripts/check_templates.py` in `make lint`.
- Autoescape is on by default; do NOT add `| safe` to user/error text.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck       # likely no-op for template-only changes
make lint            # includes scripts/check_templates.py
```

Fix any issues these report on `auto_merge_event_detail.html` or `styles.css`.

## Test Verification (NON-NEGOTIABLE)

Targeted run only — the new test file in S05 may not exist yet at S03 time. Verify your template at least renders syntactically by running:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v 2>&1 | tail -30
```

The existing route tests exercise the same fragment. Do NOT run `make test-frontend` (that's the S14 QV gate).

## TDD Note

This step is template-only. Use `tdd_red_evidence: "n/a — template/markdown edits only, no production logic; behavioural tests delegated to S05 per design doc TDD Approach"`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00103",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/auto_merge_event_detail.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template/markdown edits only, no production logic; behavioural tests delegated to S05 per design doc TDD Approach",
  "blockers": [],
  "notes": ""
}
```

If you also touched `dashboard/static/styles.css`, add it to `files_changed`.
