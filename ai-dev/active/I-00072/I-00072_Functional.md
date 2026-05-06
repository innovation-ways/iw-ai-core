# I-00072 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. Keep the body at most 500 words.
-->

## ⛔ Docker is off-limits

Standard policy. No docker interaction in this fix.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged — every status label it touches already exists in the database.

## Why

Operators recover from a failed squash-merge in two equivalent ways: by clicking "Restart merge" in the dashboard, or by running `iw merge-queue retry-merge` from a terminal. After a recent change that split clean merge failures into a dedicated terminal status, the dashboard learned about the new status but the command-line tool did not. Operators using the terminal now hit "No failed batch item found" on items that the dashboard happily retries — and there is no way to tell from the message that the surfaces simply disagree. This ticket re-aligns them so both paths accept the same items.

## What Changed (for the User)

- The terminal command now accepts every kind of recoverable merge failure that the dashboard already accepted, plus one additional category that was missed everywhere.
- The terminal command also accepts older items that failed merge before the new status labels were introduced, mirroring the dashboard's existing back-compatibility behaviour.
- The terminal command continues to refuse items whose failure was not a merge failure (for example, items that failed during setup or execution) and now explains, in the error message, where the operator should look instead.
- The dashboard's behaviour is unchanged for the operator. Internally it now reads its list of acceptable statuses from the same source the terminal uses, so the two will not drift again.

## How It Behaves

When an operator asks to retry a merge — from either the dashboard or the terminal — the system checks the failed item's category. If it is a recoverable merge failure of any of the recognised kinds, the system flips the item back to "ready to merge", records an audit entry naming the operator action, and the next polling cycle of the daemon picks the item up and tries the squash-merge again. If the item is not in a recoverable category, both surfaces refuse with the same reasoning, pointing the operator toward the right recovery action (for example, restarting the item from an earlier step rather than retrying the merge).

Edge cases:

- If the item's worktree has been pruned from disk, both surfaces still refuse — there is nothing to merge from.
- If multiple batch-item rows exist for the same item across batches, the most recent one is the one considered.
- An audit trail entry is always written when a retry is accepted, regardless of which surface initiated it.

## Out of Scope

- Removing the legacy back-compatibility path. Older items that failed before the new status labels were introduced still need to be retryable, and that path remains supported until a future cleanup confirms there are none left in production.
- Changing what the daemon does after a retry is queued. The retry mechanism itself is untouched — only which items qualify as "retryable" has changed.
