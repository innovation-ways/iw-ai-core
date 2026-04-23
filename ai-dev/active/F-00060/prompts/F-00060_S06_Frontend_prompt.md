# F-00060_S06_Frontend_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S06 — Re-index Docs button
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Same rules as S01.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — see *Frontend Changes*
- `ai-dev/active/F-00060/reports/F-00060_S05_API_report.md` — endpoint path and fragment contract
- `dashboard/templates/project_code.html` — existing Code-view action dropdown (lines 38–73)
- `dashboard/templates/fragments/code_job_status.html` — the shared progress fragment

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S06_Frontend_report.md` (new)
- `dashboard/templates/project_code.html` (modified — new dropdown entry)
- `dashboard/templates/fragments/code_job_status.html` (modified — render `job_type`)

## Context

Single dropdown item on the Code view + a small tweak to the shared status
fragment so it labels doc-index rows correctly.

## Requirements

### 1. Dropdown entry — `project_code.html`

Inside the action dropdown that already contains "Generate Code Map",
"Re-index changed files", and "Regenerate Map", add:

```html
<button
  type="button"
  class="{{ same class as sibling entries }}"
  hx-post="/project/{{ current_project.id }}/api/code/reindex-docs"
  hx-target="{{ same target as sibling entries }}"
  hx-swap="{{ same as sibling }}"
>
  Re-index Docs
</button>
```

Position: immediately below "Re-index changed files" (the other index-family
action). Use the sibling buttons' exact CSS classes and htmx attributes so
visual parity is preserved. Do NOT introduce new CSS or JS.

### 2. Fragment parameterisation — `code_job_status.html`

If the fragment currently hardcodes "Code index" or similar, extend it to
render the human label from a template variable `job.type_label` (or
similar field) that is populated by the route. Acceptable implementations:

- Template passes a pre-rendered label and the fragment just prints it.
- Or a small `{% if job.type == "doc_indexing" %}Doc index{% else %}Code index{% endif %}` switch.

Pick the simpler option; match existing patterns in other shared fragments.

### 3. No new JS

All behaviour is htmx-driven. No `<script>` additions. No new npm
dependencies.

### 4. Local visual check

After implementation, render the page once (via the existing Jinja reproduction
test harness if available, otherwise a manual `make dev`-less Jinja render in a
Python REPL) and confirm:

- The new dropdown entry visually matches its siblings.
- The fragment renders the correct label for both `code_indexing` and
  `doc_indexing` jobs.

Include the rendered HTML snippets in the step report.

## Project Conventions

Read `dashboard/CLAUDE.md`. htmx + Jinja2; no frameworks. Fragments live in
`dashboard/templates/fragments/`. Avoid inline styles.

## TDD Requirement

Integration tests live in S07 (`test_reindex_docs_endpoint.py` asserts the
fragment response shape). This step's own checks are static:

- `grep -n 'reindex-docs' dashboard/templates/project_code.html` returns at
  least one match.
- `grep -n 'Re-index Docs' dashboard/templates/project_code.html` returns at
  least one match.
- Rendering the fragment with `job_type='doc_indexing'` in a unit test
  produces the label "Doc index" (or equivalent).

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` — pass.
3. `make test-unit` — pass (if Jinja reproduction tests exist).

## Subagent Result Contract

Standard JSON with `step: "S06"`, `agent: "frontend-impl"`, `work_item: "F-00060"`.
