# F-00082 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Leaves migrations unchanged.

## Why

Operators need to stop a runaway batch or work item from the dashboard. The previous in-UI cancel only flipped a status flag — it did not kill the running agent, did not tear down the per-item working copy or its background stack, and did not unblock other work blocked by the runaway item's file scope. The most recent incident had to be resolved with a CLI command. This Feature wraps that command in a button.

## What Changed (for the User)

- A "Cancel Batch" button appears on batch detail pages whose status is still pre-terminal. Clicking opens a modal that asks for a reason and offers a "Also reset items to draft" checkbox so the operator can revise and re-run.
- A "Cancel Item" button appears on work item detail pages whose status is still cancellable, when the item does not belong to an active batch. The modal asks for a reason and offers a "Reset to draft" checkbox.
- When a work item does belong to an active batch, its Cancel button is disabled; the hint underneath links to the batch so the operator cancels the batch instead.
- The batches list grows a small per-row Cancel icon for batches in cancellable statuses. Clicking it asks the browser to confirm and then cancels with a default reason; the row updates in place.
- The audit feed records every cancellation with the reason.
- When teardown cannot fully clean up the working copy or background stack (for example because the host's docker daemon is unhealthy), the cancel still succeeds at the data layer; the toast surfaces a warning explaining what was left behind.

## How It Behaves

The cancel modal always confirms before any destructive action. Cancelling a batch flows through to every member item that is not already in a terminal state: the running agent is signalled to stop, any per-item background stack is brought down, the working copy is removed, and the work item lands in a known state (either "cancelled" by default, or "draft" with all steps reset to "pending" when the reset checkbox is ticked). Cancelling a standalone item does the same teardown for that single item.

Cancelling a batch that is in a terminal state is not offered in the UI; if a direct request slips through anyway, the server refuses with a clear error toast and leaves state unchanged.

After a successful cancellation the page updates in place and the audit feed shows a new entry. If the operator ticked "also reset", the cancelled work item can be re-approved immediately and runs from the first step again on the next daemon poll.

## Out of Scope

- Recording who performed the cancel. The audit entry captures the reason and the resulting changes but not the operator identity; a follow-up change will add that when dashboard authentication lands.
- A Cancel action surfaced from the events feed page. Cancellations are only triggered from the batch and item pages in this Feature.
