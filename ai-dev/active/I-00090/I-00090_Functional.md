# I-00090 — Functional Design

## ⛔ Docker is off-limits

Standard policy. This item does not run any docker commands.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged.

## Why

The system-wide Running Tasks page is the operator's live triage board for what needs attention right now. It currently lists failed steps from work items that have long since been completed or cancelled, so the operator sees noise from items that can no longer be acted on. Today four such stale rows appear, all belonging to old change requests closed weeks ago. The operator reported this on 17 May 2026 and asked for the page to show only steps from currently active work.

## What Changed (for the User)

- The "Failed / Needs Attention" table on the system-wide Running Tasks page and on every per-project Running Tasks page now only includes failed or needs-fix steps from a work item the operator considers currently active.
- The "Recently Completed (last hour)" table on the same pages is filtered the same way, so a step that finished an hour ago on a since-closed item no longer shows up.
- The "Running Now" table is unchanged.

A work item is "currently active" when it has not been archived and its status is neither "completed" nor "cancelled". Items in draft, approved, in progress, paused, or failed status still surface — in particular, item-level "failed" remains visible because it represents an unresolved problem the operator still needs to see.

## How It Behaves

When the operator opens the Running Tasks page, the dashboard asks the database for failed steps and for steps that completed in the last hour. Both questions now include an extra condition: the parent work item must not be archived and must not be in "completed" or "cancelled" status. Steps that fail this condition are simply not returned, so they never appear in the rendered tables.

The historical record is untouched. A failed step from an archived or closed item is still stored with its original status, available for audit, history, or the item detail page; it just no longer pollutes the live triage board. As soon as the operator closes or archives an item that previously had failed steps, those rows disappear on the next page render or live refresh. A brand-new failure on an active item appears immediately on the next refresh, exactly as it does today.

Items in "failed" status keep surfacing on purpose. "Failed" at the item level means the work could not be finished and still needs an operator decision; hiding it would defeat the point of the page.

## Out of Scope

- The "Running Now" table is not filtered by this change. In production today no running step exists whose parent item is closed, and silently hiding any such row could mask an orphaned-process bug; a follow-up will be filed only if such a case is observed.
- Historical step rows are not rewritten. Audit-trail data stays exactly as it is.
