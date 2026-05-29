# I-00118 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged.

## Why

The platform already has a feature meant to stop a work item from being blamed for
problems that were already present before it started. But that protection only
ever worked for a handful of quality checks. For all the other checks, a problem
that was already failing on the main line would be pinned on whatever work item
happened to run next — wasting its automated repair attempts and eventually
failing it for something it never touched. This is what turned a recent change
request's situation toxic: a quality check was already failing on the main line,
unrelated to the item.

## What Changed (for the User)

- The "ignore problems that already existed" protection now covers every quality
  check, not just a few.
- A work item is no longer failed or sent into repair loops because of a problem
  that was already present on the main line before it began.
- Brand-new problems the item actually introduces are still caught and reported as
  before.

## How It Behaves

When a work item starts, the system records which quality checks were already
failing at its starting point. Later, when those checks run on the item's work, it
compares the new results against that starting snapshot and only flags differences
the item itself caused. Previously this comparison happened for only four checks;
now it happens for all of them, using a precise comparison where one exists and a
safe line-by-line comparison everywhere else. If a check has a genuinely new
failure, it is still reported and repaired as usual.

## Out of Scope

- Blocking all work whenever the main line has a failing check (a blunter approach
  that was considered and rejected).
- Changing how the quality checks themselves run or what they test.
