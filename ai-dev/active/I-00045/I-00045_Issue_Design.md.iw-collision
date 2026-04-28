# I-00045: OSS Status Widget and Page — Ugly Layout and Raw JSON Rendering

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-28
**Reported By**: Sergio (user observation via dashboard)
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
orchestration DB (port 5433) from an agent context.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The OSS status dashboard widget renders the raw Python dict from `summary_json` as a string inside the status pill (e.g., `{'skip': 4, 'total': 73, 'must_fail': 4, ...}`) instead of a concise human-readable label. Additionally, the "OSS STATUS" section heading is not clickable, the Rescan button is awkwardly placed inline with the status pill, the stale warning has an unwanted white border box, and the OSS compliance page uses raw Unicode emoji circles (🔴/🟡/🟢) as status indicators instead of CSS-styled dots consistent with the rest of the UI.

## Project Context

Read `CLAUDE.md` (root) and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Key points:
- Stack is FastAPI + Jinja2 + htmx + Tailwind CSS (prebuilt via `make css`)
- No TypeScript frontend — templates are in `dashboard/templates/`
- After adding new Tailwind classes, run `make css` to regenerate `dashboard/static/styles.css`
- Fragment templates under `templates/fragments/` must NOT extend `base.html`

## Browser Evidence

Pre-fix screenshots captured during investigation:

- `ai-dev/active/I-00045/evidences/pre/I-00045-dashboard.png` — dashboard page showing the OSS status widget with raw JSON visible in the pill
- `ai-dev/active/I-00045/evidences/pre/I-00045-oss-page.png` — OSS compliance page showing emoji-based status, stale banner, and button placement

## Steps to Reproduce

1. Navigate to any project's dashboard page, e.g. `/project/iw-ai-core/`
2. Scroll to the "Git Status" panel — the OSS Status widget is embedded within it
3. Observe the status pill text: it shows the full raw Python dict string instead of a label like "50 passed · 4 critical · 9 warnings"
4. Observe that clicking "OSS STATUS" heading does nothing (it is not a link)
5. Navigate to `/project/iw-ai-core/oss`
6. Observe: the "Last scan:" pill uses 🔴 emoji; the stale banner has a white/light rectangular border; the Scan action buttons appear disconnected from the status pill

**Expected**: The OSS status pill shows a compact, readable summary (e.g., "50 passed · 4 critical"); "OSS STATUS" is a link to the OSS page; the stale indicator is subtle and borderless; the OSS page uses CSS-styled colored dots consistent with the rest of the UI.

**Actual**: Raw dict string is displayed as pill label; heading is not clickable; yellow warning box has a white border; OSS page uses mismatched emoji circles for status.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/iw-ai-core/
playwright-cli screenshot   # capture dashboard — OSS widget
# Verify pill shows readable text, not raw JSON
# Verify "OSS STATUS" heading is a link

playwright-cli goto http://localhost:9900/project/iw-ai-core/oss
playwright-cli screenshot   # capture OSS page
# Verify status indicator uses CSS dots, not emoji
# Verify stale banner has no white border box
```

## Root Cause Analysis

Five independent defects, all in two Jinja2 template files:

**Defect 1 — Raw JSON in dashboard pill** (`dashboard/templates/fragments/oss_status_frame.html:66–68`):
```jinja2
{% if scan_summary.summary %}
  <span>{{ scan_summary.summary }}</span>
{% endif %}
```
`scan_summary.summary` is set from `scan.summary_json` (a `dict[str, Any]` column in `OssScan`). Jinja2 renders dicts with Python `repr()`, producing the ugly `{'skip': 4, 'total': 73, ...}` string. The dict contains keys `must_pass`, `should_pass`, `may_pass`, `must_fail`, `should_fail`, `skip`, `total`, etc. — all needed to build a human-readable label.

**Defect 2 — "OSS STATUS" heading not clickable** (`oss_status_frame.html:7`):
```jinja2
<h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide">OSS Status</h3>
```
Plain `<h3>` with no `<a>` wrapper. Should link to `/project/{id}/oss`.

**Defect 3 — Rescan button inline with pill** (`oss_status_frame.html:81–86`):
The Rescan button is placed in a `flex items-center justify-between` row alongside the status pill, creating a wide layout that looks unbalanced. It should be a small icon button (refresh SVG) next to the heading.

**Defect 4 — Stale warning white border** (`oss_status_frame.html:91`):
```jinja2
class="flex items-center gap-2 text-xs text-warning bg-warning/10 border border-warning/30 rounded px-2 py-1.5"
```
The `border border-warning/30` produces a visible rectangular box outline, the only bordered element in the widget. Remove the border; keep background tint and text color for subtlety.

**Defect 5 — Emoji circles on OSS page** (`dashboard/templates/pages/project/oss.html:72–108`):
The "Last scan: red/yellow/green ⚠ stale" pill uses `🔴`/`🟡`/`🟢` Unicode emoji for status, and emoji `⚠` for the stale flag. The OSS summary stats card (lines 132–136) already uses CSS-styled `●` with Tailwind color classes (`text-red-700`, `text-emerald-700`) — the pill should match that pattern.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Dashboard OSS widget | `dashboard/templates/fragments/oss_status_frame.html` | Raw JSON pill, non-clickable heading, misplaced Rescan, white-bordered stale banner |
| OSS compliance page | `dashboard/templates/pages/project/oss.html` | Emoji status indicators, inconsistent styling |
| CSS bundle | `dashboard/static/styles.css` | Needs regeneration if new Tailwind classes added |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Fix `oss_status_frame.html` and `oss.html`; run `make css` | — |
| S02 | CodeReview_Frontend | Review S01 output | — |
| S03 | Tests | Write reproduction + regression tests | — |
| S04 | CodeReview_Tests | Review S03 output | — |
| S05 | CodeReview_Final | Global cross-agent review | — |
| S06 | QV: lint | `make lint` | — |
| S07 | QV: format | `make format-check` | — |
| S08 | QV: typecheck | `make typecheck` | — |
| S09 | QV: unit-tests | `make test-unit` | — |
| S10 | QV: integration-tests | `make allure-integration` | — |
| S11 | QV: Browser | Playwright verification of fixed UI | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — pure template changes

### Code Changes

- **Files to modify**:
  - `dashboard/templates/fragments/oss_status_frame.html`
  - `dashboard/templates/pages/project/oss.html`
  - `dashboard/static/styles.css` (regenerated by `make css`)
- **Nature of change**: Template rendering logic — format dict keys into human-readable text, add link on heading, relocate Rescan button, remove border, replace emoji with CSS dots

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00045_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00045_S01_Frontend_prompt.md` | Prompt | Fix templates |
| `prompts/I-00045_S02_CodeReview_Frontend_prompt.md` | Prompt | Review S01 |
| `prompts/I-00045_S03_Tests_prompt.md` | Prompt | Write regression tests |
| `prompts/I-00045_S04_CodeReview_Tests_prompt.md` | Prompt | Review S03 |
| `prompts/I-00045_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00045_S11_BrowserVerification_prompt.md` | Prompt | Browser QV |

