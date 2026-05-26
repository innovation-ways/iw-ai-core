# I-00115: Amend-scope modal locks the dashboard UI after dismissal

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-26
**Reported By**: User (dashboard interaction)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item does NOT add, modify, or otherwise touch any alembic migration. Frontend-template-only fix.

## Description

When an operator interacts with the "Amend scope" modal on the running-items dashboard (raised whenever an in-flight step is scope-blocked), several modal dismissal paths fail to fully tear down the modal markup. The submit ("Amend & restart") path never removes the modal or its full-screen backdrop, and the "×" close button leaves the backdrop in the DOM because of a broken `this.closest()` walk — so the page stays grey and click-locked until the operator manually refreshes the URL. The server-side amend-and-restart action itself completes correctly; the defect is purely a cosmetic frontend bug in `dashboard/templates/components/scope_amend_modal.html`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key for this item: dashboard CSS is prebuilt via Tailwind (no JS framework — htmx + Jinja2), the modal uses the `activity-modal` / `activity-modal-backdrop` class pair (fixed-position, `z-index: 50/51`), and `_action_response()` in `dashboard/routers/actions.py` returns HTTP 204 + an `HX-Trigger: showToast` header on success.

## Browser Evidence

Pre-fix browser evidence is **deferred**. Reproducing this defect requires the daemon to put a step into the `scope-blocked` state — that requires an agent to actually try to write outside `scope.allowed_paths`, which can't be staged on demand from the dashboard. The QV browser-verification step (S13) reproduces the locked state in the isolated worktree stack by seeding a scope-blocked step via fixture and screenshots the broken-vs-fixed behavior post-fix.

## Steps to Reproduce

1. With the daemon running, get a managed work item into the `scope-blocked` state (an agent commits or tries to commit a file outside `scope.allowed_paths`).
2. Open the dashboard at the running-items page (`/system/running`) — the row for the blocked step displays an `✎ Amend scope` button.
3. Click `✎ Amend scope` — the scope-amend modal opens (markup loaded into `#modal-root` via htmx `beforeend`).
4. Try any of the three dismissal paths:
   - **(a)** Click `Amend & restart` (form submit).
   - **(b)** Click the `×` close button in the modal header.
   - **(c)** Click the `Cancel` button in the footer.

**Expected**: Every dismissal path removes BOTH `#scope-amend-modal` AND `#scope-amend-overlay` from the DOM, restoring full page interactivity. The toast confirms success for (a). The user can continue using the dashboard without refreshing.

**Actual**:
- **(a) Amend & restart**: The form returns 204 No Content with the success toast, but neither `#scope-amend-modal` nor `#scope-amend-overlay` is removed. The modal stays open over a fully-functional but inaccessible page. Operator has to refresh the URL to recover.
- **(b) ×**: The `onclick` handler removes `#scope-amend-modal` but `this.closest('#scope-amend-overlay').remove()` throws `TypeError: Cannot read properties of null (reading 'remove')` because the X button is INSIDE the modal, not inside the overlay (they are siblings). The modal disappears, but the full-screen translucent backdrop stays, leaving the page click-locked and visibly greyed-out.
- **(c) Cancel**: Works correctly — both elements use `document.getElementById(...)` and are removed cleanly. Included as the regression-prevention reference.

The user reported they "weren't sure" which paths failed; the audit (see Root Cause Analysis) confirms (a) and (b) are broken and (c) is correct. The fix repairs (a) and (b) and adds two standard UX dismissal paths (ESC key, backdrop click), per user request.

## Browser Verification Script

Reproduced in the isolated E2E stack at S13 (qv-browser). See `prompts/I-00115_S13_BrowserVerification_prompt.md` for the full V1..V6 verification sequence (seed a scope-blocked step via fixture, then exercise each dismissal path and assert clean DOM teardown).

## Root Cause Analysis

Two defects, both in `dashboard/templates/components/scope_amend_modal.html`:

### Defect 1: Submit handler does not tear down the modal

File: `dashboard/templates/components/scope_amend_modal.html:40-41` — the form:

```html
<form
    hx-post="/project/{{ item.project_id }}/api/item/{{ item.id }}/scope/amend-and-restart/{{ step.step_id }}">
```

