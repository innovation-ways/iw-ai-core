# CR-00038 S01 — Frontend Implementation

**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. Do not run alembic against the live DB.

## Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md` before starting. Key rules:
- Templates under `dashboard/templates/fragments/` MUST NOT extend `base.html`.
- Append new CSS rules to `dashboard/static/styles.css` if `make css` fails or reports "Nothing to be done" — plain CSS is served as-is.
- Do NOT use `navigator.clipboard` directly; use `window.iwClipboard.copy()`.
- SSE pattern: htmx `hx-ext="sse"` or plain `EventSource` — either is acceptable, but `EventSource` with explicit `close()` is preferred for the running-jobs strip to avoid connection leaks on htmx swaps.

## Objective

Implement three related UX improvements to `dashboard/templates/docs_library.html` and its supporting backend:

1. **Filter bar redesign**: Replace the three-row pill/input layout with a single compact row (two `<select>` + search `<input>`).
2. **Running-jobs strip**: Add a `<div id="docs-running-jobs">` between the filter bar and the doc grid that shows active `DocGenerationJob` rows with live SSE feedback.
3. **Generate button fix**: Change the `docs_generate` POST response so the button goes disabled/grey (instead of returning a never-stopping spinner), and fire `runningJobsReload` to populate the strip.

---

## Change 1 — Filter Bar Redesign (`docs_library.html`)

**Current state** (`dashboard/templates/docs_library.html`, lines 48–117):
- Lines 50–72: Type pill buttons row
- Lines 75–97: Status pill buttons row
- Lines 99–116: Search `<input>` block (max-w-md standalone)

**Replace the entire `<!-- Filter Bar -->` section** (lines 48–117) with:

```html
<!-- Filter Bar -->
<div class="mb-4">
  <form id="docs-filter-form" class="flex items-center gap-3 flex-wrap">
    <!-- Type -->
    <div class="flex items-center gap-1.5">
      <label for="docs-filter-type" class="text-xs text-muted-foreground font-medium whitespace-nowrap">Type</label>
      <select id="docs-filter-type"
              name="doc_type"
              hx-get="/project/{{ current_project.id }}/api/docs/search"
              hx-trigger="change"
              hx-target="#docs-grid"
              hx-swap="innerHTML"
              hx-include="#docs-filter-form"
              class="docs-filter-select text-sm bg-input border border-border rounded-md px-2 py-1.5 text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
        <option value="">All</option>
        {% for dtype in doc_types %}
        <option value="{{ dtype }}">{{ dtype|title }}</option>
        {% endfor %}
      </select>
    </div>

    <!-- Status -->
    <div class="flex items-center gap-1.5">
      <label for="docs-filter-status" class="text-xs text-muted-foreground font-medium whitespace-nowrap">Status</label>
      <select id="docs-filter-status"
              name="status"
              hx-get="/project/{{ current_project.id }}/api/docs/search"
              hx-trigger="change"
              hx-target="#docs-grid"
              hx-swap="innerHTML"
              hx-include="#docs-filter-form"
              class="docs-filter-select text-sm bg-input border border-border rounded-md px-2 py-1.5 text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
        <option value="">All</option>
        {% for s in statuses %}
        <option value="{{ s }}">{{ s|title }}</option>
        {% endfor %}
      </select>
    </div>

    <!-- Search -->
    <div class="relative flex-1 min-w-[180px] max-w-sm">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none"
           fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
      </svg>
      <input type="text"
             id="docs-search-input"
             name="q"
             placeholder="Search documentation…"
             hx-get="/project/{{ current_project.id }}/api/docs/search"
             hx-trigger="input changed delay:300ms"
             hx-target="#docs-grid"
             hx-swap="innerHTML"
             hx-include="#docs-filter-form"
             class="w-full pl-10 pr-4 py-1.5 bg-input border border-border rounded-md text-sm
                    text-foreground placeholder:text-muted-foreground
                    focus:outline-none focus:ring-2 focus:ring-ring"/>
    </div>
  </form>
</div>
```

If the `<select>` elements do not render with correct background/foreground colours after `make css` (or `make css` is unavailable), append these rules to `dashboard/static/styles.css`:

