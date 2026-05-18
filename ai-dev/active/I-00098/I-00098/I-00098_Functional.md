# I-00098 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged.

## Why

The Keep-Alive Scheduler is supposed to ping the assistant once per configured slot, per day. Operators noticed (via a flaky integration test caught while triaging incident I-00090) that on hosts whose local clock is ahead of UTC, slots that had already fired successfully earlier in the day were getting fired a second time after midnight local. The extra calls launch real assistant subprocesses, write duplicate run-log rows, and create the false impression that the scheduler is over-eager.

## What Changed (for the User)

- A slot that has already succeeded earlier today is now reliably skipped for the rest of the day, regardless of where the host is in the world.
- The duplicate "Hi! How are you doing today?" pings that operators on European hosts saw between midnight and 01:00 local stop happening.
- The Keep-Alive run history no longer accumulates duplicate "success" rows around local midnight; the daily count matches what the schedule advertises.

## How It Behaves

Each minute, the daemon asks "which slots are due right now?" A slot is due when it sits inside the last 30 minutes of local time AND the daily run-log does not yet contain a successful entry for that slot today. The fix changes how "today" is evaluated inside that second check: instead of comparing two calendar-day values that secretly lived in different time zones, the scheduler now asks "did any successful run for this slot fire between today-midnight and tomorrow-midnight in the operator's own local time?" — a question that has the same answer no matter what time zone the database happens to report timestamps in.

Edge cases the new behaviour handles correctly:

- The first minute after local midnight, even when UTC is still on the previous calendar day.
- Daylight-saving boundaries: the local-midnight bounds follow the operator's wall clock, so a 23-hour or 25-hour day is still treated as one day's worth of slots.
- Hosts running in UTC: no change to behaviour — they were never affected by the bug.

## Out of Scope

- The shape of the Keep-Alive run history page and which columns it surfaces. (Unchanged.)
- The slot scheduling window (still the trailing 30 minutes) and the retry-once-on-failure policy. (Unchanged.)
