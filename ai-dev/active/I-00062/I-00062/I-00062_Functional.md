# I-00062 — Functional Design

## Why

While running a Feature with new database changes through the platform, the
operator noticed the dashboard was disabling all write actions and reporting
that its orchestration database was out of sync with the codebase. Triage
showed the in-flight Feature's database changes had been silently applied to
the orchestration database itself, instead of to the temporary database that
each Feature uses while it is being built. That is a hard isolation breach:
in-flight work is supposed to be invisible to the orchestration database
until the Feature actually merges. This incident closes that hole.

## What Changed (for the User)

- An operator running a Feature that introduces a database migration no
  longer sees the dashboard banner "schema mismatch — write actions
  disabled" while the Feature is still in progress. The orchestration
  database stays at the head matching the merged code base; only the
  Feature's own temporary database picks up the in-flight migration.
- If a future code path ever tries to leak orchestration database
  credentials into a Feature's agents again, the platform now refuses
  to start that agent and surfaces a clear error pointing at this
  incident's runbook, instead of silently writing to the wrong database.
- No user-visible change to the normal happy path: Features that have a
  per-worktree database stack continue to work, with their migrations
  landing in the right place automatically.

## How It Behaves

When the orchestrator launches a step for a Feature that has its own
temporary database stack, the step now starts with database connection
details that point at that temporary database, not at the orchestration
database. Anything the agent runs inside the worktree — including ad-hoc
build, install, or migration commands — therefore writes to the temporary
database, exactly as the architecture intends.

If a step is launched *without* a temporary database stack, the step
starts with no orchestration database connection details inherited from
the daemon. The platform still records the orchestration database's
identity in a separate set of variables (used only by `iw step-done` and
similar bookkeeping commands), so the safety net described next can
recognise the mismatch.

A safety net runs inside the configuration loader: any agent process
whose primary database port resolves to the orchestration port — for
example because a worktree's `.env` still mirrors the main configuration
— refuses to boot and prints a one-line error referencing this incident.
That makes a regression loud rather than silent, regardless of whether
the project uses a temporary database stack or shares the orchestration
database during development.

## Out of Scope

- Recovery automation for orchestration databases that were already
  contaminated by past leaks (the operator handled the F-00077 case
  manually before this incident was filed; no other instances are
  known).
- Generalising the per-worktree database stack to projects that do not
  yet opt in via `iw-config` — that work continues independently.