has no `hx-on::after-request`, no `hx-swap` directing the response anywhere, and no fallback `onclick` on the submit button. The endpoint at `dashboard/routers/actions.py:444-505` returns `Response(status_code=204, ...)` with `HX-Trigger: showToast` (via `_action_response()` at line 215-232). When htmx sees a 204 it correctly does not swap content (no body), and the page-level handler at `dashboard/templates/pages/project/item_detail.html:159-172` shows the toast — but **nothing removes the modal or overlay**, so they remain in the DOM, the `.activity-modal-backdrop` (CSS: `position:fixed; inset:0; background-color:rgba(0,0,0,0.5); z-index:50`) covers the viewport, and `.activity-modal` (z-index:51) sits on top.

### Defect 2: "×" close button has a broken DOM walk

File: `dashboard/templates/components/scope_amend_modal.html:16-24`:

```html
<button
    type="button"
    class="modal-close"
    ...
    onclick="document.getElementById('scope-amend-modal').remove(); this.closest('#scope-amend-overlay').remove();">
    ×
</button>
```

`#scope-amend-overlay` is a **sibling** of `#scope-amend-modal`, not an ancestor of the button (see lines 2-3 — both divs sit at the same DOM depth, appended via `hx-swap="beforeend"` into `#modal-root`). So `this.closest('#scope-amend-overlay')` returns `null`, and `null.remove()` throws a `TypeError`. JavaScript exception => execution halts after `getElementById('scope-amend-modal').remove()` succeeded. Net effect: modal gone, backdrop stays, page greyed out.

For comparison, the `Cancel` button at line 56-62 does it correctly — two unconditional `document.getElementById(...).remove()` calls.

### Adjacent missing UX

No ESC-key dismissal, no backdrop-click dismissal. These are standard modal-UX patterns and were requested as part of this fix.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Scope amend modal template | `dashboard/templates/components/scope_amend_modal.html` | Three dismissal paths fail to remove modal+overlay; backdrop persists, page click-locked |
| Modal route handler | `dashboard/routers/actions.py` | No change — endpoint behavior is correct; only its 204 success response surfaces the template bug |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Repair `scope_amend_modal.html` — make every dismissal path (submit, ×, Cancel, ESC, backdrop click) fully remove `#scope-amend-modal` AND `#scope-amend-overlay` | — |
| S02 | CodeReview_Frontend | Review S01 | — |
| S03 | Tests | Dashboard-level test asserting the rendered modal HTML wires up every dismissal path correctly | — |
| S04 | CodeReview_Tests | Review S03 | — |
| S05 | CodeReview_Final | Global cross-step review | — |
| S06..S12 | QV Gates | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests | — |
| S13 | QV Browser | Isolated-stack browser verification (seed scope-blocked fixture, exercise all dismissal paths) | — |
| S14 | SelfAssess | Item self-assessment (project has `self_assess = true`) | — |

