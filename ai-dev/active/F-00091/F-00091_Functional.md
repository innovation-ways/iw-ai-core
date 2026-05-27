# F-00091 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This feature adds one data-only migration that backfills context-window sizes for already-known models.

## Why

The AI Assistant on the dashboard has three usability defects that, taken together, make it disruptive to use day-to-day. Clicking any sidebar link instantly replaces the assistant's chats with whichever project the page is for, so a conversation about Project A vanishes the moment you peek at Project B. Closing the browser window has a similar effect — reopening lands you on a different chat than the one you left active. And the context-window usage indicator added recently only shows up when several server-side conditions line up, so for many users it never appears, leaving them flying blind on how much of the model's window has been spent.

## What Changed (for the User)

- The Assistant panel now has its own project selector at the top. The Assistant only changes projects when you choose a different one there. Browsing other projects or system pages no longer affects it.
- Your last open chat in each project is remembered across browser windows and full restarts. Reopening the dashboard puts you back where you were.
- The "how full is the context" reading is now a small horizontal bar with a percentage next to it, always visible while a chat is active. Green means plenty of room, amber means getting close, red means almost full. Hovering shows the exact token counts.
- When the system genuinely does not know the context window for the current model, the bar is shown greyed out with a dash for the percentage and a hint explaining why. It is never silently missing.

## How It Behaves

When you first open the dashboard, the Assistant chooses a starting project sensibly: the page's project if you are on one, otherwise the first project alphabetically. You then pick any project from the dropdown, and that choice sticks. Switching pages, hopping to system views, or opening a second browser window all keep the Assistant pointed at your chosen project until you change it.

Each project has its own list of chats and its own "last active chat" memory. Switch projects in the dropdown and you see that project's chats with the one you were last in already selected. Switch back and the previous project is exactly as you left it, including the running message history.

The usage indicator polls the active chat every few seconds. The percentage and the bar width move together. When the runtime is healthy and the model is recognised, you get a precise reading with both used and total token counts in the tooltip. When something is missing on the platform side, the indicator stays in place but switches to the greyed unknown state with an explanatory hint — never simply hidden.

## Out of Scope

- An "auto-follow the URL project" toggle. The new behaviour is strict: only the dropdown changes the Assistant's project.
- Migrating the dashboard to a single-page-application shell. The Assistant survives full page reloads through stored state, not by avoiding them.
