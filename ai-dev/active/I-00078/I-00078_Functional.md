# I-00078 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work changes only the dashboard's appearance and layout — it adds no database changes.

## Why

A user reported that the dashboard's scrollbars are very hard to see in dark mode, that the small horizontal scrollbar beneath the step pipeline crowds the steps, and that the page sometimes shows two vertical scrollbars on the right — which can push the bottom usage bar (Claude and MiniMax limits) below the visible window so it has to be scrolled into view. They also asked for the "Toggle theme" control to move out of the left navigation panel and into that bottom bar, and for the bottom bar to stretch across the whole window and stay pinned to the bottom at all times.

## What Changed (for the User)

- Scrollbars are now clearly visible in both light and dark mode, get a subtle highlight when you hover over them, and look consistent across browsers.
- The horizontal scrollbar under the step pipeline now has a bit of breathing room so it no longer sits right against the step boxes.
- The page now has a single vertical scrollbar (for the page content) instead of two competing ones.
- The bottom usage bar — showing Claude and MiniMax usage and the app version — now spans the full width of the window, including underneath the left navigation panel, and is always visible at the bottom without scrolling.
- The "Toggle theme" button has moved from the bottom of the left navigation panel into the bottom bar, on the left side, before the usage meters. It still switches between light and dark and remembers your choice.

## How It Behaves

When you load any dashboard page, the layout fills exactly the visible area of the window: the left navigation panel and the page content sit side by side, and the bottom bar runs across the full width beneath them. Only the page content area scrolls when it's long; the navigation panel and the bottom bar stay put. If the "schema is behind" warning banner appears at the top, the rest of the layout still fits the screen and the bottom bar remains visible. Clicking "Toggle theme" in the bottom bar flips the whole interface — including the freshly visible scrollbars — between light and dark immediately, and the preference persists across page loads and sessions.

## Out of Scope

- The small moon icon next to "Toggle theme" still always shows a moon glyph; making it switch to a sun in dark mode is a separate cosmetic tweak, not part of this work.
- No changes to what the usage meters measure or how often they refresh — only where the bar sits and how wide it is.
