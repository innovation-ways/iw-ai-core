# I-00117 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged.

## Why

While investigating a change request that appeared frozen, an operator found it
had actually been blocked for about nine hours with no signal anywhere. The
automated pipeline had quietly given up on a step it could neither retry nor
auto-fix, but it never told anyone. From the outside the work looked like it was
still running. This wastes operator time and lets blocked work rot unnoticed.

## What Changed (for the User)

- When the pipeline gives up on a step it cannot recover automatically, it now
  records a clear event saying the step exhausted recovery and needs a human.
- The affected work item and its batch entry move to a visible "failed" state
  instead of appearing to run forever.
- Operators can now see, on the dashboard events list and the batch view, that an
  item needs attention — instead of having to notice a suspiciously long-running
  batch by chance.

## How It Behaves

When a step fails for a reason the pipeline cannot fix on its own, the system
first tries its normal recovery paths (re-run, or an automated fix attempt for
review-type steps). If those paths are not available or have been used up, the
system stops, marks the work item and its batch entry as failed, and writes an
escalation event naming the step and the reason. A separate, already-existing
case — where a step asks for something the design explicitly excluded — keeps its
own dedicated escalation and is unaffected.

## Out of Scope

- Adding a brand-new "needs attention" status distinct from "failed".
- Automatically resuming or re-planning the blocked item; a human still decides
  the next move.
