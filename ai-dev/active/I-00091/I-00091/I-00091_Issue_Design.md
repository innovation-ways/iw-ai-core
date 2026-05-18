# I-00091: Auto-merge settings form stays "Use global default" after partial-axis override

**Type**: Issue
**Severity**: High
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This item does
not touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds NO migrations — it touches one ORM-adjacent
dataclass (`ResolvedConfig`), one Jinja2 template, one FastAPI route, and
test files only.

## Description

The Auto-Merge Resolver settings panel
(`/project/<id>/auto-merge`) does not reflect the persisted per-project
configuration when only ONE axis (phase OR runtime) is overridden — both
dropdowns render as "Use global default" even though the DB row holds a
real value for one of them. Additionally, after Save the form fragment is
never re-rendered (only the status chip is swapped), so the user gets no
visual confirmation and the dropdowns remain stale until a manual reload.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard
rules. Relevant sub-CLAUDE files: `dashboard/CLAUDE.md` (FastAPI + Jinja2
+ htmx patterns, fragment-template rules, `make css` notes) and
`orch/CLAUDE.md` (SQLAlchemy 2.0 declarative style, aggregator layer).

## Browser Evidence

Pre-fix evidence captured on `iw-dev-01:9900`:

- `ai-dev/active/I-00091/evidences/pre/I-00091-bug-evidence.png` — full
  page screenshot after `POST /auto-merge/config {"phase":1,"runtime_option_id":null}`.
  Phase dropdown reads "Use global default" but the chip shows `Phase: 1`.
- `ai-dev/active/I-00091/evidences/pre/I-00091-snapshot.yml` — Playwright
  accessibility snapshot of the same state.

## Steps to Reproduce

1. Open `http://iw-dev-01:9900/project/iw-ai-core/auto-merge`.
2. From the Phase dropdown choose `1 — dry-run`; leave Runtime on
   `Use global default`. Click **Save**.
   (Equivalent: `curl -X POST .../auto-merge/config -H "Content-Type: application/json" -d '{"phase":1,"runtime_option_id":null}'`.)
3. Reload the page.

**Expected**: Phase dropdown re-renders with `1 — dry-run` selected;
Runtime dropdown stays on `Use global default`; the status chip says
`Phase: 1`, `Source: per_project_db (Per-project override)`; the footer
under Save reads `Last changed: <timestamp> by dashboard`.

**Actual**: Phase dropdown re-renders with `Use global default` selected;
Runtime dropdown stays on `Use global default`; the status chip says
`Phase: 1`, `Source: toml`; the footer reads `Using global default`. The
user cannot tell what they saved or that they saved at all.

Additionally: even without reloading, immediately after clicking **Save**
nothing visible changes in the form section — there is no toast, no
loading indicator, and the dropdowns do not refresh. Only the chip swaps
via htmx.

## Root Cause Analysis

Two compounding defects in two files.

### Defect A — `ResolvedConfig.source` is single-axis but used as
multi-axis

`orch/auto_merge_aggregator.py:23-30` defines `ResolvedConfig` with one
`source` field:

```python
@dataclass(frozen=True)
class ResolvedConfig:
    phase: int
    runtime_option_id: int | None
    cli_tool: str
    model: str
    source: Literal["per_project_db", "toml", "hardcoded"]
```

`resolve_project_config` at lines 152-208 resolves `phase` and `runtime`
**from two independent layer stacks**, but only the runtime-resolution
loop's terminating layer ends up in `source`. The phase layer is
resolved at line 156 and the source of *that* decision is never
recorded.

`dashboard/templates/fragments/auto_merge_settings.html:3` reads
`source` as if it described BOTH axes:

```jinja
{% set _is_override = status.config.source == 'per_project_db' %}
...
<option value="1" {% if _is_override and status.config.phase == 1 %}selected{% endif %}>1 — dry-run</option>
...
<option value="{{ opt.id }}" {% if _is_override and status.config.runtime_option_id == opt.id %}selected{% endif %}>...</option>
```

When the user overrides only `phase`, `runtime` falls through to TOML →
`source='toml'` → `_is_override=False` → BOTH dropdowns render as
`Use global default selected` even though the DB has `phase=1`.

The footer attribution
(`auto_merge_settings.html:36-40`) uses the same single boolean, so the
"Last changed by …" line never appears for phase-only overrides.

The status chip
(`auto_merge_status_chip.html:32`) shows
`Source: toml (Per-project override)` for the same reason — wrong text
for the underlying state.

### Defect B — Post-save swap targets only the chip

`dashboard/templates/fragments/auto_merge_settings.html:7`:

