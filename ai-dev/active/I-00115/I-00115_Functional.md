# I-00115 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged — it is a frontend template fix only.

## Why

When the orchestrator pauses a step because the agent tried to write outside its allowed paths, the dashboard shows an "Amend scope" popup so the operator can approve the extra paths and restart the step. Operators reported that this popup gets the dashboard "stuck": after clicking the main approve button — and sometimes after closing the popup with the corner close icon — the page goes grey and stops responding to clicks, forcing a manual page refresh. Although the underlying approve action actually succeeds on the server, the cosmetic lock-up makes operators believe something went wrong and slows down recovery from scope-blocked steps.

## What Changed (for the User)

- Clicking the **Amend & restart** button now closes the popup as soon as the server confirms success, instead of leaving it open over an unresponsive page.
- Clicking the **×** close icon in the popup's top-right corner now fully clears the page — both the popup and the grey backdrop go away together, with no leftover greyed-out overlay.
- Clicking **Cancel** continues to work the same as before (it was already correct).
- Two new shortcuts: pressing **Esc** dismisses the popup, and clicking outside the popup (on the dim backdrop) also dismisses it. Both behave the same as Cancel — no server action.
- Recovery from a scope-blocked step no longer requires a manual page refresh.

## How It Behaves

When an in-flight step is paused because the agent tried to write outside its allowed paths, the running-items page shows an **✎ Amend scope** button on the affected row. Clicking it opens the popup with the offending paths pre-selected.

From there the operator can:

- Tick or untick paths and click **Amend & restart** — the server adds the chosen paths to the work item's scope and re-queues the step. A success toast confirms the action, and the popup closes automatically.
- Click **Cancel** — the popup closes immediately, no server action.
- Click the **×** close icon — same as Cancel.
- Press **Esc** — same as Cancel.
- Click the dim area outside the popup — same as Cancel.

After any of these dismissal paths, the page is fully interactive again with no residual greyed-out overlay. If the operator opens the popup a second time, no leftover keyboard or backdrop listeners from the previous open remain — every open starts with a clean slate.

If the server-side amend-and-restart action fails (rare — wrong paths, missing worktree), the popup remains open and an error toast is shown so the operator can correct and retry.

## Out of Scope

- Changes to the underlying amend-and-restart server action or its event emissions — the server side is correct today.
- Redesign of the modal's visual styling, layout, or content. This fix only repairs the dismissal lifecycle.
- The neighbouring "Revert" and "Skip step" buttons — they do not raise this popup and are unaffected.
