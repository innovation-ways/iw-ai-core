# I-00100 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migration. This work does not change any database schema.

## Why

The orchestration daemon has a built-in safety circuit meant to halt automatic recovery when the same fix-cycle keeps resetting the same upstream gates over and over. It is meant to fire after three same-shape cascades and tell the operator that automatic recovery has given up and human review is needed. In practice the circuit has never fired, because the config it needs to make a decision is dropped before it reaches the decision point. The cost of the silent failure is real: a single stuck work item observed today wasted around five hours of CI compute replaying the same gate suite, with eleven cascades fired and no warning event raised.

## What Changed (for the User)

- Operators monitoring the dashboard now see a clear `cascade thrashing detected` event when a fix cycle starts looping on the same upstream gates. Previously this event existed in code but never appeared in real runs.
- Stuck work items stop replaying the same expensive gate suite once the threshold is hit. They sit in a state that asks for a human, rather than burning more compute.
- For runs that hit a real but isolated failure, behaviour is unchanged. The safety circuit only engages on the repeated, overlapping pattern.

## How It Behaves

When a fix cycle finishes and would normally reset earlier quality gates so they re-run against the patched code, the daemon now also checks the recent history for the same trigger step. If three consecutive cycles for that trigger have asked to reset essentially the same set of upstream gates, the daemon refuses the reset, raises a thrashing event with details about the trigger, the cycle count, and the gates that would have been reset, and leaves the upstream gates in their current state. The thresholds are configurable per project and default to three cascades with at least 50% overlap between consecutive reset sets. Items that are simply slow or fail once or twice on different gates are not affected — only the pathological repeat pattern is.

## Out of Scope

- Changing the thresholds or the default per-project values.
- Changing what happens after the thrashing event fires beyond raising the event and skipping the reset. Item-level pause, alerting, or auto-cancellation are future follow-ups, not part of this incident.
- The separate cap that limits the absolute number of fix cycles per step. That cap is a different mechanism and stays as it is.