```jinja
<form hx-post="/project/{{ current_project.id }}/auto-merge/config"
      hx-ext="json-enc"
      hx-target="#auto-merge-status-chip"
      hx-swap="outerHTML"
      class="space-y-4">
```

`dashboard/routers/auto_merge_ui.py:377-382` (the
`auto_merge_set_config` non-JSON branch) returns ONLY the status-chip
fragment. The browser swaps `#auto-merge-status-chip` and leaves the
form's existing DOM intact — so the just-saved dropdowns never re-render
from server state. Combined with Defect A, even when the user picks
`1 — dry-run` and Saves successfully, a subsequent reload appears to
"forget" the choice.

There is also no `hx-indicator`, no transient "Saved" affordance, and
no error styling, so a failed Save is silent too.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/auto_merge_aggregator.py` (`ResolvedConfig`, `resolve_project_config`) | Loses per-axis source information; status chip + form template can't tell which axis is overridden |
| `dashboard/templates/fragments/auto_merge_settings.html` | Both dropdowns wrongly fall back to global; footer attribution missing on partial override; post-save UX gives no feedback |
| `dashboard/templates/fragments/auto_merge_status_chip.html` | Reports a misleading single "Source" string when one axis is overridden and the other isn't |
| `dashboard/routers/auto_merge_ui.py` (`auto_merge_set_config`) | Returns only the chip fragment; needs to also re-render the settings form |
| Tests under `tests/unit/test_auto_merge_config_resolution.py`, `tests/dashboard/test_auto_merge_routes.py`, `tests/integration/test_auto_merge_control_surface.py` | Existing tests pass because they never exercised the phase-only / runtime-only partial-override case |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Add `phase_source` + `runtime_source` to `ResolvedConfig`; populate independently in `resolve_project_config`. Keep `source` as a back-compat property (returns `phase_source` to preserve the existing chip text for now) OR migrate all callers in this step. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `frontend-impl` | (a) Update `auto_merge_settings.html` so Phase dropdown tests `phase_source == 'per_project_db'` and Runtime dropdown tests `runtime_source == 'per_project_db'` independently; (b) wrap the section in `id="auto-merge-settings"` and switch the form's `hx-target` to that id with `hx-swap="outerHTML"`; (c) update `auto_merge_set_config` to render a combined fragment that contains the new settings section AND an `hx-swap-oob="outerHTML:#auto-merge-status-chip"` chip; (d) add `hx-indicator` "Saving…" + a short-lived "Saved" indicator (CSS-only); (e) update `auto_merge_status_chip.html` to use the per-axis sources for its source line. | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `tests-impl` | Reproduction tests + regression coverage: aggregator unit tests for the four matrix cells (phase-only, runtime-only, both, neither); dashboard tests for the rendered form HTML for the same four cells; integration test that exercises POST → GET round-trip and asserts the form fragment is returned with correct `selected` attributes. | — |
| S06 | `code-review-impl` | Review S05 | — |
| S07 | `code-review-final-impl` | Global cross-agent review | — |
| S08 | `qv-gate` | `make lint` | — |
| S09 | `qv-gate` | `make format-check` | — |
| S10 | `qv-gate` | `make type-check` | — |
| S11 | `qv-gate` | `make security-sast` | — |
| S12 | `qv-gate` | `make test-unit` | — |
| S13 | `qv-gate` | `make allure-integration` | — |
| S14 | `qv-browser` | Playwright: drive `/auto-merge`, save phase-only override, reload, assert Phase dropdown is selected and Runtime is still global; submit second time saving both; clear both; verify chip + footer reflect each state. | — |
| S15 | `self-assess-impl` | Self-assessment (project has `self_assess=true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. The DB schema (`auto_merge_project_config`) already stores `phase` and `runtime_option_id` as independently-nullable columns; the bug is purely in how the resolved view is reported back to the template.

### Code Changes

- **Files to modify**:
  - `orch/auto_merge_aggregator.py`
  - `dashboard/templates/fragments/auto_merge_settings.html`
  - `dashboard/templates/fragments/auto_merge_status_chip.html`
  - `dashboard/routers/auto_merge_ui.py`
  - `dashboard/static/styles.css` (small "Saved" indicator rule; optional — append plain CSS rules per the CLAUDE.md mitigation)
- **Files to create / extend (tests)**:
  - `tests/unit/test_auto_merge_config_resolution.py` (extend)
  - `tests/dashboard/test_auto_merge_routes.py` (extend)
  - `tests/integration/test_auto_merge_control_surface.py` (extend)
- **Nature of change**: data-shape extension (one dataclass), template logic correction, route response shape (return combined fragment), and three test files growing to cover the four-cell matrix.

