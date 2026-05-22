# CR-00078 — Functional Design

## Why

Operators can now see the full list of conflicting files behind a held item, but they still have no way to release a hold for a legitimate case. The only workaround is to cancel the whole batch and rebuild it without the conflicting item — slow, destructive, and easy to get wrong. This change lets the operator selectively ignore overlapping files, or unblock the held item in one click, without affecting other batches.

## What Changed (for the User)

- Each conflicting file in the overlap panel now has an "Ignore" button. Clicking it removes the file from the list, records who did it and when, and stops counting it as a conflict for this item in this batch.
- A new "Ignore all & start" button clears every remaining conflict for the held item in one action and lets the platform start it on the next polling cycle.
- The batch Timeline tab shows the ignore actions as audit lines, so reviewers can see which overlaps the operator dismissed and when.
- Ignores apply only to the batch they were made in — there is no permanent or global ignore.

## How It Behaves

When the operator clicks "Ignore" on a file, the row disappears and the decision is recorded in an audit log. If the item still has other conflicting files, it stays held; reopening the panel shows only the files not yet ignored. Once every conflicting file has been ignored — one at a time or via the master button — the platform releases the hold on the next poll and the item starts normally, respecting the batch's parallelism limit.

If the operator presses "Ignore all & start", the platform records one audit line per remaining file plus a summary line, closes the panel, and picks up the item shortly after. The Timeline then shows the ignore events followed by the item's normal launch event.

Clicking Ignore never triggers an immediate launch — the next poll cycle does. This keeps a single owner for the "should this item start" decision and avoids race conditions with other in-flight work in the same batch.

## Out of Scope

- Permanent or cross-batch ignores — an ignore is recorded against the exact (batch, held item, blocking item, file) tuple; a second batch with the same conflict needs its own.
- Undoing an ignore. The audit record is permanent; to reverse course, cancel and rebuild the batch.
- Fixing the case where the plan stage said "no overlaps" but the runtime later finds them — tracked separately.