Agent slug mapping: Frontend = `frontend-impl`, Tests = `tests-impl`, CodeReview_* = `code-review-impl`, CodeReview_Final = `code-review-final-impl`, QV gates = `qv-gate`, QV browser = `qv-browser`, SelfAssess = `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration required.

### Code Changes

- **Files to modify**: `dashboard/templates/components/scope_amend_modal.html`
- **Nature of change**: Replace inline `this.closest(...)` with unconditional `document.getElementById(...)` (matching the Cancel-button pattern); wire the form's success-teardown via an **inline** `hx-on::after-request="…"` attribute on the `<form>` element itself (project idiom — see `dashboard/templates/fragments/oss_status_frame.html:83`), conditional on `event.detail.successful` so 4xx/5xx leaves the modal open for retry. For the other dismissal paths (× button, Cancel, ESC, backdrop click), use a single shared cleanup callback defined in a small `<script>` block scoped to this template — wire it into the × button, Cancel button, a document-level ESC keydown listener, and an overlay click handler (guarded with `event.target === overlay` so clicks inside the modal don't dismiss). The cleanup MUST also detach the ESC keydown listener it added, to avoid leaking listeners across modal opens.

## File Manifest

All files for this work item live under `ai-dev/active/I-00115/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00115_Issue_Design.md` | Design | This document |
| `I-00115_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00115_S01_Frontend_prompt.md` | Prompt | S01 frontend fix |
| `prompts/I-00115_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00115_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00115_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00115_S05_CodeReview_Final_prompt.md` | Prompt | S05 final cross-step review |
| `prompts/I-00115_S13_BrowserVerification_prompt.md` | Prompt | S13 browser verification |
| `prompts/I-00115_S14_SelfAssess_prompt.md` | Prompt | S14 item self-assessment |

Reports are created during execution in `ai-dev/active/I-00115/reports/`.

## Test to Reproduce

The defects are in template DOM wiring, not server logic. The test asserts that the rendered modal HTML contains the correct dismissal hooks. It lives under `tests/dashboard/` (the test must drive the FastAPI route to render the template, so it needs the dashboard's TestClient + `db_session` testcontainer fixture).

The test is intentionally **structural** (asserting the presence of the correct dismissal hooks in the rendered HTML) because:
- Real DOM/JS behaviour is exercised by the QV browser step (S13).
- The Python test suite has no jsdom; testing inline JS execution from pytest would require browser tooling that doesn't belong in unit/integration.

```python
# tests/dashboard/test_scope_amend_modal_i00115.py
def test_i00115_modal_submit_form_wires_cleanup_hook(client, seeded_scope_blocked_step):
    """
    AC1 / Bug fix (a): Form must remove modal + overlay after a successful POST.
    The fix wires an htmx after-request handler (or equivalent) on the form
    that removes BOTH #scope-amend-modal and #scope-amend-overlay.
    """
    item_id, step_id = seeded_scope_blocked_step
    resp = client.get(f"/project/iw-ai-core/api/item/{item_id}/scope/amend-modal/{step_id}")
    assert resp.status_code == 200
    html = resp.text
    # The form must declare a post-request cleanup that targets BOTH elements.
    # FAIL before fix: form has no after-request / on-submit cleanup wiring.
    form_match = re.search(r"<form\b[^>]*hx-post=\"[^\"]*scope/amend-and-restart[^\"]*\"[^>]*>", html)
    assert form_match, "expected the amend-and-restart form to be present"
    form_open_tag = form_match.group(0)
    # Either an hx-on::after-request, an htmx:afterRequest listener, or an
    # onsubmit / hx-on:htmx:afterRequest attribute — whatever the fix uses, it
    # MUST reference both element IDs.
    assert "scope-amend-modal" in form_open_tag and "scope-amend-overlay" in form_open_tag, (
        "form must wire teardown of both modal + overlay; current form open tag: "
        f"{form_open_tag!r}"
    )

def test_i00115_modal_close_button_uses_getelementbyid_for_overlay(client, seeded_scope_blocked_step):
    """
    AC1 / Bug fix (b): the × close button must not rely on `this.closest('#scope-amend-overlay')`,
    which returns null (overlay is a sibling of the modal, not an ancestor of the button).
    """
    item_id, step_id = seeded_scope_blocked_step
    html = client.get(
        f"/project/iw-ai-core/api/item/{item_id}/scope/amend-modal/{step_id}"
    ).text
    # Locate the × button by aria-label.
    close_btn = re.search(r"<button[^>]*aria-label=\"Close modal\"[^>]*>", html)
    assert close_btn, "expected the X close button to be present"
    btn_attrs = close_btn.group(0)
    # FAIL before fix: `this.closest('#scope-amend-overlay')` is present.
    assert "this.closest('#scope-amend-overlay')" not in btn_attrs, (
        "the X button must not use this.closest() to reach #scope-amend-overlay "
        "(overlay is a sibling of the modal, not an ancestor); use getElementById instead"
    )
```

These two assertions are the **RED phase**: they fail on the current `scope_amend_modal.html` because (a) the form open-tag contains neither element ID, and (b) the literal substring `this.closest('#scope-amend-overlay')` is present on line 22.

## Acceptance Criteria

### AC1: All dismissal paths fully tear down the modal

```
Given the scope-amend modal is open over the running-items dashboard
When the operator clicks any of: × close, Cancel, Amend & restart (success),
     presses ESC, or clicks the backdrop
