# CR-00036 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This change adds one schema migration, written by the database step and applied by the daemon during the merge pipeline.

## Why

Today every work item that finishes successfully is auto-merged into the main branch. There is no opportunity for a human to look at the work first. For sensitive items, experiments, or any case where the operator wants to eyeball the result before it lands, that is uncomfortable. We want to keep the current convenient default but allow the operator to ask for a manual merge step when they choose.

## What Changed (for the User)

- A new **Auto-merge** option is visible on the batch-creation form, alongside the maximum-parallel control. Yes is the default and matches today's behaviour exactly.
- Each project can declare its own default for Auto-merge. The form pre-fills from that default; the operator can override it on any batch.
- When Auto-merge is "no", an item that finishes its work successfully does not merge. Instead the merge step on the item detail page shows an "awaiting approval" state with a **Merge** button next to it.
- Clicking **Merge** starts the same merge that would have happened automatically — pre-merge migration rebase, squash into the main branch, worktree cleanup. Nothing else about the merge changes.
- The command line has matching support: a flag on the create-batch command and a new approve-merge command for items.
- On the batch's Plan tab the Auto-merge value is visible and editable while the batch has not yet started running, mirroring the maximum-parallel control.

## How It Behaves

- A batch with Auto-merge enabled behaves exactly as today: items run, succeed, and merge automatically with no user interaction.
- A batch with Auto-merge disabled runs items the same way, but a successful item parks in an "awaiting approval" state. It does not consume further automation; the worktree stays alive until the operator clicks Merge.
- When the operator clicks Merge (or runs the matching command), the item joins the merge queue and is processed in the usual order.
- Multiple items in the same batch can be in "awaiting approval" at the same time. They are merged in whatever order the operator approves them.
- If a manually triggered merge fails — for example, due to a rebase conflict — it surfaces the same recovery options that already exist today (Restart Merge and Abandon Merge). There is no special retry logic.
- An item that fails before reaching the merge step never enters the awaiting-approval state. The flag only applies to successfully completed items.

## Out of Scope

- A "discard without merging" action that closes the item and cleans up the worktree without ever landing the changes.
- Per-item override of the batch-level Auto-merge value. The flag is strictly batch-level.
