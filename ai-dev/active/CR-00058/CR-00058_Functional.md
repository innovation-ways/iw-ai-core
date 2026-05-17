# CR-00058 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This change does not add or modify any database migration.

## Why

Today the platform refuses to start a new work item whenever it touches any file that another in-progress item is also touching, across any batch in the same project. The rule was added to prevent merge conflicts when two parallel items finish around the same time. Now that we have started shipping automatic merge-conflict resolution (currently in a dry-run audit phase), this blanket rule is too strict — it stalls genuinely safe work, like two items both editing tests or both editing docs that the auto-merger will easily reconcile.

## What Changed (for the User)

- Operators can add an `overlap_gate` block to a project's configuration to tell the daemon which paths are safe to allow parallel work on (an allow list) and which paths must keep blocking (a block list).
- The default behaviour is unchanged: every overlap on any source file still holds the second item, exactly as today. Operators only see a change if they opt in.
- The dashboard now shows two kinds of badge on the batch and queue pages: the existing "held by scope overlap" reason, plus a new "allowed by policy" badge for items that the operator's policy let through.
- The configuration is reloaded by sending a normal reload signal to the daemon; no restart is required.

## How It Behaves

When the daemon considers launching a pending item, it asks: "does this item's set of impacted paths overlap any in-progress item in the project?" If yes, it then applies the project's policy to each overlapping path. A path that matches an allow pattern is dropped from the conflict list. If the conflict list becomes empty, the item launches and an "allowed by policy" event is recorded for the audit trail. If anything remains, the item waits as before, and the existing "held" event continues to fire.

Dependencies between items are unchanged. When item B depends on item A, B still waits until A is merged — that is enforced separately and is not affected by this change.

The hardcoded behaviour that already excluded test files from overlap checks is now visible to operators as part of the default allow list. Anyone who wants to also block on test-file overlap can shrink the allow list; anyone who wants to relax further can extend it.

When the daemon's configuration file is edited and a reload is requested, the new policy takes effect on the next poll cycle. Items that launched under the old policy continue without interruption.

## Out of Scope

- Automatically syncing the overlap policy with the separate auto-merge allow list lives in a future change; for now each is configured independently.
- Relaxing the default for everyone is not part of this change. The defaults stay strict until we have enough audit data on the auto-merger to recommend a looser default.
