# F-00086 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This Feature adds one Alembic revision creating a new table for chat tabs; no existing tables change.

## Why

Today the AI Assistant panel supports a single conversation at a time. Switching context — a different work item, a different model — means losing or burying the current thread. The user wants several independent chats running side by side, each with its own model, persistent across page reloads. This Feature delivers the multi-tab experience on the existing OpenCode runtime. A follow-up Feature will add Pi as a second selectable runtime in the same surface.

## What Changed (for the User)

- The AI Assistant panel now has a row of tabs at the top, one per open chat.
- A "+" button next to the tabs opens a small modal where the user picks a model and an optional title, then opens a new chat in a new tab.
- Each tab keeps its own conversation, its own model selection, and its own streaming output. Sending or aborting a prompt in one tab does not interrupt the others.
- The model used by a tab can be changed at any time from a dropdown above the composer; the change applies to that tab only and only to subsequent prompts.
- Tab names can be edited in place (double-click to rename), and tabs can be duplicated or closed from a right-click menu.
- Closed tabs are not gone forever. A "Recent closed" menu lists the last few closed tabs and lets the user reopen any of them with the full history intact.
- Tabs survive page reloads, in the order they were last active.
- On first load after this Feature ships, any prior conversation from the single-session chat is automatically restored as a tab called "Default" so nothing is lost.
- A "Runtime" dropdown appears in the create-tab modal but offers only "OpenCode" today. It is the seam where the next Feature will add "Pi".

## How It Behaves

Expanding the AI Assistant panel shows the user's existing tabs (or a default tab on first visit after upgrade). Clicking a tab activates it: its message history loads and its live stream attaches. Inactive tabs do not hold a streaming connection; switching back reattaches and replays anything missed.

Opening more than ten tabs at once shows a dismissible advisory banner; there is no hard limit.

Closing a tab hides it from the strip and adds it to the "Recent closed" menu. Reopening from that menu brings the tab back with its transcript intact. Closed tabs are kept indefinitely for now.

If the runtime is temporarily unavailable, tab creation fails with a clear error and existing tabs keep showing their stored history until the runtime recovers.

## Out of Scope

- Pi runtime in chat (follow-up Feature).
- Automatic cleanup of old closed tabs.
