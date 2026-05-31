# I-00122 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves migrations unchanged.

## Why

Twice now — once in April and again at the end of May — the platform appeared to
lose everything: the dashboard showed a single project and no batches at all. The
data was never actually lost. What happened is that the real production database
went offline, and the start-up routine reacted by quietly spinning up a brand-new,
empty database in its place on the same network port. Every background service
then connected to that empty stand-in while the real database sat untouched and
offline. The goal of this work is to make sure an empty database can never silently
take over for a production database that is simply down.

## What Changed (for the User)

- When a production identity is configured and the real database is offline, the
  start command now **stops and refuses** instead of creating an empty database. It
  prints a clear message explaining that the production database is down and how to
  bring it back.
- Operators get a documented, scripted way to restart the real production database
  safely, instead of relying on memory or ad-hoc commands.
- The real production database can be configured to restart automatically if it
  ever stops, so the original trigger is far less likely to occur.
- Fresh development machines are unaffected: with no production identity
  configured, the start command still creates a local database exactly as before.

## How It Behaves

In normal operation nothing changes — if the database is already running, the
start command simply confirms it and exits.

If the database is not reachable, the start command first asks one question: is a
production identity configured? If yes, it treats the situation as "production
database is down" and refuses to proceed, pointing the operator to the safe restart
procedure. If no production identity is configured, it assumes a fresh development
machine and creates a local database as it always has.

The safe restart procedure reads the location of the production data from
configuration rather than a fixed, built-in path, so it works across machines
without editing the script. When that location has not been configured, the refusal
message explains how to set it.

## Out of Scope

- Automated, off-site backups of the production database (regular snapshots kept
  somewhere other than the live data location). The current backup is old and
  stored next to the live data, which is unsafe; replacing it with proper backup
  tooling is recommended as separate, follow-up work and is not part of this fix.