## File Manifest

All files for this work item live under `ai-dev/active/I-00091/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00091_Issue_Design.md` | Design | This document |
| `I-00091_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00091_S01_Backend_prompt.md` | Prompt | S01 — ResolvedConfig per-axis source |
| `prompts/I-00091_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00091_S03_Frontend_prompt.md` | Prompt | S03 — template + router |
| `prompts/I-00091_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00091_S05_Tests_prompt.md` | Prompt | S05 — regression tests |
| `prompts/I-00091_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/I-00091_S07_CodeReview_Final_prompt.md` | Prompt | S07 — global review |
| `prompts/I-00091_S14_BrowserVerification_prompt.md` | Prompt | S14 — Playwright verification |
| `prompts/I-00091_S15_SelfAssess_prompt.md` | Prompt | S15 — self-assess |

QV gate steps (S08–S13) are script-driven and need no prompt files.
Reports created during execution land in `ai-dev/active/I-00091/reports/`.

## Test to Reproduce

The reproduction test asserts the rendered Phase dropdown shows
`value="1" selected` after a phase-only override. Pre-fix this fails
(the option re-renders with `value="global" selected`).

**Test-file location** — this test renders the auto-merge page via the
dashboard `client` fixture, so it lives under `tests/dashboard/`, not
`tests/unit/` or `tests/integration/`. See I-00067.

```python
# tests/dashboard/test_auto_merge_routes.py — add new test
# Pattern matches the existing file: local `client` fixture, `test_project`
# fixture, and direct merge of an AutoMergeProjectConfig row.

def test_settings_form_reflects_phase_only_override(
    client, db_session, test_project
):
    """RED before fix: form renders <option value='global' selected> for Phase
    even though AutoMergeProjectConfig.phase = 1. GREEN after fix: Phase dropdown
    renders <option value='1' selected>, Runtime stays on 'global'.
    """
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id,
            phase=1,
            runtime_option_id=None,
            updated_by="test-fixture",
        )
    )
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge")
    html = response.text

    # Locate the Phase <select> block — anchor on the field name to avoid
    # cross-matching the Runtime block.
    phase_block = _extract_select_block(html, name="phase")
    assert 'value="1" selected' in phase_block, (
        f"Phase dropdown should render <option value='1' selected>; got:\n{phase_block}"
    )
    assert 'value="global" selected' not in phase_block

    runtime_block = _extract_select_block(html, name="runtime_option_id")
    assert 'value="global" selected' in runtime_block
```

Three sibling tests cover the remaining matrix cells (runtime-only,
both-axes, neither/clear-back-to-global).

## Browser Verification Script

Captured during investigation; re-used by S14:

```bash
# 1. Reproduce bug state (would fail post-fix expectations pre-fix)
curl -s -X POST "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/config" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{"phase": 1, "runtime_option_id": null}'

# 2. Reload page and inspect form
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot                       # capture refs
playwright-cli screenshot                     # ai-dev/active/I-00091/evidences/post/...

# 3. Submit via UI and assert no full-page reload, dropdowns refresh
playwright-cli select <phase-select-ref> "1"
playwright-cli click <save-button-ref>
playwright-cli snapshot                       # phase should now render selected=1

# 4. Clear back to global
curl -s -X POST "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/config" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{"phase": null, "runtime_option_id": null}'
```

## Acceptance Criteria

### AC1: Phase-only override renders correctly

```
Given AutoMergeProjectConfig has phase=1, runtime_option_id=NULL for project P
When the user GETs /project/P/auto-merge
Then the Phase dropdown HTML contains <option value="1" selected>
 AND the Runtime dropdown HTML contains <option value="global" selected>
 AND the status chip text reads "Source: per_project_db" or equivalent override label
 AND the footer under Save reads "Last changed: …"
```

### AC2: Runtime-only override renders correctly

```
Given AutoMergeProjectConfig has phase=NULL, runtime_option_id=<some enabled row ID> for project P
When the user GETs /project/P/auto-merge
Then the Phase dropdown HTML contains <option value="global" selected>
 AND the Runtime dropdown HTML contains <option value="<id>" selected>
 AND the footer attribution renders
```

### AC3: Both-axes override + post-save in-place refresh

```
Given the user opens /project/P/auto-merge with no override row
When the user picks "1 — dry-run" + a specific runtime in the dropdowns and clicks Save
Then the form POST returns a fragment that swaps the settings section in place
 AND the Phase dropdown now shows <option value="1" selected>
 AND the Runtime dropdown shows <option value="<id>" selected>
 AND the status chip is also updated (hx-swap-oob)
 AND no full-page navigation occurs (htmx in-place swap)
 AND a transient "Saved" indicator appears briefly
```

