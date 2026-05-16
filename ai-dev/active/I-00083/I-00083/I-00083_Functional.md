# I-00083 — Functional Design

## ⛔ Docker is off-limits

Standard policy. No Docker usage.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration impact.

## Why

When two pieces of work are in progress at the same time, the second one
sometimes inherits half of the first one's changes — the new tests but
not the matching production fix. The second item then fails its
quality checks for reasons that have nothing to do with its own quality,
and the operator has to apply small "carry-over" fixes by hand. CR-00053
needed three of these. We want to stop creating that situation.

## What Changed (for the User)

- When a second item is approved while a first item is still being worked
  on, the second item's working area no longer inherits half-finished
  pieces of the first item.
- Operators no longer need to apply small "this test was changed by the
  other in-flight item" carry-over fixes during the second item's run.
- The daemon log shows, at worktree-create time, which other items are
  in flight and how their state was handled. Operators can use this to
  spot drift situations early.

## How It Behaves

When approving an item, the platform records its design and plan as
before, but the on-disk staging that lands on the shared main branch is
narrowed so it cannot accidentally include test fixtures or other
non-design files that should travel with the item's actual implementation.

When creating a working area for a new item, the platform looks at any
other items currently in flight and either confirms the working area is
clean of their partial state, or notes in the log how their pending
state was handled.

The single-item happy path — one item at a time — is unchanged.

## Out of Scope

- This work does not change how merges happen at the end. The pre-merge
  rebase logic is untouched.
- This work does not introduce a "wait for sibling to merge" interlock
  between items; concurrency is preserved.
