# I-00113 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This incident introduces no schema changes.

## Why

The orchestration daemon is currently flagging some review re-runs as
"process died unexpectedly" within a second or two of starting them, even
though the agent never had a chance to do any work. Each false flag consumes
one of the five retry slots the system reserves for review steps, so a work
item that should converge in two real attempts instead exhausts its budget
and stalls — needing a human to step in. We saw this happen four times in
eleven review runs on a single recent item.

## What Changed (for the User)

- Re-launched review runs no longer get marked failed before the agent has
  a fair chance to start.
- The five-retry budget reflects real work, not phantom crashes, so review
  steps converge with fewer manual interventions.
- When the daemon does report a "process died" failure, the dashboard event
  trail will carry the diagnostic detail needed to tell a real crash apart
  from a startup race.

## How It Behaves

- After a fix cycle finishes, the daemon launches a fresh review run.
- The new run is given a short grace window during which the daemon treats
  a brief "process not visible" signal as a normal startup race rather than
  a crash.
- If after the grace window the agent really has not started, the daemon
  marks the run failed and surfaces it like any other crash — the existing
  retry and escalation rules apply unchanged.
- Real crashes, timeouts, and stalls are still detected and reported on the
  same cadence as before.

## Out of Scope

- The per-step retry budget itself is not changed. The number of retries a
  step is allowed remains the same; the fix simply ensures phantom failures
  do not consume them.
- Other classes of intermittent daemon failures (heartbeat stalls, timeout
  budgets, browser-verification flakiness) are not covered by this incident.
