# I-00054: Coverage Page Toggle Label Does Not Update on Expand/Collapse

**Type**: Issue
**Severity**: Low
**Created**: 2026-04-30
**Reported By**: Sergio (manual testing)
**Status**: Draft

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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

On the `/system/coverage` page, each package row has a "click to expand" label in its rightmost cell. Clicking a row fetches and injects file-level coverage details via htmx, but the label text never changes — it stays "click to expand" even when the row is fully expanded. Clicking the expanded row a second time does not collapse it; htmx re-fires the request and re-injects the same content, leaving the row permanently expanded with no way to collapse it.

## Project Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. The dashboard is FastAPI + Jinja2 + htmx + Tailwind CSS (no TypeScript, no Alpine.js). All toggle logic must be implemented in vanilla JavaScript within the template or a static JS file.

## Browser Evidence

Screenshots captured during investigation (2026-04-30):

- `evidences/pre/I-00054-before-expand.png` — initial page state, all rows show "click to expand"
- `evidences/pre/I-00054-after-expand-bug.png` — after clicking the `dashboard` row: file details are loaded and visible, but the label still reads "click to expand"
- `evidences/pre/I-00054-second-click-no-collapse.png` — after clicking the expanded row again: the row stays expanded, content unchanged, label still "click to expand"

## Steps to Reproduce

1. Navigate to `/system/coverage`
2. Click any package row (e.g. `dashboard`)
3. Observe that file-level details appear below the row
4. **Observe bug**: the rightmost cell still reads "click to expand" — it should read "click to collapse"
5. Click the same expanded row again
6. **Observe bug**: the row does not collapse; htmx re-fetches and re-injects the same content

**Expected**:
- After step 2: label changes to "click to collapse"
- After step 5: file details hide and label returns to "click to expand"

**Actual**:
- Label always reads "click to expand" regardless of state
- Second click re-fetches from server but the row stays expanded with no collapse

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/system/coverage"
# snapshot to find package row refs
playwright-cli snapshot
# click first package row to expand
playwright-cli click <package-row-ref>
playwright-cli snapshot   # label should now read "click to collapse"
playwright-cli screenshot
# click again to collapse
playwright-cli click <package-row-ref>
playwright-cli snapshot   # label should read "click to expand", file rows gone
playwright-cli screenshot
playwright-cli close
```

## Root Cause Analysis

**File**: `dashboard/templates/pages/system/coverage.html`

- **Line 92**: `<td class="px-4 py-3 text-xs text-muted-foreground">click to expand</td>` — the label text is static Jinja2 HTML, never modified by JavaScript.
- **Lines 73–79**: The `<tr>` row uses `hx-get`, `hx-target`, `hx-trigger="click, keydown[key=='Enter']"`, and `hx-swap="innerHTML"`. There is no `data-expanded` state attribute and no guard in the trigger condition, so htmx fires on every click regardless of whether the row is already expanded.
- **Line 96**: `<div id="files-{{ pkg.name }}"></div>` is the htmx target — content is injected here but nothing listens for the swap to update the row's state or label.

There is no JavaScript that:
1. Tracks whether a row is expanded or collapsed
2. Updates the label text after a successful htmx swap
3. Intercepts the click when expanded to collapse instead of refetching

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Coverage page template | `dashboard/templates/pages/system/coverage.html` | Static label, no toggle state, no collapse logic |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Add toggle state attributes to `<tr>` rows; add `id` to label cells; add guard condition to `hx-trigger`; add inline `<script>` block with `htmx:afterSwap` listener and collapse handler | — |
| S02 | CodeReview_Frontend | Review S01 output | — |
| S03 | Tests | Write reproduction test (template renders required data attributes and guard condition) + regression tests | — |
| S04 | CodeReview_Tests | Review S03 output | — |
| S05 | CodeReview_Final | Global cross-agent review | — |
| S06 | QV: lint | `make lint` | — |
| S07 | QV: format | `make format` | — |
| S08 | QV: typecheck | `make typecheck` | — |
| S09 | QV: unit-tests | `make test-unit` | — |
| S10 | QV: integration-tests | `make allure-integration` | — |
| S11 | QV Browser | Playwright — verify expand/collapse toggle and label flip end-to-end | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `dashboard/templates/pages/system/coverage.html`
- **Nature of change**: Add `data-pkg-toggle`, `data-expanded` attributes to each package `<tr>`; add `id="expand-label-{{ pkg.name }}"` to each label `<td>`; modify `hx-trigger` to guard on `this.dataset.expanded !== 'true'`; add a `<script>` block at the bottom of `{% block content %}` implementing the collapse handler and `htmx:afterSwap` state update.

### Detailed Fix Specification for S01

The implementation agent must make these precise changes to `dashboard/templates/pages/system/coverage.html`:

**1. Package row `<tr>` (line 73)** — add two data attributes:
```html
<tr class="border-t border-border hover:bg-muted/30 cursor-pointer"
    role="button"
    tabindex="0"
    data-pkg-toggle="{{ pkg.name }}"
    data-expanded="false"
    hx-get="/system/coverage/files/{{ pkg.name }}"
    hx-target="#files-{{ pkg.name }}"
    hx-trigger="click[this.dataset.expanded!='true'], keydown[key=='Enter'][this.dataset.expanded!='true']"
    hx-swap="innerHTML">
