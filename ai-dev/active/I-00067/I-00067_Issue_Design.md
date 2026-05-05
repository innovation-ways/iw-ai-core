# I-00067: Recent Activity messages need truncation + click-to-expand popup

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-05
**Reported By**: sergio (operator)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies — see `docs/IW_AI_Core_Agent_Constraints.md`. This incident does not require any container operations.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This incident does NOT add or modify any Alembic migrations — it is a pure frontend change (Jinja2 template + a small modal partial).

---

## Description

The "Recent Activity" card on the per-project dashboard (`/project/{id}/`) renders each event's `message` field inline with no length cap. Long messages — especially failure events that include multi-line tracebacks — push the card to dozens of lines tall and visually drown the rest of the activity feed. Users can't read the full text without losing all sibling context, and there is no clean way to view the full content.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The dashboard sub-package conventions are in `dashboard/CLAUDE.md` (Jinja2 + htmx + prebuilt Tailwind CSS via `make css`).

The OSS view already has a working modal pattern at `dashboard/templates/fragments/oss_finding_modal.html` (overlay + inner card + close-on-ESC + click-outside dismiss + focus trap). Reuse the visual structure and dismissal behaviour, not the schema-specific contents.

## Steps to Reproduce

1. Open `http://iw-dev-01:9900/project/iw-ai-core/`.
2. Scroll down to the "Recent Activity" card.
3. Observe an event whose `message` is longer than 100 characters (e.g., a failure event containing a stack trace, or any of the multi-line `migration_pipeline` rejection messages).

**Expected**: The visible row shows the first 100 characters of the message followed by `...`. Clicking that row (or a clear affordance on it) opens a popup containing the full untruncated message. Messages that are 100 characters or shorter render as today, with no `...` suffix and no popup affordance.

**Actual**: The full message renders inline, wrapping to many lines. There is no popup. Long tracebacks dominate the card and crowd out shorter, more recent events.

## Browser Evidence

- Pre-fix screenshot: `ai-dev/active/I-00067/evidences/pre/I-00067-recent-activity.png`
- Pre-fix accessibility snapshot: `ai-dev/active/I-00067/evidences/pre/I-00067-snapshot.yml`

The snapshot shows ~17 events rendered as flat `<span>` text inside the card with no overflow handling.

## Browser Verification Script

The reproduction interaction is a passive view, but to make the bug photogenic in dev, force a long event into the feed and revisit the page:

```bash
# Reproduction (pre-fix): seed a long DaemonEvent for the project, then view.
playwright-cli kill-all
playwright-cli open "http://iw-dev-01:9900/project/iw-ai-core/"
playwright-cli snapshot
# In the snapshot, locate the "Recent Activity" heading and confirm the message
# text is rendered in a single span with the full payload (no truncation).
playwright-cli screenshot
cp .playwright-cli/page-*.png ai-dev/active/I-00067/evidences/pre/I-00067-recent-activity.png
```

## Root Cause Analysis

The Recent Activity card template renders each event's message as a single inline `<span>` with no length cap and no expansion control:

- `dashboard/templates/pages/project/dashboard.html:121` →
  `<span class="text-xs text-foreground">{{ event.message or event.event_type }}</span>`

`event.message` comes from `DaemonEvent.message` (`orch/db/models.py`), which is unconstrained free text. Some emitters (e.g., `orch/daemon/migration_pipeline.py`, `orch/daemon/step_monitor.py`, `orch/qv_gate_validator.py`, `orch/cli/step_commands.py`) write multi-line failure messages and tracebacks. The template trusts the field length and renders the full payload, which is the user-visible bug.