Then both #scope-amend-modal and #scope-amend-overlay are removed from the DOM
And the page becomes fully interactive (no greyed-out backdrop, no click-blocking)
And no JavaScript console errors are emitted by the dismissal path
```

### AC2: Regression test exists

```
Given the fix is applied
When `uv run pytest tests/dashboard/test_scope_amend_modal_i00115.py -v` runs
Then both reproducing tests pass
And the same tests fail against pre-fix HEAD (RED evidence captured in S03 report)
```

### AC3: Submit success still queues the step for restart

```
Given the operator clicks Amend & restart on a scope-blocked step
When the POST /scope/amend-and-restart endpoint returns 204
Then the success toast is shown (existing behaviour, must NOT regress)
And a new StepRun row is created with status=pending (existing behaviour)
And the modal + overlay are removed (new behaviour from this fix)
```

## Regression Prevention

- **Structural test on the template** (S03) prevents the broken `this.closest('#scope-amend-overlay')` pattern from re-appearing in the X button, and asserts the form has explicit teardown wiring.
- **QV browser step** (S13) exercises every dismissal path in a real browser so a future inline-JS regression (e.g. someone reverts to `this.closest()`) is caught end-to-end.
- **Code-review checklist item**: when reviewing any new modal under `dashboard/templates/components/`, verify every dismissal path removes both the modal and its backdrop using stable selectors (IDs), not DOM-walk shortcuts that depend on parent-child relationships that may change.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/components/scope_amend_modal.html`
- `dashboard/static/styles.css`
- `tests/dashboard/test_scope_amend_modal_i00115.py`

Note: `dashboard/static/styles.css` is pre-declared as a defensive allowance — this fix is JS/template-only and almost certainly needs no CSS change, but the project rule (CLAUDE.md, I-00067) instructs frontend agents to append plain CSS to that file when a new class is required and `make css` is unavailable in worktrees. Pre-declaring avoids a spurious scope-block.

## TDD Approach

- Reproducing test: `tests/dashboard/test_scope_amend_modal_i00115.py::test_i00115_modal_submit_form_wires_cleanup_hook` and `::test_i00115_modal_close_button_uses_getelementbyid_for_overlay` — both fail RED before the template fix, pass GREEN after.
- Unit tests: N/A — the defect is in a Jinja2 template, not a Python module.
- Integration tests: existing `tests/integration/test_scope_amend_endpoints.py` continues to exercise the server-side amend-and-restart flow (StepRun creation, manifest mutation, event emission). Verify it still passes — no behavioural change at the route layer is intended.

**Assertion scoping for CSS class names**: this test asserts on rendered HTML and uses attribute-scoped patterns (`re.search(r"<form\b[^>]*hx-post=\"[^\"]*scope/amend-and-restart[^\"]*\"")`) to avoid false-positive substring matches against script tags or data attributes.

## Notes

- The current modal template uses inline `onclick` handlers extensively. The fix should keep the diff minimal — either continue with inline handlers (rewriting the X button to use `getElementById`, adding a small dedicated cleanup script block in a `<script>` at the bottom of the template for ESC + backdrop + after-request), OR refactor all dismissal paths to call a single shared cleanup function defined once in that template. The frontend agent picks whichever produces the cleanest diff. Either approach is acceptable; the structural assertions in S03 only require the right hooks exist, not a specific syntactic form.
- The modal is loaded via `hx-target="#modal-root" hx-swap="beforeend"`, so multiple opens could theoretically stack modals — the cleanup MUST detach any document-level listeners (ESC key) it installs, to prevent listener accumulation across opens. The frontend agent's report should explicitly call out how the ESC listener is detached.
- The Cancel button at line 60 is correct as-is, but should be re-pointed at the shared cleanup function for consistency if the frontend agent chooses the refactor path.
- This fix does NOT touch `dashboard/routers/actions.py` — the 204+`HX-Trigger` response is correct (matches every other htmx-driven action button in this project). Adding `HX-Refresh: true` on this one endpoint would be over-scope and would also redundantly reload the whole page.
