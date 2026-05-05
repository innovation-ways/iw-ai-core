# I-00067 — Functional Design

## Why

The project dashboard's Recent Activity card was showing the full text of every event inline, including very long failure messages that span many lines. Long stack traces pushed the card to dozens of lines tall and visually drowned shorter, more recent events. Operators reported that the card had become hard to scan, and there was no clean way to read a long message in isolation.

## What Changed (for the User)

- Activity rows whose message is longer than one hundred characters now show only the first one hundred characters, followed by three dots, on the dashboard.
- Truncated rows show a click affordance. Clicking it opens a popup that displays the full untruncated message in one place, with no surrounding noise.
- Activity rows whose message is one hundred characters or shorter look exactly as they did before — no trailing dots, no popup, no click affordance.
- Links on activity rows (to batches, jobs, and work items) continue to work exactly as before.

## How It Behaves

When the dashboard loads, each Recent Activity row is rendered with the same timestamp, link badge, and message as before. The only difference is in the message text:

- If the message is short, it appears verbatim.
- If the message is long, the row shows a shortened preview ending in three dots and becomes clickable.

Clicking a shortened row opens a popup over the page. The popup shows the entire original message in a clean, scrollable area. The user can dismiss the popup by clicking its close button, by clicking outside the popup, or by pressing the Escape key. After closing, keyboard focus returns to the row that was clicked, so keyboard navigation is preserved.

The truncation only affects what is visible at first glance. Nothing about how events are stored, ordered, filtered, or generated changes. Operators still see the same events in the same order, and the full text of every event remains accessible in one click.

## Out of Scope

- Redesigning the Recent Activity card layout, adding pagination, or changing how events are filtered or ordered.
- Trimming or rewriting the messages produced by the daemon, the worker pipeline, or any other event source. This change adjusts only how the dashboard displays them.