```css
.docs-filter-select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.5rem center;
  padding-right: 2rem;
  cursor: pointer;
}
```

---

## Change 2 — Running-Jobs Strip Container (`docs_library.html`)

**After** the closing `</div>` of the `<!-- Filter Bar -->` block and **before** the `<!-- Card Grid -->` block, insert:

```html
<!-- Running Jobs Strip -->
<div id="docs-running-jobs"
     hx-get="/project/{{ current_project.id }}/api/docs/running-jobs"
     hx-trigger="load, runningJobsReload from:body"
     hx-swap="innerHTML">
</div>
```

---

## Change 3 — New Fragment: `docs_running_jobs.html`

Create `dashboard/templates/fragments/docs_running_jobs.html`. This fragment MUST NOT extend `base.html`.

```html
{% if running_jobs %}
<div class="mb-4 space-y-2">
  {% for item in running_jobs %}
  <div id="docs-rjob-{{ item.job_id }}"
       class="flex items-center justify-between gap-3 px-4 py-2.5 bg-primary/5 border border-primary/20 rounded-lg text-sm transition-colors">
    <div class="flex items-center gap-3 min-w-0">
      <svg class="animate-spin w-4 h-4 text-primary flex-shrink-0" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <span class="font-medium text-foreground truncate">{{ item.doc_title }}</span>
      <span class="text-muted-foreground text-xs flex-shrink-0" id="rjob-elapsed-{{ item.job_id }}">0:00</span>
    </div>
    <button hx-delete="/project/{{ project_id }}/api/docs/jobs/{{ item.job_id }}"
            hx-target="#docs-rjob-{{ item.job_id }}"
            hx-swap="outerHTML"
            hx-confirm="Cancel this generation job?"
            class="text-xs text-muted-foreground hover:text-red-500 transition-colors px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 flex-shrink-0"
            aria-label="Cancel generation">
      Cancel
    </button>
  </div>

  <script>
  (function() {
    var jobId = {{ item.job_id | tojson }};
    var projectId = {{ project_id | tojson }};
    var docId = {{ item.doc_id | tojson }};

    // Deduplicate: close any existing EventSource for this job
    window._docJobSources = window._docJobSources || {};
    if (window._docJobSources[jobId]) {
      window._docJobSources[jobId].close();
      delete window._docJobSources[jobId];
    }

    // Elapsed timer
    var startTs = Date.now();
    var timerId = setInterval(function() {
      var el = document.getElementById('rjob-elapsed-' + jobId);
      if (!el) { clearInterval(timerId); return; }
      var s = Math.floor((Date.now() - startTs) / 1000);
      el.textContent = Math.floor(s / 60) + ':' + (s % 60 < 10 ? '0' : '') + (s % 60);
    }, 1000);

    // SSE stream
    var url = '/project/' + projectId + '/api/docs/jobs/' + jobId + '/stream';
    var source = new EventSource(url);
    window._docJobSources[jobId] = source;

    function cleanup(className) {
      clearInterval(timerId);
      source.close();
      delete window._docJobSources[jobId];
      // Optionally colour the row before it disappears
      var row = document.getElementById('docs-rjob-' + jobId);
      if (row && className) {
        row.classList.add(className);
      }
      // Signal strip and card to update
      setTimeout(function() {
        document.body.dispatchEvent(new CustomEvent('runningJobsReload'));
      }, className ? 1200 : 0);
      document.body.dispatchEvent(new CustomEvent('docJobCompleted', {detail: {job_id: jobId, doc_id: docId}}));
    }

    source.addEventListener('completed', function() { cleanup(null); });
    source.addEventListener('failed', function(e) {
      try {
        var data = JSON.parse(e.data);
        document.body.dispatchEvent(new CustomEvent('docJobFailed', {detail: {job_id: jobId, doc_id: data.doc_id || docId, error: data.error}}));
      } catch(_) {}
      cleanup('border-red-400 bg-red-50 dark:bg-red-900/20');
    });
    source.addEventListener('timeout', function() { cleanup(null); });
    source.onerror = function() {
      // On stream error, reload the strip after a short delay to re-check
      clearInterval(timerId);
      source.close();
      delete window._docJobSources[jobId];
      setTimeout(function() {
        document.body.dispatchEvent(new CustomEvent('runningJobsReload'));
      }, 3000);
    };
  })();
  </script>
  {% endfor %}
</div>
{% endif %}
```

