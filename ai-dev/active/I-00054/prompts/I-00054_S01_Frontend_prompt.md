# I-00054_S01_Frontend_prompt

**Work Item**: I-00054 -- Coverage Page Toggle Label Does Not Update on Expand/Collapse
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step — no database changes required.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00054 --json`
- `ai-dev/active/I-00054/I-00054_Issue_Design.md` — Design document (read this first)
- `dashboard/templates/pages/system/coverage.html` — The only file to modify
- `dashboard/CLAUDE.md` — Dashboard conventions

## Output Files

- `dashboard/templates/pages/system/coverage.html` — Modified template
- `ai-dev/active/I-00054/reports/I-00054_S01_Frontend_report.md` — Step report

## Context

You are fixing a UX bug in the coverage page toggle. The `/system/coverage` page shows a table of packages; each row can be clicked to expand a file-level breakdown via htmx. The bug: the "click to expand" label never changes to "click to collapse" after expanding, and clicking an expanded row does not collapse it.

Read the full design document before starting. The fix is **template-only** — no backend, no new routes, no service changes.

## Requirements

### 1. Add toggle state attributes to each package row

In `dashboard/templates/pages/system/coverage.html`, modify the `<tr>` at lines 73–79 to add:
- `data-pkg-toggle="{{ pkg.name }}"` — identifies the row for the JS collapse handler
- `data-expanded="false"` — tracks expanded/collapsed state
- Modify `hx-trigger` to guard against re-fetching when already expanded:
  ```
  hx-trigger="click[this.dataset.expanded!='true'], keydown[key=='Enter'][this.dataset.expanded!='true']"
  ```

The guard condition is critical: it prevents htmx from firing a new request when the row is already expanded. When `data-expanded` is `'true'`, only the vanilla JS collapse handler runs.

### 2. Add an id to the label cell

Modify the label `<td>` at line 92 to add `id="expand-label-{{ pkg.name }}"`:
```html
<td id="expand-label-{{ pkg.name }}" class="px-4 py-3 text-xs text-muted-foreground">click to expand</td>
```

This gives the JS handler a stable selector to update the label text.

### 3. Add the toggle script block

At the bottom of `{% block content %}`, before the closing `</div>`, add:

```html
<script>
  (function () {
    // Collapse handler — fires when row is already expanded (htmx is guarded out)
    document.querySelectorAll('[data-pkg-toggle]').forEach(function (row) {
      var pkgName = row.dataset.pkgToggle;
      row.addEventListener('click', function () {
        if (row.dataset.expanded === 'true') {
          var filesDiv = document.getElementById('files-' + pkgName);
          var label = document.getElementById('expand-label-' + pkgName);
          if (filesDiv) filesDiv.innerHTML = '';
          row.dataset.expanded = 'false';
          if (label) label.textContent = 'click to expand';
        }
      });
    });

    // After htmx injects content, mark row as expanded and update label
    document.body.addEventListener('htmx:afterSwap', function (evt) {
      var target = evt.detail.target;
      if (!target || !target.id || !target.id.startsWith('files-')) return;
      var pkgName = target.id.slice('files-'.length);
      var row = document.querySelector('[data-pkg-toggle="' + pkgName + '"]');
      var label = document.getElementById('expand-label-' + pkgName);
      if (row && label) {
        row.dataset.expanded = 'true';
        label.textContent = 'click to collapse';
      }
    });
  }());
</script>
```

**How it works**:
- On expand click: htmx fires (because `data-expanded` is `'false'`) → injects content → `htmx:afterSwap` fires → JS sets `data-expanded='true'` and label to "click to collapse".
- On collapse click: `data-expanded` is `'true'` → htmx trigger guard blocks the request → vanilla JS click listener clears the div, resets `data-expanded='false'`, resets label to "click to expand".

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for all conventions. Key points:
- Templates in `dashboard/templates/pages/` extend `base.html`
- htmx is the primary interaction layer — JavaScript is supplemental only
- Tailwind CSS is prebuilt — avoid adding new dynamic class constructions
- Fragment templates in `dashboard/templates/fragments/` are NOT affected by this change
- Run `make css` if and only if you add new Tailwind classes (this fix adds none)

## TDD Requirement

This is a template-only fix. The test for this step lives in S03 (Tests agent). However, before reporting complete:

1. Manually verify the template renders correctly by reading the modified file and checking that all three changes (data attributes on `<tr>`, id on `<td>`, and `<script>` block) are present.
2. Run `make lint` to check no JS linting violations were introduced (the Makefile runs `node --check` on `dashboard/static/**/*.js` — inline `<script>` blocks are not linted, but confirm this is the case).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — runs `ruff format --check .` to verify Python files are formatted. This fix is HTML/JS only (ruff doesn't process Jinja2 templates), so this should be a no-op unless unrelated drift is present. If it fails, run `uv run ruff format .` to auto-fix and re-run the check.
2. **`make typecheck`** — must report zero errors in files you touched. HTML templates are not type-checked, so this should be a no-op for this step.
3. **`make lint`** — must report zero errors.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/system/coverage.html"
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