## Test to Reproduce

```python
def test_i00045_oss_status_widget_no_raw_json(client, db_session):
    """Dashboard OSS widget must NOT render the raw summary_json dict as text.

    This test should FAIL before the fix (template renders raw dict repr)
    and PASS after (template renders formatted label).
    """
    # Arrange: project with a completed OSS scan that has summary_json data
    project = make_project(db_session, id="test-proj")
    scan = make_oss_scan(
        db_session,
        project_id="test-proj",
        pill_color=OssPillColor.red,
        summary_json={
            "must_fail": 4, "must_pass": 15, "should_fail": 9,
            "should_pass": 31, "may_pass": 4, "skip": 4, "total": 73,
        },
    )

    # Act
    response = client.get("/project/test-proj/")

    # Assert: raw dict must NOT appear in rendered HTML
    assert "must_fail" not in response.text
    assert "{'skip'" not in response.text
    assert "'total'" not in response.text
    # Formatted label MUST appear instead
    assert "passed" in response.text
    assert "critical" in response.text
```

## Acceptance Criteria

### AC1: Dashboard pill shows formatted summary, not raw JSON

```
Given a project with a completed OSS scan (summary_json with must_fail=4, must_pass=15, should_fail=9, should_pass=31)
When the user views the project dashboard page
Then the OSS status pill shows a label like "50 passed · 4 critical · 9 warnings"
 AND the raw Python dict string (e.g. "{'skip':") does NOT appear anywhere in the page HTML
```

### AC2: "OSS STATUS" heading links to the OSS page

```
Given a project with OSS enabled
When the user views the project dashboard page
Then the "OSS STATUS" heading is rendered as an <a> element linking to /project/{id}/oss
 AND clicking it navigates to the OSS compliance page
```

### AC3: Stale warning has no white border

```
Given a project with a stale OSS scan
When the user views the dashboard OSS widget
Then the stale warning shows amber background tint and text
 AND has no visible rectangular border box
```

### AC4: OSS page uses CSS-styled status dots, not emoji

```
Given a project with a completed red OSS scan
When the user views the /project/{id}/oss page
Then the "Last scan" status indicator uses a CSS-styled colored dot (e.g. ● with text-red-700)
 AND does NOT contain the 🔴 / 🟡 / 🟢 Unicode emoji characters
```

### AC5: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproduction test passes (raw JSON not rendered; heading is a link)
```

## Regression Prevention

- The template fix replaces `{{ scan_summary.summary }}` with a formatted expression using specific dict keys (`must_fail`, `should_fail`, `must_pass + should_pass + may_pass`). If `summary_json` structure changes in the future, the template will render zeros rather than raw JSON.
- The dashboard test checks the rendered HTML for the absence of raw dict markers (`{'skip'`, `must_fail`) — this test will catch any future regression that re-exposes raw JSON.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: `test_i00045_oss_status_widget_no_raw_json` — fails before fix (raw dict in HTML), passes after (formatted label)
- **Unit tests**: Dashboard endpoint tests for `/project/{id}/` with mocked OSS scan data — verify pill label text and heading href
- **Integration tests**: Full stack test hitting real test-container DB — verify end-to-end rendering with `OssScan` row in DB

## Notes

The `summary_json` dict keys to display (from `OssScan.summary_json` as populated by the scan runner):
- Total passing = `(summary.must_pass or 0) + (summary.should_pass or 0) + (summary.may_pass or 0)`
- Critical = `summary.must_fail or 0`
- Warnings = `summary.should_fail or 0`

Display format: `"N passed · N critical · N warnings"` — omit a segment if its count is 0 and it is not critical (always show "critical" if must_fail > 0).

The `oss_status_frame.html` template already has the `pill_color` color logic duplicated from `oss_status_pill.html`. The fix should NOT refactor this duplication — keep scope minimal.
