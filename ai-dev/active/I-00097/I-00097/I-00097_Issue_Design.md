# I-00097: Auto-merge polish — token cost formatting & entity_id linkification

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-17
**Reported By**: sergio (manual UX audit of `/project/iw-ai-core/auto-merge`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Description

Two small polish defects, bundled because they're both one-line
template touches:

1. **Token cost rollup formats zero as `$0.000000`** — six decimals on
   zero is noisy and looks broken. On a fresh project the operator
   sees `$0.000000` and assumes something is wrong with the metering.
2. **`entity_id` column is plain text** — `CR-00057`, `CR-00060`, etc.
   render as `<td>CR-00057</td>` instead of linking to
   `/project/<id>/item/CR-00057`. Every other dashboard table linkifies
   item IDs.

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`.

## Browser Evidence

- `ai-dev/active/I-00097/evidences/pre/I-00097-polish-baseline.png` —
  baseline showing `$0.000000` in the Token cost rollup card and
  plain-text `CR-00057`/`CR-00060` cells in the events table.

## Steps to Reproduce

1. Open `/project/iw-ai-core/auto-merge`.
2. Inspect the **Token cost rollup** card — the `in: 0 · out: 0 ·
   $0.000000` line.
3. Inspect any `entity_id` cell that contains a work-item ID like
   `CR-00057` or `I-00075`.

**Expected**:
- Zero cost renders as `$0` (or `$0.00` — see Acceptance Criteria);
  small non-zero costs (e.g. `$0.000123`) still show meaningful
  precision.
- `CR-00057` is a clickable link to `/project/<id>/item/CR-00057`
  (singular `item`, matching the existing dashboard route in
  `dashboard/routers/items.py`).

**Actual**:
- `$0.000000` (six decimals on zero, looks broken).
- `CR-00057` is plain text.

## Root Cause Analysis

### Defect A — token cost format

`dashboard/templates/fragments/auto_merge_rollup.html:22`:

```jinja
<p class="text-xs">in: {{ token_cost_rollup.total_input_tokens }} · out: {{ token_cost_rollup.total_output_tokens }} · ${{ "%.6f"|format(token_cost_rollup.total_cost_usd) }}</p>
```

`%.6f` always prints six fractional digits even when the value is
0.0. Use either a custom format function or a conditional that
prints `$0` for exact zero and `%.6f`-then-strip for non-zero.

### Defect B — entity_id plain text

`dashboard/templates/fragments/auto_merge_event_row.html:5`:

```jinja
<td class="px-3 py-2 text-xs font-mono">{{ row.entity_id or '—' }}</td>
```

No link. Item IDs in other dashboard tables (e.g. queue, history,
worktree_table) are wrapped in
`<a href="/project/<id>/item/<entity_id>">` — singular `item`,
matching `dashboard/routers/items.py:1124`.

Note: `entity_id` is not always a work item — for `auto_merge_config_updated`
events it's the project_id; for `auto_merge_health_probe` events it's
null. The link should only render when the value looks like a work
item ID (matches `F-NNNNN`, `I-NNNNN`, or `CR-NNNNN`).

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/auto_merge_rollup.html` | Token cost line shows noisy zero |
| `dashboard/templates/fragments/auto_merge_event_row.html` | entity_id not clickable |

## Fix Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `frontend-impl` | (a) Replace `"%.6f"|format(...)` with a smart formatter: `$0` if exactly zero, `${{ "%.6f"|format(x) | trim('0') | trim('.') }}` for non-zero (or a Python helper exposed as a Jinja2 filter). (b) Wrap `entity_id` in a conditional `<a>` link when it matches the work-item regex `^(F|I|CR)-\d{5}$`. | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `tests-impl` | Dashboard tests: zero cost renders as `$0`; non-zero renders without trailing zeros; entity_id renders as a link when it's a work-item ID and as plain text otherwise. | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `code-review-final-impl` | Global review | — |
| S06–S11 | `qv-gate` | lint, format, typecheck, security-sast, unit-tests, integration-tests | — |
| S12 | `qv-browser` | Playwright: verify `$0` (not `$0.000000`); click an entity_id link and verify it navigates to `/item/<id>`. | — |
| S13 | `self-assess-impl` | Self-assessment | — |

### Database Changes

None.

### Code Changes

- **Files to modify**:
  - `dashboard/templates/fragments/auto_merge_rollup.html`
  - `dashboard/templates/fragments/auto_merge_event_row.html`
- **Files to extend (tests)**:
  - `tests/dashboard/test_auto_merge_routes.py`

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00097_Issue_Design.md` | Design | This document |
| `I-00097_Functional.md` | Design | Human summary |
| `workflow-manifest.json` | Manifest | Steps |
| `prompts/I-00097_S01_Frontend_prompt.md` | Prompt | The two polish fixes |
| `prompts/I-00097_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00097_S03_Tests_prompt.md` | Prompt | Tests |
| `prompts/I-00097_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00097_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `prompts/I-00097_S12_BrowserVerification_prompt.md` | Prompt | Playwright |
| `prompts/I-00097_S13_SelfAssess_prompt.md` | Prompt | Self-assess |

## Test to Reproduce

```python
def test_token_cost_zero_renders_as_dollar_zero(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge/rollup?window=7d")
    html = response.text
    # No $0.000000 — exact-zero renders as $0
    assert "$0.000000" not in html, "exact zero must not render with 6 decimal places"
    assert "$0 " in html or html.rstrip().endswith("$0") or "$0<" in html, (
        f"expected '$0' for exact zero cost; got snippet:\n{html[:500]}"
    )


def test_entity_id_renders_as_link_for_work_item_ids(client, project_factory, daemon_event_factory):
    project = project_factory(project_id="iw-ai-core")
    event = daemon_event_factory(
        project_id=project.id,
        event_type="step_launched",  # if I-00096 has landed, this needs ?all=1 to surface
        entity_id="CR-00057",
        message="step launched",
    )
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10&all=1")
    html = response.text
    # entity_id is wrapped in a link to /item/CR-00057 (singular — matches dashboard/routers/items.py)
    import re
    assert re.search(
        r'<a\b[^>]*\bhref="/project/iw-ai-core/item/CR-00057"[^>]*>\s*CR-00057\s*</a>',
        html,
    )


def test_entity_id_renders_plain_when_not_work_item_id(client, project_factory, daemon_event_factory):
    project = project_factory(project_id="iw-ai-core")
    event = daemon_event_factory(
        project_id=project.id,
        event_type="auto_merge_config_updated",
        entity_id="iw-ai-core",  # project_id, not a work item
        message="config updated",
    )
    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    html = response.text
    import re
    # 'iw-ai-core' string appears (in the entity_id cell), but NOT inside an /item/ link
    assert "iw-ai-core" in html
    assert not re.search(r'href="/project/[^"]+/item/iw-ai-core"', html)
```

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge"
playwright-cli snapshot
# - verify '$0' (not '$0.000000') in the token cost rollup
# - find a CR-XXXXX cell, verify it's a link
playwright-cli click <cr-link-ref>
# - verify navigation to /project/iw-ai-core/item/CR-XXXXX
```

## Acceptance Criteria

### AC1: Zero cost renders as `$0`

```
Given the token cost rollup total_cost_usd is exactly 0.0
When the user GETs /auto-merge/rollup
Then the rendered cost is "$0" (NOT "$0.000000" and NOT "$0.00")
```

### AC2: Small non-zero cost keeps precision

```
Given total_cost_usd is 0.000123
Then the rendered cost is "$0.000123" (NOT "$0.000123000000")
```

### AC3: entity_id is a link for work-item IDs

```
Given an event row with entity_id "CR-00057" in project "iw-ai-core"
Then the entity_id cell renders as <a href="/project/iw-ai-core/item/CR-00057">CR-00057</a>
```

Note: the route is `/project/{project_id}/item/{item_id}` (singular
`item`) — matches the existing FastAPI route in
`dashboard/routers/items.py:1124` and the existing href convention in
`queue.html`, `history.html`, `worktree_table.html`, etc.

### AC4: entity_id is plain text when not a work-item ID

```
Given an event row with entity_id "iw-ai-core" (a project_id)
Then the entity_id cell renders as plain text (NOT a link to /item/iw-ai-core)
```

### AC5: entity_id is "—" when null

```
Given an event row with entity_id NULL
Then the entity_id cell renders as "—" (existing behaviour preserved)
```

### AC6: Regression tests exist

All five named tests pass.

## Regression Prevention

- Format helper centralised either as a Jinja2 filter or a tiny
  template macro means future cost-rendering sites pick up the same
  rule.
- A regex-based test for the link pattern prevents accidentally
  linkifying every value (including project_ids and `—`).

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Conflicts with**: I-00091, I-00092, I-00093, I-00094, I-00095, I-00096 (overlapping auto-merge fragments); run sequentially.

## Impacted Paths

- `dashboard/templates/fragments/auto_merge_rollup.html`
- `dashboard/templates/fragments/auto_merge_event_row.html`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD Approach

- Reproducing tests:
  - `tests/dashboard/test_auto_merge_routes.py::test_token_cost_zero_renders_as_dollar_zero`
  - `tests/dashboard/test_auto_merge_routes.py::test_token_cost_nonzero_keeps_precision`
  - `tests/dashboard/test_auto_merge_routes.py::test_entity_id_renders_as_link_for_work_item_ids`
  - `tests/dashboard/test_auto_merge_routes.py::test_entity_id_renders_plain_when_not_work_item_id`
  - `tests/dashboard/test_auto_merge_routes.py::test_entity_id_renders_dash_when_null`

## Notes

- 7 of 7 audit incidents — the polish item.
- These changes are tiny; the workflow exists mostly to keep a paper
  trail and run the same QV gates we run on the other incidents.