---

## Change 4 — New Backend Endpoint (`dashboard/routers/docs.py`)

Add this endpoint **after** the `docs_job_cancel` endpoint (around line 537):

```python
@router.get("/api/docs/running-jobs", response_class=HTMLResponse)
def docs_running_jobs(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: running DocGenerationJob rows for the project."""
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob, DocType, ProjectDoc

    jobs = (
        db.query(DocGenerationJob)
        .join(ProjectDoc, DocGenerationJob.doc_id == ProjectDoc.id)
        .filter(
            DocGenerationJob.doc_id.startswith(f"{project_id}:"),
            DocGenerationJob.status == JobStatus.running,
            ProjectDoc.doc_type != DocType.research,
        )
        .order_by(DocGenerationJob.requested_at.asc())
        .all()
    )
    svc = DocService(db)
    running_jobs: list[dict] = []
    for job in jobs:
        doc_id_short = job.doc_id.split(":")[-1] if job.doc_id else ""
        doc = svc.get_doc(project_id, doc_id_short)
        running_jobs.append(
            {
                "job_id": job.id,
                "doc_id": doc_id_short,
                "doc_title": doc.title if doc else doc_id_short,
            }
        )
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_running_jobs.html",
        {"running_jobs": running_jobs, "project_id": project_id},
    )
```

---

## Change 5 — Fix `docs_generate` Response (`dashboard/routers/docs.py`)

**Current** (around lines 367–378 in `docs_generate`):
```python
job = svc.create_doc_job(project_id, doc_id)
db.commit()

templates: Jinja2Templates = request.app.state.templates
response = templates.TemplateResponse(
    request,
    "fragments/docs_generate_running.html",
    {"job": job, "doc_id": doc_id, "project_id": project_id},
)
response.headers["HX-Trigger"] = (
    f'{{"docJobCreated": {{"job_id": "{job.id}", "doc_id": "{doc_id}"}}}}'
)
return response
```

**Replace with**:
```python
import json as _json

job = svc.create_doc_job(project_id, doc_id)
db.commit()

disabled_btn = (
    '<button disabled '
    'class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-muted text-muted-foreground '
    'rounded-md text-sm font-medium cursor-not-allowed opacity-60 select-none" '
    'aria-label="Generation queued">'
    '<svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4">'
    '</circle>'
    '<path class="opacity-75" fill="currentColor" '
    'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 '
    '3.042 1.135 5.824 3 7.938l3-2.647z"></path>'
    '</svg>'
    'Queued…'
    '</button>'
)
response = HTMLResponse(disabled_btn)
response.headers["HX-Trigger"] = _json.dumps(
    {
        "docJobCreated": {"job_id": job.id, "doc_id": doc_id},
        "runningJobsReload": None,
    }
)
return response
```

Note: `import json as _json` should be placed at the top of the file with the other imports (or use the existing `json` import if one exists already — check before adding).

---

## Change 6 — Delete `docs_generate_running.html`

The file `dashboard/templates/fragments/docs_generate_running.html` is no longer referenced after Change 5. Delete it:

```bash
rm dashboard/templates/fragments/docs_generate_running.html
```

---

## Verification

After implementing all changes, run:

```bash
make lint
make type-check
```

Fix any issues before marking the step done.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "CR-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/docs_library.html",
    "dashboard/templates/fragments/docs_card.html",
    "dashboard/templates/fragments/docs_running_jobs.html",
    "dashboard/routers/docs.py",
    "dashboard/static/styles.css"
  ],
  "files_deleted": [
    "dashboard/templates/fragments/docs_generate_running.html"
  ],
  "preflight": {
    "lint": "ok|failed:<reason>",
    "typecheck": "ok|failed:<reason>"
  },
  "blockers": [],
  "notes": ""
}
```
