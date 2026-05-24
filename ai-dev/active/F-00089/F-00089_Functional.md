# F-00089 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by the new tests are the only exception.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations added or applied. Scenario five simulates a migration-rebase failure in the test database only.

## Why

The daemon is the riskiest component in the platform: it creates worktrees, launches AI agents, manages fix cycles, and is the only component that merges into the main branch. A regression in its recovery logic can leave main half-merged, freeze the merge queue, poison a batch, or strand an item terminal-but-not-merged. Today we have **no deterministic tests** for any of the five documented failure modes. Operators have had to trust recovery; the only signal of a regression was a real incident. This work closes the gap by exercising every failure mode on every pull request.

## What Changed (for the User)

- **For operators**: every pull request now runs a small, fast "smoke" suite of two daemon recovery scenarios; a failure blocks the merge with a clear scenario name. A nightly job runs the full five-scenario matrix and reports through the existing test-report pipeline.
- **For platform reviewers**: a new ninth test layer appears in the testing strategy document with a short section explaining what each scenario guards and how to add a new one.
- **For future feature authors**: the workflow rules now list a ninth canonical quality gate any future work item can opt into.
- **For incident responders**: when daemon recovery fails in production, the named scenarios provide an immediate hypothesis to check locally in minutes.

## How It Behaves

A new chaos test fixture wraps the daemon's poll loop and exposes five named injection hooks, one per failure mode. Each hook is **deterministic**: no random failure, no kill signals, no wall-clock sleeps. A scenario test arms one hook, advances the daemon through one or more poll cycles, and asserts what the daemon did about the failure: the work item is marked with the right terminal-error status; no zombie worktree directory is left behind; the rest of the batch keeps running; main is not left half-merged; the test database's migration history is unchanged after a failed rebase; the fix-cycle counter never exceeds its configured cap.

The five scenarios are: worktree setup failing mid-way; fix-cycle cap exhaustion when reviewers keep rejecting; an agent stalling past the configured stall threshold; a squash-merge conflict against an unrelated update to main; and a migration-rebase failure when a new revision conflicts with the database head.

If a scenario surfaces a real daemon defect, the test does not fix the daemon — it is pinned as expected-fail with a filed incident reference. This work is strictly test-only.

## Out of Scope

- Any change to the daemon's production code; surfaced bugs are filed as separate incidents.
- Browser or visual verification.
- The new ninth quality gate is not enforced on this Feature's own merge — a gate cannot gate its own delivery.
