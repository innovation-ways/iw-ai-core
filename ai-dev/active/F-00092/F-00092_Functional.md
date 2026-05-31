# F-00092 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds one new table to record backups; the agent writes
the migration and the daemon applies it.

## Why

The orchestration database had no backups worth the name — the only one was a
single snapshot taken weeks earlier and kept right next to the live data, so a
single mishap could lose both at once. After three separate scares where the
platform briefly ran on the wrong, empty database, we need dependable, automatic
backups with a clear way to restore them. This feature delivers that.

## What Changed (for the User)

- The platform now takes an automatic backup of its database once a day and keeps
  the last 30 days of them. All of these settings — on/off, where backups are
  stored, how many days to keep, and what time of day — are configurable.
- Operators can take a backup at any moment on demand, optionally tagging it with a
  label (for example, before a risky change). On-demand backups work even if the
  background service is not running.
- Tagged/manual backups are never automatically deleted, so a deliberate
  safety snapshot won't disappear on its own.
- There is a guided way to restore a backup that, by default, restores into a
  separate safe location rather than overwriting the live database, and then checks
  that the restored copy is healthy.
- Backups show up in the existing Jobs view alongside the other background jobs, so
  you can see when the last one ran and whether it succeeded.
- New written guidance explains how to restore, step by step.

## How It Behaves

Once a day at the configured time, the system makes a complete backup: the database
contents plus the account/password information needed to restore it cleanly, plus a
small summary file describing what was captured. Each backup is checked for
readability before being marked successful.

If the background service was switched off across the daily window, it notices the
missed backup as soon as it comes back and takes one right away rather than waiting
another full day.

Old daily backups beyond the retention window are cleaned up automatically; manual
labeled backups are left alone. Restoring is a guided operation that puts the data
into a safe target first and confirms the result, keeping the live system out of
harm's way unless the operator explicitly chooses otherwise.

## Out of Scope

- Continuous, minute-by-minute recovery points and copying backups to a remote or
  off-site location — these are planned as a separate, later piece of work. By
  default backups are kept on the same machine as the database, which guards
  against accidental changes but not against a full disk failure; the storage
  location is configurable so it can be moved off-machine later.
- Backups of the temporary per-task databases, which are always rebuilt from the
  main database and do not need their own backups.
