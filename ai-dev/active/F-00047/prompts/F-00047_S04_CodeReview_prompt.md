# F-00047 S04 — Code Review: Frontend Templates + JS

## Mission

Review all frontend work produced in S03 for correctness, completeness, accessibility, and adherence to project conventions.

## Required Reading

1. `CLAUDE.md` — architecture rules
2. `dashboard/CLAUDE.md` — template and styling conventions
3. `ai-dev/active/F-00047/F-00047_Feature_Design.md` — feature specification and wireframes
4. `ai-dev/active/F-00047/prompts/F-00047_S03_Frontend_prompt.md` — what was asked of S03
5. All files created or modified by S03:
   - `dashboard/templates/base.html`
   - `dashboard/templates/fragments/nav_projects.html`
   - `dashboard/templates/project_code.html`
   - `dashboard/templates/fragments/code_job_status.html`
   - `dashboard/templates/fragments/code_empty_state.html`
   - `dashboard/templates/fragments/code_architecture_view.html`
   - `dashboard/templates/fragments/code_job_report.html`

## Review Checklist

### Template Structure
- [ ] `project_code.html` extends `base.html`
- [ ] All `fragments/code_*.html` do NOT extend `base.html`
- [ ] `{% block title %}` set correctly in `project_code.html`
- [ ] `current_project` passed to template and used for sidebar highlight
- [ ] All Jinja2 template variables from the route context are used correctly (no undefined variables)
- [ ] `| safe` filter applied to `content_html` in `code_architecture_view.html`

### Nav Link
- [ ] "Code" link added to `nav_projects.html` after "Research"
- [ ] Link href is `/project/{{ project.id }}/code` (correct format matching existing links)
- [ ] Active state highlighting works via the existing path-prefix logic

### Mermaid Integration
- [ ] `mermaid.min.js` CDN script added to `base.html` after `marked.min.js`
- [ ] `mermaid.initialize()` called with `startOnLoad: true`
- [ ] `htmx:afterSwap` listener re-initializes `.mermaid` nodes injected by htmx
- [ ] Only unprocessed nodes re-initialized (check for `[data-processed]` guard)
- [ ] `.mermaid` divs render correctly — verify the route handler pre-processes fenced code blocks

### SSE Client (code_job_status.html)
- [ ] Uses vanilla JS `EventSource` — NOT `hx-ext="sse"` (explicit requirement)
- [ ] `es.close()` called on `done` event and on `onerror`
- [ ] DOM elements updated by ID (`getElementById`) — no jQuery or framework
- [ ] Progress bar width set via `element.style.width = pct + '%'` (valid inline style for dynamic value)
- [ ] Elapsed timer uses `setInterval` and is cleared when EventSource closes
- [ ] After `done` event: `htmx.ajax()` called to refresh both `#code-status-panel` and `#code-architecture-panel`
- [ ] `JSON.parse` wrapped in try/catch

### Dropdown Button
- [ ] Uses pure CSS/JS — no third-party components
- [ ] `toggleCodeDropdown()` function defined and called by the button's `onclick`
- [ ] Outside-click listener closes the dropdown
- [ ] All three POST buttons present: full index, incremental, regen-map
- [ ] Correct `hx-post` URLs matching S01's router paths
- [ ] `hx-target="#code-status-panel"` and `hx-swap="innerHTML"` on all three
- [ ] Loading state: buttons disabled during in-flight POST request

### Styling and Accessibility
- [ ] No dynamic class string construction (e.g., no `"text-" + var`)
- [ ] Dark mode variants present where color is used (`dark:bg-*`, `dark:text-*`)
- [ ] Color tokens used: `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `bg-primary`, `text-primary-foreground`
- [ ] Progress bar has `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`
- [ ] Spinner has `aria-label` and `role="status"`
- [ ] Dropdown button has `aria-expanded` attribute
- [ ] Dropdown menu has `role="menu"`

### Empty State
- [ ] Shows when `index_status` is None or `index_status.level1_doc_markdown` is None
- [ ] "Generate Code Map" button present with correct `hx-post`
- [ ] Provider/model info shown if `index_status` is available

### Architecture View
- [ ] `.prose-doc` CSS styles applied (either via `<style>` block or verified as globally available)
- [ ] `.mermaid` divs have correct CSS: `text-align: center`, max-width constraint
- [ ] Content is scrollable with `overflow-y-auto` and reasonable max-height

### Job Report
- [ ] Uses green color scheme for success state
- [ ] Shows duration, files, chunks, languages, models
- [ ] Field names used: `files_indexed`, `chunks_created`, `languages_detected`, `llm_model`, `embed_model` (F-00045 schema). NO references to `chat_model`, `languages_json`, `duration_formatted`, or `completed_recently` anywhere in the template.
- [ ] Duration comes from the route-provided `last_completed_duration` context variable (not from a non-existent `last_completed_job.duration_formatted` attribute)
- [ ] "Recent" check uses `last_completed_recent` context variable (not `last_completed_job.completed_recently`)

### Context Variable Names
- [ ] `index_status.llm_model` (not `chat_model`)
- [ ] `index_status.level1_doc_markdown` (not `level1_doc`)
- [ ] `index_status.languages_detected` (not `languages_json`)

## Output Format

```
## Review Result: PASS | FAIL | PASS WITH NOTES

### Critical Issues (must fix before QV gates)
- ...

### Minor Issues (should fix before QV gates)
- ...

### Suggestions (optional)
- ...
```

List exact file and location for each issue found.
