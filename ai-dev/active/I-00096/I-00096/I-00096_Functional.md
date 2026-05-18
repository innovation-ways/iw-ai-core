# I-00096 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Why

The Auto-Merge Resolver page has two presentation problems that
together make it feel unfocused. First, the same status chip — "phase
1, runtime X, N attempts, ● down" — appears twice: once in the global
top bar (where it is useful for a quick glance from other pages) and
once again inside the page itself (where it adds nothing because the
page already shows everything the chip says). Both copies link back
to the same page the user is already on. Second, the events list on
this page is dominated by daemon events that have nothing to do with
auto-merge — step launches, step completions, item approvals, crash
notices. On any active project these dwarf the actual auto-merge
events the page is named after, and operators have to filter every
time to see what they came for.

## What Changed (for the User)

- The Auto-Merge Resolver page shows the status chip exactly once,
  inline in the page header. The top-bar copy is hidden while the
  operator is on this page (it still appears on every other page).
- The events list defaults to showing only auto-merge events. The
  health probes, the config-update entries, the resolved-merge entries
  — those are visible. Step launches, item approvals, fix-cycle
  notifications, and crashes are filtered out by default.
- A new "Show all daemon events" toggle in the filter row reveals the
  full project-wide event log when an operator explicitly asks for it.
  The choice is reflected in the URL so it can be bookmarked and
  shared.

## How It Behaves

The status chip works as today, just no longer duplicated. Every page
in the project that isn't the auto-merge page continues to show the
top-bar chip; the auto-merge page itself shows the bigger in-page
chip instead.

The events table defaults to a tight set of event types — anything
the daemon emits with an `auto_merge_*` or `merge_auto_*` prefix.
Toggling "Show all daemon events" widens the query to include every
daemon event for the project, sorted and filtered the same way as
before. The seven existing filter chips ("all", "resolved",
"attempted", …) keep their existing meaning; the "Show all" toggle
sits next to them as a distinct affordance.

## Out of Scope

- Reorganising how daemon events are stored or named.
- Adding new filter categories beyond the existing seven and the new
  "Show all" toggle.
- The status chip's visual design itself.
