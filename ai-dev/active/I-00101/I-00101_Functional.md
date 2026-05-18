# I-00101 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged.

## Why

The platform's recovery system can hold a work item indefinitely when a self-healing attempt edits a file the item never declared it would touch. The system records the rejection correctly behind the scenes, but the operator sees only a generic "needs fix" indicator with no clue that the problem is a permission decision rather than a real failure. The standard recovery buttons make things worse — restarting reproduces the loop, and skipping lets a real failure slip through. The operator has to drop into a shell, hand-edit a JSON file in two places, and run a CLI command. This stranded a real work item for over half an hour this week.

## What Changed (for the User)

- A new amber-with-warning **Scope blocked** indicator now appears on any step whose self-healing attempt was rejected for touching a file outside its declared scope. It replaces the generic "needs fix" pill for that case both on the per-item view and in the global "needs attention" table. Hovering reveals the exact files involved.
- Two new buttons sit next to Restart and Skip on a scope-blocked row:
  - **Amend scope & restart** — opens a dialog that pre-fills the offending paths as checkboxes. Submitting adds the selected paths to the work item's permitted-file list (in both the live working-copy version and the design-time record), records who amended it, and re-queues the step. The recovery system picks it up within a minute.
  - **Revert & restart** — discards the out-of-scope edits and re-queues the step without changing the permitted-file list, giving the recovery system a fresh chance to fix the gate failure a different way.
- A scope rejection no longer consumes one of the limited self-healing attempts. Operators get back the full retry budget for genuine failures.

## How It Behaves

When the recovery system rejects an edit as out of scope, it records both the rejection (as before) and a marker the dashboard uses to identify the situation. The Scope blocked indicator surfaces only when a step is waiting on operator input *and* that marker is present.

If an operator tries either new button on a step that's stuck for any other reason (a code defect, a test failure), the system declines and explains why. The buttons appear only when scope is actually the blocker.

The Restart button is hidden on scope-blocked rows because it would reproduce the same loop. Skip remains available.

## Out of Scope

- No changes to the permission model. Any operator viewing the dashboard can amend or revert scope; the new buttons inherit the same access as Restart, Skip, and Approve.
- No automatic acceptance of out-of-scope edits. The operator is always the one deciding whether a path goes into the permitted list.
