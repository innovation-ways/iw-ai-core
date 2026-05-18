# I-00101: Scope-violation escalations strand work items with no UI surface or remedy

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-18
**Reported By**: sergio (observed unblocking CR-00060/S11 after the fix-cycle agent edited `.gitleaks.toml` outside `allowed_paths`)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged. The fix is pure Python (daemon + dashboard) plus templates and tests. No schema changes — `FixCycle.fix_metadata` (JSONB) already carries `scope_violations`; the new `daemon_events.event_type = "scope_amended_by_operator"` is a free-form string column.

## Description

When a fix-cycle agent edits a file outside `scope.allowed_paths`, the daemon correctly marks the cycle as `escalated` and the step as `needs_fix` — but the dashboard surfaces it as a generic `needs_fix` row indistinguishable from a "tests failed" needs_fix. The operator has no UI indicator of *why* the step is stuck, no view of the offending paths, and no in-UI remedy: "Restart" reruns the same gate (which still fails until the manifest is amended or the agent's edit is reverted) and "Skip" lets a real gate failure through. The escalation also burns one of the per-step fix-cycle budget slots, even though it is an operator-decidable scope decision rather than a real failed retry attempt. Net effect: every scope-violation escalation strands a work item until the operator manually inspects `daemon_events`, edits `workflow-manifest.json` by hand, and runs `iw step-restart` from a shell.

## Project Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md`. The daemon's fix-cycle lifecycle and scope reconciliation live in `orch/daemon/fix_cycle.py`; per-step fix-cycle budgets are computed in `_max_cycles_for` / aggregate check at lines ~482-505. The dashboard's needs-attention table is in `dashboard/routers/running.py`; per-item step rows render via `dashboard/templates/fragments/item_steps_table.html`. Action endpoints (restart, skip, approve-merge, etc.) live in `dashboard/routers/actions.py`. `WorkflowStep.status` is a SQLAlchemy enum (`StepStatus`); `FixCycle.status` is `FixStatus`; both are imported throughout the daemon and dashboard. `WorkItem` has no `worktree_path` column — the active worktree path is on the latest `StepRun.worktree_path` (and is also captured on `StepRun.worktree_path` for every retry); the new scope-amend endpoints must resolve the worktree by reading the latest `StepRun` row for the step (or via `_get_last_run`).

## Browser Evidence

The pre-fix evidence is captured live in PostgreSQL (no static screenshot — the bug surfaces as a missing UI affordance rather than a wrong-pixel rendering):

- `daemon_events` row at 2026-05-18 13:47 UTC, `event_type='scope_violation_escalation'`,
  message `Fix cycle 1 on S11 touched 1 out-of-scope file(s): ['.gitleaks.toml']. Operator must amend allowed_paths or revert.`
- The item-detail page for CR-00060 at that time showed CR-00060/S11 with the generic
  amber `needs_fix` badge and the standard Restart + Skip buttons — no scope indicator,
  no amend/revert affordance. The operator hand-edited `ai-dev/active/CR-00060/workflow-manifest.json` and ran `iw step-restart` from a shell. (35-minute stall before manual recovery.)
- Post-fix evidence lives under `ai-dev/active/I-00101/evidences/post/` and is produced by
  the qv-browser step (S15) via the synthetic-seed fixture described in `## Notes`.

## Steps to Reproduce

1. Approve and launch any work item whose `scope.allowed_paths` is narrower than the test/lint/security gates need.
2. Let a fix cycle fire (any QV gate failure that the agent fixes by touching a file outside scope — e.g. CR-00060/S11: gitleaks tripped on `.hypothesis/` cache files; the agent's correct fix was to add `.hypothesis/` to `.gitleaks.toml`'s allowlist; `.gitleaks.toml` was not in `allowed_paths`).
3. The daemon's `_complete_fix_cycle` at `orch/daemon/fix_cycle.py:1088-1122` detects the out-of-scope edit, marks the cycle `escalated`, writes `fix_metadata.scope_violations = ['.gitleaks.toml']`, emits `scope_violation_escalation`, and leaves the step at `needs_fix`.
4. Visit the item detail page in the dashboard.

**Expected**: The step row shows a distinct "Scope blocked" badge, lists the offending paths, and offers an "Amend scope & restart" action that appends the paths to `scope.allowed_paths` and re-queues the step. The escalation does not count against the step's fix-cycle budget.

**Actual**: The step row shows a generic amber `needs_fix` badge with no indication that scope is the issue. The only available actions are "Restart" (which queues another run of the failing gate; the underlying fix is still on disk but the next cycle will re-detect the same out-of-scope edits and escalate again) and "Skip" (which lets a real failure through). The operator must read `daemon_events` to learn about the scope violation, manually edit `ai-dev/active/<ID>/workflow-manifest.json` in the worktree, then run `iw step-restart <ID> --step <SID>` from a shell. One fix-cycle slot has been consumed by the escalation (CR-00060/S11 burned 1 of 5).

Concrete live example (2026-05-18 13:47 UTC): `daemon_events` row `scope_violation_escalation`, message `Fix cycle 1 on S11 touched 1 out-of-scope file(s): ['.gitleaks.toml']. Operator must amend allowed_paths or revert.` CR-00060/S11 sat in `needs_fix` for ~35 minutes until the operator hand-edited both manifests and ran `iw step-restart`. The restarted run (#3) passed in 0.7 s — the agent's original fix was correct end-to-end; only the scope gate had blocked it.

## Root Cause Analysis

Three contributing locations:

1. **`orch/daemon/fix_cycle.py:1088-1122`** — when scope violations are detected, sets `cycle.status = FixStatus.escalated` and emits `scope_violation_escalation`. The `fix_metadata.scope_violations` list is preserved, but no marker propagates to a place the dashboard would consult. `WorkflowStep.status` is left at `needs_fix`, identical to a code/test-failure `needs_fix`.

2. **`orch/daemon/fix_cycle.py:482, 498-504`** — `_max_cycles_for` counts FixCycle rows via raw `.count()` (per-step budget at line 482; aggregate per-work-item at lines 498-504). Escalated cycles caused by scope violations are indistinguishable in the count from genuine failed retry attempts, so the scope escalation eats budget the operator can never use back.

3. **`dashboard/routers/running.py:133-193`** and **`dashboard/templates/fragments/item_steps_table.html:157-167`** — the needs-attention query joins `WorkflowStep` ↔ `WorkItem` ↔ `Project` but never consults `fix_cycles` for the latest cycle's status/metadata. The step row renders the same `status_badge.html` "needs_fix" amber pill regardless of why the step is stuck. The action buttons (`restart_button`, `skip_button`) have no scope-aware variant.

Secondary observation: the dashboard's `restart_step` endpoint at `dashboard/routers/actions.py:323-371` only accepts `failed` or `skipped` — `needs_fix` is reachable via the `iw step-restart` CLI (`orch/cli/step_commands.py:189` accepts `failed | needs_fix`) but not from the dashboard. This is a separate inconsistency that the new amend-and-restart endpoint must also handle correctly.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/fix_cycle.py` | Budget counters include scope-escalated cycles; no marker distinguishes scope-stuck steps from code-stuck steps. |
| `dashboard/routers/running.py` | Global needs-attention table doesn't surface scope-blocked steps differently — they hide among real failures. |
| `dashboard/routers/actions.py` | Missing `amend-scope-and-restart` and `revert-scope-and-restart` endpoints; existing `restart_step` rejects `needs_fix`. |
| `dashboard/templates/fragments/item_steps_table.html` | Renders generic `needs_fix` badge; no per-step modal/action affordance for the scope case. |
| `dashboard/templates/components/` | No badge variant for `scope_blocked`; no modal partial for the amend/revert UI. |
| `orch/daemon/scope_amendment.py` (NEW) | New helper module: append paths to manifests in both worktree + parent design-time copy; emit `scope_amended_by_operator`. Keeps the dashboard router thin. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | (a) In `orch/daemon/fix_cycle.py`, exempt scope-escalated cycles from per-step + aggregate budget `.count()` queries. (b) New module `orch/daemon/scope_amendment.py` with two pure functions: `amend_allowed_paths(worktree_path, item_id, paths_to_add)` and `revert_paths_in_worktree(worktree_path, paths_to_revert)`. (c) New helper `latest_scope_violation(db, step_id)` returning `list[str] | None`. | — |
| S02 | CodeReview_Backend | Review S01 | — |
| S03 | Frontend | (a) New `scope_blocked` badge variant in `status_badge.html`. (b) `item_steps_table.html` queries the latest fix_cycle for each needs_fix step and renders the new badge when scope violations are present; adds "Amend scope & restart" / "Revert & restart" buttons next to existing Restart/Skip. (c) New partial `scope_amend_modal.html` rendered by an htmx GET endpoint. (d) Update `running.py` to surface the same badge in the global table. (e) Two new htmx POST endpoints in `actions.py`: `scope_amend_and_restart` and `scope_revert_and_restart`. | — |
| S04 | CodeReview_Frontend | Review S03 | — |
| S05 | Tests | Reproduction + regression tests: unit tests on the budget-exemption query, the `amend_allowed_paths` helper (both files written), and `latest_scope_violation`; integration tests on the two endpoints (full fix-cycle row setup → POST → assert manifest amended, event emitted, step restarted, run #N+1 enqueued); dashboard test on the badge presence given a synthetic escalated fix_cycle row. | — |
| S06 | CodeReview_Tests | Review S05 | — |
| S07 | CodeReview_Final | Global cross-agent review | — |
| S08 | qv-gate | lint | — |
| S09 | qv-gate | format-check | — |
| S10 | qv-gate | type-check | — |
| S11 | qv-gate | test-assertions | — |
| S12 | qv-gate | unit-tests | — |
| S13 | qv-gate | integration-tests | — |
| S14 | qv-gate | security-secrets | — |
| S15 | qv-browser | Browser verification — synthetic seed fixture creates an escalated fix_cycle row; verify badge + modal + amend action end-to-end | — |
| S16 | SelfAssess | iw-item-analyze post-mortem | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — `FixCycle.fix_metadata` JSONB already carries `scope_violations`. `daemon_events.event_type` is a free-form string; adding `scope_amended_by_operator` is content, not schema.

### Code Changes

- **Files to modify**:
  - `orch/daemon/fix_cycle.py` (Backend, S01) — budget-exemption filter on FixCycle counts
  - `dashboard/routers/actions.py` (Frontend, S03) — two new endpoints
  - `dashboard/routers/running.py` (Frontend, S03) — surface badge in global table
  - `dashboard/routers/items.py` (Frontend, S03) — pass `latest_scope_violation` per step to the steps-table render context
  - `dashboard/templates/components/status_badge.html` (Frontend, S03) — new variant
  - `dashboard/templates/fragments/item_steps_table.html` (Frontend, S03) — buttons + badge wiring
- **Files to create**:
  - `orch/daemon/scope_amendment.py` (Backend, S01)
  - `dashboard/templates/components/scope_amend_modal.html` (Frontend, S03)
  - `tests/unit/daemon/test_fix_cycle_budget_exemption.py` (Tests, S05)
  - `tests/unit/daemon/test_scope_amendment.py` (Tests, S05)
  - `tests/dashboard/test_scope_blocked_badge.py` (Tests, S05)
  - `tests/integration/test_scope_amend_endpoints.py` (Tests, S05)
- **Nature of change**: Backend is subtractive (don't count escalated-with-scope-violations) + pure new helper module; Frontend is additive (new badge variant, new modal partial, two new endpoints) — no rewrite of existing render paths.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00101_Issue_Design.md` | Design | This document |
| `I-00101_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00101_S01_Backend_prompt.md` | Prompt | S01 Backend — budget exemption + scope_amendment helper |
| `prompts/I-00101_S02_CodeReview_Backend_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00101_S03_Frontend_prompt.md` | Prompt | S03 Frontend — badge, modal, endpoints, running.py |
| `prompts/I-00101_S04_CodeReview_Frontend_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00101_S05_Tests_prompt.md` | Prompt | S05 reproduction + regression tests |
| `prompts/I-00101_S06_CodeReview_Tests_prompt.md` | Prompt | S06 per-agent review of S05 |
| `prompts/I-00101_S07_CodeReview_Final_prompt.md` | Prompt | S07 final cross-agent review |
| `prompts/I-00101_S15_BrowserVerification_prompt.md` | Prompt | S15 qv-browser end-to-end verification |
| `prompts/I-00101_S16_SelfAssess_prompt.md` | Prompt | S16 self-assessment |

## Test to Reproduce

The reproduction test goes in `tests/unit/daemon/test_fix_cycle_budget_exemption.py`. It FAILS against pre-S01 code (where `.count()` includes scope-escalated cycles) and PASSES after the fix (where the count filters them out). A second reproduction test in `tests/integration/test_scope_amend_endpoints.py` proves the amend-and-restart endpoint path.

```python
# tests/unit/daemon/test_fix_cycle_budget_exemption.py
def test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget(db_session):
    """I-00101 — a fix_cycle whose status=escalated AND fix_metadata.scope_violations
    is non-empty must NOT count toward _max_cycles_for's budget check.

    Pre-fix behaviour: 1 scope-escalated cycle consumed 1 of 5 slots and the operator
    had no way to recover the slot. Post-fix: the same cycle is exempt; the step
    retains its full budget for genuine retries.
    """
    step = _make_qv_step(db_session, gate="security-secrets")
    # Create one scope-escalated cycle exactly as the daemon would.
    db_session.add(FixCycle(
        step_id=step.id,
        cycle_number=1,
        status=FixStatus.escalated,
        trigger_type=FixTrigger.quality_validation,
        fix_metadata={"scope_violations": [".gitleaks.toml"]},
    ))
    db_session.commit()

    project_config = _make_project_config(qv_fix_cycle_max={"security-secrets": 5})
    # Budget-effective remaining capacity after one scope-escalated cycle:
    remaining = _remaining_cycle_budget(db_session, step, project_config)
    assert remaining == 5, (
        "Scope-escalated cycle must be exempt from per-step budget count "
        f"(expected remaining == 5, got {remaining})"
    )
```

## Browser Verification Script

The full script lives in `prompts/I-00101_S15_BrowserVerification_prompt.md`. Condensed reference:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"

# Login (read credentials from $IW_BROWSER_E2E_USER / $IW_BROWSER_E2E_PASSWORD).

# V1 — Scope-blocked badge renders on the synthetic seeded item
playwright-cli open "$IW_BROWSER_BASE_URL/system/running"
playwright-cli snapshot     # click row for I-00101-SYNTH
# Assert: row shows a badge labelled "Scope blocked" (NOT generic "Needs Fix")
# Assert: title/aria-label lists ".test-target.toml"
# Assert: Restart button NOT visible; Skip + "Amend scope & restart" + "Revert & restart" ARE visible
playwright-cli screenshot   # cp .playwright-cli/page-*.png evidences/post/I-00101_v1_badge_visible.png

# V2 — Amend modal opens with the offending path pre-checked
playwright-cli click <amend-button-ref>
# Assert: modal titled "Amend scope for …"; checkbox for ".test-target.toml" is checked
playwright-cli screenshot   # → evidences/post/I-00101_v2_modal_open.png

# V3 — Submit modal: manifest written, event emitted, step restarted
playwright-cli click <amend-and-restart-button-ref>
# Assert: row no longer shows "Scope blocked"; step is in pending/in-progress state
# Assert: latest daemon event for I-00101-SYNTH is "scope_amended_by_operator"
# Assert: synthetic worktree manifest's scope.allowed_paths now contains ".test-target.toml"
playwright-cli screenshot   # → evidences/post/I-00101_v3_after_amend.png

# V(n) — No regressions on adjacent flows
# Visit /system/running, project home, project history — confirm no 5xx, no console errors,
# and an unrelated needs_fix step still renders the generic badge + standard Restart/Skip.
playwright-cli screenshot   # → evidences/post/I-00101_v_n_no_regressions.png
```

## Acceptance Criteria

### AC1: Scope-blocked badge appears on steps escalated by scope violations

```
Given a work item with a workflow_step in status='needs_fix'
And the latest fix_cycle on that step has status='escalated' AND fix_metadata.scope_violations is non-empty
When the operator visits the item detail page in the dashboard
Then the step row renders a distinct "Scope blocked" badge (not the generic needs_fix amber pill)
And a tooltip / accessible-name on the badge lists the offending paths
And the same badge variant appears in the global needs-attention table at /system/running
```

### AC2: Amend scope & restart action succeeds end-to-end

```
Given a step in status='needs_fix' with a scope_violation_escalation cycle naming [".gitleaks.toml"]
When the operator clicks "Amend scope & restart" and submits the modal with [".gitleaks.toml"] checked
Then the worktree's ai-dev/active/<ID>/workflow-manifest.json scope.allowed_paths has ".gitleaks.toml" appended
And the parent repo's ai-dev/active/<ID>/workflow-manifest.json scope.allowed_paths has ".gitleaks.toml" appended
And a daemon_event of type 'scope_amended_by_operator' is emitted with metadata {item_id, step_id, added_paths: [".gitleaks.toml"]}
And the workflow_step.status flips to 'pending' with started_at/completed_at cleared
And a new StepRun row exists with run_number = previous_run.run_number + 1 and status='pending'
And the daemon picks up the step within one poll interval and runs the gate
```

### AC3: Revert scope & restart action succeeds end-to-end

```
Given the same setup as AC2 but the operator instead clicks "Revert & restart"
When they confirm the modal
Then git checkout -- .gitleaks.toml is executed in the worktree (the file returns to its HEAD content)
And the workflow-manifest.json files are NOT amended (revert is the alternative to amend, not in addition)
And a daemon_event of type 'scope_reverted_by_operator' is emitted with metadata {item_id, step_id, reverted_paths}
And the workflow_step.status flips to 'pending' and a new StepRun is enqueued
```

### AC4: Scope-escalated cycles do not count against fix-cycle budgets

```
Given a workflow_step with one fix_cycle in status='escalated' and fix_metadata.scope_violations non-empty
And the project's qv_fix_cycle_max for that gate is 5
When the daemon evaluates _max_cycles_for / aggregate_used at the start of the next cycle attempt
Then the budget computation excludes that escalated-with-scope-violations row
And the step has its full 5 retry slots available for genuine failures
And the aggregate_fix_cycle_max budget (default 25) also excludes scope-escalated rows project-wide
```

### AC5: Regression test exists

```
Given the fix is applied
When `make test-unit`, `make test-dashboard` (where applicable), and `make test-integration` run
Then tests/unit/daemon/test_fix_cycle_budget_exemption.py::test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget passes
And tests/dashboard/test_scope_blocked_badge.py asserts the badge HTML appears for a seeded escalated fix_cycle
And tests/integration/test_scope_amend_endpoints.py asserts the manifest write + event + restart side effects
```

## Regression Prevention

1. **Filter, don't mutate** — the budget-exemption fix is a predicate added to `.count()` queries, not a rollback of `cycle_number`. Past `daemon_events` and the audit trail remain intact. Anyone re-introducing a raw `.count()` of FixCycle rows for budget purposes would re-break the AC4 test.
2. **Codified end-to-end reproduction** — the integration test in `tests/integration/test_scope_amend_endpoints.py` sets up the exact pre-conditions (escalated FixCycle row with `scope_violations` metadata, step in needs_fix, manifest with narrow allowed_paths) and asserts every observable side effect of the amend action. Any future routing change or template rename would surface here.
3. **Two-manifest write is encapsulated** — `orch/daemon/scope_amendment.py::amend_allowed_paths` writes both copies (worktree + parent) in a single helper. The dashboard endpoint cannot accidentally update only one because there is only one call site.
4. **Badge sourcing is data-driven** — the template reads `latest_scope_violation(step)` and renders the badge variant when truthy. There is no string-matching on `last_error` or other fragile heuristics.
5. **Endpoint guard** — both new endpoints reject calls when the latest fix_cycle is *not* a scope escalation (HTTP 422 with a specific message), preventing operators from accidentally amending scope after a code-defect escalation.

## Dependencies

- **Depends on**: None
- **Blocks**: None (CR-00060/S11 was already manually unblocked by hand-editing the manifest and running `iw step-restart`; this fix prevents the same toil for future scope-violation escalations)

## Impacted Paths

- `orch/daemon/fix_cycle.py`
- `orch/daemon/scope_amendment.py`
- `dashboard/routers/actions.py`
- `dashboard/routers/items.py`
- `dashboard/routers/running.py`
- `dashboard/templates/components/status_badge.html`
- `dashboard/templates/components/scope_amend_modal.html`
- `dashboard/templates/fragments/item_steps_table.html`
- `tests/unit/daemon/test_fix_cycle_budget_exemption.py`
- `tests/unit/daemon/test_scope_amendment.py`
- `tests/dashboard/test_scope_blocked_badge.py`
- `tests/integration/test_scope_amend_endpoints.py`

## TDD Approach

- **Reproducing test (unit)**: `test_fix_cycle_budget_exemption.py::test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget` — fails when `.count()` includes scope-escalated rows; passes when the filter excludes them.
- **Reproducing test (integration)**: `test_scope_amend_endpoints.py::test_amend_writes_both_manifests_and_restarts_step` — fails when no endpoint exists; passes when the endpoint writes both manifest files, emits the event, and creates a new StepRun.
- **Unit tests**: `test_scope_amendment.py` covers the helper functions directly — both-file writes, idempotency on duplicate paths, behaviour when one of the two manifest files is missing, and `latest_scope_violation` returning `None` for steps with no scope-escalated cycles.
- **Integration tests**: `test_scope_amend_endpoints.py` exercises the full HTTP path — amend, revert, and the rejection of calls when the latest cycle is not a scope escalation.
- **Dashboard tests**: `test_scope_blocked_badge.py` uses the `client` fixture to render the item detail page with a seeded escalated FixCycle row and asserts the attribute-scoped `class="badge-scope-blocked"` substring is present (per the CSS class assertion note in this template). It also asserts the generic `needs_fix` badge is *absent* on that row.

**Assertion scoping for CSS class names** — All CSS class assertions use the `class="…"` attribute-scoped form to avoid false-positives from inline `<script>` JSON, `data-*` attributes, or HTML comments (per I-00067 lesson in this template's TDD section).

## Notes

- **Why not a schema change.** Everything we need is already on `FixCycle.fix_metadata` (JSONB). Adding a dedicated column would be a migration-tax for zero gain.
- **Why the cycle counter is not rolled back.** The filter approach (predicate on `.count()`) preserves the audit trail (`cycle_number = 1` still appears, with `status = escalated`, so historical reports show the escalation happened) while making it invisible to budget math. Mutating `cycle_number` would force renumbering and risk uniqueness constraints.
- **Why both manifests get amended.** The worktree's copy is what the daemon re-reads on the next cycle (`_load_allowed_paths` at `orch/daemon/fix_cycle.py:1049`). The parent's design-time copy is what `iw item-status`/`/system/all-active`/the design-doc review consult. Keeping them in sync preserves the principle that the parent manifest is a faithful design-time snapshot.
- **Permission model.** Any operator viewing the dashboard can amend or revert scope. iw-ai-core has no per-user auth today; this is consistent with existing actions (approve, restart, cancel). When auth is introduced later, the new endpoints will inherit the same gate as the existing ones.
- **Browser-verification approach.** The QV-browser step at S15 uses a small e2e fixture (`ai-dev/active/I-00101/e2e_fixtures/001_escalated_fix_cycle.py`) to seed a synthetic work item with an escalated FixCycle row + scope_violations metadata, then navigates to the item detail page, asserts the badge, clicks "Amend scope & restart", and confirms the post-action state. This is the cleanest way to verify a scenario that requires daemon-side state, since the real CR-00060/S11 case has already been hand-resolved.
- **Migration lock** at design time: `free` (no Database step planned).