### AC4: Clear-back-to-global

```
Given AutoMergeProjectConfig has phase=1, runtime_option_id=<id> for project P
When the user picks "Use global default" in BOTH dropdowns and clicks Save
Then the AutoMergeProjectConfig row for P is deleted
 AND the form re-renders with both dropdowns selected on "global"
 AND the footer reads "Using global default"
```

### AC5: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test (tests/dashboard/test_auto_merge_routes.py::test_settings_form_reflects_phase_only_override) passes
 AND its three sibling matrix tests also pass
 AND existing auto_merge tests still pass
```

## Regression Prevention

1. **Per-axis source on `ResolvedConfig`** makes "which axis is overridden"
   explicit data rather than an implicit derivation — anyone adding a new
   source layer (CR-, env override, …) must populate two fields and the
   compiler / mypy will surface the omission.
2. **Four-cell matrix tests** lock in the partial-override behaviour; any
   future refactor that flattens sources back to one boolean will turn
   three of those tests red.
3. **Combined form + chip fragment response** is asserted by both a
   dashboard test (HTML shape) and a browser verification (UX behaviour),
   so removing the `hx-swap-oob` will fail.
4. **Functional doc note** about the four-cell matrix anchors the
   expected behaviour for any reviewer of a future change.

## Dependencies

- **Depends on**: None
- **Blocks**: None (separate auto-merge UI incidents I-B..I-G will be filed
  in parallel and do not share allowed_paths with this one)

## Impacted Paths

- `orch/auto_merge_aggregator.py`
- `dashboard/templates/fragments/auto_merge_settings.html`
- `dashboard/templates/fragments/auto_merge_status_chip.html`
- `dashboard/routers/auto_merge_ui.py`
- `dashboard/static/styles.css`
- `tests/unit/test_auto_merge_config_resolution.py`
- `tests/dashboard/test_auto_merge_routes.py`
- `tests/integration/test_auto_merge_control_surface.py`

## TDD Approach

- **Reproducing tests** (RED before S01/S03 changes, GREEN after):
  - `tests/dashboard/test_auto_merge_routes.py::test_settings_form_reflects_phase_only_override`
  - `tests/dashboard/test_auto_merge_routes.py::test_settings_form_reflects_runtime_only_override`
  - `tests/dashboard/test_auto_merge_routes.py::test_settings_form_reflects_both_axes_override`
  - `tests/dashboard/test_auto_merge_routes.py::test_settings_form_clears_back_to_global`
- **Unit tests** (extend `tests/unit/test_auto_merge_config_resolution.py`):
  - `test_resolve_project_config_records_per_axis_source_phase_only_override`
  - `test_resolve_project_config_records_per_axis_source_runtime_only_override`
  - `test_resolve_project_config_records_per_axis_source_both_axes_override`
  - `test_resolve_project_config_records_per_axis_source_no_override`
- **Integration tests** (extend `tests/integration/test_auto_merge_control_surface.py`):
  - `test_save_config_returns_combined_fragment` — POST /auto-merge/config returns HTML containing both the settings-form `id="auto-merge-settings"` block AND a `hx-swap-oob="outerHTML:#auto-merge-status-chip"` (or equivalent) chip fragment.

**Assertion scoping for CSS class names** — when asserting CSS classes
in rendered HTML, use the attribute-scoped form `assert 'class="my-class"' in html`
or a regex anchored on `class\s*=\s*"[^"]*my-class[^"]*"` rather than the
bare substring form. See I-00067.

## Notes

- This is the **first** of seven incidents filed from the 2026-05-17
  auto-merge view audit. Sibling incidents (filter highlight, modal
  enrichment, cursor/a11y, sortable columns, status-chip dedup + auto-
  merge-only default filter, polish) will be filed separately so each
  ships in a tight cycle.
- The user explicitly approved (via the GO/NO-GO checkpoint):
  - re-render form + chip after save (option A in the question above);
  - add `phase_source` + `runtime_source` to `ResolvedConfig` (rather
    than passing the raw DB row to the template);
  - include `qv-browser` end-to-end verification.
- No `hx-swap-oob` consumers currently exist in the auto-merge fragments;
  the dashboard already uses htmx everywhere else and `hx-ext="json-enc"`
  is already loaded for this form. No new JS dependency.
- `make css` is currently broken in worktrees; the small "Saved" indicator
  rule should be appended directly to `dashboard/static/styles.css` (plain
  CSS) per the I-00067 mitigation in CLAUDE.md.
