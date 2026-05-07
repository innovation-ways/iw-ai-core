# F-00080 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This feature does not touch migrations.

## Why

When IW AI Core ships as public Apache 2.0 OSS, a first-time visitor opens the dashboard with no idea what most of the pages do — Queue, Batches, Worktrees, Jobs, Code, Quality — the vocabulary is novel and the relationships between pages are not obvious. Forced welcome tours have a high skip rate and annoy returning users. The goal is to make every page self-explanatory within seconds, without ever blocking the workflow, so a curious developer evaluating the project can get oriented and stay.

## What Changed (for the User)

- A small "?" help button now appears next to the title on every project and system page in the dashboard.
- Clicking it opens a short popover with four sections: a one-sentence definition of the page, what you can do on it, the vocabulary used here (e.g. "worktree", "fix cycle"), and a button to take an optional thirty-second guided tour.
- Empty list views (queue, batches, jobs, history, tests, quality, research, docs, worktrees, active items) now show a clear heading, a one-sentence explanation of what populates the list, a primary action button, and a "Learn more" link, instead of a blank screen.
- The optional tour, when started, walks through three to five highlighted spots on the page. It can be exited with the Escape key, a Close button, or by clicking outside it. Once finished or dismissed, a subtle check mark next to the help button reminds returning users that they have already seen the tour.
- Nothing pops up automatically on first visit. There is no welcome modal and the tour never starts on its own.

## How It Behaves

The help button is always available but never demands attention. Click or focus it with the keyboard, and the popover loads its content from the server (so help text is in regular templates, not buried in JavaScript). Pressing Escape closes the popover and returns focus to the help button, so a screen-reader user is never trapped.

The "Take the tour" button inside the popover starts the guided walkthrough. The tour highlights one element at a time, in a fixed three-to-five-step sequence per page. At any moment the user can press Escape, click "Close", or click outside the highlighted area to leave the tour. When it ends — completed or dismissed — the dashboard remembers, locally in the user's browser, that this page's tour has been seen, and the small check mark appears the next time the page loads.

If the dashboard cannot find a help topic for a page, the help button simply does not render on that page; nothing breaks. If the tour script fails to load (vendored library missing), the "Take the tour" button is disabled with a tooltip and the rest of the popover still works. None of this involves cookies, telemetry, or any outbound network call — everything stays inside the user's browser and the project's own server.

## Out of Scope

- A "Load demo project" button that pre-populates the dashboard with realistic example data — that is planned as a separate, larger feature.
- A keyboard "command palette" for searching across help topics — also a separate, later feature.
- Translation of help text into other languages — not part of this work, but the architecture leaves it as a future translation pass on the help templates.
