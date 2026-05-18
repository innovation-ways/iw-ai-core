# I-00092 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Why

In the Auto-Merge events table, a user picks one of the seven filter
buttons across the top — "all", "resolved", "attempted", and so on —
and the table correctly narrows to just those events. But none of the
buttons themselves change appearance. There is no visual cue showing
which filter is active, so the operator has to remember what they
clicked or read the URL bar. This is the smallest possible information
gap, and it makes the filter bar feel broken even when it isn't.

## What Changed (for the User)

- The currently-active filter button is now visually distinguished from
  the inactive ones — same highlighting style the rest of the dashboard
  already uses on selected chips and toggles.
- Each filter button now has a hover tooltip naming the underlying
  event type it filters to (e.g. hovering "resolved" reveals
  "merge_auto_resolved"). Operators can correlate the chip with the
  event_type column without leaving the page.
- The active button is also announced as such to screen readers via
  standard ARIA attributes.

## How It Behaves

The page reads which filter is in effect from the URL query string. If
the URL has no filter set, the "all" button is highlighted. If the URL
has `?type=merge_auto_resolved`, the "resolved" button is highlighted.
Switching filters clicks through the same way as before; the only
behaviour change is the cosmetic and assistive one. The events table
itself, the pagination, and the underlying filter URLs are unchanged.

## Out of Scope

- Renaming chip labels to exactly match their event_type values
  (e.g. "resolved" → "merge_auto_resolved") — kept as a future polish.
- Adding new filter categories beyond the seven that exist today.
