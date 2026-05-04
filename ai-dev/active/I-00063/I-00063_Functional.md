# I-00063 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This issue does not add or modify any migration — it
fixes a session-lifecycle bug in the daemon's migration apply path.)

## Why

A live operator incident on 2026-05-04 froze the iw-ai-core dashboard
for over three hours after a routine batch merge. The migration banner
appeared, every page that listed batches or work items hung, and the
daemon stopped processing batches entirely. Recovery required a force
kill of the daemon plus manual database edits. We need to make this
class of failure impossible to repeat — every future schema change that
touches a busy orchestration table is otherwise at risk of triggering
the same multi-hour outage.

## What Changed (for the User)

- Routine batch merges that include a database schema change no longer
  freeze the daemon or the dashboard. Pages that list batches and work
  items stay responsive while a migration is being applied.
- If a migration cannot acquire its database lock within thirty seconds
  (or whatever value the operator has configured), it fails fast with a
  clear error in the daemon log instead of hanging silently. The
  rollback step then runs automatically.
- The audit trail captures every failed apply attempt with a useful
  error message, so an on-call engineer can see what went wrong without
  digging into PostgreSQL internals.
- The migration banner on the dashboard will appear and disappear in
  seconds rather than persisting for hours when something goes wrong.

## How It Behaves

When the daemon merges a batch that includes a schema change, it now
finishes recording the merge — the success event, the worktree
teardown, any downstream document-regeneration triggers — and lets go
of its database connection before starting the migration apply. The
migration then runs against a clean lock state, finishes within
seconds, and the daemon picks up its next item.

If something unexpected does block the migration — a stale connection
elsewhere, an ad-hoc query holding the table — the apply waits up to
thirty seconds, then aborts with an error naming the lock and the
backend that held it. The standard rollback step kicks in, the audit
log records the failure, and the daemon continues with the next item
instead of stalling. The operator sees a clear actionable line in the
daemon log and the audit trail rather than a silent freeze.

For migrations that are genuinely slow on large tables, the operator
can raise the wait limit via configuration. The default is tuned for
the orchestration database, where every table is small enough that
thirty seconds is a generous upper bound on legitimate lock waits.

## Out of Scope

- Migrations that take exclusive locks on tables outside the
  orchestration database (per-worktree application databases) are
  unaffected and unchanged.
- Adding a periodic heartbeat to the daemon log so future hangs are
  diagnosable without reaching for database internals — useful but
  filed separately.
