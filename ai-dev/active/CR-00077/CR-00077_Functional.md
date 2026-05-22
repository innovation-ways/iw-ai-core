# CR-00077 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This work adds no schema changes and no migrations.

## Why

When a batch is running and one of its items is held because its files conflict with another item, the dashboard shows a small pill that lists the first two conflicting files and abbreviates the rest as "plus N more". Operators have no way to discover the full list, no way to see whether the same item conflicts with one other item or with several, and have to read the database directly to investigate. This change closes that visibility gap.

## What Changed (for the User)

- The "held because of overlap" pill is now a button.
- Clicking it opens a small panel that lists every conflicting file, grouped by the other item that is causing the conflict.
- Each group shows the other item's ID and title with a link to its detail page.
- The panel is read-only — the operator can still only cancel the whole batch to release a held item; this work does not yet add a per-file "ignore" control. That follows in a separate change.

## How It Behaves

In the Items tab of any batch, every held item displays the familiar "held because of overlap" pill. Clicking the pill opens a panel centred over the page; the panel lists each other item this one conflicts with as its own section, and under each section every conflicting file is shown verbatim with no abbreviation. The panel can be dismissed by clicking outside it, clicking its close button, or pressing the Escape key. When the operator opens the panel after the held item has just been released by the daemon (rare timing window), the panel shows a short message saying the overlap details are no longer available rather than presenting stale data.

## Out of Scope

- Adding an Ignore button per file or an Ignore-all-and-start button. Those ship in a follow-up change request.
- Changing how the platform detects overlaps in the first place. A separate incident covers the planner reporting "no overlaps" at batch-creation time while the runtime detects them.
