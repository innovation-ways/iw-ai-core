# I-00114 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This Incident does not touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This Incident does not add or modify any migration.

## Why

When a work item runs under the Codex agent runtime, the agent sometimes ends a turn by announcing its next move in plain prose ("I'll now run the tests and report back") instead of actually performing the move. The runtime then considers the turn over and quits. The orchestrator has no way to tell that apart from a genuine crash, so it counts the silent quit as a real failure and spends one of the item's two retry attempts on it. When the same pattern repeats on the retry, the item stalls and an operator has to step in. This was discovered today while investigating why one work item stalled on its 5th step.

## What Changed (for the User)

- Steps that previously stalled because the agent narrated instead of acting are now recovered automatically, without consuming the retry budget.
- Operators see a new event in the Jobs view labelled "narration exit". It tells them which step had to be re-prompted, how many times, and what the agent's last narrated message said. This makes the pattern visible at a glance instead of hiding behind a generic "crash" entry.
- The genuine retry budget (two attempts per implementation step) is now spent only on real failures — broken tests, crashed test runners, real timeouts.

## How It Behaves

When the Codex runtime exits cleanly after the agent emitted only narration, the orchestrator pauses, records what the agent's last message was, and re-launches the same agent in the same conversation with a brief nudge: "you announced an action but did not perform it; please continue and finish the step properly". The agent picks up where it left off. This can repeat up to five times. If after five nudges the agent still has not closed the step, the orchestrator gives up on the in-place recovery and lets the normal retry machinery take over — same behaviour as today.

For agent runs that end normally (the agent did close the step), nothing changes. For runs that end with a real crash (non-zero exit code) or a real failure signal, nothing changes either — those still count as real failures and consume a retry slot.

The change applies only to the Codex runtime. Other agent runtimes the platform supports are untouched because they do not exhibit the same exit-on-narration pattern.

## Out of Scope

- Changing how the agent itself behaves (the narration tendency is a model property and is not addressable on the orchestrator side).
- Generalising the guard to other agent runtimes; that would only be revisited if a different runtime ever shows the same pattern.
- A dedicated dashboard badge for narration-exit events; the existing generic event row in the Jobs view is sufficient for now and can be styled later if the pattern becomes frequent.
