# I-00089 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This item does not execute any docker commands.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged.

## Why

A user reported that the AI Assistant panel on the dashboard has a broken collapse affordance. When the panel is closed, a chevron icon is still shown at the top that looks like it should collapse the panel — but clicking it does nothing because the panel is already closed. And when the panel is open, the icon that actually collapses the panel is so small and crowded next to the other header icons that users cannot find it and end up feeling stuck with the panel permanently open.

## What Changed (for the User)

- When the AI Assistant panel is closed, the redundant chevron at the top of the panel is no longer shown. Only the vertical "AI Assistant" tab on the left edge is visible, and it is the single, unambiguous way to open the panel.
- When the AI Assistant panel is open, the collapse control in the header is now visually distinct from the other small icons next to it. Hovering over it reveals a tooltip that names it, so users can confidently find and click it to close the panel.
- The keyboard shortcut (Ctrl+/) and the toggle button in the top navigation bar continue to work exactly as before — they are unaffected.

## How It Behaves

The AI Assistant panel has two states: closed and open. In the closed state the panel renders as a thin vertical rail on the left of the page with a single "AI Assistant" tab; clicking that tab opens the panel. In the open state the panel expands to its full width, shows the chat history, a model selector, three small action icons (skills tray, history, new chat), and — at the right end of the header — a clearly marked collapse control. Clicking the collapse control returns the panel to the closed state. Hovering the control shows a "Collapse panel" tooltip so its purpose is obvious.

Users always have at least one always-visible way to switch states from inside the panel, and the keyboard shortcut and the top-bar toggle remain as additional shortcuts.

## Out of Scope

- The collapse button's click handler in JavaScript is correct and is not changed.
- The Ctrl+/ keyboard shortcut and the top-navigation toggle button are not changed.
- No changes are made to the chat content, model selector, skills tray, history dropdown, composer, or any backend or database concern.