There is no UI affordance for "show more" — `oss_finding_modal.html` exists for OSS findings but is not generic. We need a small generic "expand text" modal partial reused from the project dashboard template (and available for future reuse on other activity-style cards).

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/pages/project/dashboard.html` | Renders message inline without truncation; needs a length-conditional template branch and a click affordance. |
| `dashboard/templates/fragments/` | Needs a small new partial (e.g., `activity_text_modal.html`) — generic show-full-text modal, structurally modelled on `oss_finding_modal.html` (overlay + inner card + close + ESC + click-outside). |
| `dashboard/static/styles.css` | May need `make css` re-run if new Tailwind classes appear. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend (`frontend-impl`) | Truncate `event.message` to 100 chars in the project dashboard template; append `...` only when the original is longer; render hidden full-text payload (e.g., `<template data-full-text>` or `data-full-text` JSON-escaped attribute on the trigger element); add a generic activity-text modal partial; small JS to wire click-to-open + ESC + click-outside-to-close + focus return. Messages ≤100 chars render exactly as today (no `...`, no click affordance). | — |
| S02 | CodeReview (`code-review-impl`) | Review S01: correctness of length cutoff, escape safety, accessibility, no regressions on the doc_job / batch / item link rendering paths. | — |
| S03 | Tests (`tests-impl`) | Integration tests asserting (a) a 99-char message renders verbatim with no `...` and no modal trigger; (b) a 200-char message renders 100 chars + `...` and exposes the full text in the DOM via the modal payload; (c) the entity-link routing for `batch` / `doc_job` / `work_item` rows is unchanged. Tests assert specific values, not shape. | — |
| S04 | CodeReview (`code-review-impl`) | Review S03: tests are falsifiable on `main`, no flakiness, no double-escape bugs, no shape-only assertions. | — |
| S05 | CodeReview_Final (`code-review-final-impl`) | Global review across S01 + S03; full unit + integration suite. | — |
| S06 | self-assess-impl | Self-assessment via `iw-item-analyze`. | — |
| S07..S13 | qv-gate | lint, format, typecheck, arch-check, security-sast, unit-tests, integration-tests | — |
| S14 | qv-browser | Browser verification of truncation + popup behaviour in the isolated worktree stack. | — |

Agent slugs: `frontend-impl`, `code-review-impl`, `tests-impl`, `code-review-final-impl`, `self-assess-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `dashboard/templates/pages/project/dashboard.html`, `dashboard/static/styles.css` (rebuilt via `make css`)
- **Files to create**: `dashboard/templates/fragments/activity_text_modal.html`, `tests/integration/test_i00067_recent_activity_truncation.py`
- **Nature of change**: Template + small JS for click-to-expand modal; behaviour-preserving for short messages.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00067_Issue_Design.md` | Design | This document |
| `I-00067_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00067_S01_Frontend_prompt.md` | Prompt | S01 frontend fix |
| `prompts/I-00067_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 review |
| `prompts/I-00067_S03_Tests_prompt.md` | Prompt | S03 tests |
| `prompts/I-00067_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review |
| `prompts/I-00067_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00067_S06_SelfAssess_prompt.md` | Prompt | S06 self-assessment |
| `prompts/I-00067_S14_BrowserVerification_prompt.md` | Prompt | S14 browser verification |
| `evidences/pre/I-00067-recent-activity.png` | Evidence | Pre-fix screenshot |
| `evidences/pre/I-00067-snapshot.yml` | Evidence | Pre-fix a11y snapshot |

Reports are created during execution in `ai-dev/active/I-00067/reports/`.

## Test to Reproduce

```python
# tests/integration/test_i00067_recent_activity_truncation.py
def test_long_activity_message_is_truncated_and_full_text_available(client, db_session, seed_project):
    """A message > 100 chars renders 100 chars + '...' and exposes the full text via a modal payload."""
    long_msg = "x" * 200
    db_session.add(
        DaemonEvent(
            project_id="iw-ai-core",
            event_type="step_failed",
            entity_id="I-00099",
            entity_type="work_item",
            message=long_msg,
        )
    )
    db_session.commit()

    response = client.get("/project/iw-ai-core/")
    html = response.text
    # Visible truncation: first 100 chars followed by literal "..."
    assert ("x" * 100 + "...") in html
    # Full message NOT visible inline (i.e., the 200-char run does not appear as plain inline text)
    # But IS available as the modal payload (data-full-text attribute or hidden <template>)
    assert long_msg in html  # in the modal payload
    # The trigger affordance is present — assert specific class / data attribute we ship
    assert "activity-message-truncated" in html
```

## Browser Verification Test

After the fix:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"
# 1. Confirm at least one truncated event row contains "..." at the end
playwright-cli snapshot
# 2. Click that row's expand affordance
playwright-cli click <truncated-row-ref>
# 3. Confirm a modal/dialog opens containing the full untruncated text
playwright-cli snapshot
# 4. Verify ESC closes the modal
# 5. Verify a short message (≤100 chars) row has NO "..." and NO click affordance
playwright-cli screenshot
```

## Acceptance Criteria

### AC1: Long messages truncate to 100 chars + ellipsis

```
Given the project dashboard "Recent Activity" card
And a DaemonEvent.message longer than 100 characters
When the dashboard renders
Then the visible row shows exactly the first 100 characters of the message followed by "..."
And the full untruncated text is available in the DOM as a modal payload
```

### AC2: Short messages render unchanged

```
Given a DaemonEvent.message of 100 characters or fewer
When the dashboard renders
Then the visible row shows the full message verbatim
And no "..." suffix is appended
And no click-to-expand affordance is rendered for that row
```

### AC3: Click-to-expand opens a popup

```
Given a truncated event row in the "Recent Activity" card
When the user clicks the row's expand affordance
Then a modal opens containing the full untruncated message text
And ESC, the close button, and clicking outside the modal all dismiss it
And keyboard focus returns to the trigger element on close
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the integration test asserting truncation + payload availability passes
And it would fail when run against the pre-fix code
```

## Regression Prevention

- Integration tests in `tests/integration/test_i00067_recent_activity_truncation.py` lock in the 100-char rule and the popup-payload contract; both are checked with specific values, not shape.
- The truncation logic is centralised in the template (single Jinja2 block + Python-side helper if needed) so future activity-style cards can opt in by reusing the same partial. This avoids re-introducing the bug in a sibling component.
- Browser verification (qv-browser) confirms the modal works in the real isolated worktree stack, not just in HTML diffing.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/pages/project/dashboard.html`
- `dashboard/templates/fragments/activity_text_modal.html`
- `dashboard/static/styles.css`
- `tests/integration/test_i00067_recent_activity_truncation.py`

## TDD Approach

- Reproducing test: `test_long_activity_message_is_truncated_and_full_text_available` (above) — fails on `main`, passes after S01.
- Unit tests: not applicable (template-only change with no Python helper).
- Integration tests: cover (a) truncation cutoff, (b) full-text payload presence, (c) short-message no-affordance path, (d) link routing for batch/doc_job/work_item rows is unchanged.

## Notes

- The popup pattern is structurally modelled on `dashboard/templates/fragments/oss_finding_modal.html`, but the new partial is generic ("show full activity text"). Do NOT reuse `oss-finding-modal` IDs/classes — give the new partial its own unique IDs to avoid collision when both modals coexist on a future shared page.
- Truncation cutoff is exactly 100 characters of the *original* message string, measured by Python `len()` (i.e., codepoint count, not bytes). Suffix is the literal three ASCII dots `...`, not the `…` Unicode ellipsis (per operator confirmation).
- Out of scope: redesigning the activity feed, adding pagination, changing event ordering, or modifying the message field on the database side.
