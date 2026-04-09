# F-00001_S04_Frontend_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Step**: S04
**Agent**: Frontend

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- `ai-dev/work/F-00001/reports/F-00001_S03_API_report.md` -- API step report

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S04_Frontend_report.md` -- Step report

## Context

You are implementing the frontend changes for **Batch Archive with Post-Merge Actions**.

Read the design document first to understand the full scope and your step's deliverables. Then read `CLAUDE.md` for project-specific patterns and conventions.

The API endpoint and SSE event types were implemented in S03. You need to wire up the Archive button in the template.

## Requirements

### 1. Update `dashboard/templates/pages/project/batch_detail.html`

Replace the disabled Archive button placeholder (lines 73-78) with an active htmx button that follows the exact same pattern as the other batch action buttons.

**Current code (replace this):**
```html
{% elif batch_status in ('completed', 'completed_with_errors') %}
  <button disabled
          class="px-3 py-1.5 bg-muted text-muted-foreground rounded text-sm opacity-60 cursor-not-allowed">
    Archive
  </button>
```

**New code:**
```html
{% elif batch_status in ('completed', 'completed_with_errors') %}
  <button hx-get="/project/{{ current_project.id }}/api/confirm-batch/archive/{{ batch.id }}"
          hx-target="#confirm-dialog"
          hx-swap="innerHTML"
          class="px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm hover:opacity-90 transition-opacity">
    Archive
  </button>
```

This uses the same pattern as the Approve, Pause, Resume buttons:
- `hx-get` fetches the confirmation dialog fragment
- `hx-target="#confirm-dialog"` loads it into the dialog container
- `hx-swap="innerHTML"` replaces the container content
- The `confirm_batch_dialog()` endpoint in `actions.py` reads from `_BATCH_ACTION_LABELS["archive"]` (added in S03) and renders the dialog with a POST URL to `/project/{project_id}/api/batch/{batch_id}/archive`

### 2. Add archived status display

After the Archive button block, add a display for when the batch is already archived:

```html
{% elif batch_status == 'archived' %}
  <span class="px-3 py-1.5 text-muted-foreground text-sm">
    Archived
  </span>
```

This prevents showing action buttons on already-archived batches.

### 3. Verify SSE toast integration

The batch detail page extends `base.html` which includes the toast component and SSE EventSource listener. Verify that the `batch_archived`, `batch_archive_failed`, and `batch_archiving` event types (added to SSE in S03) will be picked up by the existing toast listener. If the batch detail page does NOT have an SSE listener, add one following the pattern in `pages/system/running.html`.

Check `base.html` for whether SSE is wired up globally or per-page. If per-page, you need to add:

```html
{% block extra_scripts %}
<script>
  var es = new EventSource('/api/stream/events');
  es.addEventListener('toast', function(e) {
    showToast(JSON.parse(e.data));
  });
</script>
{% endblock %}
```

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Framework-specific patterns (Jinja2 + htmx + Tailwind CDN)
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Frontend template changes are verified via browser verification in the QV gates. However, verify that the htmx attributes are correct by reading the existing patterns in the same template file.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run the project's unit test command
2. Run lint and type checking
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass with zero failures
4. If tests fail, fix them before reporting completion

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Frontend",
  "work_item": "F-00001",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/project/batch_detail.html"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
