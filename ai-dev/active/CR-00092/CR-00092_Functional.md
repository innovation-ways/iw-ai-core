# CR-00092 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This work item adds NO migration. Column descriptions are ORM-side metadata and never reach the SQL schema.

## Why

A previous change introduced a scanner that flags any database column that does not carry a one-line description. To land that scanner without first writing 450 descriptions, the team accepted the existing offenders as a temporary cleanup backlog and configured the gate as "warn-only". This work item pays down that backlog and converts the gate from warn-only to blocking, so the database documentation stays honest from now on instead of silently rotting again.

## What Changed (for the User)

- Every database column on every model now carries a short, plain-English description. Reviewers reading the schema doc or the models file can see at a glance what each column is for.
- The "warn-only" period for the column-documentation gate ends. From this point on, any new column added without a description blocks the change-quality gate before merge, instead of producing a quiet warning that nobody acts on.
- The cleanup-backlog file is removed entirely. There is no longer a list of "known-undocumented" columns to keep in sync — the only acceptable state is "every column has a description".

## How It Behaves

When someone adds a new database column in the future, they have to write a one-line description for it at the same time. If they forget, the change-quality gate fails before the change can land, and the failure message points at exactly which column is missing the description. Existing columns are unaffected — the work item touches only the descriptions on column declarations, not the columns themselves, the data inside them, or the database schema.

For day-to-day users of the platform — operators watching the dashboard, agents running through the work-item pipeline, anyone reading the database schema document — nothing changes visibly. No tables move, no rows change, no screens look different, and no command behaves differently. The benefit is invisible until the next time a reviewer reaches for the schema doc and finds that every column actually has a description, or until the next time someone tries to land a sloppy new column and the gate catches it.

## Out of Scope

- Editing the schema documentation itself. The schema document is the source of truth that descriptions are read from where available; this work item never writes to it.
- Old database migration files. The scanner only sees the live ORM models, so historical migration files are not in scope.
