# I-00088 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations are added or modified.

## Why

The dashboard's auto-merge resolver badge has been reading "down" for every project since the feature shipped, even when nothing is actually wrong. The badge is supposed to reflect whether the platform can reach the AI runtime that resolves merge conflicts; instead it reflects a wiring bug that prevents the platform from even attempting the check. Operators cannot trust the badge, and if the runtime ever does go down for real, no one will be able to distinguish a real outage from the permanent false alarm.

## What Changed (for the User)

- The auto-merge badge in each project's dashboard header now reflects the true reachability of the AI runtime, not a wiring bug.
- When the runtime is reachable, the badge reads "healthy". When it has been failing repeatedly over the last 24 hours, the badge reads "down" — for a real reason this time.
- The badge will read "down" for a short period right after this fix lands, until the last 24 hours of historical failures age out of the rolling window. After that, it should self-correct to "healthy".
- No new buttons, screens, or settings — the change is purely in how the badge is computed.

## How It Behaves

Every five minutes, the platform asks the configured AI runtime to reply with a single word. If the runtime replies in time, the platform records "reachable"; if the runtime is missing, slow, or returns an error, the platform records "unreachable" along with a short error string. The dashboard badge looks at the most recent reply and at the rate of failures over the last day to pick one of four states:

- "healthy" — the last reply was reachable and no failures piled up in the last 24 hours.
- "degraded" — there have been some failures recently, but not enough to call it down.
- "down" — the failure rate has crossed the configured threshold for the day.
- "unknown" — the platform has never even tried a probe yet (typically right after enabling the feature for a new project).

Clicking the badge still takes the operator to the Auto-merge view for that project, where the recent probe results, attempts, and verdicts are listed. Nothing about that view changes; only the truthfulness of the badge does.

## Out of Scope

- Changing how the auto-merge resolver itself behaves when a real merge conflict happens — only the health probe is touched.
- Manually clearing the historical "down" verdict from the database — that is operational hygiene, not part of this fix.
