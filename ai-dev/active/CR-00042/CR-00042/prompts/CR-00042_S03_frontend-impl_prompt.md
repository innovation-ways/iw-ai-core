# CR-00042_S03_frontend-impl_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does not touch migrations.

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — full design and acceptance criteria
- `ai-dev/active/CR-00042/reports/CR-00042_S02_code_review_report.md` — S02 review findings (fix any CRITICAL/HIGH before proceeding)
- `dashboard/templates/_partials/help/*.html` — all 22 files to update
- `dashboard/routers/help.py` — the `_SLUG_TO_DOC` dict added in S01 (reference for which slugs exist)

## Output Files

- `dashboard/templates/_partials/help/*.html` — 22 files updated
- `ai-dev/active/CR-00042/reports/CR-00042_S03_frontend-impl_report.md` — step report

## Context

S01 added a `_SLUG_TO_DOC` dict to `help.py` and updated `_render_help_fragment` to pass `docs_link` as Jinja2 context. Your job is to update all 22 help partial templates to use that variable instead of the old hardcoded hrefs.

## Requirements

### 1. Update all 22 help partial templates

For each file in `dashboard/templates/_partials/help/`:

```
all_active.html    batch_detail.html  batches.html    code.html
config.html        containers.html    coverage.html   docs.html
history.html       item_detail.html   job_detail.html jobs.html
keep_alive.html    projects.html      quality.html    queue.html
research.html      running.html       search.html     status.html
tests.html         worktrees.html
```

In each file, find the footer link:
```html
<a class="help-content__docs-link" href="...">Open full docs →</a>
```

Replace the hardcoded `href="..."` with `href="{{ docs_link }}"`:
```html
<a class="help-content__docs-link" href="{{ docs_link }}">Open full docs →</a>
```

Do not change anything else — the link text, CSS class, or surrounding HTML must stay identical.

### 2. Verify the mapping is complete

After editing, run a quick grep to confirm no old-style hrefs remain:

```bash
grep -r 'href="/docs/' dashboard/templates/_partials/help/
grep -r 'href="/orch/' dashboard/templates/_partials/help/
```

Both commands must return zero results.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete:
1. `make format` — auto-fixes formatting
2. `make lint` — zero errors (HTML linting if configured)

## Test Verification

Run the existing help tests to ensure no regression:
```bash
uv run pytest tests/dashboard/test_help_fragments_present.py tests/dashboard/test_help_router.py -v
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/_partials/help/all_active.html",
    "dashboard/templates/_partials/help/batch_detail.html",
    "dashboard/templates/_partials/help/batches.html",
    "dashboard/templates/_partials/help/code.html",
    "dashboard/templates/_partials/help/config.html",
    "dashboard/templates/_partials/help/containers.html",
    "dashboard/templates/_partials/help/coverage.html",
    "dashboard/templates/_partials/help/docs.html",
    "dashboard/templates/_partials/help/history.html",
    "dashboard/templates/_partials/help/item_detail.html",
    "dashboard/templates/_partials/help/job_detail.html",
    "dashboard/templates/_partials/help/jobs.html",
    "dashboard/templates/_partials/help/keep_alive.html",
    "dashboard/templates/_partials/help/projects.html",
    "dashboard/templates/_partials/help/quality.html",
    "dashboard/templates/_partials/help/queue.html",
    "dashboard/templates/_partials/help/research.html",
    "dashboard/templates/_partials/help/running.html",
    "dashboard/templates/_partials/help/search.html",
    "dashboard/templates/_partials/help/status.html",
    "dashboard/templates/_partials/help/tests.html",
    "dashboard/templates/_partials/help/worktrees.html",
    "ai-dev/active/CR-00042/reports/CR-00042_S03_frontend-impl_report.md"
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