```

**2. Label `<td>` (line 92)** — add an `id`:
```html
<td id="expand-label-{{ pkg.name }}" class="px-4 py-3 text-xs text-muted-foreground">click to expand</td>
```

**3. Add a `<script>` block** at the bottom of `{% block content %}` (before `</div>` closing the outer div):
```javascript
<script>
  (function () {
    // Collapse handler — fires when row is already expanded
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

The guard condition `click[this.dataset.expanded!='true']` ensures htmx does NOT fire a new request when the row is already expanded — the vanilla JS click listener handles the collapse path instead.

## File Manifest

All files for this work item live under `ai-dev/active/I-00054/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00054_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00054_S01_Frontend_prompt.md` | Prompt | S01 — fix template toggle logic |
| `prompts/I-00054_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00054_S03_Tests_prompt.md` | Prompt | S03 — reproduction + regression tests |
| `prompts/I-00054_S04_CodeReview_Tests_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00054_S05_CodeReview_Final_prompt.md` | Prompt | S05 — global review |
| `prompts/I-00054_S11_BrowserVerification_prompt.md` | Prompt | S11 — Playwright verification |

Reports are created during execution in `ai-dev/active/I-00054/reports/`.

## Test to Reproduce

```python
def test_i00054_coverage_page_toggle_attributes_present(client: TestClient) -> None:
    """This test should FAIL before the fix and PASS after.

    Verifies the template renders the data attributes and hx-trigger guard
    that enable the JS toggle behaviour.
    """
    populated = CoverageView(
        available=True,
        error=None,
        overall_line_pct=75.0,
        overall_branch_pct=None,
        threshold=80,
        gap_pct=-5.0,
        mtime_iso="2026-04-30T00:00:00Z",
        test_count=100,
        packages=[
            PackageRow(name="orch", line_pct=80.0, branch_pct=None, missing_lines=10, badge="green"),
        ],
        files_by_package={"orch": []},
    )
    with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
        resp = client.get("/system/coverage")
    assert resp.status_code == 200
    html = resp.text

    # data-pkg-toggle identifies each toggle row for the JS collapse handler
    assert 'data-pkg-toggle="orch"' in html
    # data-expanded initial state must be false
    assert 'data-expanded="false"' in html
    # label cell must have an id so JS can update its text
    assert 'id="expand-label-orch"' in html
    # hx-trigger must guard against firing when already expanded
    assert "this.dataset.expanded!='true'" in html
    # initial label text must be "click to expand"
    assert "click to expand" in html
    # "click to collapse" must NOT appear in the initial render
    assert "click to collapse" not in html
```

## Acceptance Criteria

### AC1: Label changes to "click to collapse" after expanding

```
Given the user navigates to /system/coverage
When they click a package row
Then the file details table appears AND the rightmost cell reads "click to collapse"
```

### AC2: Row collapses and label resets on second click

```
Given a package row is expanded and shows "click to collapse"
When the user clicks that row again
Then the file details are hidden AND the label returns to "click to expand"
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproduction test (test_i00054_coverage_page_toggle_attributes_present) passes
```

## Regression Prevention

The reproduction test verifies that the template renders the required `data-pkg-toggle`, `data-expanded`, `id`, and `hx-trigger` guard attributes. Any future template refactor that removes these attributes will cause the test to fail, catching the regression before merge.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: `test_i00054_coverage_page_toggle_attributes_present` — verifies the template renders the data attributes and hx-trigger guard condition required for JS toggle behavior. Fails before the fix (attributes absent), passes after.
- **Unit tests**: Template rendering tests in `tests/dashboard/test_coverage_page.py` — add to the existing `TestCoveragePage` class.
- **Integration tests**: None required — the toggle is purely client-side JS; end-to-end behavior is verified by the QV Browser step (S11).

## Notes

The fix is intentionally minimal: only `dashboard/templates/pages/system/coverage.html` is touched. No backend changes, no new routes, no service layer changes. The JavaScript is inlined in the template (IIFE pattern) rather than as a separate static file, keeping the change self-contained and auditable. The guard condition `this.dataset.expanded!='true'` in `hx-trigger` is the key safety mechanism — it prevents htmx from re-fetching while the collapse path runs synchronously via the click listener.
