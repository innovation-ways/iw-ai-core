# F-00079_S07_Template_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S07
**Agent**: template-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Migration was added in S01.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `dashboard/routers/docs.py:169` and `:861` — existing WeasyPrint integration to mirror
- `dashboard/templates/exports/` — likely-existing PDF templates to mirror brand patterns (check first)
- `orch/diff_service.py` — for the unidiff parser used to feed the template context
- IW brand palette tokens (see `theme.css` / `styles.css` for `--color-primary`, `--color-foreground`, etc.)

## Output Files

- New: `dashboard/templates/exports/diff_pdf.html`
- `ai-dev/active/F-00079/reports/F-00079_S07_Template_report.md`

## Context

You are creating the WeasyPrint Jinja template for the "Export PDF" action on the Files tab. The route handler in S05 (`/files/export.pdf`) renders this template with a parsed diff summary and per-file Pygments-highlighted hunks, then pipes the HTML to WeasyPrint.

Read the design document's `Functional Requirements` (`Rendering` section) and `Acceptance Criteria` AC4 in full.

## Requirements

### 1. Template structure

`dashboard/templates/exports/diff_pdf.html` should produce a single self-contained HTML document (not extending `base.html`) suitable for WeasyPrint. Sections:

1. **Header** — work-item ID + title, item type, timestamp (`now() ISO`), step label (`All steps` or specific step name), aggregate `+N −M` counts and total file count.
2. **Summary table** — one row per file in `summary_files + truncated_files` (every file in the changeset, including those omitted from the body). Columns:
   - Status badge (colored cell with letter)
   - Path (with old → new for renames)
   - `+added` / `−removed`
   - "Generated" tag if `is_generated`
3. **Per-file diff sections** — one section per entry in `summary_files` whose `hunks_html` is not None (i.e., text file, ≤5000 lines, within the body cap):
   - Sticky-style header with file path and counts
   - `{{ file.hunks_html | safe }}` — pre-rendered Pygments output, never re-escape
4. **Truncation notes** inline in the per-file sections — for files ≥5000 lines (`hunks_html is None` and `is_binary is False`), render "Diff omitted — too large for PDF (X lines)" placeholder instead of hunks.
5. **Binary placeholder** — for binary files (`is_binary is True`), render "Binary file — N bytes" placeholder.
6. **Body cap footer note** — when `truncated_files` is non-empty, append a section after the per-file diffs: "{{ truncated_files | length }} additional files omitted from this PDF body (still listed in the summary table). PDF caps the body at 100 files alphabetical-by-path."
7. **Footer** — IW branding line, page numbers via `@page` CSS (`counter(page)` / `counter(pages)`).

### 2. Pygments integration and template context contract

The route in S05 calls Pygments to syntax-highlight each file's hunks BEFORE passing them to the template (highlighting lives in the route layer; the template stays a pure renderer). The canonical context shape (mirrored in `F-00079_S05_API_prompt.md` §4 — keep these in sync):

```python
{
    "item": WorkItem,                # for header (id, title, type)
    "project_id": str,
    "step_label": str,               # "All steps (aggregate)" or the specific step name
    "aggregate_added": int,
    "aggregate_removed": int,
    "aggregate_file_count": int,     # sum across summary_files + truncated_files
    "summary_files": list[dict],     # files rendered in the body (≤100 entries)
    "truncated_files": list[dict],   # files past the 100-file body cap (summary-only)
    "generated_at": datetime,        # for the header timestamp
}
```

Each entry in `summary_files` and `truncated_files` is:

```python
{
    "path": str,
    "status": "A" | "M" | "D" | "R",
    "added": int,
    "removed": int,
    "is_generated": bool,
    "is_binary": bool,
    "old_path": str | None,         # only for status=="R"
    "hunks_html": str | None,        # Markup-safe Pygments HTML; None for binary, ≥5000-line, or truncated_files entries
}
```

Template emits `{{ file.hunks_html | safe }}` — never re-escape Pygments HTML.

Do NOT introduce alternative names like `summary` or `files`. If S05 ships with a different shape, file a finding in your report and have S08 reconcile.

### 3. CSS / branding

- Embed CSS inline in the template (`<style>...</style>` in `<head>`) — WeasyPrint resolves relative URLs only if `base_url` is set, so inline is safest.
- Use the IW palette via CSS custom properties or hardcoded values from `theme.css`. Match the look-and-feel of existing PDF exports under `dashboard/templates/exports/` (inspect first).
- Status colors: green for adds, red for removes, amber for modified, blue for renames. Use both color AND a letter (WCAG 1.4.1).
- `@page` rule for size (A4), margins (~20 mm), and a footer with page numbers (`counter(page)` / `counter(pages)`).
- Print-friendly: line-wrap long lines; preserve monospace within hunks; small font for code (8.5 pt is reasonable).

### 4. Empty-state handling

If the diff is empty (no files), render a minimal one-page PDF: header + "No changes recorded for this item" message. Do not error.

### 5. Branding consistency

Read existing PDF templates in the project (e.g., `dashboard/templates/exports/*` — list them first) and match the header/footer style, font choices, and palette. Do not invent a new visual identity.

## Project Conventions

- Jinja2 templates use `{% raw %}` only when necessary; the diff content is pre-rendered HTML and should be marked safe at the route layer.
- Inline `<style>` is acceptable for PDF templates because of WeasyPrint's URL resolution constraints.
- Brand palette comes from `theme.css` / `styles.css` — read those once and stay consistent.

## TDD Requirement

PDF rendering is integration-tested in S09 (the route returns `application/pdf` with non-empty body). For this step:
- Manually render the template via WeasyPrint with a synthetic context (a small Python snippet in `tests/integration/test_files_tab.py` will do this in S09; you can prototype with `uv run python -c "..."` to confirm WeasyPrint accepts the HTML).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` (Jinja templates are not auto-formatted; this primarily ensures Python files you touched are formatted)
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. WeasyPrint can render the template without errors (smoke-test by calling the route via `make test-integration` if S05 / S09 have wired it up; otherwise document a manual verification).

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "template-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/exports/diff_pdf.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
