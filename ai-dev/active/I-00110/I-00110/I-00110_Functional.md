# I-00110 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves migrations unchanged — no database schema change is involved.

## Why

Two endpoints on the Keep Alive operator page returned a generic Server Error (HTTP 500) whenever a caller supplied a slot identifier larger than what the database can store. The error was harmless in terms of data integrity, but it polluted dashboard logs with a noisy stack trace on every bad request and gave an attacker a cheap way to make the system look broken. The contract fuzz suite added earlier this month flagged both routes as known offenders and asked for a proper fix.

## What Changed (for the User)

- Both Keep Alive slot actions (delete and toggle) now reject a clearly out-of-range slot identifier with a clean validation error (HTTP 422) instead of a generic server crash (HTTP 500).
- The validation error message names the offending field so an operator or integration caller can immediately see what went wrong.
- Normal day-to-day use is unchanged. Operators clicking Delete or Toggle on the Keep Alive page see identical behaviour to before. The fix only affects requests with absurdly large slot identifiers that no real UI flow would ever produce.

## How It Behaves

When the dashboard receives a Keep Alive slot action with an identifier in the normal range, the system behaves exactly as it always has — the slot is deleted, the slot is toggled, or the system reports the slot was not found. When the identifier is below one, negative, or large enough to overflow the database column, the system now rejects the request up front with a structured validation error that callers can parse. The database is never queried for the impossible value, so no error trace is written to the logs. The automated contract fuzz suite no longer has to skip these two routes, which means future regressions of the same shape will be caught immediately by the existing test infrastructure.

## Out of Scope

- Other endpoints across the dashboard that take integer identifiers are not audited or changed by this work. If a similar overflow problem exists on another route, that is a separate incident.
- No change is made to how slot identifiers are issued, stored, or displayed — only to how the two affected routes validate the incoming value.
