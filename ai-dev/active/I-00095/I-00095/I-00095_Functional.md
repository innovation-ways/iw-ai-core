# I-00095 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Why

The events table on the Auto-Merge Resolver view shows up to fifty
rows per page and always returns them newest-first. Every other table
on the dashboard supports clicking a column header to sort by that
column — but here the headers are static. Operators routinely need to
group by event type to scan all health probes together, or to find the
earliest event for a given work item by sorting timestamp ascending,
or to gather all events for a single entity by sorting by entity_id.
Today the only way is to copy the table elsewhere and sort manually,
which defeats the purpose of having a dashboard.

## What Changed (for the User)

- The timestamp, event_type, entity_id, and verdict column headers are
  now clickable buttons. Clicking one sorts the table by that column.
- Clicking the same column again reverses the sort direction.
- An up or down arrow next to the active column shows the current
  direction at a glance.
- Sorting cooperates with filtering and pagination: the active filter
  and current page size are preserved through any sort change, and
  vice versa.

## How It Behaves

The page reads sort state from the URL. With no sort query param, the
table shows the default newest-first order, no header is highlighted.
Clicking timestamp once switches to oldest-first; clicking it again
returns to newest-first. Clicking event_type switches to grouping by
event type starting in descending order; clicking it a second time
reverses to ascending. Clicking any other sortable column starts that
column in descending order. The free-text message column and the
non-data actions column are not sortable; their headers remain plain
text.

If a stale URL or a typo arrives with an unknown sort or direction —
for example, `?sort=message` — the server rejects the request with a
clear "bad request" error rather than silently falling back to a
default. This stops accidental column-name injection and surfaces
broken bookmarks immediately.

## Out of Scope

- Multi-column sorting (e.g. "by entity_id then by timestamp"). Single
  column only.
- Persisting an operator's preferred sort across page visits. Each
  load starts from the default.
- A backend-level reverse index for sorting on `message`.
